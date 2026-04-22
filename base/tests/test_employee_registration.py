import os
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch, MagicMock
from base.models import Registration, Skill, UserAccount
from base.services.resume_parser import ParsedResume
import time

class EmployeeRegistrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('employee_register')
        
        # Patch the parser globally for all tests in this class to avoid real PDF processing
        self.patcher_extractor = patch('base.views.extract_text_from_pdf')
        self.patcher_parser = patch('base.views.parse_resume_with_llm')
        self.mock_extractor = self.patcher_extractor.start()
        self.mock_parser = self.patcher_parser.start()
        
        # Default mock values
        self.mock_extractor.return_value = "Mocked Resume Text"
        self.mock_parser.return_value = ParsedResume()

        # Create a dummy PDF for testing
        self.dummy_pdf = SimpleUploadedFile(
            "test_resume.pdf",
            b"%PDF-1.4 %dummy content",
            content_type="application/pdf"
        )

    def tearDown(self):
        self.patcher_extractor.stop()
        self.patcher_parser.stop()

    def test_honeypot_trap(self):
        """If fax_number (honeypot) is filled, return 400."""
        payload = {
            'name': 'Bot User',
            'email': 'bot@example.com',
            'password': 'password123',
            'confirm_password': 'password123',
            'phone': '+971501234567',
            'nationality': 'Indian',
            'location': 'Dubai',
            'qualification': 'MBA',
            'experience': '3-5',
            'role': 'Accountant',
            'resume': self.dummy_pdf,
            'fax_number': 'I am a bot'  # Honeypot filled
        }
        response = self.client.post(self.register_url, payload)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Registration.objects.filter(email='bot@example.com').exists())

    def test_rate_limiting(self):
        """Submit requests from a non-local IP until the rate limiter blocks them."""
        payload = {
            'name': 'Rate User',
            'email': 'rate@example.com',
            'password': 'password123',
            'confirm_password': 'password123',
            'phone': '+971501234567',
            'nationality': 'Indian',
            'location': 'Dubai',
            'qualification': 'MBA',
            'experience': '3-5',
            'role': 'Accountant',
            'resume': self.dummy_pdf,
            'terms': 'on',
        }

        for _ in range(10):
            self.client.post(self.register_url, payload, REMOTE_ADDR='10.0.0.5')

        response = self.client.post(self.register_url, payload, REMOTE_ADDR='10.0.0.5')
        
        self.assertEqual(response.status_code, 429)

    def test_happy_path_with_ai_enrichment(self):
        """Valid registration should trigger AI parsing and calculate profile score."""
        self.mock_parser.return_value = ParsedResume(
            certifications=['ACCA', 'CPA'],
            erp_software=['Tally', 'SAP'],
            regulatory_knowledge=['IFRS', 'VAT'],
            core_competencies=['Internal Audit'],
            years_of_experience=5,
            notice_period='Immediate'
        )

        payload = {
            'name': 'Real User',
            'email': 'real@example.com',
            'password': 'password123',
            'confirm_password': 'password123',
            'phone': '+971501234567',
            'nationality': 'Indian',
            'location': 'Dubai',
            'qualification': 'MBA',
            'experience': '1-3', # Manual entry
            'role': 'Senior Accountant',
            'resume': self.dummy_pdf,
            'terms': 'on',
        }

        response = self.client.post(self.register_url, payload)
        
        # Check redirection to login
        self.assertEqual(response.status_code, 302)
        
        # Verify Registration creation
        reg = Registration.objects.get(email='real@example.com')
        self.assertEqual(reg.name, 'Real User')
        
        # Verify AI Enrichment
        # Parsed years_of_experience is 5, notice_period is Immediate
        self.assertEqual(reg.years_of_experience, 5)
        self.assertEqual(reg.notice_period, 'Immediate')
        
        # Verify Skills M2M and Category
        skills_with_cats = {s.name: s.category for s in reg.skills.all()}
        self.assertEqual(skills_with_cats.get('ACCA'), 'Certification')
        self.assertEqual(skills_with_cats.get('SAP'), 'ERP Software')
        self.assertEqual(skills_with_cats.get('Internal Audit'), 'Competency')
        self.assertEqual(skills_with_cats.get('IFRS'), 'Regulatory')
        
        
        # Verify Auth User creation
        self.assertTrue(UserAccount.objects.filter(email='real@example.com').exists())
