from django.test import TestCase
from django.urls import reverse

from base.models import EmployeeInterest, Employer, JobOpening, Registration, Skill, UserAccount


class EmployeeDashboardTest(TestCase):
    def setUp(self):
        self.registration = Registration.objects.create(
            name='Aisha Khan',
            email='aisha@example.com',
            password='hashed-password',
            phone='+971501234567',
            nationality='Indian',
            location='Dubai',
            qualification='ACCA',
            experience='5',
            role='Senior Accountant',
            resume='resumes/aisha.pdf',
            plan='basic',
        )
        self.skill_excel = Skill.objects.create(name='Excel')
        self.skill_ifrs = Skill.objects.create(name='IFRS')
        self.registration.skills.add(self.skill_excel, self.skill_ifrs)

        self.user = UserAccount.objects.create_user(
            email='aisha@example.com',
            password='password123',
            role='employee',
            profile_id=self.registration.id,
        )

        self.employer = Employer.objects.create(
            company_name='Finance Co',
            email='hiring@financeco.com',
            password='hashed-password',
            phone='+971500000000',
            company_description='Finance hiring team.',
            location='Dubai',
            industry='Accounting',
        )

        self.matching_job = JobOpening.objects.create(
            employer=self.employer,
            title='Senior Accountant',
            description='Looking for IFRS reporting and Excel strength.',
            requirements='ACCA and Excel required.',
            salary_range='AED 12,000 - 15,000',
            location='Dubai',
            job_type='Full-time',
            is_active=True,
        )
        self.generic_job = JobOpening.objects.create(
            employer=self.employer,
            title='Finance Analyst',
            description='General finance role.',
            requirements='Attention to detail.',
            salary_range='AED 9,000 - 11,000',
            location='Abu Dhabi',
            job_type='Full-time',
            is_active=True,
        )

    def test_dashboard_context_includes_guided_workspace_data(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('employee_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('profile_completion', response.context)
        self.assertIn('recommended_count', response.context)
        self.assertIn('next_steps', response.context)
        self.assertIn('job_cards', response.context)
        self.assertGreaterEqual(response.context['profile_completion'], 90)
        self.assertGreaterEqual(response.context['recommended_count'], 1)

    def test_interested_jobs_are_prioritized_in_job_cards(self):
        EmployeeInterest.objects.create(employee=self.registration, job=self.generic_job)
        self.client.force_login(self.user)

        response = self.client.get(reverse('employee_dashboard'))

        job_cards = response.context['job_cards']
        self.assertEqual(job_cards[0]['job'].id, self.generic_job.id)
