from django.shortcuts import render, HttpResponse, redirect
from django.http import JsonResponse
from .models import Registration, Contact
import stripe
from django.conf import settings
from django.core.files import File
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.auth.decorators import login_required

stripe.api_key = settings.STRIPE_SECRET_KEY


def registration_view(request):
    return render(request, 'base/index.html', {
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY
    })


def register_user(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        nationality = request.POST.get('nationality')
        location = request.POST.get('location')
        qualification = request.POST.get('qualification')
        experience = request.POST.get('experience')
        role = request.POST.get('role')
        resume = request.FILES.get('resume')

        Registration.objects.create(
            name=name,
            email=email,
            phone=phone,
            nationality=nationality,
            location=location,
            qualification=qualification,
            experience=experience,
            role=role,
            resume=resume
        )
        return JsonResponse({'status': 'success', 'message': 'Registration submitted successfully.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=400)


def contact_user(request):
    if request.method == 'POST':
        name = request.POST.get('contact-name')
        email = request.POST.get('contact-email')
        phone = request.POST.get('contact-phone')
        message = request.POST.get('contact-message')

        Contact.objects.create(
            name=name,
            email=email,
            phone=phone,
            message=message
        )
        messages.success(request, "We will get back to you soon!")
        return redirect('/')

    return redirect('/')


@csrf_exempt
def create_checkout_session(request):
    if request.method == 'POST':
        try:
            # Amount in cents (e.g., 50 USD = 5000)
            amount = 4900

            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'aed',
                        'product_data': {
                            'name': 'Registration Fee',
                        },
                        'unit_amount': amount,
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=request.build_absolute_uri('/register/success/'),
                cancel_url=request.build_absolute_uri('/'),
            )
            return JsonResponse({'id': session.id})
        except Exception as e:
            return JsonResponse({'error': str(e)})
        

def registration_success(request):
    data = request.session.get('registration_data')
    if not data:
        return HttpResponse("No registration data found in session.", status=400)

    resume_tmp_path = data.pop('resume', None)
    registration = Registration(
        name=data['name'],
        email=data['email'],
        phone=data['phone'],
        nationality=data['nationality'],
        location=data['location'],
        qualification=data['qualification'],
        experience=data['experience'],
        role=data['role'],
    )

    # Assign resume if it exists
    if resume_tmp_path and os.path.exists(resume_tmp_path):
        # Open the file and keep it open while saving
        f = open(resume_tmp_path, 'rb')
        registration.resume.save(os.path.basename(resume_tmp_path), File(f))
        f.close()  # can close after save

        # Remove temp file after saving
        os.remove(resume_tmp_path)

    registration.save()

    # Clean session
    del request.session['registration_data']

    messages.success(request, "Your registration was successful!")
    return redirect('/')



@csrf_exempt
def temp_save_registration(request):
    if request.method == 'POST':
        # Save form data to session
        data = {
            'name': request.POST.get('name'),
            'email': request.POST.get('email'),
            'phone': request.POST.get('phone'),
            'nationality': request.POST.get('nationality'),
            'location': request.POST.get('location'),
            'qualification': request.POST.get('qualification'),
            'experience': request.POST.get('experience'),
            'role': request.POST.get('role'),
        }

        # Save resume temporarily
        resume = request.FILES.get('resume')
        if resume:
            tmp_dir = os.path.join(settings.MEDIA_ROOT, 'tmp')
            os.makedirs(tmp_dir, exist_ok=True)
            tmp_path = os.path.join(tmp_dir, resume.name)
            with open(tmp_path, 'wb+') as f:
                for chunk in resume.chunks():
                    f.write(chunk)
            data['resume'] = tmp_path

        request.session['registration_data'] = data
        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'error'}, status=400)


def terms(request):
    return render(request, 'base/terms.html')



# DASHBOARD

@login_required(login_url='/admin')
def registrations_dashboard(request):
    registrations = Registration.objects.all().order_by('-id')
    return render(request, 'base/registrations_dashboard.html', {'registrations': registrations})