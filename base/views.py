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
from django.contrib.auth import login, authenticate, logout as django_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password, check_password
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Registration, Contact, Employer, JobOpening, EmployerInterest, EmployeeInterest, UserAccount
from .validators import (
    validate_company_name,
    validate_phone_number,
    validate_safe_email,
    validate_text_input
)
import logging
from .decorators import rate_limit

logger = logging.getLogger(__name__)
from .services.resume_parser import extract_text_from_pdf, parse_resume_with_llm, ParsedResume
from .models import Skill

stripe.api_key = settings.STRIPE_SECRET_KEY


def registration_view(request):
    user = request.user if request.user.is_authenticated else None
    context = {
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
        'session_user_type': user.role if user else None,
        'session_user_name': (
            user.email if user else None
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

            # ✅ Map plan to price (in AED) - Consumed from settings
            amount_aed = settings.STRIPE_PLAN_PRICES.get(plan, settings.STRIPE_PLAN_PRICES['basic'])
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

    with transaction.atomic():
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

        # Create auth user
        UserAccount.objects.create(
            email=registration.email,
            password=registration.password, # Already hashed
            role='employee',
            profile_id=registration.id
        )

    # Clean session
    del request.session['registration_data']

    messages.success(request, "Your registration was successful! Please login.")
    return redirect('employee_login')




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
            if resume.size > 5 * 1024 * 1024:
                return JsonResponse({'status': 'error', 'message': 'Resume file size must not exceed 5 MB.'}, status=400)
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


@rate_limit(max_requests=10, time_window=600, block_duration=600)
def employee_register(request):
    def render_employee_register(form_data=None, initial_step=1):
        context = {'initial_step': initial_step}
        if form_data:
            context['form_data'] = form_data
        return render(request, 'base/employee_register.html', context)

    def get_initial_step(error_message):
        message = (error_message or '').lower()
        if any(token in message for token in ['resume', 'deposit', 'refund', 'terms', 'photo']):
            return 3
        if any(token in message for token in ['phone', 'nationality', 'location', 'qualification', 'experience', 'role']):
            return 2
        return 1

    if request.user.is_authenticated:
        if request.user.role == 'employee':
            return redirect('employee_dashboard')
        elif request.user.role == 'employer':
            return redirect('employer_dashboard')
    if request.method == 'POST':
        # --- TASK 1: HONEYPOT BOT TRAP ---
        if request.POST.get('fax_number'):
            logger.warning(f"Bot detected: Honeypot field filled. IP: {request.META.get('REMOTE_ADDR')}")
            return HttpResponse("Bad Request", status=400)

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
        terms_accepted = request.POST.get('terms') == 'on'

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
            if resume.size > 5 * 1024 * 1024:
                raise ValidationError("Resume file size must not exceed 5 MB.")
            if not terms_accepted:
                raise ValidationError("Please confirm the deposit and refund policy to continue.")

        except ValidationError as e:
            error_message = str(e)
            messages.error(request, error_message)
            return render_employee_register(form_data, get_initial_step(error_message))

        # Phase 0: Photo upload size cap
        if photo and photo.size > 5 * 1024 * 1024:
            error_message = "Photo file size must not exceed 5 MB."
            messages.error(request, error_message)
            return render_employee_register(form_data, get_initial_step(error_message))

        if Registration.objects.filter(email=email).exists():
            error_message = "An account with this email already exists. Please login."
            messages.error(request, error_message)
            return render_employee_register(form_data, get_initial_step(error_message))

        with transaction.atomic():
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

            # --- AI INGESTION PIPELINE ---
            # Extract and parse resume to auto-populate skills and score profile.
            try:
                resume_path = registration.resume.path
                if os.path.exists(resume_path):
                    raw_text = extract_text_from_pdf(resume_path)
                    parsed_data = parse_resume_with_llm(raw_text)

                    # 1. Experience Mapping
                    if parsed_data.years_of_experience > 0:
                        registration.experience = str(parsed_data.years_of_experience)

                    # 2. Skill & Competency Mapping (M2M)
                    # Combine all extracted semantic fields into Skill objects
                    all_skill_items = (
                        parsed_data.certifications + 
                        parsed_data.erp_software + 
                        parsed_data.core_competencies +
                        parsed_data.regulatory_knowledge
                    )
                    
                    for item in all_skill_items:
                        skill_obj, _ = Skill.objects.get_or_create(name=item.strip())
                        registration.skills.add(skill_obj)

                    registration.save()
                    
            except Exception as e:
                # Log the error but do NOT roll back registration. 
                # We want the user to be registered even if the AI parsing fails.
                print(f"AI Ingestion Failed for {email}: {str(e)}")

            # Create auth user
            UserAccount.objects.create(
                email=email,
                password=registration.password, # Reuse hash
                role='employee',
                profile_id=registration.id
            )

        messages.success(request, "Registration successful! Please login to access your dashboard.")
        return redirect('employee_login')

    return render_employee_register()


def terms(request):
    return render(request, 'base/terms.html')



# DASHBOARD

@login_required(login_url='/admin/login/')
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
    placed_count = registrations.filter(is_placed=True).count()
    interests = EmployerInterest.objects.select_related('employer', 'employee').order_by('-created_at')
    employee_interests = EmployeeInterest.objects.select_related('employee', 'job', 'job__employer').order_by('-created_at')

    return render(request, 'base/registrations_dashboard.html', {
        'registrations': registrations,
        'employers': employers,
        'job_openings': job_openings,
        'placed_count': placed_count,
        'interests': interests,
        'employee_interests': employee_interests,
    })


# ==========================================
# EMPLOYEE AUTHENTICATION
# ==========================================

def employee_login(request):
    if request.user.is_authenticated:
        if request.user.role == 'employee':
            return redirect('employee_dashboard')
        elif request.user.role == 'employer':
            return redirect('employer_dashboard')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Phase 0: Password Length Guard
        if not password or len(password) > 1000:
            messages.error(request, "Invalid email or password.")
            return render(request, 'base/employee_login.html')

        user = authenticate(request, email=email, password=password)
        
        if user is not None and user.role == 'employee':
            login(request, user)
            messages.success(request, f"Welcome back, {email}!")
            return redirect('employee_dashboard')
        else:
            messages.error(request, "Invalid email or password.")
    
    return render(request, 'base/employee_login.html')


def employee_logout(request):
    django_logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('/')


@login_required(login_url='employee_login')
def employee_dashboard(request):
    if request.user.role != 'employee':
        messages.error(request, "Unauthorized access.")
        return redirect('registration_view')
    
    employee_id = request.user.profile_id
    try:
        employee = Registration.objects.get(id=employee_id)
    except Registration.DoesNotExist:
        return redirect('employee_login')
    
    # Handle skills update
    if request.method == 'POST' and request.POST.get('action') == 'update_skills':
        from .models import Skill
        skills_raw = request.POST.get('skills', '')
        skill_names = [s.strip() for s in skills_raw.split(',') if s.strip()]
        skill_objs = []
        for name in skill_names:
            obj, created = Skill.objects.get_or_create(name=name)
            skill_objs.append(obj)
        employee.skills.set(skill_objs)
        employee.save()
        messages.success(request, "Skills updated successfully!")
        return redirect('employee_dashboard')

    employee_skills = list(employee.skills.values_list('name', flat=True))
    employee_skill_set = {skill.lower() for skill in employee_skills}

    profile_checks = [
        bool(employee.name),
        bool(employee.email),
        bool(employee.phone),
        bool(employee.location),
        bool(employee.nationality),
        bool(employee.qualification),
        bool(employee.experience),
        bool(employee.role),
        bool(employee.resume),
        bool(employee_skill_set),
    ]
    profile_completion = int((sum(profile_checks) / len(profile_checks)) * 100)

    # Get all active job openings
    job_openings = list(JobOpening.objects.filter(is_active=True).select_related('employer').order_by('-created_at'))

    interested_job_ids = set(
        EmployeeInterest.objects.filter(employee=employee).values_list('job_id', flat=True)
    )

    role_tokens = {token.lower() for token in employee.role.replace('/', ' ').replace(',', ' ').split() if len(token) > 2}
    suggested_skills_pool = [
        'IFRS', 'Excel', 'VAT', 'SAP', 'Power BI', 'Financial Reporting',
        'Internal Audit', 'Reconciliation', 'Budgeting', 'Payroll',
    ]
    suggested_skills = [skill for skill in suggested_skills_pool if skill.lower() not in employee_skill_set][:5]

    job_cards = []
    recommended_count = 0

    for job in job_openings:
        haystack = " ".join(filter(None, [job.title, job.description, job.requirements, job.location])).lower()
        matched_skills = [skill for skill in employee_skills if skill.lower() in haystack]

        match_score = 0
        match_reasons = []

        if any(token in haystack for token in role_tokens):
            match_score += 3
            match_reasons.append("Role aligned")

        if matched_skills:
            match_score += min(len(matched_skills), 3) * 2
            match_reasons.append(f"{len(matched_skills)} skill match" if len(matched_skills) > 1 else "1 skill match")

        if employee.location and employee.location.lower() in haystack:
            match_score += 1
            match_reasons.append("Location aligned")

        is_interested = job.id in interested_job_ids
        if is_interested:
            match_score += 1

        is_recommended = match_score >= 3
        if is_recommended:
            recommended_count += 1

        if not match_reasons:
            match_reasons.append("Open to finance applicants")

        job_cards.append({
            'job': job,
            'is_interested': is_interested,
            'is_recommended': is_recommended,
            'match_score': match_score,
            'match_reason': match_reasons[0],
            'match_detail': ", ".join(match_reasons),
            'matched_skills': matched_skills[:3],
        })

    job_cards.sort(
        key=lambda item: (
            not item['is_interested'],
            not item['is_recommended'],
            -item['match_score'],
            -item['job'].created_at.timestamp(),
        )
    )

    next_steps = []
    if not employee_skill_set:
        next_steps.append({
            'title': 'Add your core skills',
            'detail': 'Include systems, certifications, and finance tools so matching is more precise.',
            'action': 'Update skills below',
        })
    if not interested_job_ids:
        next_steps.append({
            'title': 'Save your first opportunity',
            'detail': 'Mark roles as interested so the team can see where you want to be introduced.',
            'action': 'Review today\'s openings',
        })
    if profile_completion < 100:
        next_steps.append({
            'title': 'Complete your profile',
            'detail': f'Your profile is {profile_completion}% complete. A more complete profile is easier to shortlist.',
            'action': 'Review profile signals',
        })

    if not next_steps:
        next_steps.append({
            'title': 'Keep momentum',
            'detail': 'Your profile is in good shape. Stay active by reviewing new openings and updating skills as they grow.',
            'action': 'Check new roles weekly',
        })

    return render(request, 'base/employee_dashboard.html', {
        'employee': employee,
        'job_cards': job_cards,
        'interested_job_ids': interested_job_ids,
        'profile_completion': profile_completion,
        'recommended_count': recommended_count,
        'skills_count': len(employee_skills),
        'next_steps': next_steps,
        'suggested_skills': suggested_skills,
    })


# ==========================================
# EMPLOYER AUTHENTICATION
# ==========================================

@rate_limit(max_requests=5, time_window=60, block_duration=300)
def employer_register(request):
    def render_employer_register(form_data=None, initial_section='company'):
        context = {'initial_section': initial_section}
        if form_data:
            context['form_data'] = form_data
        return render(request, 'base/employer_register.html', context)

    def get_initial_section(error_message):
        message = (error_message or '').lower()
        if any(token in message for token in ['password', 'logo', 'security']):
            return 'security'
        if any(token in message for token in ['industry', 'description', 'hiring']):
            return 'hiring'
        return 'company'

    if request.user.is_authenticated:
        if request.user.role == 'employer':
            return redirect('employer_dashboard')
        elif request.user.role == 'employee':
            return redirect('employee_dashboard')
    if request.method == 'POST':
        if request.POST.get('fax_number'):
            logger.warning(f"Bot detected: Employer honeypot field filled. IP: {request.META.get('REMOTE_ADDR')}")
            return HttpResponse("Bad Request", status=400)

        company_name = request.POST.get('company_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        phone = request.POST.get('phone', '').strip()
        company_description = request.POST.get('company_description', '').strip()
        location = request.POST.get('location', '').strip()
        industry = request.POST.get('industry', '').strip()
        logo = request.FILES.get('logo')

        form_data = {
            'company_name': company_name,
            'email': email,
            'phone': phone,
            'company_description': company_description,
            'location': location,
            'industry': industry,
        }

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

            if password != confirm_password:
                raise ValidationError("Passwords do not match.")

            if logo and logo.size > 5 * 1024 * 1024:
                raise ValidationError("Logo file size must not exceed 5 MB.")

        except ValidationError as e:
            error_message = str(e)
            messages.error(request, error_message)
            return render_employer_register(form_data, get_initial_section(error_message))

        # Check if email already exists
        if Employer.objects.filter(email=email).exists():
            error_message = "An account with this email already exists."
            messages.error(request, error_message)
            return render_employer_register(form_data, get_initial_section(error_message))

        # Create employer and user atomically
        with transaction.atomic():
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

            # Create auth user
            UserAccount.objects.create(
                email=email,
                password=employer.password, # Reuse hash
                role='employer',
                profile_id=employer.id
            )

        messages.success(request, "Registration successful! Please login.")
        return redirect('employer_login')

    return render_employer_register()


def employer_login(request):
    if request.user.is_authenticated:
        if request.user.role == 'employer':
            return redirect('employer_dashboard')
        elif request.user.role == 'employee':
            return redirect('employee_dashboard')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Phase 0: Password Length Guard
        if not password or len(password) > 1000:
            messages.error(request, "Invalid email or password.")
            return render(request, 'base/employer_login.html')

        user = authenticate(request, email=email, password=password)
        
        if user is not None and user.role == 'employer':
            login(request, user)
            messages.success(request, f"Welcome back, {email}!")
            return redirect('employer_dashboard')
        else:
            messages.error(request, "Invalid email or password.")
    
    return render(request, 'base/employer_login.html')


def employer_logout(request):
    django_logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('/')


@login_required(login_url='/admin/login/')
def toggle_placed(request):
    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        action = request.POST.get('action')
        try:
            employee = Registration.objects.get(id=employee_id)
            employee.is_placed = (action == 'place')
            employee.save()
            if employee.is_placed:
                messages.success(request, f"{employee.name} has been marked as placed.")
            else:
                messages.success(request, f"{employee.name} has been marked as available.")
        except Registration.DoesNotExist:
            messages.error(request, "Employee not found.")
    return redirect('registrations_dashboard')


@login_required(login_url='employer_login')
def employer_dashboard(request):
    if request.user.role != 'employer':
        messages.error(request, "Unauthorized access.")
        return redirect('registration_view')
    
    employer_id = request.user.profile_id
    try:
        employer = Employer.objects.get(id=employer_id)
    except Employer.DoesNotExist:
        return redirect('employer_login')

    from django.db.models import Count, Q
    from django.core.paginator import Paginator

    if request.method == 'POST':
        action = request.POST.get('action')

        if action in ['create_job', 'update_job']:
            title = request.POST.get('title', '').strip()
            description = request.POST.get('description', '').strip()
            requirements = request.POST.get('requirements', '').strip()
            salary_range = request.POST.get('salary_range', '').strip()
            location = request.POST.get('location', '').strip()
            job_type = request.POST.get('job_type', 'Full-time').strip() or 'Full-time'
            is_active = request.POST.get('is_active') == 'on'

            try:
                validate_text_input(title, min_length=3, max_length=200)
                validate_text_input(description, min_length=20, max_length=3000)
                validate_text_input(requirements, min_length=10, max_length=3000)
                validate_text_input(location, min_length=2, max_length=100)
                if salary_range:
                    validate_text_input(salary_range, min_length=2, max_length=50)
                validate_text_input(job_type, min_length=2, max_length=50)

                if action == 'create_job':
                    JobOpening.objects.create(
                        employer=employer,
                        title=title,
                        description=description,
                        requirements=requirements,
                        salary_range=salary_range,
                        location=location,
                        job_type=job_type,
                        is_active=is_active,
                    )
                    messages.success(request, "Job opening created successfully.")
                else:
                    job_id = request.POST.get('job_id')
                    job = JobOpening.objects.get(id=job_id, employer=employer)
                    job.title = title
                    job.description = description
                    job.requirements = requirements
                    job.salary_range = salary_range
                    job.location = location
                    job.job_type = job_type
                    job.is_active = is_active
                    job.save()
                    messages.success(request, "Job opening updated successfully.")

            except JobOpening.DoesNotExist:
                messages.error(request, "The selected job could not be found.")
            except ValidationError as e:
                messages.error(request, str(e))

            return redirect('employer_dashboard')

        if action == 'delete_job':
            job_id = request.POST.get('job_id')
            deleted, _ = JobOpening.objects.filter(id=job_id, employer=employer).delete()
            if deleted:
                messages.success(request, "Job opening deleted successfully.")
            else:
                messages.error(request, "The selected job could not be found.")
            return redirect('employer_dashboard')

    # Base queryset
    employees = Registration.objects.all().order_by('-created_at')

    # Get search parameters
    search_query = request.GET.get('q', '').strip()
    skill_query = request.GET.get('skill', '').strip()
    availability_filter = request.GET.get('availability', 'available').strip()
    experience_filter = request.GET.get('experience_band', '').strip()
    interested_filter = request.GET.get('interest_scope', '').strip()
    verified_filter = request.GET.get('verified', '1').strip()

    # Apply text filter
    if search_query:
        if search_query.lower().startswith('emp-'):
            emp_id = ''.join(filter(str.isdigit, search_query))
            if emp_id:
                employees = employees.filter(id=int(emp_id))
            else:
                employees = employees.none()
        else:
            employees = employees.filter(
                Q(name__icontains=search_query) | 
                Q(role__icontains=search_query) | 
                Q(location__icontains=search_query)
            ).distinct()

    # Apply skills filter using the new M2M relationship
    if skill_query:
        req_skills = [s.strip() for s in skill_query.split(',') if s.strip()]
        for skill in req_skills:
            employees = employees.filter(skills__name__icontains=skill)

    if availability_filter == 'available':
        employees = employees.filter(is_placed=False)
    elif availability_filter == 'placed':
        employees = employees.filter(is_placed=True)

    if experience_filter == 'junior':
        employees = employees.filter(Q(experience='0-1') | Q(experience='1-3'))
    elif experience_filter == 'mid':
        employees = employees.filter(Q(experience='3-5') | Q(experience='5'))
    elif experience_filter == 'senior':
        employees = employees.filter(Q(experience='5-10') | Q(experience='10+') | Q(experience__iregex=r'^[6-9]$'))

    employer_interest_ids = set(
        EmployerInterest.objects.filter(employer=employer).values_list('employee_id', flat=True)
    )

    if interested_filter == 'saved':
        employees = employees.filter(id__in=employer_interest_ids)

    employees = employees.distinct()

    candidate_cards = []
    for emp in employees:
        profile_checks = [
            bool(emp.resume),
            bool(emp.role),
            bool(emp.qualification),
            bool(emp.experience),
            bool(emp.location),
            bool(emp.skills.exists()),
        ]
        profile_score = int((sum(profile_checks) / len(profile_checks)) * 100)
        is_verified_profile = profile_score >= 80 and not emp.is_placed

        if verified_filter == '1' and not is_verified_profile:
            continue

        skill_names = list(emp.skills.values_list('name', flat=True))
        match_notes = []
        if employer.industry and employer.industry.lower() in (emp.role or '').lower():
            match_notes.append('Industry aligned')
        if skill_names:
            match_notes.append(f"{len(skill_names)} skill{'s' if len(skill_names) != 1 else ''} listed")
        if emp.location and employer.location and emp.location.lower() == employer.location.lower():
            match_notes.append('Local profile')
        if not match_notes:
            match_notes.append('Finance candidate')

        candidate_cards.append({
            'employee': emp,
            'profile_score': profile_score,
            'is_verified_profile': is_verified_profile,
            'match_note': match_notes[0],
            'skill_names': skill_names[:4],
            'is_saved': emp.id in employer_interest_ids,
        })

    candidate_cards.sort(
        key=lambda item: (
            not item['is_saved'],
            not item['is_verified_profile'],
            -item['profile_score'],
            -item['employee'].created_at.timestamp(),
        )
    )

    # Paginate results (20 per page)
    paginator = Paginator(candidate_cards, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    owned_jobs = list(
        JobOpening.objects.filter(employer=employer)
        .annotate(employee_interest_count=Count('employee_interests'))
        .order_by('-created_at')
    )

    employee_interest_feed = list(
        EmployeeInterest.objects.filter(job__employer=employer)
        .select_related('employee', 'job')
        .order_by('-created_at')[:8]
    )

    total_candidates = Registration.objects.count()
    verified_candidates = sum(1 for card in candidate_cards if card['is_verified_profile'])
    active_jobs_count = sum(1 for job in owned_jobs if job.is_active)

    return render(request, 'base/employer_dashboard.html', {
        'employer': employer,
        'candidate_cards': page_obj,
        'interested_ids': employer_interest_ids,
        'search_q': search_query,
        'search_skill': skill_query,
        'availability_filter': availability_filter,
        'experience_filter': experience_filter,
        'interest_scope': interested_filter,
        'verified_filter': verified_filter,
        'owned_jobs': owned_jobs,
        'employee_interest_feed': employee_interest_feed,
        'total_candidates': total_candidates,
        'verified_candidates': verified_candidates,
        'active_jobs_count': active_jobs_count,
    })


@rate_limit(max_requests=30, time_window=60, block_duration=120)
@login_required
def express_interest(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    if request.user.role != 'employer':
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    employer_id = request.user.profile_id
    employee_id = request.POST.get('employee_id')

    if not employee_id:
        return JsonResponse({'error': 'Missing employee_id'}, status=400)

    try:
        employee_id = int(employee_id)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid employee_id'}, status=400)

    try:
        employer = Employer.objects.get(id=employer_id)
        employee = Registration.objects.get(id=employee_id)
    except (Employer.DoesNotExist, Registration.DoesNotExist):
        return JsonResponse({'error': 'Not found'}, status=404)

    interest, created = EmployerInterest.objects.get_or_create(employer=employer, employee=employee)

    if not created:
        interest.delete()
        return JsonResponse({'status': 'removed'})

    return JsonResponse({'status': 'added'})


@login_required
def employee_express_interest(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    if request.user.role != 'employee':
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    employee_id = request.user.profile_id
    job_id = request.POST.get('job_id')

    if not job_id:
        return JsonResponse({'error': 'Missing job_id'}, status=400)

    try:
        job_id = int(job_id)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid job_id'}, status=400)

    try:
        employee = Registration.objects.get(id=employee_id)
        job = JobOpening.objects.get(id=job_id)
    except (Registration.DoesNotExist, JobOpening.DoesNotExist):
        return JsonResponse({'error': 'Not found'}, status=404)

    interest, created = EmployeeInterest.objects.get_or_create(employee=employee, job=job)

    if not created:
        interest.delete()
        return JsonResponse({'status': 'removed'})

    return JsonResponse({'status': 'added'})
