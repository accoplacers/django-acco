from django.contrib import admin
from .models import Registration, Contact, Employer, JobOpening, EmployerInterest


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'name', 'email', 'phone', 'role', 'location', 'experience', 'plan', 'is_placed', 'created_at')
    search_fields = ('id', 'name', 'email', 'role', 'location', 'qualification')
    list_filter = ('is_placed', 'experience', 'qualification', 'plan', 'created_at', 'location')
    readonly_fields = ('employee_id', 'created_at')
    ordering = ('-created_at',)
    actions = ['mark_as_placed', 'mark_as_available']

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
            'fields': ('plan', 'is_placed', 'created_at')
        }),
    )

    def employee_id(self, obj):
        if obj.id is None:
            return "N/A"
        return f"EMP-{obj.id:04d}"
    employee_id.short_description = 'Employee ID'
    employee_id.admin_order_field = 'id'

    @admin.action(description='Mark selected employees as Placed')
    def mark_as_placed(self, request, queryset):
        updated = queryset.update(is_placed=True)
        self.message_user(request, f"{updated} employee(s) marked as placed.")

    @admin.action(description='Mark selected employees as Available')
    def mark_as_available(self, request, queryset):
        updated = queryset.update(is_placed=False)
        self.message_user(request, f"{updated} employee(s) marked as available.")


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
        if obj.id is None:
            return "N/A"
        return f"EMPR-{obj.id:04d}"
    employer_id.short_description = 'Employer ID'
    employer_id.admin_order_field = 'id'


@admin.register(JobOpening)
class JobOpeningAdmin(admin.ModelAdmin):
    list_display = ('title', 'employer', 'location', 'job_type', 'is_active', 'created_at')
    search_fields = ('title', 'employer__company_name')
    list_filter = ('job_type', 'is_active', 'location', 'created_at')
    ordering = ('-created_at',)


@admin.register(EmployerInterest)
class EmployerInterestAdmin(admin.ModelAdmin):
    list_display = ('employer', 'employee_id_display', 'employee_name', 'employee_role', 'created_at')
    search_fields = ('employer__company_name', 'employee__name', 'employee__role')
    list_filter = ('employer', 'created_at')
    ordering = ('-created_at',)
    readonly_fields = ('employer', 'employee', 'created_at')

    def employee_id_display(self, obj):
        return f"EMP-{obj.employee.id:04d}"
    employee_id_display.short_description = 'Employee ID'
    employee_id_display.admin_order_field = 'employee__id'

    def employee_name(self, obj):
        return obj.employee.name
    employee_name.short_description = 'Candidate Name'
    employee_name.admin_order_field = 'employee__name'

    def employee_role(self, obj):
        return obj.employee.role
    employee_role.short_description = 'Role'
    employee_role.admin_order_field = 'employee__role'