from django.contrib import admin
from .models import Registration, Contact, Employer, JobOpening, EmployerInterest, ContactEvent, ApplicationStatus, Skill, EmployeeInterest


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'name', 'email', 'role', 'location', 'get_profile_score', 'is_featured', 'is_placed', 'created_at')
    list_editable = ('is_featured', 'is_placed')
    search_fields = ('name', 'email', 'role')
    list_filter = ('location', 'is_featured', 'is_placed', 'experience', 'plan', 'created_at')
    readonly_fields = ('employee_id', 'created_at')
    filter_horizontal = ('skills',)
    ordering = ('-created_at',)
    actions = ['mark_as_placed', 'mark_as_available']

    fieldsets = (
        ('Employee ID', {
            'fields': ('employee_id',)
        }),
        ('Personal Information', {
            'fields': ('name', 'email', 'phone', 'nationality', 'location')
        }),
        ('Professional Details', {
            'fields': ('qualification', 'experience', 'role', 'resume', 'photo', 'skills')
        }),
        ('Plan & Status', {
            'fields': ('plan', 'is_placed', 'is_featured', 'created_at')
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

    def get_profile_score(self, obj):
        score = 0
        if obj.name: score += 1
        if obj.email: score += 1
        if obj.role: score += 1
        if obj.location: score += 1
        if obj.skills.exists(): score += 1
        if obj.resume: score += 1
        return f"{int((score/6)*100)}%"
    get_profile_score.short_description = 'Profile Score'


@admin.register(ApplicationStatus)
class ApplicationStatusAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'status', 'updated_at')
    list_filter = ('status',)
    list_editable = ('status',)
    search_fields = ('candidate__name', 'candidate__email')


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
            'fields': ('company_name', 'email', 'phone', 'industry', 'location')
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


@admin.register(ContactEvent)
class ContactEventAdmin(admin.ModelAdmin):
    list_display = ('employer', 'candidate', 'contact_type', 'contacted_at')
    readonly_fields = ('contacted_at',)
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'created_at')
    search_fields = ('name', 'category')


@admin.register(EmployerInterest)
class EmployerInterestAdmin(admin.ModelAdmin):
    list_display = ('employer', 'employee', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(EmployeeInterest)
class EmployeeInterestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'job', 'created_at')
    readonly_fields = ('created_at',)
