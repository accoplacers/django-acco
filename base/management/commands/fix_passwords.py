from django.core.management.base import BaseCommand
from base.models import UserAccount


class Command(BaseCommand):
    help = 'Verify UserAccount password hashes are well-formed (Registration/Employer password fields have been removed)'

    def handle(self, *args, **kwargs):
        self.stdout.write("Checking UserAccount password hashes...")
        count = 0
        for account in UserAccount.objects.all():
            if account.password and not account.password.startswith('pbkdf2_sha256$'):
                self.stdout.write(f"WARNING: UserAccount {account.email} has a non-pbkdf2 password hash — manual intervention required.")
                count += 1

        if count == 0:
            self.stdout.write(self.style.SUCCESS("All UserAccount passwords are properly hashed."))
        else:
            self.stdout.write(self.style.WARNING(f"{count} account(s) may need attention."))
