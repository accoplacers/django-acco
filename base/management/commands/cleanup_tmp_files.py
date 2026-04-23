import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Delete temporary registration files in media/tmp/ that are older than 2 hours'

    def handle(self, *args, **options):
        tmp_dir = os.path.join(settings.MEDIA_ROOT, 'tmp')
        if not os.path.isdir(tmp_dir):
            self.stdout.write('No tmp directory found — nothing to clean.')
            return

        cutoff = time.time() - (2 * 60 * 60)  # 2 hours ago
        deleted = 0
        errors = 0

        for filename in os.listdir(tmp_dir):
            filepath = os.path.join(tmp_dir, filename)
            try:
                if os.path.isfile(filepath) and os.path.getmtime(filepath) < cutoff:
                    os.remove(filepath)
                    deleted += 1
            except OSError as e:
                self.stderr.write(f'Error deleting {filepath}: {e}')
                errors += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Cleaned {deleted} stale temp file(s). Errors: {errors}'
            )
        )
