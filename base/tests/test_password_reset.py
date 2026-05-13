from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from base.models import UserAccount


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    ALLOWED_HOSTS=['testserver'],
)
class PasswordResetTest(TestCase):
    def setUp(self):
        self.user = UserAccount.objects.create_user(
            email='reset@example.com',
            password='OldS3curePass!2026',
            role='employee',
        )

    def test_login_pages_link_to_password_reset(self):
        reset_url = reverse('password_reset')

        employee_response = self.client.get(reverse('employee_login'))
        employer_response = self.client.get(reverse('employer_login'))

        self.assertContains(employee_response, f'href="{reset_url}"')
        self.assertContains(employer_response, f'href="{reset_url}"')

    def test_password_reset_request_sends_email(self):
        response = self.client.post(reverse('password_reset'), {'email': self.user.email})

        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Reset your Accoplacers password', mail.outbox[0].subject)
        self.assertIn('/password-reset/', mail.outbox[0].body)
