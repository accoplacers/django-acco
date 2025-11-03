from django.urls import path

from . import views

urlpatterns = [
    # path("", views.index, name="index"),
    # path('register/', views.register_user, name='register_user'),
    path('contact/', views.contact_user, name='contact_user'),
    path('', views.registration_view, name='register_user'),
    path('create-checkout-session/', views.create_checkout_session, name='create_checkout_session'),
    path('register/success/', views.registration_success, name='registration_success'),
    path('register/temp-save/', views.temp_save_registration, name='temp_save_registration'),
    path('dashboard/', views.registrations_dashboard, name='registrations_dashboard'),
    path("terms/", views.terms, name="terms"),
]
