from django.core.management.base import BaseCommand
from django.db import transaction
from base.models import Employer, Registration, UserAccount

class Command(BaseCommand):
    help = 'Backfills UserAccount records from existing Employer and Registration records'

    def handle(self, *args, **options):
        employer_count = 0
        employee_count = 0
        
        self.stdout.write(self.style.NOTICE('Starting UserAccount backfill...'))

        with transaction.atomic():
            # 1. Backfill Employers
            employers = Employer.objects.all()
            for emp in employers:
                user, created = UserAccount.objects.get_or_create(
                    email=emp.email,
                    defaults={
                        'password': emp.password,
                        'role': 'employer',
                        'profile_id': emp.id,
                        'is_active': True
                    }
                )
                if created:
                    employer_count += 1
                else:
                    # Update password and profile_id if they changed
                    user.password = emp.password
                    user.profile_id = emp.id
                    user.role = 'employer'
                    user.save()

            # 2. Backfill Employees (Registration)
            employees = Registration.objects.all()
            for reg in employees:
                user, created = UserAccount.objects.get_or_create(
                    email=reg.email,
                    defaults={
                        'password': reg.password,
                        'role': 'employee',
                        'profile_id': reg.id,
                        'is_active': True
                    }
                )
                if created:
                    employee_count += 1
                else:
                    # Update password and profile_id if they changed
                    user.password = reg.password
                    user.profile_id = reg.id
                    user.role = 'employee'
                    user.save()

        self.stdout.write(self.style.SUCCESS(f'Successfully migrated {employer_count} Employers'))
        self.stdout.write(self.style.SUCCESS(f'Successfully migrated {employee_count} Employees'))
