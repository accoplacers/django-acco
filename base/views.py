from django.shortcuts import render, HttpResponse, redirect
from django.http import JsonResponse
from .models import Registration, Contact
from django.conf import settings
from django.core.files import File
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout as django_logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.hashers import make_password, check_password
from django.views.decorators.cache import never_cache
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Registration, Contact, Employer, JobOpening, EmployerInterest, EmployeeInterest, UserAccount, ContactEvent
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




def registration_view(request):
    user = request.user if request.user.is_authenticated else None
    context = {
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
            try:
                tmp_path = os.path.join(tmp_dir, os.path.basename(resume.name))
                with open(tmp_path, 'wb+') as f:
                    for chunk in resume.chunks():
                        f.write(chunk)
                data['resume'] = tmp_path
            except OSError as e:
                logger.error(f"Failed to save temp resume for {email}: {e}")
                return JsonResponse({'status': 'error', 'message': 'Failed to save resume. Please try again.'}, status=500)

        # Save photo temporarily
        photo = request.FILES.get('photo')
        if photo:
            try:
                photo_tmp_path = os.path.join(tmp_dir, os.path.basename(photo.name))
                with open(photo_tmp_path, 'wb+') as f:
                    for chunk in photo.chunks():
                        f.write(chunk)
                data['photo'] = photo_tmp_path
            except OSError as e:
                logger.error(f"Failed to save temp photo for {email}: {e}")
                if 'resume' in data and os.path.exists(data['resume']):
                    os.remove(data['resume'])
                return JsonResponse({'status': 'error', 'message': 'Failed to save photo. Please try again.'}, status=500)

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
        if any(token in message for token in ['resume', 'photo']):
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
                raise ValidationError("Password must be at least 6 characters long (server-side check).")
            if len(password) > 128:
                raise ValidationError("Password is too long.")
            if password != confirm_password:
                raise ValidationError("Passwords do not match.")
            validate_password(password)
            if plan not in ['basic', 'intermediate', 'premium']:
                plan = 'basic'
            if not resume:
                raise ValidationError("Please upload your resume.")
            if resume.size > 5 * 1024 * 1024:
                raise ValidationError("Resume file size must not exceed 5 MB.")

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

            except TimeoutError:
                # LLM timed out — registration is saved, skills will be parsed later.
                # Do NOT roll back the transaction.
                logger.warning(f"Resume parse timed out for {email}. Flagging for deferred processing.")
                request.session['resume_parse_pending'] = True
            except Exception as e:
                # Any other AI failure must not roll back the registration.
                logger.error(f"AI Ingestion Failed for {email}: {str(e)}")

            # Create auth user
            user_account = UserAccount.objects.create(
                email=email,
                password=make_password(password),
                role='employee',
                profile_id=registration.id
            )

        user_account.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user_account)
        messages.success(request, "Welcome to Accoplacers! Your profile is now live.")
        return redirect('employee_dashboard')

    return render_employee_register()


def terms(request):
    return render(request, 'base/terms.html')



# DASHBOARD



@staff_member_required
@never_cache
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

@rate_limit(max_requests=5, time_window=60, block_duration=300)
@never_cache
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
@rate_limit(max_requests=30, time_window=60, block_duration=120)
@never_cache
def employee_dashboard(request):
    if request.user.role != 'employee':
        messages.error(request, "Unauthorized access.")
        return redirect('registration_view')
    
    employee_id = request.user.profile_id
    try:
        employee = Registration.objects.prefetch_related('skills').get(id=employee_id)
    except Registration.DoesNotExist:
        messages.error(request, "Profile not found.")
        return redirect('registration_view')

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
    job_openings = JobOpening.objects.filter(is_active=True).select_related('employer').order_by('-created_at')

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

    from django.urls import reverse
    profile_url = reverse('employee_profile')

    next_steps = []
    if not employee_skill_set:
        next_steps.append({
            'title': 'Add your core skills',
            'detail': 'Include systems, certifications, and finance tools so matching is more precise.',
            'action': 'Update skills below',
            'action_url': f'{profile_url}#skills',
        })
    if not interested_job_ids:
        next_steps.append({
            'title': 'Save your first opportunity',
            'detail': 'Mark roles as interested so the team can see where you want to be introduced.',
            'action': "Review today's openings",
            'action_url': '#jobs-section',
        })
    if profile_completion < 100:
        next_steps.append({
            'title': 'Complete your profile',
            'detail': f'Your profile is {profile_completion}% complete. A more complete profile is easier to shortlist.',
            'action': 'Review profile signals',
            'action_url': profile_url,
        })

    if not next_steps:
        next_steps.append({
            'title': 'Keep momentum',
            'detail': 'Your profile is in good shape. Stay active by reviewing new openings and updating skills as they grow.',
            'action': 'Check new roles weekly',
            'action_url': '#jobs-section',
        })

    try:
        app_status = employee.application_status
    except Exception:
        app_status = None

    return render(request, 'base/employee_dashboard.html', {
        'employee': employee,
        'job_cards': job_cards,
        'interested_job_ids': interested_job_ids,
        'profile_completion': profile_completion,
        'recommended_count': recommended_count,
        'skills_count': len(employee_skills),
        'next_steps': next_steps,
        'suggested_skills': suggested_skills,
        'app_status': app_status,
    })



@login_required(login_url='employee_login')
def employee_profile(request):
    if request.user.role != 'employee':
        messages.error(request, "Unauthorized access.")
        return redirect('registration_view')

    employee_id = request.user.profile_id
    try:
        employee = Registration.objects.prefetch_related('skills').get(id=employee_id)
    except Registration.DoesNotExist:
        return redirect('employee_login')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_profile':
            full_name = request.POST.get('full_name', '').strip()
            phone = request.POST.get('phone', '').strip()
            location = request.POST.get('location', '').strip()
            role = request.POST.get('role', '').strip()
            experience = request.POST.get('experience', '').strip()
            skills_raw = request.POST.get('skills', '').strip()

            if full_name:
                employee.name = full_name
            if phone:
                employee.phone = phone
            if location:
                employee.location = location
            if role:
                employee.role = role
            if experience:
                employee.experience = experience

            skill_names = [s.strip() for s in skills_raw.split(',') if s.strip()]
            skill_objs = []
            for name in skill_names:
                obj, _ = Skill.objects.get_or_create(name=name)
                skill_objs.append(obj)
            employee.skills.set(skill_objs)

            employee.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('employee_profile')

        elif action == 'upload_resume':
            import os as _os
            resume_file = request.FILES.get('resume')
            if not resume_file:
                messages.error(request, "No file selected.")
            else:
                allowed_extensions = {'.pdf', '.doc', '.docx'}
                file_ext = _os.path.splitext(resume_file.name)[1].lower()
                if file_ext not in allowed_extensions:
                    messages.error(request, "Invalid file type. Accepted: PDF, DOC, DOCX.")
                elif resume_file.size > 5 * 1024 * 1024:
                    messages.error(request, "File too large. Maximum size is 5 MB.")
                else:
                    employee.resume = resume_file
                    employee.save()
                    messages.success(request, "Resume updated successfully.")
            return redirect('employee_profile')

    employee_skills = list(employee.skills.all())
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
        bool(employee_skills),
    ]
    profile_completion = int((sum(profile_checks) / len(profile_checks)) * 100)

    return render(request, 'base/employee_profile.html', {
        'employee': employee,
        'employee_skills': employee_skills,
        'profile_completion': profile_completion,
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
        contact_name = request.POST.get('contact_name', '').strip()
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
            'contact_name': contact_name,
            'email': email,
            'phone': phone,
            'company_description': company_description,
            'location': location,
            'industry': industry,
        }

        try:
            # Validate all inputs
            validate_company_name(company_name)
            validate_text_input(contact_name, min_length=2, max_length=100)
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

        # Check if email already exists in UserAccount (Critical Bug Fix 006-H)
        if UserAccount.objects.filter(email=email).exists():
            error_message = "An account with this email already exists."
            messages.error(request, error_message)
            return render_employer_register(form_data, get_initial_section(error_message))

        # Create employer and user atomically
        with transaction.atomic():
            employer = Employer.objects.create(
                company_name=company_name,
                contact_name=contact_name,
                email=email,
                phone=phone,
                company_description=company_description,
                location=location,
                industry=industry,
                logo=logo
            )

            # Create auth user
            user = UserAccount.objects.create_user(
                email=email,
                password=password,
                role='employer',
                profile_id=employer.id
            )

        # Auto-login the user (Smoke B fix)
        login(request, user)

        messages.success(request, "Registration successful!")
        return redirect('employer_dashboard')

    return render_employer_register()


@rate_limit(max_requests=5, time_window=60, block_duration=300)
@never_cache
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


@staff_member_required
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
@never_cache
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

    # Base queryset — prefetch skills to avoid N+1 in the candidate card loop
    employees = Registration.objects.prefetch_related('skills').order_by('-created_at')

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

    # ORM annotations — compute profile field presence and sort signals at DB level,
    # preventing O(N) Python iteration over the full candidate table.
    from django.db.models import Case, When, Value, IntegerField, BooleanField, Exists, OuterRef, F

    _SkillM2M = Registration.skills.through  # auto through table: registration_id, skill_id

    employees = employees.annotate(
        f_resume=Case(When(resume__isnull=False, then=Value(1)), default=Value(0), output_field=IntegerField()),
        f_role=Case(When(~Q(role=''), then=Value(1)), default=Value(0), output_field=IntegerField()),
        f_qual=Case(When(~Q(qualification=''), then=Value(1)), default=Value(0), output_field=IntegerField()),
        f_exp=Case(When(~Q(experience=''), then=Value(1)), default=Value(0), output_field=IntegerField()),
        f_loc=Case(When(~Q(location=''), then=Value(1)), default=Value(0), output_field=IntegerField()),
        f_skills=Case(
            When(Exists(_SkillM2M.objects.filter(registration_id=OuterRef('pk'))), then=Value(1)),
            default=Value(0), output_field=IntegerField()
        ),
        is_saved_ann=Case(
            When(id__in=employer_interest_ids, then=Value(True)),
            default=Value(False), output_field=BooleanField()
        ),
    ).annotate(
        field_score=F('f_resume') + F('f_role') + F('f_qual') + F('f_exp') + F('f_loc') + F('f_skills'),
    ).annotate(
        is_verified_ann=Case(
            When(field_score__gte=5, is_placed=False, then=Value(True)),
            default=Value(False), output_field=BooleanField()
        ),
    )

    if verified_filter == '1':
        employees = employees.filter(is_verified_ann=True)

    employees = employees.order_by(
        '-is_saved_ann',
        '-is_verified_ann',
        '-field_score',
        '-created_at',
    )

    total_candidates = Registration.objects.count()
    verified_candidates = employees.filter(is_verified_ann=True).count()

    # Paginate the QuerySet — avoids loading all rows into memory
    paginator = Paginator(employees, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Build card dicts for the current page only (≤20 rows)
    _card_dicts = []
    for emp in page_obj:
        emp_skills = list(emp.skills.all())  # uses prefetch cache — no extra DB hit
        skill_names = [s.name for s in emp_skills]
        profile_score = int((emp.field_score / 6) * 100)

        match_notes = []
        if employer.industry and employer.industry.lower() in (emp.role or '').lower():
            match_notes.append('Industry aligned')
        if skill_names:
            match_notes.append(f"{len(skill_names)} skill{'s' if len(skill_names) != 1 else ''} listed")
        if emp.location and employer.location and emp.location.lower() == employer.location.lower():
            match_notes.append('Local profile')
        if not match_notes:
            match_notes.append('Finance candidate')

        _card_dicts.append({
            'employee': emp,
            'profile_score': profile_score,
            'is_verified_profile': emp.is_verified_ann,
            'match_note': match_notes[0],
            'skill_names': skill_names[:4],
            'is_saved': emp.is_saved_ann,
        })

    # Thin wrapper: preserves page_obj.paginator for the template's
    # candidate_cards.paginator.count tag while iterating over card dicts.
    class _CardPage:
        def __init__(self, page, cards):
            self.paginator = page.paginator
            self._cards = cards
        def __iter__(self): return iter(self._cards)
        def __bool__(self): return bool(self._cards)
        def __len__(self): return len(self._cards)

    candidate_cards = _CardPage(page_obj, _card_dicts)

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

    active_jobs_count = sum(1 for job in owned_jobs if job.is_active)

    return render(request, 'base/employer_dashboard.html', {
        'employer': employer,
        'candidate_cards': candidate_cards,
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
        'subscription_tier': employer.subscription_tier,
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


def custom_404(request, exception):
    return render(request, '404.html', status=404)


def custom_500(request):
    return render(request, '500.html', status=500)


def job_detail(request, pk):
    job = JobOpening.objects.get(pk=pk)
    
    # Markdown Interception for AI Agents (AIO Pivot)
    if request.GET.get('format') == 'md':
        from django.http import HttpResponse
        content = f"""# {job.title}
## Company: {job.employer.company_name}
## Location: {job.location} | Type: {job.job_type}

### Description
{job.description}

### Requirements
{job.requirements}

---
Apply via AccoPlacers: {request.build_absolute_uri(job.get_absolute_url())}
"""
        return HttpResponse(content, content_type='text/markdown; charset=utf-8')
        
    return render(request, 'base/job_detail.html', {'job': job})


@login_required
def log_whatsapp_contact(request, candidate_id):
    from django.http import HttpResponseForbidden
    is_staff = request.user.is_staff or request.user.is_superuser
    is_active_employer = (
        request.user.role == 'employer' and
        Employer.objects.filter(id=request.user.profile_id, is_active=True).exists()
    )
    if not (is_staff or is_active_employer):
        return HttpResponseForbidden("Access denied.")

    try:
        candidate = Registration.objects.get(pk=candidate_id)
    except Registration.DoesNotExist:
        from django.http import Http404
        raise Http404("Candidate not found.")

    employer = None
    if request.user.role == 'employer':
        try:
            employer = Employer.objects.get(id=request.user.profile_id)
        except Employer.DoesNotExist:
            pass

    ContactEvent.objects.create(
        employer=employer,
        candidate=candidate,
        contact_type='whatsapp',
    )

    whatsapp_url = f"https://wa.me/{candidate.phone}"
    return redirect(whatsapp_url)


_ANALYTICS_CACHE_KEY = 'admin_analytics_v1'
_ANALYTICS_CACHE_TTL = 300  # 5 minutes


@staff_member_required
def admin_analytics_view(request):
    from django.core.cache import cache
    from django.db.models import Count, Avg, Q
    from django.utils import timezone
    from datetime import timedelta

    context = cache.get(_ANALYTICS_CACHE_KEY)
    if context is not None:
        return render(request, 'base/admin_analytics.html', context)

    now = timezone.now()
    days_7 = now - timedelta(days=7)
    days_30 = now - timedelta(days=30)
    days_90 = now - timedelta(days=90)

    # Sales Dashboard
    total_active_employers = Employer.objects.filter(is_active=True).count()
    new_employers_7 = Employer.objects.filter(created_at__gte=days_7).count()
    new_employers_30 = Employer.objects.filter(created_at__gte=days_30).count()
    new_employers_90 = Employer.objects.filter(created_at__gte=days_90).count()

    tier_counts = Employer.objects.values('subscription_tier').annotate(count=Count('id'))
    tier_breakdown = []
    total_tiers = sum(t['count'] for t in tier_counts) or 1
    for t in tier_counts:
        tier_breakdown.append({
            'label': t['subscription_tier'].capitalize(),
            'count': t['count'],
            'width_pct': (t['count'] / total_tiers) * 100
        })

    # Acquisition Dashboard
    total_candidates = Registration.objects.count()
    new_candidates_7 = Registration.objects.filter(created_at__gte=days_7).count()
    new_candidates_30 = Registration.objects.filter(created_at__gte=days_30).count()
    new_candidates_90 = Registration.objects.filter(created_at__gte=days_90).count()

    top_locations = Registration.objects.values('location').annotate(count=Count('id')).order_by('-count')[:5]
    top_locations_list = [{'label': l['location'], 'count': l['count']} for l in top_locations]

    top_roles = Registration.objects.values('role').annotate(count=Count('id')).order_by('-count')[:5]
    top_roles_list = [{'label': r['role'], 'count': r['count']} for r in top_roles]

    # Engagement Dashboard
    active_jobs = JobOpening.objects.filter(is_active=True).count()
    avg_exp = Registration.objects.aggregate(Avg('years_of_experience'))['years_of_experience__avg'] or 0

    # Success Dashboard
    total_contacts = ContactEvent.objects.count()
    top_contacted = ContactEvent.objects.values('candidate__name').annotate(contact_count=Count('id')).order_by('-contact_count')[:5]
    top_contacted_list = [{'candidate_name': c['candidate__name'], 'contact_count': c['contact_count']} for c in top_contacted]

    # Operations Dashboard — evaluate QuerySet before caching
    pending_review = list(Registration.objects.order_by('-created_at')[:10])

    context = {
        'page_title': 'Intelligence Terminal',
        'sales_dashboard': {
            'total_active_employers': total_active_employers,
            'new_employers_7_days': new_employers_7,
            'new_employers_30_days': new_employers_30,
            'new_employers_90_days': new_employers_90,
            'tier_breakdown': tier_breakdown,
            'tier_upgrade_rate': 12.5,
        },
        'acquisition_dashboard': {
            'total_candidate_registrations': total_candidates,
            'new_candidates_7_days': new_candidates_7,
            'new_candidates_30_days': new_candidates_30,
            'new_candidates_90_days': new_candidates_90,
            'top_candidate_locations': top_locations_list,
            'top_candidate_roles': top_roles_list,
        },
        'engagement_dashboard': {
            'total_active_job_postings': active_jobs,
            'average_years_experience': round(avg_exp, 1),
        },
        'success_dashboard': {
            'total_contact_events': total_contacts,
            'top_contacted_candidates': top_contacted_list,
            'verified_candidate_rate': (Registration.objects.filter(profile_score__gte=70).count() / (total_candidates or 1)) * 100,
        },
        'operations_dashboard': {
            'pending_admin_review': pending_review,
            'candidates_without_resume': Registration.objects.filter(Q(resume='') | Q(resume=None)).count(),
            'candidates_without_skills': Registration.objects.annotate(skill_count=Count('skills')).filter(skill_count=0).count(),
            'stale_job_postings': JobOpening.objects.filter(is_active=True, created_at__lt=now - timedelta(days=60)).count(),
        },
    }
    cache.set(_ANALYTICS_CACHE_KEY, context, _ANALYTICS_CACHE_TTL)
    return render(request, 'base/admin_analytics.html', context)


@login_required(login_url='employee_login')
@never_cache
def employee_profile(request):
    if request.user.role != 'employee':
        messages.error(request, "Unauthorized access.")
        return redirect('registration_view')
        
    employee_id = request.user.profile_id
    try:
        employee = Registration.objects.get(id=employee_id)
    except Registration.DoesNotExist:
        messages.error(request, "Profile not found.")
        return redirect('registration_view')

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_profile':
            employee.name = request.POST.get('name', employee.name)
            employee.phone = request.POST.get('phone', employee.phone)
            employee.nationality = request.POST.get('nationality', employee.nationality)
            employee.location = request.POST.get('location', employee.location)
            employee.role = request.POST.get('role', employee.role)
            employee.experience = request.POST.get('experience', employee.experience)
            employee.qualification = request.POST.get('qualification', employee.qualification)
            employee.save()
            messages.success(request, "Profile updated successfully.")
            
        elif action == 'update_resume':
            resume = request.FILES.get('resume')
            if resume:
                # Security check for file type
                ext = os.path.splitext(resume.name)[1].lower()
                if ext not in ['.pdf', '.doc', '.docx']:
                    messages.error(request, "Invalid file type. Only PDF, DOC, and DOCX are accepted.")
                elif resume.size > 5 * 1024 * 1024:
                    messages.error(request, "File size too large (max 5MB).")
                else:
                    # Replace old resume file if it exists
                    if employee.resume:
                        try:
                            if os.path.isfile(employee.resume.path):
                                os.remove(employee.resume.path)
                        except:
                            pass
                    
                    employee.resume.save(resume.name, resume)
                    messages.success(request, "Resume replaced successfully.")
            else:
                messages.error(request, "No file selected.")

        return redirect('employee_profile')

    return render(request, 'base/employee_profile.html', {'employee': employee})

@login_required
def delete_job_api(request, job_id):
    if request.method != 'POST':
        from django.http import JsonResponse
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    if request.user.role != 'employer':
        from django.http import JsonResponse
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    try:
        from django.http import JsonResponse
        employer = Employer.objects.get(id=request.user.profile_id)
        deleted, _ = JobOpening.objects.filter(id=job_id, employer=employer).delete()
        if deleted:
            return JsonResponse({'status': 'success'})
        return JsonResponse({'error': 'Job not found or unauthorized'}, status=404)
    except Exception as e:
        from django.http import JsonResponse
        return JsonResponse({'error': str(e)}, status=500)
