from django.core.management.base import BaseCommand
from base.models import Employer
import re

class Command(BaseCommand):
    help = 'Removes malicious SQL injection attempts from Employer database'

    def handle(self, *args, **kwargs):
        self.stdout.write("Scanning for malicious employer entries...")

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

        for employer in Employer.objects.all():
            total_checked += 1
            is_malicious = False

            # Check company_name and email for SQL injection patterns
            for pattern in sql_injection_patterns:
                if re.search(pattern, employer.company_name or '', re.IGNORECASE):
                    is_malicious = True
                    break
                if re.search(pattern, employer.email or '', re.IGNORECASE):
                    is_malicious = True
                    break

            # Also check for obviously fake data
            if employer.company_name and (
                len(employer.company_name) < 3 or
                employer.company_name == 'pHqghUme'
            ):
                is_malicious = True

            if is_malicious:
                self.stdout.write(f"Deleting malicious entry: {employer.company_name} - {employer.email}")
                employer.delete()
                count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Successfully cleaned up {count} malicious entries out of {total_checked} total entries.'
        ))
