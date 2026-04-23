# Job Management

## Overview
The job management domain owns requisition lifecycle, required/preferred skill definition, candidate submissions, and AI-assisted candidate ranking cache. It is the source-of-truth for job state used by pipeline, scheduling, communication templates, and analytics.

## Responsibilities
Primary responsibilities:
- Create, update, and query jobs by workspace and operational filters.
- Enforce job lifecycle state transitions.
- Accept candidate submissions to active jobs with dedup protection.
- Trigger and cache AI match results per job.
- Provide job context to downstream services.

## Data Model
Core tables:
- `jobs`: requisition details, salary/experience range, urgency, status, timestamps.
- `job_skills`: required vs preferred skills per job.
- `job_submissions`: candidate-to-job submissions and submission status.
- `job_match_cache`: ranked candidate IDs with fit score breakdown and generation timestamp.

Key constraints:
- Salary and experience range validation constraints.
- One submission per `(job_id, candidate_id)`.
- Terminal job statuses (`filled`, `cancelled`) restrict further transitions.

## API Endpoints
Representative endpoints:
- `POST /api/v1/jobs` create job
- `GET /api/v1/jobs/{job_id}` get job
- `PATCH /api/v1/jobs/{job_id}` update job
- `GET /api/v1/jobs/search` filtered job search
- `PATCH /api/v1/jobs/{job_id}/status` state transition
- `POST /api/v1/jobs/{job_id}/submit` submit candidate to job
- `GET /api/v1/jobs/{job_id}/submissions` list submissions
- `POST /api/v1/jobs/{job_id}/match` trigger AI matching
- `GET /api/v1/jobs/{job_id}/matches` read cached ranking

## Business Logic
- Workspace access is enforced from JWT claims for all operations.
- New jobs default to `draft`; visibility and submission behavior depend on status.
- Status transition graph is explicit; invalid transitions return deterministic errors.
- Candidate submission validates candidate existence via candidate-management and blocks duplicates.
- AI matching:
  - Trigger endpoint can force refresh or reuse cache.
  - Matching is async and persists ranked outputs to cache table.
  - Read endpoint enriches with `already_submitted` marker for recruiter workflow.
- Ranking exposes category-level explainability (`skills_overlap`, `location_compatibility`, `experience_fit`).

## Notes / Constraints
- This service owns workflow state for requisitions, but not pipeline cards (owned by pipeline service).
- Matching logic implementation belongs to `ai-services`; this module orchestrates and caches outputs.
- External posting boards and approval workflows are out of scope for Phase 1.
- Keep status semantics stable to avoid downstream regressions in pipeline and analytics.
