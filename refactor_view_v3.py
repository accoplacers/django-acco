import os
path = "base/views.py"
with open(path, "rb") as f:
    content = f.read()

# Marker for the start of the block
start_marker = b"            # --- AI INGESTION PIPELINE ---"
# Marker for the end of the block (the last print statement)
end_marker = b"print(f\"AI Ingestion Failed for {email}: {str(e)}\")"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker, start_idx)

if start_idx != -1 and end_idx != -1:
    # Find the end of the line for end_idx
    end_line_idx = content.find(b"\n", end_idx) + 1
    
    new_code = b"""            # --- AI INGESTION PIPELINE (Refactored) ---
            try:
                # 1. Idempotency Guard: skip if already has skills
                if registration.skills.count() == 0:
                    resume_path = registration.resume.path
                    if os.path.exists(resume_path):
                        # 3. Extract text
                        raw_text = extract_text_from_pdf(resume_path)
                        # 4. Parse with LLM
                        parsed_data = parse_resume_with_llm(raw_text)

                        # Step 5 & 6: Database Mapping (Atomic)
                        with transaction.atomic():
                            # Skill Mapping by Category
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
                                    registration.skills.add(skill_obj)

                            # Scalar Mapping
                            registration.years_of_experience = parsed_data.years_of_experience
                            registration.notice_period = parsed_data.notice_period
                            registration.save(update_fields=["years_of_experience", "notice_period"])

            except Exception as e:
                logger.error(f"Resume parse failed for user {registration.email}: {str(e)}")
                request.session["resume_parse_pending"] = True
"""
    # Use the same line endings as the file (\r\n)
    new_code = new_code.replace(b"\\n", b"\\r\\n")
    
    new_content = content[:start_idx] + new_code + content[end_line_idx:]
    with open(path, "wb") as f:
        f.write(new_content)
    print("Replacement successful")
else:
    print(f"Markers not found: start={start_idx}, end={end_idx}")
