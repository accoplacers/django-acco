# Accoplacers QA And Launch Readiness Report

Date: 2026-05-13
Scope: local Django app audit, public page crawl, registration/login checks, dashboard route checks, test-suite run, deployment-readiness review.

## Executive Summary

Accoplacers is functional enough for local demonstration, but it is not ready for production launch yet. The public site loads, the main routes return successfully, login failures behave cleanly, and protected dashboard pages redirect unauthenticated users to login. The architecture has also improved materially from earlier versions: authentication now uses `UserAccount`, candidate skills are normalized, employer dashboard data is paginated/filterable server-side, and security settings are much stronger than a first-pass Django app.

The current launch blockers are concentrated in a few areas: stale tests, a real candidate-registration UX bug, dependency drift around resume parsing, incomplete account recovery, production data hygiene, and a few security/privacy hardening gaps.

## What Was Verified

- Public pages loaded locally: home, employee registration, employer registration, employee login, employer login, terms, job detail pages, sitemap-style routes, robots, and llms.
- Protected employee/employer dashboard routes redirected unauthenticated users instead of exposing private data.
- Invalid login attempts showed user-facing errors instead of crashing.
- Registration form behavior was inspected across desktop and mobile screenshots.
- Mobile navigation was opened and visually checked.
- Synthetic QA records were used for dashboard inspection, then removed.
- Django migrations were checked in the prior run and were reported applied through `base.0028_employer_contact_name`.
- Fresh test run on 2026-05-13: `python manage.py test base` ran 15 tests: 5 passed, 1 failed, 9 errored.

QA screenshots from the prior run are stored at:

`C:\tmp\acco-qa`

## Release Blockers

### 1. Automated Test Suite Is Stale

Current result:

`15 tests run: 5 passed, 1 failed, 9 errored`

The dominant error is that tests still create `Registration` and `Employer` records with a `password` field, but passwords were moved into `UserAccount`.

Examples:

- `base/tests/test_employee_dashboard.py`
- `base/tests/test_employer_dashboard.py`
- `base/tests/test_employer_registration.py`

Risk: future changes cannot be trusted. This is the first thing to fix before serious production work because the app has no reliable regression net right now.

Recommended fix:

- Update all test factories/setup helpers to create `UserAccount` records linked to `Registration` or `Employer`.
- Add login helpers for employee, employer, and admin roles.
- Keep one test proving that legacy `password` fields no longer exist on profile models.

### 2. Candidate Registration Enter-Key Bug

Location:

- `base/templates/base/employee_register.html`

The skill input says users can press Enter to add skills. The skill input handler catches Enter, but the form-level Enter handler also advances the wizard. Result: pressing Enter to add the second skill can unexpectedly move the user from step 2 to step 3.

Relevant area:

- Skill key handling around `employee_register.html:444`
- Form-level Enter handling around `employee_register.html:590`

Risk: users may skip required profile review, feel the form is unstable, or submit incomplete data.

Recommended fix:

- In the form-level Enter handler, ignore events from `#skill-input`.
- Alternatively, call `event.stopPropagation()` in the skill input handler after adding a skill.
- Add a browser-level test for "Enter adds skill but stays on step 2".

### 3. Resume Parser Dependency Drift

Location:

- `base/services/resume_parser.py`
- `req.txt`

The resume parser references packages such as `fitz`, `pdfplumber`, `openai`, and `anthropic`, but the dependency file does not fully reflect the parser's runtime imports.

Risk: resume parsing or AI enrichment can fail in a fresh deployment even if local development happens to have packages installed.

Recommended fix:

- Decide whether the production parser uses PyMuPDF/fitz, pdfplumber, OpenAI, Anthropic, or a smaller subset.
- Add the exact packages and pinned versions to `req.txt`.
- Add a smoke test using the checked-in sample PDFs.

### 4. Password UX Does Not Match Server Validation

Server-side validation uses Django's `MinimumLengthValidator` with `min_length=10` in `acco/settings.py`.

The registration UI still communicates a shorter minimum in places.

Risk: users may choose a password that the UI appears to accept but the server rejects.

Recommended fix:

- Update all password help text to "at least 10 characters".
- Add client-side validation that mirrors the server minimum.
- Keep server validation as the source of truth.

### 5. Forgot Password Links Are Placeholders

Locations:

- `base/templates/base/employee_login.html`
- `base/templates/base/employer_login.html`

The "Forgot Password?" links currently point to `#`.

Risk: account recovery is a core production requirement. Without it, users who forget passwords must contact the business manually.

Recommended fix:

- Add Django password reset views/templates.
- Configure production email.
- Add tests for reset request, token flow, expired token, and successful password update.

## High Priority Before Launch

### Security And Privacy

- Add `Cache-Control: no-store` on authenticated dashboards and profile pages.
- Confirm production `SECURE_SSL_REDIRECT`, HSTS, secure cookies, CSRF cookie security, and session cookie security are enabled under `DEBUG=False`.
- Confirm uploaded resumes are private and not directly web-accessible through static/media paths.
- Confirm employers can only access candidate data intended for employer visibility.
- Add rate limiting to registration endpoints as well as login endpoints.
- Ensure PII-heavy admin screens are staff-only and audited.

### Admin And Operations

- Register `UserAccount` in Django admin with safe list/search fields.
- Add admin actions for deactivating suspicious users/employers.
- Add export controls carefully; exports should be permissioned and logged.
- Add monitoring for failed resume parse jobs, failed payments, and failed logins.

### Production Data Hygiene

The local database contains sample active jobs from test recruiters, and those jobs appear in public discovery surfaces.

Recommended fix:

- Create a staging/demo flag or separate seed data workflow.
- Before launch, clean production DB of fake jobs, synthetic candidates, and test employers.
- Add a management command or checklist for pre-launch data verification.

### Mobile UX

The mobile hamburger opens, but the menu visually overlaps awkwardly at the top.

Recommended fix:

- Give the mobile menu a stable top offset below the fixed header.
- Verify at 360px, 390px, 430px, 768px widths.
- Add screenshot checks for open/closed nav state.

### Scroll Reveal UX

Homepage reveal sections can appear blank in full-page screenshots until scrolled into view.

Recommended fix:

- Ensure reveal content has a non-JS fallback visible state.
- Respect `prefers-reduced-motion`.
- Avoid hiding content permanently if JS fails or IntersectionObserver behaves differently.

## Product Recommendations

### Candidate Side

- Make profile completeness honest and data-driven: resume uploaded, skills count, role selected, location, experience, notice period, and verification status.
- Add "save and continue later" for registration.
- Add resume parsing preview so candidates can correct extracted skills and experience.
- Add application status timeline: submitted, reviewed, shortlisted, contacted, placed.

### Employer Side

- Show employer subscription tier and limits clearly in the dashboard.
- Add upgrade CTA only where it maps to a real plan/feature.
- Add saved searches and candidate shortlists.
- Add notes per candidate for employer teams.
- Add job analytics: views, interested candidates, shortlists, contact events.

### Admin Side

- Add a moderation queue for new candidates and employers.
- Add suspicious activity views: duplicate emails/domains, repeated failed logins, honeypot hits, unusual uploads.
- Add business metrics: placements, active employers, active candidates, conversion funnel, revenue by subscription tier.

## Recommended Build Order

1. Fix the test suite around `UserAccount`.
2. Fix the candidate registration Enter-key bug.
3. Implement password reset.
4. Align password copy/client validation with server rules.
5. Finalize resume parser dependencies and add parser smoke tests.
6. Add authenticated page `Cache-Control: no-store`.
7. Register and harden `UserAccount` admin.
8. Clean sample data and define staging/demo seed workflow.
9. Polish mobile nav and reveal fallback behavior.
10. Run a final browser QA pass across desktop/mobile before launch.

## Current State

The app is promising and visibly past the fragile prototype stage, but it needs one focused stabilization pass before it should handle real candidate resumes, employer accounts, payments, or production traffic.

Best next engineering move: fix tests first, then repair the registration and account-recovery issues. That gives the project a trustworthy baseline for the bigger AI matching and production deployment work.
