from django.test import TestCase, Client
from django.urls import reverse
from base.models import Employer, Registration, JobOpening, UserAccount, EmployeeInterest, EmployerInterest

class EmployerDashboardTest(TestCase):
    def setUp(self):
        # 1. Create an Employer
        self.employer = Employer.objects.create(
            company_name='Dubai Finance Group',
            email='hiring@dubaifinance.com',
            password='password123',
            phone='+971501112233',
            location='Dubai, UAE',
            industry='Banking'
        )
        self.employer_user = UserAccount.objects.create_user(
            email='hiring@dubaifinance.com',
            password='password123',
            role='employer',
            profile_id=self.employer.id
        )

        # 2. Create an Employee
        self.employee = Registration.objects.create(
            name='Omar Hassan',
            email='omar@example.com',
            phone='+971509998877',
            nationality='Egyptian',
            location='Dubai',
            qualification='CPA',
            experience='8',
            role='Finance Manager',
            resume='resumes/omar.pdf'
        )
        
        # 3. Create a Job Opening
        self.job = JobOpening.objects.create(
            employer=self.employer,
            title='Senior Accountant',
            description='Detailed job description for senior accountant role.',
            requirements='CPA or ACCA required.',
            location='Dubai',
            job_type='Full-time',
            is_active=True
        )

    def test_dashboard_access_and_context(self):
        """Verify employer can access dashboard and receives necessary context."""
        self.client.force_login(self.employer_user)
        response = self.client.get(reverse('employer_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('candidate_cards', response.context)
        self.assertIn('owned_jobs', response.context)
        self.assertIn('employee_interest_feed', response.context)
        self.assertEqual(len(response.context['owned_jobs']), 1)

    def test_create_job_opening(self):
        """Verify employer can create a new job opening."""
        self.client.force_login(self.employer_user)
        payload = {
            'action': 'create_job',
            'title': 'Internal Auditor',
            'description': 'Description that is long enough to pass validation rules.',
            'requirements': 'Requirements that are also long enough.',
            'location': 'Abu Dhabi',
            'job_type': 'Full-time',
            'is_active': 'on'
        }
        response = self.client.post(reverse('employer_dashboard'), payload)
        
        self.assertEqual(response.status_code, 302)
        self.assertTrue(JobOpening.objects.filter(title='Internal Auditor').exists())

    def test_delete_job_opening(self):
        """Verify employer can delete their own job opening."""
        self.client.force_login(self.employer_user)
        payload = {
            'action': 'delete_job',
            'job_id': self.job.id
        }
        response = self.client.post(reverse('employer_dashboard'), payload)
        
        self.assertEqual(response.status_code, 302)
        self.assertFalse(JobOpening.objects.filter(id=self.job.id).exists())

    def test_candidate_search_filter(self):
        """Verify candidate filtering by name/role works."""
        self.client.force_login(self.employer_user)
        
        # Search for 'Omar'
        response = self.client.get(reverse('employer_dashboard'), {'q': 'Omar'})
        candidate_cards = response.context['candidate_cards'].object_list
        self.assertTrue(any(card['employee'].id == self.employee.id for card in candidate_cards))
        
        # Search for something non-existent
        response = self.client.get(reverse('employer_dashboard'), {'q': 'NonExistentCandidate'})
        candidate_cards = response.context['candidate_cards'].object_list
        self.assertEqual(len(candidate_cards), 0)

    def test_employer_interest_toggle(self):
        """Verify employer can mark/unmark a candidate as interested (saved)."""
        self.client.force_login(self.employer_user)
        url = reverse('express_interest')
        
        # Toggle ON
        response = self.client.post(url, {'employee_id': self.employee.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'added')
        self.assertTrue(EmployerInterest.objects.filter(employer=self.employer, employee=self.employee).exists())
        
        # Toggle OFF
        response = self.client.post(url, {'employee_id': self.employee.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'removed')
        self.assertFalse(EmployerInterest.objects.filter(employer=self.employer, employee=self.employee).exists())

    def test_employee_interest_feed(self):
        """Verify employer can see employees who signaled interest in their jobs."""
        # 1. Employee signals interest
        EmployeeInterest.objects.create(employee=self.employee, job=self.job)
        
        self.client.force_login(self.employer_user)
        response = self.client.get(reverse('employer_dashboard'))
        
        feed = response.context['employee_interest_feed']
        self.assertEqual(len(feed), 1)
        self.assertEqual(feed[0].employee.id, self.employee.id)
