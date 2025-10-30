from django.contrib import admin
from .models import Registration, Contact

@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'role', 'created_at')
    search_fields = ('name', 'email', 'role')
    list_filter = ('experience', 'qualification', 'created_at')

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'created_at')
    search_fields = ('name', 'email', 'message')