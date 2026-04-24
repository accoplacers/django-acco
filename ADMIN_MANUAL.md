# AccoPlacers Admin & Staff Manual

This manual is for authorized AccoPlacers staff and administrators. It covers platform management, security protocols, and operational intelligence.

---

## 🔐 Administrative Access
- **Django Admin**: Accessible at `/admin/`. Requires Superuser or Staff credentials.
- **Intelligence Terminal**: Accessible at `/admin-analytics/`. Provides a high-level overview of platform health and engagement metrics.

---

## 🛠️ Model Management (Django Admin)

### 1. User Accounts
- **User Management**: Add, update, or deactivate accounts.
- **Role Control**: Manually toggle users between `employee` (Candidate) and `employer` roles if necessary.

### 2. Candidate Registrations
- **Profile Moderation**: Edit candidate details or update their "Skills" (using the Many-to-Many tagging interface).
- **Placement Status**: Mark candidates as "Placed" to remove them from active search results.
- **Plan Management**: Manually upgrade candidates to "Premium" or "Basic" tiers.

### 3. Employer & Job Management
- **Company Verification**: Review and approve new employer accounts.
- **Job Auditing**: Monitor and moderate job postings to ensure compliance with quality standards.
- **Industry Categorization**: Update company industry tags to improve search accuracy.

---

## 📊 Operational Intelligence (Analytics)

The custom **Admin Analytics** dashboard (`/admin-analytics/`) surfaces critical recruitment KPIs:
- **Acquisition**: Tracks growth in candidate and employer signups.
- **Engagement**: Monitor active job counts and candidate "Interest" signals.
- **Success Metrics**: Logs of employer contacts and candidate placements.
- **Regional Trends**: Visibility into the top locations and roles being searched.

---

## 🛡️ Security Protocols

### 1. Bot Protection (Honeypot)
- **Mechanism**: A hidden `fax_number` field exists on all registration forms.
- **Incident Response**: Any submission containing data in this field is automatically blocked (HTTP 400) and logged. No manual action is required unless a flood of bots is detected.

### 2. Rate Limiting (Throttling)
- **Mechanism**: The platform enforces IP-based rate limiting on sensitive views:
    - **Logins**: 5 attempts per minute.
    - **Dashboard Actions**: 30 actions per minute.
- **Blocking**: Offenders are automatically blocked for 5 minutes (HTTP 429). This is handled by the cache layer; no database records are created for blocked attempts.

---

## 🚀 SEO & Discoverability Maintenance

### 1. Sitemap Management
- **Dynamic Sitemaps**: Located at `/sitemap.xml`. These update automatically when new jobs are posted.
- **Indexing**: Google Search Console should be configured to crawl this path weekly.

### 2. AI Discoverability
- **llms.txt**: Located at `/llms.txt`. This provides a Markdown summary for AI agents (ChatGPT, etc.) to understand platform offerings.
- **Markdown Mirrors**: Job listings support a `?format=md` parameter, allowing AI agents to scrape clean, structured job data.

---

## 📋 Emergency Procedures
- **Clearing Cache**: If rate limits are accidentally triggered for a valid user, clear the cache via the server shell:
  `python manage.py shell -c "from django.core.cache import cache; cache.clear()"`
- **Superuser Recovery**: Use `python manage.py createsuperuser` if staff credentials are lost.

**Technical Lead**: Antigravity AI
**System Version**: 2.0 (Dubai Premium)
