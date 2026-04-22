import time
import os
from django.core.management.base import BaseCommand
from base.models import Registration, Skill
from base.services.embedding_service import build_embedding_text, upsert_candidate_to_pinecone, get_pinecone_index
from base.services.resume_parser import extract_text_from_pdf, parse_resume_with_llm
from django.db import transaction

class Command(BaseCommand):
    help = "Backfill Pinecone embeddings for all existing Registration profiles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Log what would be processed without calling any APIs."
        )
        parser.add_argument(
            "--batch-size", type=int, default=50,
            help="Number of records to process per batch (default: 50)."
        )
        parser.add_argument(
            "--skip-existing", action="store_true", default=True,
            help="Skip candidates who already have a Pinecone vector (check via fetch)."
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]
        skip_existing = options["skip_existing"]

        # 1. Fetch all Registration objects that have a resume file
        # Use .prefetch_related("skills") to avoid N+1 queries
        qs = Registration.objects.exclude(resume__isnull=True).exclude(resume="").prefetch_related("skills")
        
        if not qs.exists():
            self.stdout.write(self.style.WARNING("No candidates with resumes found."))
            return

        # WALLET PROTECTION: Token and Cost Estimation
        total_tokens_estimate = 0
        for r in qs:
            # Simple word count as proxy for token estimation
            total_tokens_estimate += len(build_embedding_text(r).split())

        estimated_cost = (total_tokens_estimate / 1000) * 0.00002
        
        self.stdout.write(f"Found {qs.count()} candidates for processing.")
        self.stdout.write(f"Estimated token usage: ~{total_tokens_estimate} tokens")
        self.stdout.write(f"Estimated cost: ~${estimated_cost:.4f} USD")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("\n--- DRY RUN MODE ---"))
            for r in qs:
                text = build_embedding_text(r)
                self.stdout.write(f"[DRY-RUN] ID {r.pk}: {text[:100]}...")
            self.stdout.write(self.style.SUCCESS("Dry run complete. No API calls were made."))
            return

        # Confirm before proceeding
        confirm = input("\nProceed with backfill? (yes/no): ")
        if confirm.lower() != "yes":
            self.stdout.write("Operation cancelled.")
            return

        processed = 0
        skipped = 0
        failed = 0

        index = None
        if skip_existing:
            try:
                # Check environment before starting
                if not os.environ.get("PINECONE_API_KEY") or not os.environ.get("PINECONE_INDEX_NAME"):
                    raise RuntimeError("Missing Pinecone credentials in environment.")
                index = get_pinecone_index()
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed to initialize Pinecone: {e}"))
                return

        self.stdout.write("\nStarting backfill...")

        for r in qs:
            try:
                # a. Skip existing check
                if skip_existing and index:
                    # WALLET GUARD: Pinecone Fetch
                    fetch_res = index.fetch(ids=[str(r.pk)])
                    if fetch_res and str(r.pk) in fetch_res.vectors:
                        self.stdout.write(f"[SKIP] ID {r.pk} already vectorized")
                        skipped += 1
                        continue

                # b. If skills.count() == 0, attempt parse first
                if r.skills.count() == 0:
                    try:
                        self.stdout.write(f"[INFO] ID {r.pk} has 0 skills. Attempting resume parse...")
                        if not r.resume or not os.path.exists(r.resume.path):
                            raise FileNotFoundError(f"Resume file not found at {r.resume.path if r.resume else 'N/A'}")
                            
                        text_content = extract_text_from_pdf(r.resume.path)
                        parsed_data = parse_resume_with_llm(text_content)
                        
                        # map parsed → M2M skills (atomic)
                        with transaction.atomic():
                            SKILL_CATEGORY_MAP = {
                                "certifications": "Certification",
                                "erp_software": "ERP Software",
                                "regulatory_knowledge": "Regulatory",
                                "core_competencies": "Competency",
                            }

                            for field_name, category in SKILL_CATEGORY_MAP.items():
                                items = getattr(parsed_data, field_name, [])
                                for item in items:
                                    skill_obj, _ = Skill.objects.get_or_create(
                                        name=item.strip(),
                                        defaults={"category": category}
                                    )
                                    r.skills.add(skill_obj)
                            
                            r.years_of_experience = parsed_data.years_of_experience
                            r.notice_period = parsed_data.notice_period
                            r.save(update_fields=["years_of_experience", "notice_period"])
                            
                        self.stdout.write(f"[PARSE OK] ID {r.pk} enriched with skills.")
                    except Exception as e:
                        self.stderr.write(self.style.ERROR(f"[PARSE FAIL] ID {r.pk}: {e}"))
                        failed += 1
                        continue  # Skip upsert if parsing failed and no skills exist

                # c. Call upsert_candidate_to_pinecone
                # WALLET GUARD: API Calls inside this service
                success = upsert_candidate_to_pinecone(r)
                if success:
                    processed += 1
                    self.stdout.write(self.style.SUCCESS(f"[OK] ID {r.pk} — {r.skills.count()} skills vectorized"))
                else:
                    failed += 1

                # Batch with time.sleep to avoid rate limit spikes
                time.sleep(0.1)

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"[UNEXPECTED ERROR] ID {r.pk}: {e}"))
                failed += 1

        self.stdout.write(self.style.SUCCESS(f"\nFinal Summary: Processed {processed} / Skipped {skipped} / Failed {failed}"))
