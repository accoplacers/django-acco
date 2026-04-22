from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class UserAccountManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin') # Default for superusers

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class UserAccount(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('employer', 'Employer'),
        ('employee', 'Employee'),
        ('admin', 'Admin'),
    ]

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    profile_id = models.IntegerField(null=True, blank=True) # ID of Employer or Registration record
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserAccountManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Registration(models.Model):
    PLAN_CHOICES = [
        ('basic', 'Basic'),
        ('intermediate', 'Intermediate'),
        ('premium', 'Premium'),
    ]

    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128, blank=True)  # hashed password for login
    phone = models.CharField(max_length=20)
    nationality = models.CharField(max_length=100)
    location = models.CharField(max_length=100, db_index=True)
    qualification = models.CharField(max_length=100)
    experience = models.CharField(max_length=20)
    role = models.CharField(max_length=100)
    resume = models.FileField(upload_to='resumes/')
    photo = models.ImageField(upload_to='employee_photos/', blank=True, null=True)  # Professional photo
    skills = models.ManyToManyField(Skill, blank=True, related_name='registrations')
    years_of_experience = models.PositiveIntegerField(default=0)
    notice_period = models.CharField(max_length=50, blank=True, default='Unknown')
    profile_score = models.IntegerField(default=0) # Deprecated — use computed score in views.py
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='basic')
    is_placed = models.BooleanField(default=False, help_text="Mark this employee as placed (hired by an employer)")
    is_featured = models.BooleanField(default=False, help_text="Feature this candidate on the employer dashboard")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.role} ({self.plan})"

    @property
    def skills_list(self):
        return ", ".join(self.skills.values_list('name', flat=True))

    @property
    def admin_url(self):
        from django.urls import reverse
        return reverse('admin:base_registration_change', args=[self.id])

    def save(self, *args, **kwargs):
        # Auto-hash password if it's plaintext
        if self.password and not self.password.startswith('pbkdf2_sha256$'):
            from django.contrib.auth.hashers import make_password
            self.password = make_password(self.password)
        super().save(*args, **kwargs)


class ApplicationStatus(models.Model):
    STATUS_CHOICES = [
        ('submitted', 'Application Submitted'),
        ('under_review', 'Under Review'),
        ('shortlisted', 'Shortlisted'),
        ('contacted', 'Contacted'),
    ]

    candidate = models.OneToOneField(Registration, on_delete=models.CASCADE, related_name='application_status')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Status for {self.candidate.name}: {self.get_status_display()}"


class Employer(models.Model):
    SUBSCRIPTION_TIER_CHOICES = [
        ('basic', 'Basic'),
        ('intermediate', 'Intermediate'),
        ('premium', 'Premium'),
    ]

    company_name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)  # hashed password
    phone = models.CharField(max_length=20)
    company_description = models.TextField(blank=True)
    location = models.CharField(max_length=100)
    industry = models.CharField(max_length=100)
    logo = models.ImageField(upload_to='employer_logos/', blank=True, null=True)
    subscription_tier = models.CharField(max_length=20, choices=SUBSCRIPTION_TIER_CHOICES, default='basic')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.company_name

    @property
    def admin_url(self):
        from django.urls import reverse
        return reverse('admin:base_employer_change', args=[self.id])

    def save(self, *args, **kwargs):
        # Auto-hash password if it's plaintext
        if self.password and not self.password.startswith('pbkdf2_sha256$'):
            from django.contrib.auth.hashers import make_password
            self.password = make_password(self.password)
        super().save(*args, **kwargs)


class JobOpening(models.Model):
    employer = models.ForeignKey(Employer, on_delete=models.PROTECT, related_name='job_openings')
    title = models.CharField(max_length=200)
    description = models.TextField()
    requirements = models.TextField()
    skills_required = models.TextField(blank=True, default='')
    salary_range = models.CharField(max_length=50, blank=True)
    location = models.CharField(max_length=100)
    job_type = models.CharField(max_length=50, default='Full-time')  # Full-time, Part-time, Contract
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} at {self.employer.company_name}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('job_detail', kwargs={'pk': self.pk})


class Contact(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class EmployerInterest(models.Model):
    employer = models.ForeignKey(Employer, on_delete=models.PROTECT, related_name='interests')
    employee = models.ForeignKey(Registration, on_delete=models.PROTECT, related_name='interests')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employer', 'employee')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employer.company_name} → EMP-{self.employee.id:04d} ({self.employee.name})"


class ContactEvent(models.Model):
    employer = models.ForeignKey(Employer, on_delete=models.SET_NULL, null=True)
    candidate = models.ForeignKey(Registration, on_delete=models.SET_NULL, null=True)
    contact_type = models.CharField(max_length=20, default='whatsapp')
    contacted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-contacted_at']

    def __str__(self):
        return f"{self.employer.company_name} contacted {self.candidate.name}"


class EmployeeInterest(models.Model):
    employee = models.ForeignKey(Registration, on_delete=models.PROTECT, related_name='job_interests')
    job = models.ForeignKey(JobOpening, on_delete=models.PROTECT, related_name='employee_interests')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employee', 'job')
        ordering = ['-created_at']

    def __str__(self):
        return f"EMP-{self.employee.id:04d} ({self.employee.name}) → {self.job.title} at {self.job.employer.company_name}"
