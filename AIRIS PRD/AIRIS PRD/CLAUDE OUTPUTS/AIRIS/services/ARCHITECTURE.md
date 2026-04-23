# AIRIS architecture

**Version**: 1.0
**Date**: 2026-04-18
**Last updated by**: Shen

---

## System overview

AIRIS is an AI-powered recruiting operating system for staffing agencies. The backend is a Python monolith built with FastAPI, organised into eight service modules. Each module owns its data, exposes a public interface, and communicates with other modules via direct Python imports (for internal services) or REST API calls (for the frontend).

The frontend is a Next.js single-page application that communicates exclusively with the backend's REST API.

---

## Service map

```
┌─────────────────────────────────────────────────────────────────┐
│                        AIRIS Backend                             │
│                                                                  │
│  ┌──────────┐  ┌──────────────────┐  ┌────────────┐            │
│  │  auth/    │  │ candidate-mgmt/  │  │ job-mgmt/  │            │
│  │          │  │                  │  │            │            │
│  │ Users    │  │ Profiles         │  │ Jobs       │            │
│  │ Orgs     │  │ Resumes          │  │ Intake     │            │
│  │ RBAC     │  │ Skills           │  │ Submissions│            │
│  │ Sessions │  │ Interactions     │  │ Matching   │            │
│  └────┬─────┘  └───────┬──────────┘  └─────┬──────┘            │
│       │                │                    │                   │
│       │         ┌──────┴────────────────────┤                   │
│       │         │                           │                   │
│  ┌────┴─────┐  ┌┴───────────┐  ┌───────────┴──┐               │
│  │scheduling/│  │ pipeline/  │  │ ai-services/ │               │
│  │          │  │            │  │              │               │
│  │ Calendar │  │ Kanban     │  │ Resume parse │               │
│  │ Booking  │  │ Stages     │  │ Matching     │               │
│  │ Reminders│  │ History    │  │ Questions    │               │
│  └────┬─────┘  └──────┬─────┘  │ Summaries   │               │
│       │                │        │ Smart search │               │
│       │         ┌──────┘        └──────────────┘               │
│  ┌────┴─────┐  ┌┴───────────┐                                  │
│  │communic/ │  │ analytics/ │                                  │
│  │          │  │            │                                  │
│  │ Email    │  │ Dashboard  │                                  │
│  │ Templates│  │ KPIs       │                                  │
│  │ Sync     │  │ Metrics    │                                  │
│  └──────────┘  └────────────┘                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Services and responsibilities

### 1. auth/

**Owns**: Users, organisations, client workspaces, workspace assignments, sessions, MFA.

Every API request is authenticated via a JWT issued by this service. The JWT encodes user ID, organisation ID, role, and assigned workspace IDs. All other services read these claims for authorisation decisions.

**Key tables**: `users`, `organisations`, `client_workspaces`, `workspace_assignments`, `sessions`, `mfa_configs`

**If you need to**: add a user, create a workspace, check permissions, manage login → look here.

---

### 2. candidate-management/

**Owns**: Candidate profiles, resumes, skills, notes, interaction history, duplicate detection.

Maintains a universal candidate database shared across all client workspaces. Other services never write directly to candidate data; they call this service's API.

**Key tables**: `candidates`, `candidate_skills`, `candidate_interactions`, `candidate_audit_log`, `bulk_upload_jobs`, `bulk_upload_items`

**If you need to**: create/search/update a candidate, upload a resume, merge duplicates, log an interaction → look here.

---

### 3. job-management/

**Owns**: Job requisitions, job-candidate submissions, AI match results.

Manages the lifecycle of job postings (draft → open → on_hold → filled → cancelled) and tracks which candidates have been submitted to which jobs.

**Key tables**: `jobs`, `job_skills`, `job_submissions`, `job_match_results`

**If you need to**: create a job, submit a candidate to a job, trigger AI matching, track job status → look here.

---

### 4. pipeline/

**Owns**: Pipeline stage configuration, candidate pipeline cards, stage transition history.

Provides the Kanban board view where recruiters drag candidates through hiring stages. Handles optimistic concurrency for concurrent edits.

**Key tables**: `pipeline_stages`, `pipeline_cards`, `pipeline_stage_history`, `placement_records`

**If you need to**: move a candidate between stages, configure pipeline stages, record a placement → look here.

---

### 5. scheduling/

**Owns**: Calendar connections, booking links, interviews, reminders.

Integrates with Google Calendar and Outlook via OAuth. Generates booking links for candidate self-scheduling and automates reminders.

**Key tables**: `calendar_connections`, `booking_links`, `interviews`, `interview_reminders`

**If you need to**: connect a calendar, schedule an interview, generate a booking link, send reminders → look here.

---

### 6. communication/

**Owns**: Email connections, sent/received emails, email templates, sync status.

Handles two-way email sync with Gmail and Outlook. Provides template management with variable substitution.

**Key tables**: `email_connections`, `emails`, `email_templates`, `email_sync_status`

**If you need to**: send an email, sync inbox, manage templates, view communication timeline → look here.

---

### 7. ai-services/

**Owns**: AI request logging and cost tracking.

Wraps all AI provider APIs (OpenAI, Anthropic Claude) behind a stable internal Python interface. No other service calls external AI APIs directly.

**Key tables**: `ai_request_log`

**Functions**: `parse_resume()`, `match_candidates()`, `generate_interview_questions()`, `generate_interview_summary()`, `smart_search()`

**If you need to**: add an AI capability, change the AI provider, tune prompts, track AI costs → look here.

---

### 8. analytics/

**Owns**: Dashboard snapshots, metric caches, recruiter performance aggregates.

Pre-computes and caches all dashboard metrics. Serves the operational dashboard with sub-100ms response times.

**Key tables**: `dashboard_snapshots`, `placement_records`, `shortlist_records`, `recruiter_metrics`, `metric_cache`

**If you need to**: add a new dashboard metric, change how KPIs are calculated, modify trend logic → look here.

---

## Dependency graph

```
auth/ ──────────────────────────────────────────────────────────►  (all services)
                                                                    (JWT verification)

candidate-management/ ───► ai-services/        (parse_resume, smart_search)
                     ───► storage/             (S3 upload/delete)

job-management/ ─────────► candidate-management/ (read profiles for submissions)
                     ───► ai-services/          (match_candidates, questions, summaries)

pipeline/ ───────────────► candidate-management/ (add_interaction on stage move)
                     ───► job-management/        (read job data for pipeline context)

scheduling/ ─────────────► candidate-management/ (read candidate contact info)
                     ───► job-management/        (read job details for events)
                     ───► communication/         (send confirmation/reminder emails)

communication/ ──────────► candidate-management/ (add_interaction for emails)
                     ───► job-management/        (read job details for templates)

analytics/ ──────────────► candidate-management/ (candidate counts)
                     ───► job-management/        (job counts, submissions)
                     ───► pipeline/              (stage history, placements)
                     ───► scheduling/            (interview counts)
                     ───► auth/                  (user activity)

ai-services/ ────────────► (external: OpenAI API, Anthropic Claude API)
storage/ ────────────────► (external: AWS S3)
```

---

## Cross-cutting concerns

### Authentication and authorisation

Every REST endpoint (except auth/login, auth/password-reset, and public booking link endpoints) requires a valid JWT in the `Authorization: Bearer` header. The JWT is issued by `auth/` and contains:

```json
{
  "user_id": "uuid",
  "org_id": "uuid",
  "role": "admin | recruiter | client_viewer",
  "workspace_ids": ["uuid", "uuid"],
  "exp": 1234567890
}
```

Each service enforces its own authorisation rules based on these claims. The general pattern is:

- **Admin**: access to everything within their organisation
- **Recruiter**: access limited to assigned workspaces
- **Client viewer**: read-only access to their single workspace

### Audit logging

All services that handle candidate PII (candidate-management, communication) maintain audit logs. Write operations record: what changed, who changed it, and when. Audit logs are append-only and retained for a minimum of 12 months.

### Error handling

All services follow a consistent error response format:

```json
{
  "success": false,
  "error": "ERROR_CODE",
  "error_message": "Human-readable description",
  "details": {}
}
```

Standard HTTP status codes: 400 (validation), 401 (unauthenticated), 403 (unauthorised), 404 (not found), 409 (conflict), 413 (too large), 422 (unprocessable), 500 (internal error).

### Async processing

Long-running operations (resume parsing, bulk uploads, email sync, metric cache refresh) are queued via Redis + Celery. The API returns immediately with a job ID, and the caller polls for status.

---

## Technology stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Next.js (React) | Single-page application |
| Backend | FastAPI (Python 3.11+) | REST API, service modules |
| Database | PostgreSQL 15+ | Primary data store |
| Task queue | Redis + Celery | Async jobs, scheduled tasks |
| File storage | AWS S3 | Resume uploads |
| AI providers | OpenAI API, Anthropic Claude API | Resume parsing, matching, NLP |
| Auth | JWT (PyJWT) + bcrypt | Authentication tokens |
| Calendar | Google Calendar API, Microsoft Graph API | Scheduling integration |
| Email | Gmail API, Microsoft Graph API, SMTP | Communication |
| Hosting | AWS (EC2/ECS, RDS, ElastiCache) | Infrastructure |

---

## Folder structure

```
airis/
├── ARCHITECTURE.md              ← this file
├── auth/
│   ├── SPEC.md
│   ├── api.py                   ← public interface (FastAPI router)
│   ├── schemas.py               ← public Pydantic models
│   ├── service.py
│   ├── repository.py
│   ├── models.py
│   └── tests/
├── candidate-management/
│   ├── SPEC.md
│   ├── api.py
│   ├── schemas.py
│   ├── service.py
│   ├── repository.py
│   ├── models.py
│   ├── tasks.py                 ← Celery tasks (bulk upload)
│   └── tests/
├── job-management/
│   ├── SPEC.md
│   ├── api.py
│   ├── schemas.py
│   ├── ...
│   └── tests/
├── pipeline/
│   ├── SPEC.md
│   ├── api.py
│   ├── ...
│   └── tests/
├── scheduling/
│   ├── SPEC.md
│   ├── api.py
│   ├── ...
│   └── tests/
├── communication/
│   ├── SPEC.md
│   ├── api.py
│   ├── ...
│   └── tests/
├── ai-services/
│   ├── SPEC.md
│   ├── api.py                   ← internal Python interface (no REST)
│   ├── providers.py             ← OpenAI/Claude client wrappers
│   ├── prompts/                 ← versioned prompt templates
│   ├── ...
│   └── tests/
├── analytics/
│   ├── SPEC.md
│   ├── api.py
│   ├── ...
│   └── tests/
├── shared/
│   ├── auth_middleware.py       ← JWT verification middleware
│   ├── error_handlers.py       ← consistent error response formatting
│   ├── database.py             ← SQLAlchemy engine/session setup
│   ├── redis_client.py         ← Redis connection
│   └── config.py               ← environment config
├── main.py                      ← FastAPI app entry point, mounts all routers
├── requirements.txt
└── docker-compose.yml
```

**Import rules**: Services import only from other services' `api.py` and `schemas.py`. Everything else within a service folder is internal. The `shared/` folder contains infrastructure code that all services use.

---

## Phase 1 scope

All eight services are in scope for Phase 1 MVP. The following capabilities are explicitly deferred to Phase 2 or later:

- WhatsApp integration (communication/)
- AI conversational screening agent (ai-services/)
- External ATS integrations — Greenhouse, Lever, Workday (new service)
- Predictive analytics and forecasting (analytics/)
- Native mobile apps
- White-label client portals
- Multi-region deployment

---

## How to use this document

If you are an AI coding tool starting a session on AIRIS:

1. Read this file first. It tells you where everything lives.
2. Identify which service your task belongs to.
3. Read that service's `SPEC.md` for the full interface contract, behaviour requirements, and test cases.
4. Implement against the interface. Run the tests. They define 'done'.
5. If your task spans multiple services, read all relevant `SPEC.md` files and respect the dependency direction (never create circular dependencies).
