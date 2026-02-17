from django.core.management.base import BaseCommand
from base.models import Contact
import re

class Command(BaseCommand):
    help = 'Removes malicious SQL injection attempts from Contact database'

    def handle(self, *args, **kwargs):
        self.stdout.write("Scanning for malicious contact entries...")

        # Patterns that indicate SQL injection attempts
        sql_injection_patterns = [
            r'(SELECT|SLEEP|WAITFOR|DELAY|UNION|DROP|INSERT|UPDATE|DELETE|EXEC|EXECUTE)',
            r'(--|;|\'|\"|\)|\()',  # SQL syntax characters in suspicious places
            r'PG_SLEEP',
            r'waitfor\s+delay',
            r'@@\w+',  # SQL Server variables
        ]

        count = 0
        total_checked = 0

        for contact in Contact.objects.all():
            total_checked += 1
            is_malicious = False

            # Check all fields for SQL injection patterns
            fields_to_check = [
                contact.name,
                contact.email,
                contact.phone,
                contact.message
            ]

            for field_value in fields_to_check:
                if not field_value:
                    continue

                for pattern in sql_injection_patterns:
                    if re.search(pattern, str(field_value), re.IGNORECASE):
                        is_malicious = True
                        break

                if is_malicious:
                    break

            # Also check for obviously fake/random data
            if contact.name and len(contact.name) < 2:
                is_malicious = True

            if is_malicious:
                self.stdout.write(f"Deleting malicious entry: {contact.name} - {contact.email}")
                contact.delete()
                count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Successfully cleaned up {count} malicious contact entries out of {total_checked} total entries.'
        ))
