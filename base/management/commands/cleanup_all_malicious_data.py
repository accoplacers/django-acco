from django.core.management.base import BaseCommand
from base.models import Employer, Contact, Registration
import re

class Command(BaseCommand):
    help = 'Removes all malicious SQL injection attempts from the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def is_malicious(self, *values):
        """Check if any value contains SQL injection patterns."""
        sql_injection_patterns = [
            r'(SELECT|SLEEP|WAITFOR|DELAY|UNION|DROP|INSERT|UPDATE|DELETE|EXEC|EXECUTE)',
            r'PG_SLEEP',
            r'waitfor\s+delay',
            r'@@\w+',  # SQL Server variables
            r'0x[0-9A-F]{6,}',  # Hex encoded strings
            r'(\'|\")(\s)*(OR|AND)',  # SQL boolean injection
        ]

        for value in values:
            if not value:
                continue

            for pattern in sql_injection_patterns:
                if re.search(pattern, str(value), re.IGNORECASE):
                    return True

        return False

    def handle(self, *args, **kwargs):
        dry_run = kwargs.get('dry_run', False)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - Nothing will be deleted"))

        self.stdout.write("=" * 70)
        self.stdout.write("Scanning database for malicious entries...")
        self.stdout.write("=" * 70)

        total_deleted = 0

        # Clean Employers
        self.stdout.write("\n[1/3] Scanning Employer table...")
        employer_count = 0
        for employer in Employer.objects.all():
            if self.is_malicious(
                employer.company_name,
                employer.email,
                employer.phone,
                employer.location,
                employer.industry
            ) or (employer.company_name and len(employer.company_name) < 3):
                self.stdout.write(
                    f"  → Malicious: {employer.company_name} ({employer.email})"
                )
                if not dry_run:
                    employer.delete()
                employer_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"  ✓ Found {employer_count} malicious employer entries"
        ))
        total_deleted += employer_count

        # Clean Contacts
        self.stdout.write("\n[2/3] Scanning Contact table...")
        contact_count = 0
        for contact in Contact.objects.all():
            if self.is_malicious(
                contact.name,
                contact.email,
                contact.phone,
                contact.message
            ) or (contact.name and len(contact.name) < 2):
                self.stdout.write(
                    f"  → Malicious: {contact.name} ({contact.email})"
                )
                if not dry_run:
                    contact.delete()
                contact_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"  ✓ Found {contact_count} malicious contact entries"
        ))
        total_deleted += contact_count

        # Clean Registrations (Employees)
        self.stdout.write("\n[3/3] Scanning Registration (Employee) table...")
        registration_count = 0
        for reg in Registration.objects.all():
            if self.is_malicious(
                reg.name,
                reg.email,
                reg.phone,
                reg.nationality,
                reg.location,
                reg.qualification,
                reg.role
            ) or (reg.name and len(reg.name) < 2):
                self.stdout.write(
                    f"  → Malicious: {reg.name} ({reg.email})"
                )
                if not dry_run:
                    reg.delete()
                registration_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"  ✓ Found {registration_count} malicious employee entries"
        ))
        total_deleted += registration_count

        # Summary
        self.stdout.write("\n" + "=" * 70)
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"DRY RUN: Would delete {total_deleted} malicious entries total"
            ))
            self.stdout.write("Run without --dry-run to actually delete them")
        else:
            self.stdout.write(self.style.SUCCESS(
                f"✓ Successfully cleaned up {total_deleted} malicious entries total!"
            ))
        self.stdout.write("=" * 70)

        # Show recommendations
        if total_deleted > 0:
            self.stdout.write("\n" + self.style.WARNING("RECOMMENDATIONS:"))
            self.stdout.write("  1. Review your Django admin for any remaining suspicious entries")
            self.stdout.write("  2. Consider adding CAPTCHA to forms (django-recaptcha)")
            self.stdout.write("  3. Monitor your logs regularly")
            self.stdout.write("  4. All forms now have rate limiting and input validation")
