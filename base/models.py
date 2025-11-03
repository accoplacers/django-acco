from django.db import models

class Registration(models.Model):
    PLAN_CHOICES = [
        ('basic', 'Basic'),
        ('intermediate', 'Intermediate'),
        ('premium', 'Premium'),
    ]

    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    nationality = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    qualification = models.CharField(max_length=100)
    experience = models.CharField(max_length=20)
    role = models.CharField(max_length=100)
    resume = models.FileField(upload_to='resumes/')
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='basic')  # ✅ new field
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.role} ({self.plan})"



class Contact(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
