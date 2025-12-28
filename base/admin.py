from django.contrib import admin
from .models import Registration, Contact, Employer, JobOpening


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'name', 'email', 'phone', 'role', 'location', 'experience', 'plan', 'created_at')
    search_fields = ('id', 'name', 'email', 'role', 'location', 'qualification')
    list_filter = ('experience', 'qualification', 'plan', 'created_at', 'location')
    readonly_fields = ('employee_id', 'created_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Employee ID', {
            'fields': ('employee_id',)
        }),
        ('Personal Information', {
            'fields': ('name', 'email', 'password', 'phone', 'nationality', 'location')
        }),
        ('Professional Details', {
            'fields': ('qualification', 'experience', 'role', 'resume', 'photo')
        }),
        ('Plan & Status', {
            'fields': ('plan', 'created_at')
        }),
    )
    
    def employee_id(self, obj):
        return f"EMP-{obj.id:04d}"
    employee_id.short_description = 'Employee ID'
    employee_id.admin_order_field = 'id'


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'created_at')
    search_fields = ('name', 'email', 'message')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)


@admin.register(Employer)
class EmployerAdmin(admin.ModelAdmin):
    list_display = ('employer_id', 'company_name', 'email', 'phone', 'industry', 'location', 'created_at')
    search_fields = ('id', 'company_name', 'email', 'industry', 'location')
    list_filter = ('industry', 'location', 'created_at')
    readonly_fields = ('employer_id', 'created_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Employer ID', {
            'fields': ('employer_id',)
        }),
        ('Company Information', {
            'fields': ('company_name', 'email', 'password', 'phone', 'industry', 'location')
        }),
        ('Details', {
            'fields': ('company_description', 'logo', 'created_at')
        }),
    )
    
    def employer_id(self, obj):
        return f"EMPR-{obj.id:04d}"
    employer_id.short_description = 'Employer ID'
    employer_id.admin_order_field = 'id'


@admin.register(JobOpening)
class JobOpeningAdmin(admin.ModelAdmin):
    list_display = ('title', 'employer', 'location', 'job_type', 'is_active', 'created_at')
    search_fields = ('title', 'employer__company_name')
    list_filter = ('job_type', 'is_active', 'location', 'created_at')
    ordering = ('-created_at',)