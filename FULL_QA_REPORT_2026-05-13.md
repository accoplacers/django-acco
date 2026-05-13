# Full QA Report

Date: 2026-05-13
Scope: current working tree of the Accoplacers Django app.

## Verdict

The current build passes the tested launch-stabilization QA scope. The earlier "Fix First" blockers are now verified as fixed in automated tests and browser checks.

This does not mean the product is production-complete. It means the current critical flows are stable enough to continue into the next hardening/design phase.

## Checks Run

### Django Test Suite

Command:

`.\env\Scripts\python.exe manage.py test base`

Result:

- 17 tests run
- 17 passed
- 0 failed
- 0 errors

### Migration Health

Command:

`.\env\Scripts\python.exe manage.py makemigrations --check --dry-run`

Result:

- No model migration changes detected

Command:

`.\env\Scripts\python.exe manage.py showmigrations base`

Result:

- Base migrations applied through `0028_employer_contact_name`

### Deployment Check

Command:

`DEBUG=False .\env\Scripts\python.exe manage.py check --deploy`

Result:

- No deployment check issues reported

### Python Compile Check

Files compiled:

- `base/views.py`
- `base/models.py`
- `base/urls.py`
- `acco/settings.py`
- `acco/urls.py`

Result:

- No syntax errors

### Template Load Check

Critical templates loaded successfully:

- `base/index.html`
- `base/employee_register.html`
- `base/employer_register.html`
- `base/employee_login.html`
- `base/employer_login.html`
- `base/password_reset_form.html`
- `base/password_reset_done.html`
- `base/password_reset_confirm.html`
- `base/password_reset_complete.html`
- `base/employer_dashboard.html`
- `base/employee_dashboard.html`
- `base/job_detail.html`
- `base/admin_analytics.html`

Result:

- 13 templates loaded successfully

### Black-Box Flow QA

Temporary QA script:

`C:\tmp\acco_full_qa.py`

Result:

- 29 checks run
- 29 passed
- 0 failed

Covered:

- Public routes load
- Protected routes redirect unauthenticated users
- Candidate invalid login shows error
- Employer invalid login shows error
- Employer valid login reaches dashboard
- Candidate short password is rejected
- Candidate registration succeeds with valid password
- Candidate auth user is created
- Resume enrichment persists parsed years, notice period, and skill category
- Candidate dashboard loads after registration
- Employer duplicate email is rejected
- Employer honeypot blocks bot submission
- Password reset redirects to done page
- Password reset email is generated

### Browser QA

Temporary local server:

`http://127.0.0.1:8090`

Temporary browser QA script:

`C:\tmp\acco_browser_qa.py`

Screenshots:

`C:\tmp\acco-browser-qa`

Result:

- 29 browser checks run
- 29 passed
- 0 failed

Covered in Chromium:

- Desktop route loads and titles
- Mobile route loads and titles
- Home
- Candidate registration
- Employer registration
- Candidate login
- Employer login
- Password reset
- Mobile menu opens
- Candidate skill input Enter key stays on step 2
- Candidate skill input creates skill chips
- No severe console errors
- No failed browser requests

### Resume Parser Dependencies

Command:

`.\env\Scripts\python.exe -c "import fitz, pdfplumber, openai, anthropic; print('parser-deps-ok')"`

Result:

- Parser dependencies import successfully after installing `req.txt`

PDF extraction smoke test:

`extract_text_from_pdf('valid_resume.pdf')`

Result:

- Extracted 452 characters

## Findings

### P2: Static Collection Duplicate Warnings

`collectstatic --dry-run --noinput` completed, but Django warned that duplicate static paths exist for many files under `base/css`, `base/js`, and `base/img`.

Likely cause: `base/static` is included through both the app static finder and `STATICFILES_DIRS`.

Risk:

- Usually not a runtime blocker, but it can hide the wrong version of a static asset during production collection.

Recommendation:

- Remove `BASE_DIR / "base" / "static"` from `STATICFILES_DIRS`, or move shared static assets outside the app package so each static path has only one source.

### P3: Placeholder `href="#"` Remain In Modal Action Buttons

Remaining placeholders:

- `base/templates/base/employee_dashboard.html`
- `base/templates/base/employer_dashboard.html`

These are WhatsApp/modal buttons populated dynamically by JavaScript. They are acceptable if JS always sets the final URL before use, but should be reviewed during manual dashboard QA.

### P3: Production Email Provider Still Needs Real SMTP/API Configuration

The password reset flow is implemented and tested with local in-memory/console email backends. Production still needs a real provider via `EMAIL_BACKEND` and related credentials.

### Coverage Limits

Not covered in this pass:

- Real SMTP delivery
- Real OpenAI/Anthropic API calls
- Payment/Stripe end-to-end flow
- S3/R2 private media behavior under `DEBUG=False`
- Cross-browser visual QA beyond Chromium
- Manual review of every dashboard modal state

## Launch-Stabilization Status

The previously listed "Fix First" items are verified:

- Stale test suite: fixed and passing
- Candidate registration Enter-key bug: fixed and browser verified
- Missing password reset: implemented and tested
- Resume parser dependency mismatch: fixed in `req.txt` and installed locally
- Password UI/backend mismatch: fixed to 10-character minimum

Recommended next phase:

1. Resolve static duplicate warnings.
2. Configure production email.
3. Verify private resume/media storage in production mode.
4. Run manual employer/candidate dashboard modal QA.
5. Begin premium visual redesign after the above hardening checks.
