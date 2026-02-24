# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Django-based job placement platform called "Acco Placers" that connects employees with employers. It features:
- Employee registration with tiered subscription plans (basic, intermediate, premium) via Stripe
- Employer registration and job posting capabilities
- Custom authentication system for both employees and employers (not using Django's built-in User model)
- MySQL database backend

## Development Setup

### Prerequisites
- Python 3.12
- MySQL server running locally
- Virtual environment in `env/`

### Install dependencies
```bash
source env/bin/activate
pip install -r req.txt
```

### Environment Variables
Create `.env` file in `acco/` directory with:
```
STRIPE_PUBLIC_KEY=<your_stripe_public_key>
STRIPE_SECRET_KEY=<your_stripe_secret_key>
```

### Common Commands

```bash
# Run development server
source env/bin/activate && python manage.py runserver 8080

# Database migrations
python manage.py makemigrations && python manage.py migrate

# Run tests
python manage.py test base

# Collect static files
python manage.py collectstatic
```

### Custom Management Commands

```bash
# Hash any plaintext passwords still in the database
python manage.py fix_passwords

# Scan and remove malicious/SQL-injected data
python manage.py cleanup_all_malicious_data          # all tables
python manage.py cleanup_all_malicious_data --dry-run # preview without deleting
python manage.py cleanup_malicious_employers
python manage.py cleanup_malicious_contacts
```

## Architecture

### Project Structure
- **acco/** - Django project configuration (settings, root URLs, WSGI/ASGI config)
- **base/** - Main Django app containing all business logic
  - `models.py` - Registration (employees), Employer, JobOpening, Contact
  - `views.py` - Registration flow, authentication, dashboards, Stripe checkout
  - `validators.py` - Input validation including SQL injection pattern detection
  - `decorators.py` - IP-based rate limiting decorator (`@rate_limit`)
  - `admin.py` - Django admin config with custom list displays and bulk actions
  - `management/commands/` - Custom management commands
  - `templates/base/` - All HTML templates
  - `static/base/` - CSS, JS, images

### Key Design Decisions

**Custom Authentication System:**
- Does NOT use Django's built-in `auth.User` model
- Two separate user types: `Registration` (employees) and `Employer` models
- Both models store hashed passwords directly in their tables
- Password hashing is automatic via model `save()` method override (checks for `pbkdf2_sha256$` prefix)
- Authentication uses `check_password()` from Django's hashers
- Sessions managed via Django's session framework

**Stripe Registration Flow:**
- Employee fills form → data saved to session via `/register/temp-save/` (rate limited)
- Stripe checkout session created at `/create-checkout-session/` (@csrf_exempt)
- After successful payment, Stripe redirects to `/register/success/` which reads session and saves to DB
- Temporary uploaded files stored in `media/tmp/` during this flow

**Security Middleware:**
- `validators.py` validates all user inputs against SQL injection patterns, length limits, and format rules
- `@rate_limit` decorator: 5 requests per 60 seconds per IP, 5-minute block on violation (returns HTTP 429)
- Applied to: `temp_save_registration`, `employee_register`, `employer_register`, `contact_user`
- File upload limits: 10 MB per file, 15 MB total request

**Media Files:**
- Employee resumes in `media/resumes/`
- Employee photos in `media/employee_photos/`
- Employer logos in `media/employer_logos/`
- Temporary files during checkout in `media/tmp/`

### Database Configuration
- Engine: MySQL, database name: `emp`
- Credentials: user=`accoplacers`, password=`accoplacers`, host: `localhost:3306`
- Timezone: Asia/Dubai

### URL Routing Structure
All routes defined in `base/urls.py`:

| URL | View | Notes |
|-----|------|-------|
| `/` | `registration_view` | Landing page |
| `/contact/` | `contact_user` | Rate limited |
| `/create-checkout-session/` | `create_checkout_session` | CSRF exempt |
| `/register/temp-save/` | `temp_save_registration` | Rate limited |
| `/register/success/` | `registration_success` | Stripe redirect target |
| `/employee/register/` | `employee_register` | Rate limited |
| `/employee/login/` | `employee_login` | |
| `/employee/logout/` | `employee_logout` | |
| `/employee/dashboard/` | `employee_dashboard` | |
| `/employer/register/` | `employer_register` | Rate limited |
| `/employer/login/` | `employer_login` | |
| `/employer/logout/` | `employer_logout` | |
| `/employer/dashboard/` | `employer_dashboard` | |
| `/dashboard/` | `registrations_dashboard` | Requires Django session login |
| `/dashboard/toggle-placed/` | `toggle_placed` | Requires Django session login |
| `/terms/` | `terms` | |
| `/admin/` | Django admin | Separate from `/dashboard/` |

### Important Model Fields

**Registration (Employee):**
- `email` (unique), `password` (nullable), `plan` (basic/intermediate/premium)
- `skills` (comma-separated text), `is_placed` (boolean), `resume`, `photo`
- `role`, `experience`, `qualification`, `nationality`, `location`

**Employer:**
- `email` (unique), `password` (required), `company_name`, `industry`, `logo`
- Related JobOpenings via FK (CASCADE delete)

**JobOpening:**
- FK to Employer (CASCADE delete), `is_active` boolean controls visibility
- `title`, `description`, `requirements`, `salary_range`, `location`, `job_type`

## Testing

```bash
source env/bin/activate
python manage.py test base
```

`base/tests.py` currently has minimal coverage.

## Deployment Notes

- `DEBUG = False` in `settings.py` (production setting)
- `ALLOWED_HOSTS`: 127.0.0.1, accoplacers.com, www.accoplacers.com, 35.154.23.157
- `SECRET_KEY` is hardcoded — should be moved to environment variable
- Static files collected to `staticfiles/`
- Media files served by Django — should use dedicated object storage in production
- See `SECURITY_FIXES.md` for prior security audit findings
