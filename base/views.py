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
from django.contrib.auth.hashers import make_password, check_password
from django.core.exceptions import ValidationError
from .validators import (
    validate_company_name,
    validate_phone_number,
    validate_safe_email,
    validate_text_input
)
from .decorators import rate_limit

stripe.api_key = settings.STRIPE_SECRET_KEY


def registration_view(request):
    context = {
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
        'session_user_type': request.session.get('user_type'),
        'session_user_name': (
            request.session.get('employee_name') if request.session.get('user_type') == 'employee'
            else request.session.get('employer_name') if request.session.get('user_type') == 'employer'
            else None
        ),
    }
    return render(request, 'base/index.html', context)


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

        if Registration.objects.filter(email=email).exists():
             return JsonResponse({'status': 'error', 'message': 'Email already registered.'}, status=400)

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


@rate_limit(max_requests=3, time_window=60, block_duration=300)
def contact_user(request):
    if request.method == 'POST':
        name = request.POST.get('contact-name', '').strip()
        email = request.POST.get('contact-email', '').strip()
        phone = request.POST.get('contact-phone', '').strip()
        message = request.POST.get('contact-message', '').strip()

        try:
            # Validate all inputs
            validate_text_input(name, min_length=2, max_length=150)
            validate_safe_email(email)
            validate_phone_number(phone)
            validate_text_input(message, min_length=10, max_length=2000)

        except ValidationError as e:
            messages.error(request, f"Invalid input: {str(e)}")
            return redirect('/')

        Contact.objects.create(
            name=name,
            email=email,
            phone=phone,
            message=message
        )
        messages.success(request, "Thank you for contacting us! We will get back to you soon!")
        return redirect('/')

    return redirect('/')


@csrf_exempt
def create_checkout_session(request):
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body.decode('utf-8'))
            plan = data.get('plan', 'basic')

            # ✅ Map plan to price (in AED)
            plan_prices = {
                'basic': 49,
                'intermediate': 89,
                'premium': 149,
            }

            amount_aed = plan_prices.get(plan, 49)
            amount = int(amount_aed * 100)  # Stripe expects amount in fils

            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'aed',
                        'product_data': {
                            'name': f'{plan.capitalize()} Registration Plan',
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

    # Check if email already exists
    email = data.get('email')
    if Registration.objects.filter(email=email).exists():
        # Clean up temp files if they exist
        resume_tmp_path = data.get('resume')
        photo_tmp_path = data.get('photo')
        if resume_tmp_path and os.path.exists(resume_tmp_path):
            os.remove(resume_tmp_path)
        if photo_tmp_path and os.path.exists(photo_tmp_path):
            os.remove(photo_tmp_path)
        # Clean session
        del request.session['registration_data']
        messages.error(request, "An account with this email already exists. Please login or use a different email.")
        return redirect('/')

    resume_tmp_path = data.pop('resume', None)
    photo_tmp_path = data.pop('photo', None)
    password = data.pop('password', None)
    if not password:
        messages.error(request, "Registration error: Missing password. Please try again.")
        return redirect('/')

    registration = Registration(
        name=data['name'],
        email=data['email'],
        password=make_password(password),
        phone=data['phone'],
        nationality=data['nationality'],
        location=data['location'],
        qualification=data['qualification'],
        experience=data['experience'],
        role=data['role'],
        plan=data.get('plan', 'basic'),
    )

    # Assign resume if it exists
    if resume_tmp_path and os.path.exists(resume_tmp_path):
        f = open(resume_tmp_path, 'rb')
        registration.resume.save(os.path.basename(resume_tmp_path), File(f))
        f.close()
        os.remove(resume_tmp_path)

    # Assign photo if it exists
    if photo_tmp_path and os.path.exists(photo_tmp_path):
        f = open(photo_tmp_path, 'rb')
        registration.photo.save(os.path.basename(photo_tmp_path), File(f))
        f.close()
        os.remove(photo_tmp_path)

    registration.save()

    # Clean session
    del request.session['registration_data']

    messages.success(request, "Your registration was successful!")
    return redirect('/')




@csrf_exempt
@rate_limit(max_requests=5, time_window=60, block_duration=300)
def temp_save_registration(request):
    if request.method == 'POST':
        # Get and sanitize inputs
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        phone = request.POST.get('phone', '').strip()
        nationality = request.POST.get('nationality', '').strip()
        location = request.POST.get('location', '').strip()
        qualification = request.POST.get('qualification', '').strip()
        experience = request.POST.get('experience', '').strip()
        role = request.POST.get('role', '').strip()
        plan = request.POST.get('plan', 'basic')

        try:
            # Validate all inputs
            validate_text_input(name, min_length=2, max_length=150)
            validate_safe_email(email)
            validate_phone_number(phone)
            validate_text_input(nationality, min_length=2, max_length=100)
            validate_text_input(location, min_length=2, max_length=100)
            validate_text_input(qualification, min_length=2, max_length=100)
            validate_text_input(experience, min_length=1, max_length=20)
            validate_text_input(role, min_length=2, max_length=100)

            # Validate password
            if not password or len(password) < 6:
                raise ValidationError("Password must be at least 6 characters long.")
            if len(password) > 128:
                raise ValidationError("Password is too long.")

            # Validate plan
            if plan not in ['basic', 'intermediate', 'premium']:
                raise ValidationError("Invalid plan selected.")

        except ValidationError as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

        # Check if email already exists
        if Registration.objects.filter(email=email).exists():
            return JsonResponse({'status': 'error', 'message': 'An account with this email already exists. Please login.'})

        data = {
            'name': name,
            'email': email,
            'password': password,
            'phone': phone,
            'nationality': nationality,
            'location': location,
            'qualification': qualification,
            'experience': experience,
            'role': role,
            'plan': plan,
        }

        tmp_dir = os.path.join(settings.MEDIA_ROOT, 'tmp')
        os.makedirs(tmp_dir, exist_ok=True)

        # Save resume temporarily
        resume = request.FILES.get('resume')
        if resume:
            tmp_path = os.path.join(tmp_dir, resume.name)
            with open(tmp_path, 'wb+') as f:
                for chunk in resume.chunks():
                    f.write(chunk)
            data['resume'] = tmp_path

        # Save photo temporarily
        photo = request.FILES.get('photo')
        if photo:
            photo_tmp_path = os.path.join(tmp_dir, photo.name)
            with open(photo_tmp_path, 'wb+') as f:
                for chunk in photo.chunks():
                    f.write(chunk)
            data['photo'] = photo_tmp_path

        request.session['registration_data'] = data
        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'error'}, status=400)


@rate_limit(max_requests=5, time_window=60, block_duration=300)
def employee_register(request):
    if request.session.get('user_type') == 'employee':
        return redirect('employee_dashboard')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        phone = request.POST.get('phone', '').strip()
        nationality = request.POST.get('nationality', '').strip()
        location = request.POST.get('location', '').strip()
        qualification = request.POST.get('qualification', '').strip()
        experience = request.POST.get('experience', '').strip()
        role = request.POST.get('role', '').strip()
        resume = request.FILES.get('resume')
        photo = request.FILES.get('photo')
        plan = request.POST.get('plan', 'basic')

        form_data = {
            'name': name, 'email': email, 'phone': phone,
            'nationality': nationality, 'location': location,
            'qualification': qualification, 'experience': experience, 'role': role,
        }

        try:
            validate_text_input(name, min_length=2, max_length=150)
            validate_safe_email(email)
            validate_phone_number(phone)
            validate_text_input(nationality, min_length=2, max_length=100)
            validate_text_input(location, min_length=2, max_length=100)
            validate_text_input(qualification, min_length=2, max_length=100)
            validate_text_input(experience, min_length=1, max_length=20)
            validate_text_input(role, min_length=2, max_length=100)

            if not password or len(password) < 6:
                raise ValidationError("Password must be at least 6 characters long.")
            if len(password) > 128:
                raise ValidationError("Password is too long.")
            if password != confirm_password:
                raise ValidationError("Passwords do not match.")
            if plan not in ['basic', 'intermediate', 'premium']:
                plan = 'basic'
            if not resume:
                raise ValidationError("Please upload your resume.")

        except ValidationError as e:
            messages.error(request, str(e))
            return render(request, 'base/employee_register.html', {'form_data': form_data})

        if Registration.objects.filter(email=email).exists():
            messages.error(request, "An account with this email already exists. Please login.")
            return render(request, 'base/employee_register.html', {'form_data': form_data})

        registration = Registration(
            name=name,
            email=email,
            password=make_password(password),
            phone=phone,
            nationality=nationality,
            location=location,
            qualification=qualification,
            experience=experience,
            role=role,
            plan=plan,
        )

        if resume:
            registration.resume.save(resume.name, resume, save=False)
        if photo:
            registration.photo.save(photo.name, photo, save=False)

        registration.save()

        messages.success(request, "Registration successful! Please login to access your dashboard.")
        return redirect('employee_login')

    return render(request, 'base/employee_register.html')


def terms(request):
    return render(request, 'base/terms.html')



# DASHBOARD

@login_required(login_url='/admin')
def registrations_dashboard(request):
    # Handle job opening creation
    if request.method == 'POST' and request.POST.get('action') == 'create_job':
        try:
            employer_id = request.POST.get('employer')
            employer = Employer.objects.get(id=employer_id)
            JobOpening.objects.create(
                employer=employer,
                title=request.POST.get('title'),
                description=request.POST.get('description'),
                requirements=request.POST.get('requirements'),
                salary_range=request.POST.get('salary_range', ''),
                location=request.POST.get('location'),
                job_type=request.POST.get('job_type', 'Full-time'),
                is_active=request.POST.get('is_active') == 'on'
            )
            messages.success(request, 'Job opening created successfully!')
        except Exception as e:
            messages.error(request, f'Error creating job: {str(e)}')
        return redirect('registrations_dashboard')
    
    # Handle job deletion
    if request.method == 'POST' and request.POST.get('action') == 'delete_job':
        try:
            job_id = request.POST.get('job_id')
            JobOpening.objects.filter(id=job_id).delete()
            messages.success(request, 'Job opening deleted successfully!')
        except Exception as e:
            messages.error(request, f'Error deleting job: {str(e)}')
        return redirect('registrations_dashboard')
    
    registrations = Registration.objects.all().order_by('-id')
    employers = Employer.objects.all().order_by('-id')
    job_openings = JobOpening.objects.all().order_by('-created_at')
    
    return render(request, 'base/registrations_dashboard.html', {
        'registrations': registrations,
        'employers': employers,
        'job_openings': job_openings,
    })


# ==========================================
# EMPLOYEE AUTHENTICATION
# ==========================================

from .models import Employer, JobOpening

def employee_login(request):
    if request.session.get('user_type') == 'employee':
        return redirect('employee_dashboard')
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            employee = Registration.objects.get(email=email)
            
            if employee.password and check_password(password, employee.password):
                # Set session
                request.session['employee_id'] = employee.id
                request.session['employee_name'] = employee.name
                request.session['user_type'] = 'employee'
                messages.success(request, f"Welcome back, {employee.name}!")
                return redirect('employee_dashboard')
            else:
                messages.error(request, "Invalid email or password.")
        except Registration.DoesNotExist:
            messages.error(request, "No account found with this email.")
    
    return render(request, 'base/employee_login.html')


def employee_logout(request):
    # Clear employee session
    if 'employee_id' in request.session:
        del request.session['employee_id']
    if 'employee_name' in request.session:
        del request.session['employee_name']
    if 'user_type' in request.session:
        del request.session['user_type']
    messages.success(request, "You have been logged out.")
    return redirect('/')


def employee_dashboard(request):
    # Check if employee is logged in
    if 'employee_id' not in request.session or request.session.get('user_type') != 'employee':
        messages.error(request, "Please login to access your dashboard.")
        return redirect('employee_login')
    
    employee_id = request.session.get('employee_id')
    try:
        employee = Registration.objects.get(id=employee_id)
    except Registration.DoesNotExist:
        return redirect('employee_login')
    
    # Handle skills update
    if request.method == 'POST' and request.POST.get('action') == 'update_skills':
        skills = request.POST.get('skills', '')
        employee.skills = skills
        employee.save()
        messages.success(request, "Skills updated successfully!")
        return redirect('employee_dashboard')
    
    # Get all active job openings
    job_openings = JobOpening.objects.filter(is_active=True).order_by('-created_at')
    
    return render(request, 'base/employee_dashboard.html', {
        'employee': employee,
        'job_openings': job_openings,
    })


# ==========================================
# EMPLOYER AUTHENTICATION
# ==========================================

@rate_limit(max_requests=5, time_window=60, block_duration=300)
def employer_register(request):
    if request.session.get('user_type') == 'employer':
        return redirect('employer_dashboard')
    if request.method == 'POST':
        company_name = request.POST.get('company_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        phone = request.POST.get('phone', '').strip()
        company_description = request.POST.get('company_description', '').strip()
        location = request.POST.get('location', '').strip()
        industry = request.POST.get('industry', '').strip()
        logo = request.FILES.get('logo')

        try:
            # Validate all inputs
            validate_company_name(company_name)
            validate_safe_email(email)
            validate_phone_number(phone)
            validate_text_input(location, min_length=2, max_length=100)
            validate_text_input(industry, min_length=2, max_length=100)

            if company_description:
                validate_text_input(company_description, min_length=0, max_length=2000)

            # Validate password length
            if not password or len(password) < 6:
                raise ValidationError("Password must be at least 6 characters long.")

            if len(password) > 128:
                raise ValidationError("Password is too long (max 128 characters).")

        except ValidationError as e:
            messages.error(request, str(e))
            return render(request, 'base/employer_register.html')

        # Check if email already exists
        if Employer.objects.filter(email=email).exists():
            messages.error(request, "An account with this email already exists.")
            return render(request, 'base/employer_register.html')

        # Create employer with hashed password
        employer = Employer.objects.create(
            company_name=company_name,
            email=email,
            password=make_password(password),
            phone=phone,
            company_description=company_description,
            location=location,
            industry=industry,
            logo=logo
        )

        messages.success(request, "Registration successful! Please login.")
        return redirect('employer_login')

    return render(request, 'base/employer_register.html')


def employer_login(request):
    if request.session.get('user_type') == 'employer':
        return redirect('employer_dashboard')
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            employer = Employer.objects.get(email=email)
            if check_password(password, employer.password):
                # Set session
                request.session['employer_id'] = employer.id
                request.session['employer_name'] = employer.company_name
                request.session['user_type'] = 'employer'
                messages.success(request, f"Welcome back, {employer.company_name}!")
                return redirect('employer_dashboard')
            else:
                messages.error(request, "Invalid email or password.")
        except Employer.DoesNotExist:
            messages.error(request, "No account found with this email.")
    
    return render(request, 'base/employer_login.html')


def employer_logout(request):
    # Clear employer session
    if 'employer_id' in request.session:
        del request.session['employer_id']
    if 'employer_name' in request.session:
        del request.session['employer_name']
    if 'user_type' in request.session:
        del request.session['user_type']
    messages.success(request, "You have been logged out.")
    return redirect('/')


def employer_dashboard(request):
    # Check if employer is logged in
    if 'employer_id' not in request.session or request.session.get('user_type') != 'employer':
        messages.error(request, "Please login to access your dashboard.")
        return redirect('employer_login')
    
    employer_id = request.session.get('employer_id')
    try:
        employer = Employer.objects.get(id=employer_id)
    except Employer.DoesNotExist:
        return redirect('employer_login')
    
    # Get all registered employees
    employees = Registration.objects.all().order_by('-created_at')
    
    return render(request, 'base/employer_dashboard.html', {
        'employer': employer,
        'employees': employees,
    })