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

### Environment Variables
Create `.env` file in `acco/` directory with:
```
STRIPE_PUBLIC_KEY=<your_stripe_public_key>
STRIPE_SECRET_KEY=<your_stripe_secret_key>
```

### Common Commands

**Activate virtual environment and run server:**
```bash
source env/bin/activate
python manage.py runserver 8080
```

**Database migrations:**
```bash
source env/bin/activate
python manage.py makemigrations
python manage.py migrate
```

**Create superuser for admin access:**
```bash
source env/bin/activate
python manage.py createsuperuser
```

**Collect static files:**
```bash
source env/bin/activate
python manage.py collectstatic
```

**Fix plaintext passwords (custom management command):**
```bash
source env/bin/activate
python manage.py fix_passwords
```

## Architecture

### Project Structure
- **acco/** - Django project configuration (settings, root URLs, WSGI/ASGI config)
- **base/** - Main Django app containing all business logic
  - Models: Registration (employees), Employer, JobOpening, Contact
  - Views: Registration flow, authentication, dashboards, Stripe checkout
  - Templates: All HTML files for the application
  - Static files: CSS, JS, images
  - Custom management commands in `management/commands/`

### Key Design Decisions

**Custom Authentication System:**
- Does NOT use Django's built-in `auth.User` model
- Two separate user types: `Registration` (employees) and `Employer` models
- Both models store hashed passwords directly in their tables
- Password hashing is automatic via model `save()` method override
- Authentication uses `check_password()` from Django's hashers
- Sessions managed via Django's session framework

**Password Handling:**
- Models auto-hash plaintext passwords on save if not already hashed (checks for `pbkdf2_sha256$` prefix)
- Custom management command `fix_passwords` available to migrate existing plaintext passwords
- Password field max length: 128 characters (standard for hashed passwords)

**Stripe Integration:**
- Employees select subscription plans during registration (basic/intermediate/premium)
- Checkout session created with `/create-checkout-session/` endpoint
- Success URL redirects to `/register/temp-save/` after payment
- Temporary data saved in session before payment, finalized after successful checkout

**Media Files:**
- Employee resumes stored in `media/resumes/`
- Employee photos in `media/employee_photos/`
- Employer logos in `media/employer_logos/`
- MEDIA_ROOT set to `media/` directory

### Database Configuration
- Engine: MySQL
- Database name: `emp`
- Default credentials: user=`accoplacers`, password=`accoplacers`
- Host: `localhost:3306`
- Timezone: Asia/Dubai

### URL Routing Structure
Main routes defined in `base/urls.py`:
- `/` - Employee registration/landing page
- `/employee/login/` - Employee login
- `/employee/dashboard/` - Employee dashboard
- `/employer/register/` - Employer registration
- `/employer/login/` - Employer login
- `/employer/dashboard/` - Employer dashboard with job posting
- `/admin/` - Django admin interface
- `/contact/` - Contact form
- `/create-checkout-session/` - Stripe payment initiation

### Important Model Fields

**Registration (Employee):**
- Auto-incrementing ID (primary key)
- Email must be unique
- Password field is nullable (for users who haven't set passwords yet)
- Plan choices: 'basic', 'intermediate', 'premium'
- Skills stored as comma-separated text

**Employer:**
- Auto-incrementing ID (primary key)
- Email must be unique
- Related to JobOpening via foreign key
- Password field is required

**JobOpening:**
- Foreign key to Employer with CASCADE delete
- `is_active` boolean to control visibility
- No direct employee application tracking (may be future enhancement)

## Testing

The project uses Django's test framework. Run tests with:
```bash
source env/bin/activate
python manage.py test base
```

Currently `base/tests.py` contains minimal test coverage.

## Deployment Notes

- Static files collected to `staticfiles/` directory
- ALLOWED_HOSTS configured for: 127.0.0.1, accoplacers.com, www.accoplacers.com, 35.154.23.157
- DEBUG mode is currently ON - must be disabled for production
- SECRET_KEY is hardcoded - should use environment variable in production
- Media files served via Django in development, should use dedicated storage in production
