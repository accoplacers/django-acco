from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from base.models import Employer, UserAccount


class EmployerRegistrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('employer_register')
        self.logo = SimpleUploadedFile(
            "logo.png",
            b"fake-image-content",
            content_type="image/png",
        )

    def test_happy_path_creates_employer_and_auth_user(self):
        payload = {
            'company_name': 'Acme Finance',
            'email': 'hiring@acmefinance.com',
            'password': 'password123',
            'confirm_password': 'password123',
            'phone': '+971501234567',
            'company_description': 'We hire finance transformation and controllership talent.',
            'location': 'Dubai, UAE',
            'industry': 'Accounting',
            'logo': self.logo,
        }

        response = self.client.post(self.register_url, payload)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Employer.objects.filter(email='hiring@acmefinance.com').exists())
        self.assertTrue(UserAccount.objects.filter(email='hiring@acmefinance.com', role='employer').exists())

    def test_duplicate_email_returns_form_with_error(self):
        Employer.objects.create(
            company_name='Existing Co',
            email='duplicate@company.com',
            password='hashed-password',
            phone='+971501234567',
            company_description='Existing employer account.',
            location='Dubai, UAE',
            industry='Accounting',
        )

        payload = {
            'company_name': 'Another Co',
            'email': 'duplicate@company.com',
            'password': 'password123',
            'confirm_password': 'password123',
            'phone': '+971509999999',
            'company_description': 'Trying to register again.',
            'location': 'Dubai, UAE',
            'industry': 'Audit',
        }

        response = self.client.post(self.register_url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'An account with this email already exists.')
        self.assertContains(response, 'Another Co')

    def test_honeypot_blocks_bot_submission(self):
        payload = {
            'company_name': 'Spam Co',
            'email': 'spam@company.com',
            'password': 'password123',
            'confirm_password': 'password123',
            'phone': '+971500000000',
            'company_description': 'Spam submission.',
            'location': 'Dubai, UAE',
            'industry': 'Accounting',
            'fax_number': 'bot-filled',
        }

        response = self.client.post(self.register_url, payload)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Employer.objects.filter(email='spam@company.com').exists())

    def test_password_mismatch_returns_error(self):
        payload = {
            'company_name': 'Mismatch Co',
            'email': 'mismatch@company.com',
            'password': 'password123',
            'confirm_password': 'password124',
            'phone': '+971501111111',
            'company_description': 'Testing mismatched password handling.',
            'location': 'Dubai, UAE',
            'industry': 'Accounting',
        }

        response = self.client.post(self.register_url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Passwords do not match.')
