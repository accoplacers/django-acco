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
    password = models.CharField(max_length=128, blank=True, null=True)  # hashed password for login
    phone = models.CharField(max_length=20)
    nationality = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    qualification = models.CharField(max_length=100)
    experience = models.CharField(max_length=20)
    role = models.CharField(max_length=100)
    resume = models.FileField(upload_to='resumes/')
    photo = models.ImageField(upload_to='employee_photos/', blank=True, null=True)  # Professional photo
    skills = models.ManyToManyField(Skill, blank=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='basic')
    is_placed = models.BooleanField(default=False, help_text="Mark this employee as placed (hired by an employer)")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.role} ({self.plan})"

    @property
    def skills_list(self):
        return ", ".join(self.skills.values_list('name', flat=True))

    def save(self, *args, **kwargs):
        # Auto-hash password if it's plaintext
        if self.password and not self.password.startswith('pbkdf2_sha256$'):
            from django.contrib.auth.hashers import make_password
            self.password = make_password(self.password)
        super().save(*args, **kwargs)



class Employer(models.Model):
    company_name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)  # hashed password
    phone = models.CharField(max_length=20)
    company_description = models.TextField(blank=True)
    location = models.CharField(max_length=100)
    industry = models.CharField(max_length=100)
    logo = models.ImageField(upload_to='employer_logos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.company_name

    def save(self, *args, **kwargs):
        # Auto-hash password if it's plaintext
        if self.password and not self.password.startswith('pbkdf2_sha256$'):
            from django.contrib.auth.hashers import make_password
            self.password = make_password(self.password)
        super().save(*args, **kwargs)


class JobOpening(models.Model):
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name='job_openings')
    title = models.CharField(max_length=200)
    description = models.TextField()
    requirements = models.TextField()
    salary_range = models.CharField(max_length=50, blank=True)
    location = models.CharField(max_length=100)
    job_type = models.CharField(max_length=50, default='Full-time')  # Full-time, Part-time, Contract
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} at {self.employer.company_name}"


class Contact(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class EmployerInterest(models.Model):
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name='interests')
    employee = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name='interests')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employer', 'employee')

    def __str__(self):
        return f"{self.employer.company_name} → EMP-{self.employee.id:04d} ({self.employee.name})"


class EmployeeInterest(models.Model):
    employee = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name='job_interests')
    job = models.ForeignKey(JobOpening, on_delete=models.CASCADE, related_name='employee_interests')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employee', 'job')

    def __str__(self):
        return f"EMP-{self.employee.id:04d} ({self.employee.name}) → {self.job.title} at {self.job.employer.company_name}"

