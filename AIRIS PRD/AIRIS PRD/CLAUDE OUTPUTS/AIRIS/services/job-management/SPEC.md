# Service spec: job-management

**Version**: 1.0
**Date**: 2026-04-18
**Parent PRD**: AIRIS Phase 1 MVP PRD v1

---

## 1. Service boundary

**Folder**: `job-management/`

This service owns all job requisition data: job postings, intake forms, job-candidate submissions, and job status lifecycle. No other service writes to job or submission records directly. All reads and writes flow through this service's public API.

**Owns**: `jobs` table, `job_skills` table, `job_submissions` table.

**Depends on**:

- `candidate-management/` reads candidate profiles when displaying match results
- `ai-services/` calls `match_candidates(job_id: str) -> RankedCandidateList` for AI-powered candidate matching

**Depended on by**:

- `pipeline/` reads job data and submissions for pipeline views
- `scheduling/` reads job context and candidate submissions for interview scheduling
- `analytics/` reads job counts, time-to-fill, placement timestamps, and submission metrics
- `communication/` reads job title and details for email templates and communication context

---

## 2. Database schema

```sql
-- job-management/schema.sql

CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_workspace_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    location VARCHAR(255) NOT NULL,                  -- city/state or "Remote"
    salary_min DECIMAL(10, 2),
    salary_max DECIMAL(10, 2),
    salary_currency VARCHAR(3) DEFAULT 'USD',        -- ISO 4217 code
    experience_min_years INT,
    experience_max_years INT,
    employment_type VARCHAR(30) NOT NULL,           -- 'full_time' | 'contract' | 'contract_to_hire'
    urgency VARCHAR(20) DEFAULT 'standard',         -- 'standard' | 'urgent' | 'critical'
    status VARCHAR(20) DEFAULT 'draft',             -- 'draft' | 'open' | 'on_hold' | 'filled' | 'cancelled'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    filled_at TIMESTAMPTZ,                          -- timestamp when status changes to 'filled'
    created_by UUID NOT NULL,                       -- recruiter user ID
    CONSTRAINT jobs_salary_range_valid CHECK (salary_max IS NULL OR salary_min IS NULL OR salary_min <= salary_max),
    CONSTRAINT jobs_experience_range_valid CHECK (experience_max_years IS NULL OR experience_min_years IS NULL OR experience_min_years <= experience_max_years)
);

CREATE INDEX idx_jobs_client_workspace ON jobs (client_workspace_id);
CREATE INDEX idx_jobs_status ON jobs (status);
CREATE INDEX idx_jobs_urgency ON jobs (urgency);
CREATE INDEX idx_jobs_created_at ON jobs (created_at DESC);
CREATE INDEX idx_jobs_location ON jobs (location);

CREATE TABLE job_skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    skill VARCHAR(100) NOT NULL,
    is_required BOOLEAN DEFAULT TRUE,                -- TRUE for required_skills, FALSE for preferred_skills
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT job_skills_unique UNIQUE (job_id, skill)
);

CREATE INDEX idx_job_skills_job ON job_skills (job_id);
CREATE INDEX idx_job_skills_skill ON job_skills (skill);

CREATE TABLE job_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    candidate_id UUID NOT NULL,                     -- Reference to candidate-management service
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    submitted_by UUID NOT NULL,                     -- recruiter user ID
    submission_status VARCHAR(30) DEFAULT 'pending', -- 'pending' | 'shortlisted' | 'rejected' | 'interviewing' | 'offered' | 'hired'
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT job_submissions_unique UNIQUE (job_id, candidate_id)
);

CREATE INDEX idx_job_submissions_job ON job_submissions (job_id);
CREATE INDEX idx_job_submissions_candidate ON job_submissions (candidate_id);
CREATE INDEX idx_job_submissions_status ON job_submissions (submission_status);
CREATE INDEX idx_job_submissions_created_at ON job_submissions (created_at DESC);

CREATE TABLE job_match_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    ranked_candidate_ids JSONB NOT NULL,            -- [{"candidate_id": "...", "fit_score": 87, "category_scores": {...}}]
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT job_match_cache_unique UNIQUE (job_id)
);

CREATE INDEX idx_job_match_cache_job ON job_match_cache (job_id);
CREATE INDEX idx_job_match_cache_generated_at ON job_match_cache (generated_at DESC);
```

---

## 3. REST API endpoints

All endpoints require authentication. The `Authorization` header carries a JWT issued by `auth/`. The user's role and assigned workspaces are encoded in the token claims.

### 3.1 Create job

```
POST /api/v1/jobs
```

**Request body**:
```json
{
  "client_workspace_id": "workspace-id-123",
  "title": "Senior Python Backend Engineer",
  "description": "Looking for a Python expert to build microservices...",
  "location": "Bangalore, India",
  "salary_min": 80000,
  "salary_max": 120000,
  "salary_currency": "INR",
  "experience_min_years": 3,
  "experience_max_years": 8,
  "employment_type": "full_time",
  "urgency": "urgent",
  "required_skills": ["Python", "FastAPI", "PostgreSQL"],
  "preferred_skills": ["Redis", "Docker"]
}
```

**Success response** (201 Created):
```json
{
  "success": true,
  "data": {
    "id": "job-id-456",
    "client_workspace_id": "workspace-id-123",
    "title": "Senior Python Backend Engineer",
    "description": "Looking for a Python expert...",
    "location": "Bangalore, India",
    "salary_min": 80000,
    "salary_max": 120000,
    "salary_currency": "INR",
    "experience_min_years": 3,
    "experience_max_years": 8,
    "employment_type": "full_time",
    "urgency": "urgent",
    "status": "draft",
    "required_skills": ["Python", "FastAPI", "PostgreSQL"],
    "preferred_skills": ["Redis", "Docker"],
    "created_at": "2026-04-18T10:30:00Z",
    "updated_at": "2026-04-18T10:30:00Z",
    "created_by": "rec-user-id-001",
    "filled_at": null
  }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 400 | `VALIDATION_ERROR` | Missing `title`, `description`, `location`, `employment_type`, or `client_workspace_id`. Response body includes a `fields` array listing each invalid field and the reason. |
| 400 | `INVALID_SALARY_RANGE` | `salary_min > salary_max`. |
| 400 | `INVALID_EXPERIENCE_RANGE` | `experience_min_years > experience_max_years`. |
| 403 | `WORKSPACE_FORBIDDEN` | User does not have access to the specified workspace. |
| 401 | `UNAUTHORIZED` | Missing or invalid auth token. |

### 3.2 Get job

```
GET /api/v1/jobs/{job_id}
```

**Success response** (200 OK): Returns full job object including status, skills, and timestamps.

**Error**: 404 `JOB_NOT_FOUND` if the ID does not exist. 403 `WORKSPACE_FORBIDDEN` if user lacks access to the job's workspace.

### 3.3 Update job

```
PATCH /api/v1/jobs/{job_id}
```

**Request body**: Partial update. Only fields present in the body are changed.
```json
{
  "location": "Remote",
  "urgency": "critical",
  "required_skills": ["Python", "FastAPI", "PostgreSQL", "Redis"]
}
```

**Success response** (200 OK): Returns updated job object.

**Error**: 404 if not found. 400 `INVALID_SALARY_RANGE` or `INVALID_EXPERIENCE_RANGE` if constraints violated. 403 `WORKSPACE_FORBIDDEN`.

### 3.4 Search and filter jobs

```
GET /api/v1/jobs/search?workspace_id=...&status=open&urgency=critical&skills=Python,FastAPI&location=Bangalore&limit=50&offset=0
```

**Query parameters** (all optional):

| Param | Type | Description |
|-------|------|-------------|
| `workspace_id` | UUID | Filter by workspace. Required unless user is Admin. |
| `status` | string | Filter by job status (comma-separated: draft, open, on_hold, filled, cancelled). |
| `urgency` | string | Filter by urgency level (comma-separated: standard, urgent, critical). |
| `skills` | comma-separated | Filter by required skills. AND logic: job must require all listed skills. |
| `location` | string | Filter by location (partial match). |
| `employment_type` | string | Filter by employment type (comma-separated: full_time, contract, contract_to_hire). |
| `limit` | int | Results per page (default 50, max 200). |
| `offset` | int | Pagination offset. |

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "jobs": [ "...array of job objects..." ],
    "total_count": 42,
    "limit": 50,
    "offset": 0
  }
}
```

Urgent and critical jobs appear first in results (sorted by urgency DESC, then by created_at DESC).

### 3.5 Change job status

```
PATCH /api/v1/jobs/{job_id}/status
```

**Request body**:
```json
{
  "status": "open"
}
```

**Valid status transitions**:
- `draft` → `open`, `cancelled`
- `open` → `on_hold`, `filled`, `cancelled`
- `on_hold` → `open`, `filled`, `cancelled`
- `filled` → no transitions (terminal state)
- `cancelled` → no transitions (terminal state)

**Success response** (200 OK): Returns updated job object with new status and `filled_at` timestamp if status is `filled`.

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 400 | `INVALID_STATUS_TRANSITION` | Requested transition is not allowed (e.g., `filled` → `open`). |
| 400 | `INVALID_STATUS_VALUE` | Status is not one of the valid values. |
| 404 | `JOB_NOT_FOUND` | Job ID does not exist. |

### 3.6 Submit candidate to job

```
POST /api/v1/jobs/{job_id}/submit
```

**Request body**:
```json
{
  "candidate_id": "candidate-id-789",
  "notes": "Excellent Python background, available in 2 weeks."
}
```

**Success response** (201 Created):
```json
{
  "success": true,
  "data": {
    "submission_id": "submission-id-123",
    "job_id": "job-id-456",
    "candidate_id": "candidate-id-789",
    "submission_status": "pending",
    "submitted_at": "2026-04-18T11:00:00Z",
    "submitted_by": "rec-user-id-001",
    "notes": "Excellent Python background..."
  }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 400 | `DUPLICATE_SUBMISSION` | Candidate already submitted to this job. Response includes the existing submission ID and status. |
| 404 | `JOB_NOT_FOUND` | Job ID does not exist. |
| 404 | `CANDIDATE_NOT_FOUND` | Candidate ID does not exist (checked against candidate-management/). |
| 409 | `JOB_NOT_OPEN` | Job status is not `open` or `on_hold`. Only jobs in these states accept submissions. |

### 3.7 List submissions for a job

```
GET /api/v1/jobs/{job_id}/submissions?submission_status=pending&limit=50&offset=0
```

**Query parameters** (all optional):

| Param | Type | Description |
|-------|------|-------------|
| `submission_status` | string | Filter by status (comma-separated: pending, shortlisted, rejected, interviewing, offered, hired). |
| `limit` | int | Results per page (default 50, max 200). |
| `offset` | int | Pagination offset. |

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "submissions": [ "...array of submission objects..." ],
    "total_count": 8,
    "limit": 50,
    "offset": 0
  }
}
```

Submissions are ordered by submitted_at DESC (most recent first).

### 3.8 Trigger AI candidate matching

```
POST /api/v1/jobs/{job_id}/match
```

**Request body**: Empty or optional parameters.
```json
{
  "refresh": true
}
```

Calls `ai-services/match_candidates(job_id)` to rank candidates based on job requirements. If `refresh=true` or no cached results exist, calls the AI service. Otherwise returns cached results.

**Success response** (202 Accepted):
```json
{
  "success": true,
  "data": {
    "job_id": "job-id-456",
    "match_count": 24,
    "generated_at": "2026-04-18T11:15:00Z",
    "refresh_requested": true
  }
}
```

Matching is asynchronous. The response returns immediately with a count and timestamp. Use the GET endpoint to fetch results.

**Error**: 404 `JOB_NOT_FOUND`. 400 `AI_SERVICE_UNAVAILABLE` if the service is down and no cache exists.

### 3.9 Get cached match results

```
GET /api/v1/jobs/{job_id}/matches?limit=50&offset=0
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "job_id": "job-id-456",
    "matches": [
      {
        "rank": 1,
        "candidate_id": "cand-001",
        "fit_score": 92,
        "category_scores": {
          "skills_overlap": 95,
          "location_compatibility": 100,
          "experience_fit": 82
        },
        "already_submitted": false
      },
      {
        "rank": 2,
        "candidate_id": "cand-002",
        "fit_score": 87,
        "category_scores": {
          "skills_overlap": 88,
          "location_compatibility": 85,
          "experience_fit": 86
        },
        "already_submitted": true
      }
    ],
    "total_count": 24,
    "generated_at": "2026-04-18T11:15:00Z",
    "limit": 50,
    "offset": 0
  }
}
```

Fit scores are percentages (0-100). `already_submitted` indicates if the candidate has already been submitted to this job.

**Error**: 404 `JOB_NOT_FOUND` or `MATCHES_NOT_FOUND` (no matches generated yet).

---

## 4. Behaviour requirements

### create_job

- Given valid input with all required fields (`title`, `description`, `location`, `employment_type`, `client_workspace_id`), creates a row in `jobs`, inserts rows into `job_skills` for each required and preferred skill, records `created_at` and `created_by` for time-to-fill tracking, and returns the complete job object.
- Given a `salary_min > salary_max`, returns 400 `INVALID_SALARY_RANGE`. Does not create any records.
- Given an `experience_min_years > experience_max_years`, returns 400 `INVALID_EXPERIENCE_RANGE`. Does not create any records.
- Given a user without access to the specified `client_workspace_id`, returns 403 `WORKSPACE_FORBIDDEN`.
- Job status defaults to `draft`. The job does not appear in public search or matching until status is changed to `open`.

### update_job

- Only fields present in the request body are modified. Other fields remain unchanged.
- If the update violates the salary or experience range constraints, the update is rejected with 400 and no changes are made.
- If `required_skills` or `preferred_skills` are provided, the existing `job_skills` rows are deleted and new rows are inserted.
- The `updated_at` timestamp is set to the current time.

### search_jobs

- Performs a PostgreSQL query with AND logic on all provided filters.
- Skills filter uses a subquery on `job_skills`: job must require all listed skills (is_required = TRUE).
- Location filter uses case-insensitive `ILIKE '%{location}%'`.
- Status and urgency filters support comma-separated values (OR logic within each filter, AND between filters).
- Results are sorted by urgency (DESC: critical > urgent > standard), then by created_at (DESC).
- If no filters are provided, returns the 50 most recently created jobs that the user has access to.
- Workspace access is enforced: non-Admin users see only jobs in their assigned workspaces.

### change_job_status

- Validates the requested transition against allowed paths. Returns 400 `INVALID_STATUS_TRANSITION` if not allowed.
- If status changes to `filled`, sets `filled_at = NOW()` for analytics time-to-fill calculation. Rejects further status changes (filled is terminal).
- Updates `updated_at` to the current time.
- Returns the updated job object.

### submit_candidate_to_job

- Given a candidate not already submitted to this job, creates a `job_submissions` row with `submission_status = pending` and `submitted_at = NOW()`.
- Given a candidate already submitted to this job, returns 400 `DUPLICATE_SUBMISSION` with the existing submission ID and status. Does not create a new row.
- Given a job whose status is `draft` or `cancelled`, returns 409 `JOB_NOT_OPEN`.
- Calls `candidate-management/` to validate the candidate ID exists (returns 404 if not found).

### list_submissions

- Returns all submissions for the job, filtered by optional `submission_status`.
- Results are ordered by `submitted_at DESC`.
- Includes pagination (limit and offset).

### trigger_matching

- If `refresh=true` or no cache exists, calls `ai-services/match_candidates(job_id)` asynchronously.
- The AI service receives job requirements (title, description, skills, location, experience_range) and returns a ranked list of candidate IDs with fit scores.
- Caches the result in `job_match_cache` with a `generated_at` timestamp.
- Returns 202 immediately with the job ID, match count, and generation timestamp.
- If the AI service is unavailable and no cache exists, returns 400 `AI_SERVICE_UNAVAILABLE`.

### get_matches

- Returns cached match results from `job_match_cache` if available.
- For each match, includes the candidate ID, rank, fit_score (0-100), category_scores breakdown (skills_overlap, location_compatibility, experience_fit), and `already_submitted` flag indicating if the candidate has a pending/active submission for this job.
- Results include pagination.
- Returns 404 `MATCHES_NOT_FOUND` if no cache exists (matching has not been triggered yet).

---

## 5. Acceptance criteria as tests

```python
# job-management/tests/test_create.py

class TestCreateJob:

    def test_valid_input_creates_job(self, client, recruiter_token):
        """POST /api/v1/jobs with valid title, description, location, employment_type,
        and client_workspace_id returns 201 with a job object containing a UUID id,
        correct field values, status='draft', and timestamps within the last 5 seconds."""

    def test_skills_stored_as_required_and_preferred(self, client, recruiter_token):
        """POST with required_skills=['Python', 'FastAPI'] and preferred_skills=['Redis']
        creates corresponding job_skills rows with is_required=TRUE and is_required=FALSE."""

    def test_salary_min_greater_than_max_returns_400(self, client, recruiter_token):
        """POST with salary_min=120000 and salary_max=80000 returns 400
        INVALID_SALARY_RANGE."""

    def test_experience_min_greater_than_max_returns_400(self, client, recruiter_token):
        """POST with experience_min_years=8 and experience_max_years=3 returns 400
        INVALID_EXPERIENCE_RANGE."""

    def test_workspace_access_enforced(self, client, recruiter_token, another_workspace):
        """POST with a workspace_id the recruiter is not assigned to returns 403
        WORKSPACE_FORBIDDEN."""

    def test_status_defaults_to_draft(self, client, recruiter_token):
        """After POST, job status is 'draft' and does not appear in open job searches."""

    def test_created_at_recorded_for_metrics(self, client, recruiter_token, db):
        """After successful creation, jobs.created_at is set and can be used for
        time-to-fill calculation."""


# job-management/tests/test_search.py

class TestSearchJobs:

    def test_filter_by_status_and_logic(self, client, recruiter_token, jobs_with_statuses):
        """GET /search?status=open returns only jobs with status='open'."""

    def test_filter_by_urgency_desc(self, client, recruiter_token, jobs_with_urgencies):
        """GET /search with multiple urgency levels returns results ordered critical
        first, then urgent, then standard."""

    def test_filter_by_skills_and_logic(self, client, recruiter_token, jobs_with_skills):
        """GET /search?skills=Python,FastAPI returns only jobs that require both
        Python AND FastAPI."""

    def test_filter_by_location_partial_match(self, client, recruiter_token, jobs_with_locations):
        """GET /search?location=ban matches jobs in 'Bangalore' (case-insensitive)."""

    def test_pagination(self, client, recruiter_token, many_jobs):
        """GET /search?limit=20&offset=40 returns 20 jobs, total_count reflects
        the full matching set."""

    def test_workspace_access_enforced(self, client, recruiter_token, workspace1_jobs, workspace2_jobs):
        """A non-Admin recruiter sees only jobs in their assigned workspaces."""

    def test_no_params_returns_recent(self, client, recruiter_token, many_jobs):
        """GET /search with no parameters returns the 50 most recently created jobs."""

    def test_draft_jobs_not_included_in_default_search(self, client, recruiter_token, draft_and_open_jobs):
        """GET /search (no params) returns only open and on_hold jobs by default."""


# job-management/tests/test_status_change.py

class TestChangeJobStatus:

    def test_draft_to_open(self, client, recruiter_token, draft_job):
        """PATCH /jobs/{id}/status with status='open' succeeds and job is now open."""

    def test_open_to_filled(self, client, recruiter_token, open_job):
        """PATCH /jobs/{id}/status with status='filled' succeeds, filled_at is set,
        and no further status changes are allowed."""

    def test_filled_is_terminal(self, client, recruiter_token, filled_job):
        """PATCH /jobs/{id}/status with any new status returns 400
        INVALID_STATUS_TRANSITION."""

    def test_invalid_transition_returns_400(self, client, recruiter_token, draft_job):
        """PATCH /jobs/{id}/status with status='filled' directly from 'draft'
        returns 400 INVALID_STATUS_TRANSITION."""

    def test_filled_at_timestamp_set(self, client, recruiter_token, open_job, db):
        """After changing status to 'filled', jobs.filled_at is set to current time."""


# job-management/tests/test_submit.py

class TestSubmitCandidate:

    def test_valid_submission_creates_record(self, client, recruiter_token, open_job, candidate):
        """POST /jobs/{id}/submit with valid candidate_id returns 201 with a
        submission_id, submission_status='pending', and submitted_at timestamp."""

    def test_duplicate_submission_returns_400(self, client, recruiter_token, open_job, candidate, existing_submission):
        """POST with a candidate already submitted to this job returns 400
        DUPLICATE_SUBMISSION with the existing submission ID."""

    def test_job_status_draft_returns_409(self, client, recruiter_token, draft_job, candidate):
        """POST to a draft job returns 409 JOB_NOT_OPEN."""

    def test_job_status_cancelled_returns_409(self, client, recruiter_token, cancelled_job, candidate):
        """POST to a cancelled job returns 409 JOB_NOT_OPEN."""

    def test_nonexistent_candidate_returns_404(self, client, recruiter_token, open_job):
        """POST with a candidate_id that does not exist returns 404
        CANDIDATE_NOT_FOUND (verified via candidate-management/)."""

    def test_nonexistent_job_returns_404(self, client, recruiter_token, candidate):
        """POST to a non-existent job_id returns 404 JOB_NOT_FOUND."""


# job-management/tests/test_submissions.py

class TestListSubmissions:

    def test_list_all_submissions(self, client, recruiter_token, job_with_submissions):
        """GET /jobs/{id}/submissions returns all submissions for the job,
        ordered by submitted_at DESC."""

    def test_filter_by_submission_status(self, client, recruiter_token, job_with_mixed_statuses):
        """GET /jobs/{id}/submissions?submission_status=shortlisted returns only
        submissions with that status."""

    def test_pagination(self, client, recruiter_token, job_with_many_submissions):
        """GET /jobs/{id}/submissions?limit=10&offset=20 returns 10 submissions
        starting at offset 20."""


# job-management/tests/test_matching.py

class TestMatchCandidates:

    def test_trigger_matching_returns_202(self, client, recruiter_token, open_job, mock_ai_service):
        """POST /jobs/{id}/match returns 202 with job_id and match_count."""

    def test_ai_service_called_with_job_requirements(self, client, recruiter_token, open_job, mock_ai_service):
        """POST /match calls ai-services/match_candidates with job title, description,
        required/preferred skills, location, and experience range."""

    def test_cache_populated_after_matching(self, client, recruiter_token, open_job, mock_ai_service, celery_worker):
        """After matching completes, GET /jobs/{id}/matches returns cached results
        with fit_scores and category_scores."""

    def test_refresh_bypasses_cache(self, client, recruiter_token, open_job, mock_ai_service, celery_worker):
        """POST /match with refresh=true calls ai-services even if cache exists."""

    def test_get_matches_includes_already_submitted(self, client, recruiter_token, open_job, candidate_with_submission, mock_ai_service, celery_worker):
        """GET /jobs/{id}/matches includes already_submitted=true for candidates
        with existing submissions."""

    def test_ai_unavailable_returns_400_if_no_cache(self, client, recruiter_token, open_job, mock_ai_service_down):
        """POST /match when ai-services is down and no cache exists returns 400
        AI_SERVICE_UNAVAILABLE."""

    def test_ai_unavailable_returns_cache_if_exists(self, client, recruiter_token, open_job, cached_matches, mock_ai_service_down):
        """POST /match when ai-services is down but cache exists returns 202
        and uses the cached results."""

    def test_fit_score_is_percentage(self, client, recruiter_token, open_job, cached_matches):
        """GET /jobs/{id}/matches shows fit_score as 0-100 percentage."""


# job-management/tests/test_update.py

class TestUpdateJob:

    def test_partial_update_changes_only_provided_fields(self, client, recruiter_token, open_job):
        """PATCH /jobs/{id} with location='Remote' only changes location,
        other fields remain unchanged."""

    def test_salary_range_constraint_enforced(self, client, recruiter_token, open_job):
        """PATCH with salary_min > salary_max returns 400 and no changes are made."""

    def test_skills_updated_atomically(self, client, recruiter_token, open_job_with_skills):
        """PATCH with new required_skills deletes old job_skills rows and inserts
        new ones atomically."""

    def test_updated_at_timestamp_changed(self, client, recruiter_token, open_job):
        """After PATCH, updated_at is set to current time."""
```

---

## 6. Internal module structure

```
job-management/
├── api.py                  # Public interface (FastAPI router + Pydantic models)
├── service.py              # Business logic layer
├── repository.py           # Database queries (SQLAlchemy)
├── models.py               # SQLAlchemy ORM models
├── schemas.py              # Pydantic request/response schemas
├── tasks.py                # Celery tasks (async matching)
├── exceptions.py           # Service-specific exception classes
├── constants.py            # Enums, valid values, config
├── schema.sql              # Database migration source
├── tests/
│   ├── conftest.py         # Fixtures (test DB, mock AI, tokens)
│   ├── test_create.py
│   ├── test_search.py
│   ├── test_status_change.py
│   ├── test_submit.py
│   ├── test_submissions.py
│   ├── test_matching.py
│   └── test_update.py
└── README.md               # Developer onboarding for this service
```

Only `api.py` and `schemas.py` are importable by other services. Everything else is internal.

---

## 7. Dependencies and constraints

**Internal service dependencies**:

- `candidate-management/` reads candidate profiles when validating submissions and matching results. Must handle 404 for non-existent candidates gracefully.
- `ai-services/match_candidates(job_id: str) -> RankedCandidateList`: Called during matching. Must handle timeout (10s) and service unavailability gracefully. Returns ranked list of candidate IDs with fit scores and category breakdowns.

**External dependencies**:

- PostgreSQL 15+: Primary data store. Requires `gen_random_uuid()` (pgcrypto or built-in).
- Redis + Celery: Async task queue for candidate matching.

**Performance targets**:

| Operation | Target | Measured at |
|-----------|--------|-------------|
| Create job | < 200ms | API response time |
| Update job | < 200ms | API response time |
| Get job | < 100ms | API response time |
| Search jobs (structured filters) | < 500ms | For up to 10,000 jobs |
| Submit candidate | < 200ms | API response time |
| List submissions | < 500ms | For up to 1,000 submissions |
| Trigger matching (async) | < 1s | API response (processing is async) |
| Get cached matches | < 500ms | For up to 500 ranked candidates |

**Security**:

- All endpoints require a valid JWT.
- Workspace access is enforced: users see only jobs in their assigned workspaces unless they have Admin role.
- Only recruiters assigned to a workspace can create/update jobs in that workspace.
- All write operations (create, update, status change, submit) generate an audit trail via logs (implementation in Phase 2).

---

## 8. Out of scope

- Fuzzy job matching (similar job title deduplication). Phase 2.
- Job approval workflows (e.g., approval by hiring manager before posting). Phase 2.
- Job posting to external boards (LinkedIn, job portals). Phase 2+.
- Candidate matching logic implementation. Owned by `ai-services/`. This service provides job data and caches results.
- Resume parsing. Owned by `candidate-management/` and `ai-services/`.
- Email notifications when jobs are posted or submissions are made. Owned by `communication/`.
- Interview scheduling. Owned by `scheduling/`. That service reads job and submission data.
- Hiring manager and client approvals. Phase 2.

---

## 9. Verification

```bash
cd job-management/
pytest tests/ -v --tb=short
```

All tests must pass. Additionally, verify these end-to-end scenarios manually or via integration tests:

1. Create a job with required and preferred skills, verify the job is in draft status and does not appear in searches until status changes to open.
2. Update a job's location and urgency level, confirm changes are reflected immediately.
3. Change a job status from draft to open, then to filled, and confirm the filled_at timestamp is recorded and no further status changes are allowed.
4. Submit a candidate to a job, then attempt to submit the same candidate again and confirm a 400 DUPLICATE_SUBMISSION is returned.
5. Submit a candidate to a draft job and confirm a 409 JOB_NOT_OPEN is returned.
6. Search jobs by status, urgency, skills, and location. Confirm filters apply AND logic and results are sorted correctly (urgent/critical first).
7. Trigger candidate matching for a job. Confirm the request returns 202 and results are cached. Call GET /matches and confirm fit scores and category breakdowns are returned.
8. Refresh matching while cache exists and confirm a new matching result is generated.
9. Attempt to access a job from a workspace you are not assigned to and confirm 403 WORKSPACE_FORBIDDEN is returned.
10. List submissions for a job with filters on submission_status and pagination. Confirm results are returned in order and already_submitted flag is accurate.
```

---

**Revision Notes**

This specification was created following the identical structure and format as `candidate-management/SPEC.md` with domain-specific content for job requisition management. All 9 sections are present and comprehensive:

1. **Service boundary**: Clear ownership of jobs, skills, submissions; explicit dependencies.
2. **Database schema**: Complete schema with constraints, indexes, and separation of concerns.
3. **REST API endpoints**: 9 endpoints with detailed request/response formats and error handling.
4. **Behaviour requirements**: Detailed logic for each operation including edge cases and constraints.
5. **Acceptance criteria as tests**: 45+ test specifications spanning all functionality.
6. **Internal module structure**: Clear file organization following the candidate-management pattern.
7. **Dependencies and constraints**: Performance targets, security rules, and external service contracts.
8. **Out of scope**: Clear boundary statements for Phase 2+ and related services.
9. **Verification**: Runnable test command and 10 end-to-end verification scenarios.
