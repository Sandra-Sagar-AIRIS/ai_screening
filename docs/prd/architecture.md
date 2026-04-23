# AIRIS Architecture

## Overview
AIRIS is an AI-powered recruiting operating system for staffing agencies. The platform uses a Next.js frontend and a Python FastAPI backend organized into domain modules. The backend follows a modular monolith style: each service owns its data and exposes a public interface, while cross-service access goes through defined contracts (`api.py` / `schemas.py`).

Core runtime stack:
- Frontend: Next.js + Tailwind + shadcn/ui
- Backend: FastAPI (Python 3.11+)
- Data: PostgreSQL 15+
- Async: Redis + Celery
- Storage: AWS S3 (resume files)
- AI: OpenAI + Anthropic Claude

## Responsibilities
Architecture responsibilities:
- Define service ownership boundaries and dependency direction.
- Standardize shared concerns: JWT auth, error handling, audit logs, async jobs.
- Enforce import rules to avoid hidden coupling.
- Keep module contracts explicit for AI-assisted development and team scaling.

Service map:
- `auth`: identity, RBAC, workspaces, sessions
- `candidate-management`: candidate records, skills, interactions, uploads
- `job-management`: jobs, submissions, AI match caching
- `pipeline`: stage configuration, kanban movement, transition history
- `scheduling`: calendars, booking links, interviews, reminders
- `communication`: email sync, send, templates, thread timeline
- `ai-services`: provider abstraction, AI functions, cost logs
- `analytics`: KPI aggregation, cached dashboard metrics

## Data Model
Cross-service entities and ownership:
- `User`, `Organisation`, `Workspace` -> `auth`
- `Candidate`, `CandidateSkill`, `CandidateInteraction` -> `candidate-management`
- `Job`, `JobSkill`, `JobSubmission` -> `job-management`
- `PipelineStage`, `PipelineCard`, `PipelineStageHistory`, `PipelinePlacement` -> `pipeline`
- `CalendarConnection`, `BookingLink`, `Interview`, `InterviewReminder` -> `scheduling`
- `EmailConnection`, `Email`, `EmailTemplate` -> `communication`
- `AIRequestLog` -> `ai-services`
- `DashboardSnapshot`, `RecruiterMetrics`, `MetricCache` -> `analytics`

Ownership rule: each module is the only writer for its tables; other modules consume through contract APIs.

## API Endpoints
Global API contract principles:
- REST endpoints under `/api/v1/...` for user-facing modules.
- `ai-services` exposes internal Python functions (no public REST surface).
- JWT Bearer auth required for all protected routes.
- Consistent response envelope:
  - Success: `{ "success": true, "data": ... }`
  - Error: `{ "success": false, "error": "CODE", "error_message": "...", "details": {} }`

Typical status usage:
- `400` validation/business constraint
- `401` unauthenticated
- `403` unauthorized
- `404` not found
- `409` conflict (duplicates/version mismatch)
- `422` semantic processing errors (e.g., parse failures)
- `500` internal errors

## Business Logic
Cross-cutting logic:
- JWT claims (`user_id`, `org_id`, `role`, `workspace_ids`) drive authorization in each service.
- Candidate PII write operations require audit logging.
- Long-running jobs (resume parse, bulk uploads, sync, metric refresh) run asynchronously with Celery.
- Pipeline and scheduling events must update candidate interactions for a complete timeline.
- Analytics derives near-real-time metrics with cache-first reads and scheduled refresh.

Dependency direction (important):
- `auth` authenticates all services.
- `candidate-management` is a core dependency for `job-management`, `pipeline`, `scheduling`, `communication`, and `analytics`.
- `job-management` feeds `pipeline`, `scheduling`, `communication`, and `analytics`.
- `ai-services` is consumed by candidate and job domains only.
- `analytics` is read-heavy and depends on upstream services; upstream services should not depend on analytics.

## Notes / Constraints
- Services may import only another service's `api.py` and `schemas.py`.
- Avoid circular dependencies; follow documented flow direction.
- Phase 1 defers WhatsApp, AI conversational screening agent maturity, advanced ATS breadth, and predictive analytics.
- Keep architecture docs aligned with service-level specs before generating implementation code.
