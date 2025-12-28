from django.core.management.base import BaseCommand
from base.models import Registration, Employer
from django.contrib.auth.hashers import make_password

class Command(BaseCommand):
    help = 'Fixes plaintext passwords for Registration and Employer models'

    def handle(self, *args, **kwargs):
        self.stdout.write("Checking for plaintext passwords...")
        
        # specific logic: checks if password doesn't start with pbkdf2_sha256$
        # Note: This assumes default hasher. If empty, skips.
        
        count = 0
        
        # 1. Employees
        for user in Registration.objects.all():
            if user.password and not user.password.startswith('pbkdf2_sha256$'):
                self.stdout.write(f"Fixing employee: {user.email}")
                user.password = make_password(user.password)
                user.save()
                count += 1
                
        # 2. Employers
        for user in Employer.objects.all():
            if user.password and not user.password.startswith('pbkdf2_sha256$'):
                self.stdout.write(f"Fixing employer: {user.email}")
                user.password = make_password(user.password)
                user.save()
                count += 1
                
        self.stdout.write(self.style.SUCCESS(f'Successfully fixed {count} accounts.'))
