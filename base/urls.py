from django.urls import path

from . import views

urlpatterns = [
    # Main pages
    path('contact/', views.contact_user, name='contact_user'),
    path('', views.registration_view, name='register_user'),
    path('create-checkout-session/', views.create_checkout_session, name='create_checkout_session'),
    path('register/success/', views.registration_success, name='registration_success'),
    path('register/temp-save/', views.temp_save_registration, name='temp_save_registration'),
    path('dashboard/', views.registrations_dashboard, name='registrations_dashboard'),
    path('dashboard/toggle-placed/', views.toggle_placed, name='toggle_placed'),
    path("terms/", views.terms, name="terms"),
    
    # Employee Authentication
    path('employee/register/', views.employee_register, name='employee_register'),
    path('employee/login/', views.employee_login, name='employee_login'),
    path('employee/logout/', views.employee_logout, name='employee_logout'),
    path('employee/dashboard/', views.employee_dashboard, name='employee_dashboard'),
    
    # Employer Authentication
    path('employer/register/', views.employer_register, name='employer_register'),
    path('employer/login/', views.employer_login, name='employer_login'),
    path('employer/logout/', views.employer_logout, name='employer_logout'),
    path('employer/dashboard/', views.employer_dashboard, name='employer_dashboard'),
    path('employer/interest/', views.express_interest, name='express_interest'),
    path('employee/interest/', views.employee_express_interest, name='employee_express_interest'),
]
