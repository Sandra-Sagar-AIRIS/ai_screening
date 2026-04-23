# Service spec: candidate-management

**Version**: 1.0
**Date**: 2026-04-18
**Parent PRD**: AIRIS Phase 1 MVP PRD v1

---

## 1. Service boundary

**Folder**: `candidate-management/`

This service owns all candidate data: profiles, resume file references, skill tags, recruiter notes, interaction history, and duplicate detection. No other service writes to candidate records directly. All reads and writes flow through this service's public API.

**Owns**: `candidates` table, `candidate_interactions` table, `candidate_skills` table, `candidate_audit_log` table.

**Depends on**:

- `ai-services/` for resume parsing (`parse_resume`) and natural language search (`smart_search`)
- `storage/` for S3 file upload and deletion of resume files

**Depended on by**:

- `job-management/` reads candidate profiles when displaying match results
- `pipeline/` reads candidate profiles for pipeline card rendering and writes stage change interactions via this service's `add_interaction` endpoint
- `scheduling/` reads candidate contact details for booking link generation
- `communication/` reads candidate email and interaction timeline
- `analytics/` reads candidate counts, submission counts, and placement records

---

## 2. Database schema

```sql
-- candidate-management/schema.sql

CREATE TABLE candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    email_encrypted BYTEA,                    -- AES-256 encrypted copy for at-rest compliance
    phone VARCHAR(50),
    phone_encrypted BYTEA,
    location VARCHAR(255),
    experience_summary TEXT,
    education TEXT,
    resume_s3_key VARCHAR(500),
    resume_original_filename VARCHAR(255),
    parse_confidence FLOAT,                   -- 0.0 to 1.0, NULL if manually created
    low_confidence_fields TEXT[],             -- array of field names where confidence < 0.7
    notes TEXT,
    is_deleted BOOLEAN DEFAULT FALSE,         -- soft delete flag
    deleted_at TIMESTAMPTZ,
    deleted_by UUID,
    created_by UUID NOT NULL,                 -- recruiter user ID
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT candidates_email_unique UNIQUE (email) WHERE is_deleted = FALSE
);

CREATE INDEX idx_candidates_email ON candidates (email) WHERE is_deleted = FALSE;
CREATE INDEX idx_candidates_location ON candidates (location) WHERE is_deleted = FALSE;
CREATE INDEX idx_candidates_created_at ON candidates (created_at DESC);
CREATE INDEX idx_candidates_is_deleted ON candidates (is_deleted);

CREATE TABLE candidate_skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    skill VARCHAR(100) NOT NULL,
    source VARCHAR(20) DEFAULT 'manual',      -- 'manual' | 'parsed' | 'ai_suggested'
    confidence FLOAT,                          -- NULL for manual, 0.0-1.0 for AI-sourced
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT candidate_skills_unique UNIQUE (candidate_id, skill)
);

CREATE INDEX idx_candidate_skills_skill ON candidate_skills (skill);
CREATE INDEX idx_candidate_skills_candidate ON candidate_skills (candidate_id);

CREATE TABLE candidate_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    interaction_type VARCHAR(30) NOT NULL,     -- 'note' | 'email_sent' | 'email_received' | 'call' | 'stage_change' | 'submission'
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',              -- flexible store for type-specific data (e.g. stage names, job ID)
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_interactions_candidate ON candidate_interactions (candidate_id, created_at DESC);

CREATE TABLE candidate_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID,                         -- NULL after hard delete (ID preserved, PII removed)
    action VARCHAR(50) NOT NULL,               -- 'created' | 'updated' | 'soft_deleted' | 'hard_deleted' | 'merged' | 'accessed'
    performed_by UUID NOT NULL,
    details JSONB DEFAULT '{}',                -- action-specific details (fields changed, merge source, deletion reason)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_candidate ON candidate_audit_log (candidate_id, created_at DESC);
CREATE INDEX idx_audit_action ON candidate_audit_log (action);

CREATE TABLE bulk_upload_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uploaded_by UUID NOT NULL,
    total_files INT NOT NULL,
    successful INT DEFAULT 0,
    failed INT DEFAULT 0,
    pending INT NOT NULL,
    status VARCHAR(20) DEFAULT 'processing',   -- 'processing' | 'completed'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE bulk_upload_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES bulk_upload_jobs(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    status VARCHAR(30) DEFAULT 'pending',      -- 'pending' | 'parsed' | 'duplicate_found' | 'failed'
    candidate_id UUID REFERENCES candidates(id),
    duplicate_candidate_id UUID,               -- existing candidate if duplicate detected
    error_code VARCHAR(50),
    error_message TEXT,
    processed_at TIMESTAMPTZ
);

CREATE INDEX idx_bulk_items_job ON bulk_upload_items (job_id);
```

---

## 3. REST API endpoints

All endpoints require authentication. The `Authorization` header carries a JWT issued by `auth/`. The user's role and assigned workspaces are encoded in the token claims.

### 3.1 Create candidate

```
POST /api/v1/candidates
```

**Request body**:
```json
{
  "first_name": "Priya",
  "last_name": "Kumar",
  "email": "priya.kumar@example.com",
  "phone": "+91-9876543210",
  "location": "Chennai",
  "skills": ["Python", "FastAPI", "PostgreSQL"],
  "notes": "Referred by existing candidate Arun."
}
```

**Success response** (201 Created):
```json
{
  "success": true,
  "data": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "first_name": "Priya",
    "last_name": "Kumar",
    "email": "priya.kumar@example.com",
    "phone": "+91-9876543210",
    "location": "Chennai",
    "skills": ["Python", "FastAPI", "PostgreSQL"],
    "experience_summary": null,
    "education": null,
    "resume_s3_key": null,
    "notes": "Referred by existing candidate Arun.",
    "created_at": "2026-04-18T10:30:00Z",
    "updated_at": "2026-04-18T10:30:00Z",
    "created_by": "rec-user-id-001"
  }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 400 | `VALIDATION_ERROR` | Missing `first_name`, `last_name`, or `email`. Response body includes a `fields` array listing each invalid field and the reason. |
| 409 | `DUPLICATE_EMAIL` | Email already exists for a non-deleted candidate. Response includes `existing_candidate_id`. |
| 401 | `UNAUTHORIZED` | Missing or invalid auth token. |

### 3.2 Upload and parse single resume

```
POST /api/v1/candidates/upload
Content-Type: multipart/form-data
```

**Request**: Form field `file` containing a PDF or DOCX resume.

**Success response** (201 Created):
```json
{
  "success": true,
  "data": {
    "candidate_id": "a1b2c3d4-...",
    "profile": { "...full CandidateProfile..." },
    "parse_confidence": 0.87,
    "low_confidence_fields": ["phone"],
    "duplicate_detected": null
  }
}
```

**Duplicate detected response** (200 OK):
```json
{
  "success": true,
  "data": {
    "candidate_id": null,
    "profile": { "...parsed but not saved..." },
    "parse_confidence": 0.91,
    "low_confidence_fields": [],
    "duplicate_detected": {
      "existing_candidate_id": "existing-id-123",
      "match_reason": "email",
      "existing_profile": { "...existing CandidateProfile..." }
    }
  }
}
```

When a duplicate is detected, the new profile is not saved. The client must call either `POST /api/v1/candidates/merge` or `POST /api/v1/candidates` (with a `force_create=true` query param) to proceed.

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 400 | `INVALID_FILE_FORMAT` | File is not PDF or DOCX. File is not uploaded to S3. |
| 422 | `PARSE_FAILED` | AI parser returned an error or timed out after 30 seconds. File remains in S3 for retry. |
| 413 | `FILE_TOO_LARGE` | File exceeds 10 MB. |

### 3.3 Bulk upload resumes

```
POST /api/v1/candidates/upload/bulk
Content-Type: multipart/form-data
```

**Request**: Multiple files in `files[]` field.

**Success response** (202 Accepted):
```json
{
  "success": true,
  "data": {
    "job_id": "bulk-job-id-456",
    "total_files": 12,
    "status": "processing"
  }
}
```

Returns immediately. Processing is asynchronous via Celery.

### 3.4 Check bulk upload status

```
GET /api/v1/candidates/upload/bulk/{job_id}
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "job_id": "bulk-job-id-456",
    "total_files": 12,
    "successful": 8,
    "failed": 1,
    "pending": 3,
    "status": "processing",
    "results": [
      {
        "filename": "priya_kumar_resume.pdf",
        "status": "parsed",
        "candidate_id": "a1b2c3d4-...",
        "error": null
      },
      {
        "filename": "corrupt_file.doc",
        "status": "failed",
        "candidate_id": null,
        "error": { "code": "INVALID_FILE_FORMAT", "message": ".doc format is not supported. Please convert to .docx." }
      },
      {
        "filename": "arun_sharma_resume.pdf",
        "status": "duplicate_found",
        "candidate_id": null,
        "duplicate_candidate_id": "existing-id-789",
        "error": null
      }
    ]
  }
}
```

### 3.5 Get candidate

```
GET /api/v1/candidates/{candidate_id}
```

**Success response** (200 OK): Returns full `CandidateProfile` wrapped in `ServiceResult`.

**Error**: 404 `CANDIDATE_NOT_FOUND` if the ID does not exist or the candidate is soft-deleted.

### 3.6 Update candidate

```
PATCH /api/v1/candidates/{candidate_id}
```

**Request body**: Partial update. Only fields present in the body are changed.
```json
{
  "location": "Bangalore",
  "skills": ["Python", "FastAPI", "PostgreSQL", "Redis"]
}
```

**Success response** (200 OK): Returns updated `CandidateProfile`.

**Error**: 404 if not found. 409 `DUPLICATE_EMAIL` if changing email to one that already exists.

### 3.7 Search candidates

```
GET /api/v1/candidates/search?query=...&skills=Python,FastAPI&location=Chennai&min_experience=3&max_experience=8&limit=50&offset=0
```

**Query parameters** (all optional):

| Param | Type | Description |
|-------|------|-------------|
| `query` | string | Natural language search (routed to `ai-services/smart_search`). |
| `skills` | comma-separated | Filter by skills. AND logic: candidate must have all listed skills. |
| `location` | string | Filter by location (partial match). |
| `min_experience` | int | Minimum years of experience. |
| `max_experience` | int | Maximum years of experience. |
| `limit` | int | Results per page (default 50, max 200). |
| `offset` | int | Pagination offset. |

If `query` is provided, structured filters are applied as post-filters on the AI-ranked results.

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "candidates": [ "...array of CandidateProfile..." ],
    "total_count": 142,
    "limit": 50,
    "offset": 0
  }
}
```

Soft-deleted candidates are never returned.

### 3.8 Add interaction

```
POST /api/v1/candidates/{candidate_id}/interactions
```

**Request body**:
```json
{
  "interaction_type": "note",
  "content": "Spoke with Priya. Available to start in 30 days. Prefers hybrid roles."
}
```

**Success response** (201 Created): Returns `InteractionRecord`.

**Valid interaction types**: `note`, `email_sent`, `email_received`, `call`, `stage_change`, `submission`.

### 3.9 Get interactions

```
GET /api/v1/candidates/{candidate_id}/interactions?limit=50&offset=0
```

Returns interactions in reverse chronological order.

### 3.10 Merge candidates

```
POST /api/v1/candidates/merge
```

**Request body**:
```json
{
  "primary_candidate_id": "keep-this-id",
  "duplicate_candidate_id": "merge-this-in"
}
```

**Behaviour**:
1. All interactions from the duplicate are reassigned to the primary.
2. Skills from the duplicate that the primary does not already have are added to the primary.
3. The primary's field values are retained where both profiles have data.
4. The duplicate is soft-deleted.
5. An audit log entry is created with action `merged` and details recording both IDs.

**Error**: 404 if either ID not found. 400 `MERGE_CONFLICT` if primary and duplicate are the same ID.

### 3.11 Soft delete candidate

```
DELETE /api/v1/candidates/{candidate_id}
```

Sets `is_deleted = TRUE` and `deleted_at = NOW()`. The profile is hidden from search and all list views but retained in the database. Creates an audit log entry.

**Requires**: Recruiter or Admin role.

### 3.12 Hard delete candidate (GDPR/DPDPA)

```
DELETE /api/v1/candidates/{candidate_id}/permanent
```

**Request body**:
```json
{
  "deletion_reason": "gdpr_request"
}
```

Permanently removes all candidate data: profile row, interactions, skills, S3 resume file. Creates an audit log entry before deletion that records the candidate ID (not PII), reason, and requesting user.

**Requires**: Admin role only. Returns 403 `UNAUTHORIZED` for non-Admin users.

**Valid deletion reasons**: `gdpr_request`, `dpdpa_request`.

---

## 4. Behaviour requirements

### create_candidate

- Given valid input with all required fields (`first_name`, `last_name`, `email`), creates a row in `candidates`, inserts rows into `candidate_skills` for each skill, creates an audit log entry with action `created`, and returns the complete profile.
- Given an email that matches an existing non-deleted candidate, returns 409 with `DUPLICATE_EMAIL` and the existing candidate's ID. Does not create any records.
- Given whitespace-only `first_name` or `last_name`, returns 400 `VALIDATION_ERROR`. The validation is performed before any database write.
- Given an email with mixed case (e.g. `Priya.Kumar@Example.com`), normalises it to lowercase before storage and duplicate checking.

### upload_and_parse_resume

- Given a valid PDF, uploads to S3 at path `resumes/{generated_candidate_id}/{original_filename}`, calls `ai-services/parse_resume()` with the S3 key, receives structured data, creates a candidate profile, and returns the parsed result.
- If `ai-services/parse_resume()` returns confidence < 0.7 for any field, the field is still populated with the parsed value, but the field name is listed in `low_confidence_fields`. The profile is created. The front end uses `low_confidence_fields` to render a review indicator.
- If the parsed email matches an existing non-deleted candidate, the profile is not saved. The response includes `duplicate_detected` with the existing profile. The caller decides next steps (merge or force create).
- If the parsed phone matches an existing candidate but the email does not, the response still includes `duplicate_detected` with `match_reason: "phone"`. The profile is not saved.
- Given a file larger than 10 MB, rejects immediately with 413. No S3 upload occurs.
- If `ai-services/parse_resume()` does not respond within 30 seconds, the request returns 422 `PARSE_FAILED`. The file remains in S3 so the user can retry without re-uploading.

### bulk_upload_resumes

- Given N files, creates a `bulk_upload_jobs` row and N `bulk_upload_items` rows, enqueues N Celery tasks, and returns the job ID within 2 seconds regardless of N.
- Each file is processed independently by a separate Celery task. A failure on file 3 has no effect on files 1, 2, 4, etc.
- As each task completes, it updates its `bulk_upload_items` row and increments the parent job's `successful` or `failed` counter atomically.
- When all items are processed (pending = 0), the job's status is set to `completed` and `completed_at` is timestamped.
- Duplicate detection works the same as single upload: duplicates get status `duplicate_found` and are not auto-merged.

### search_candidates

- Given structured filters only, performs a PostgreSQL query with AND logic. Skills filter uses a subquery on `candidate_skills`. Location filter uses case-insensitive `ILIKE '%{location}%'`. Experience filter uses a text-extraction heuristic on `experience_summary` (Phase 1 simplification; Phase 2 adds a structured `years_of_experience` column).
- Given a `query` string, calls `ai-services/smart_search()` which returns an ordered list of candidate IDs with relevance scores. This service hydrates those IDs into full profiles, then applies any structured filters as post-filters.
- Results never include candidates where `is_deleted = TRUE`.
- Given no parameters, returns the 50 most recently created candidates.

### merge_candidates

- The primary profile's field values are kept wherever both profiles have a non-null value for the same field. The duplicate's values fill in nulls on the primary.
- All `candidate_interactions` rows for the duplicate are re-pointed to the primary's `candidate_id`.
- All `candidate_skills` rows from the duplicate that do not conflict with the primary's existing skills (same skill name) are re-pointed. Conflicts are dropped (primary's version kept).
- The duplicate candidate is soft-deleted after all data is moved.
- The entire operation runs in a single database transaction. If any step fails, the transaction rolls back and returns 500.

### hard_delete_candidate

- Deletes the S3 resume file first (via `storage/`). If S3 deletion fails, the operation aborts and returns 500 (no partial deletion).
- Creates an audit log entry before deleting database rows. The audit entry uses the candidate ID but does not store any PII fields.
- Deletes all rows from `candidate_interactions`, `candidate_skills`, and `candidates` for the given ID. This is a CASCADE from the `candidates` primary key.
- If the candidate is already soft-deleted, hard delete still proceeds.
- Returns 403 if the requesting user's role (from JWT claims) is not `admin`.

---

## 5. Acceptance criteria as tests

```python
# candidate-management/tests/test_create.py

class TestCreateCandidate:

    def test_valid_input_creates_profile(self, client, recruiter_token):
        """POST /api/v1/candidates with valid first_name, last_name, email
        returns 201 with a profile containing a UUID id, correct field values,
        and timestamps within the last 5 seconds."""

    def test_skills_are_stored(self, client, recruiter_token):
        """POST with skills=['Python', 'FastAPI'] creates corresponding
        candidate_skills rows with source='manual'."""

    def test_duplicate_email_returns_409(self, client, recruiter_token, existing_candidate):
        """POST with an email matching an existing non-deleted candidate
        returns 409 with error code DUPLICATE_EMAIL and existing_candidate_id."""

    def test_email_normalised_to_lowercase(self, client, recruiter_token):
        """POST with email='Priya.Kumar@Example.COM' stores 'priya.kumar@example.com'
        and duplicate check uses the normalised form."""

    def test_empty_first_name_returns_400(self, client, recruiter_token):
        """POST with first_name='   ' returns 400 VALIDATION_ERROR
        with 'first_name' in the fields array."""

    def test_audit_log_created(self, client, recruiter_token, db):
        """After successful creation, candidate_audit_log has one row
        with action='created' and the recruiter's user ID."""


# candidate-management/tests/test_upload.py

class TestUploadResume:

    def test_valid_pdf_creates_profile(self, client, recruiter_token, mock_ai_parser):
        """POST /api/v1/candidates/upload with a valid PDF returns 201
        with a candidate profile and parse_confidence > 0."""

    def test_s3_key_follows_convention(self, client, recruiter_token, mock_ai_parser, mock_s3):
        """The resume is stored at resumes/{candidate_id}/{original_filename}."""

    def test_low_confidence_fields_flagged(self, client, recruiter_token, mock_ai_parser_low_confidence):
        """When parser returns confidence < 0.7 for 'phone', the response
        includes 'phone' in low_confidence_fields and the field is still populated."""

    def test_duplicate_by_email_not_saved(self, client, recruiter_token, existing_candidate, mock_ai_parser):
        """When parsed email matches existing candidate, response has
        duplicate_detected with existing profile, and no new candidate row exists."""

    def test_duplicate_by_phone_detected(self, client, recruiter_token, existing_candidate_with_phone, mock_ai_parser):
        """When parsed phone matches existing candidate, duplicate_detected
        includes match_reason='phone'."""

    def test_unsupported_format_returns_400(self, client, recruiter_token):
        """Uploading a .txt file returns 400 INVALID_FILE_FORMAT.
        No S3 upload occurs (mock_s3.upload not called)."""

    def test_file_too_large_returns_413(self, client, recruiter_token):
        """Uploading a 15 MB file returns 413 FILE_TOO_LARGE."""

    def test_parser_timeout_returns_422(self, client, recruiter_token, mock_ai_parser_timeout):
        """When ai-services times out, returns 422 PARSE_FAILED.
        S3 file still exists (not cleaned up)."""


# candidate-management/tests/test_bulk_upload.py

class TestBulkUpload:

    def test_returns_job_id_immediately(self, client, recruiter_token):
        """POST /api/v1/candidates/upload/bulk with 10 files returns 202
        within 2 seconds with a job_id and status='processing'."""

    def test_individual_failure_does_not_block_others(self, client, recruiter_token, celery_worker):
        """Given 5 files where file 3 is corrupt, after processing completes
        the job shows successful=4, failed=1."""

    def test_duplicate_flagged_without_merge(self, client, recruiter_token, existing_candidate, celery_worker):
        """A file whose parsed email matches existing candidate gets
        status='duplicate_found'. The candidates table has no new row."""

    def test_job_status_completed_when_done(self, client, recruiter_token, celery_worker):
        """After all items are processed, GET /bulk/{job_id} shows
        status='completed' and pending=0."""


# candidate-management/tests/test_search.py

class TestSearchCandidates:

    def test_filter_by_skills_and_logic(self, client, recruiter_token, candidates_with_skills):
        """GET /search?skills=Python,FastAPI returns only candidates
        who have both Python AND FastAPI in their skills."""

    def test_excludes_soft_deleted(self, client, recruiter_token, soft_deleted_candidate):
        """A soft-deleted candidate matching the query does not appear in results."""

    def test_smart_search_natural_language(self, client, recruiter_token, mock_ai_smart_search):
        """GET /search?query='Java developers in Bangalore with 5+ years'
        calls ai-services/smart_search and returns results in ranked order."""

    def test_pagination(self, client, recruiter_token, many_candidates):
        """GET /search?limit=20&offset=40 returns 20 candidates,
        total_count reflects the full matching set."""

    def test_no_params_returns_recent(self, client, recruiter_token, many_candidates):
        """GET /search with no parameters returns the 50 most recently
        created candidates ordered by created_at DESC."""

    def test_location_partial_match(self, client, recruiter_token, candidates_with_locations):
        """GET /search?location=chen matches candidates in 'Chennai'
        (case-insensitive partial match)."""


# candidate-management/tests/test_interactions.py

class TestInteractions:

    def test_add_note(self, client, recruiter_token, candidate):
        """POST /candidates/{id}/interactions with type='note'
        returns 201 with the interaction record."""

    def test_timeline_reverse_chronological(self, client, recruiter_token, candidate_with_interactions):
        """GET /candidates/{id}/interactions returns interactions
        ordered most recent first."""

    def test_interaction_on_nonexistent_candidate(self, client, recruiter_token):
        """POST interaction on a non-existent candidate ID returns 404."""


# candidate-management/tests/test_merge.py

class TestMergeCandidates:

    def test_interactions_combined(self, client, admin_token, primary_with_3_interactions, duplicate_with_2_interactions):
        """After merge, primary candidate has 5 interactions."""

    def test_primary_fields_retained(self, client, admin_token, primary_in_chennai, duplicate_in_bangalore):
        """After merge, primary's location is still 'Chennai'."""

    def test_duplicate_fills_null_fields(self, client, admin_token, primary_without_phone, duplicate_with_phone):
        """After merge, primary's phone is populated from duplicate."""

    def test_skills_merged_without_duplicates(self, client, admin_token):
        """Primary has [Python, FastAPI], duplicate has [Python, Redis].
        After merge, primary has [Python, FastAPI, Redis]."""

    def test_duplicate_soft_deleted(self, client, admin_token, primary, duplicate):
        """After merge, GET /candidates/{duplicate_id} returns 404."""

    def test_audit_log_created(self, client, admin_token, primary, duplicate, db):
        """After merge, audit log has action='merged' with both candidate IDs."""

    def test_nonexistent_candidate_returns_404(self, client, admin_token):
        """Merge with a non-existent duplicate_candidate_id returns 404."""

    def test_same_id_returns_400(self, client, admin_token, candidate):
        """Merge where primary and duplicate are the same ID returns 400 MERGE_CONFLICT."""

    def test_transaction_rollback_on_failure(self, client, admin_token, primary, duplicate, db_failure_mock):
        """If the database fails mid-merge, no data is moved and both
        candidates remain unchanged."""


# candidate-management/tests/test_delete.py

class TestSoftDelete:

    def test_soft_delete_hides_from_search(self, client, recruiter_token, candidate):
        """After DELETE /candidates/{id}, the candidate no longer
        appears in search results."""

    def test_soft_delete_returns_404_on_get(self, client, recruiter_token, candidate):
        """After soft delete, GET /candidates/{id} returns 404."""

    def test_soft_delete_preserves_data(self, client, recruiter_token, candidate, db):
        """After soft delete, the candidates row still exists with
        is_deleted=TRUE and deleted_at set."""


class TestHardDelete:

    def test_removes_all_data(self, client, admin_token, candidate_with_interactions, mock_s3):
        """After permanent delete, no candidates, candidate_interactions,
        or candidate_skills rows exist for this ID. S3 delete was called."""

    def test_audit_log_before_deletion(self, client, admin_token, candidate, db):
        """After permanent delete, audit log has action='hard_deleted'
        with deletion_reason and no PII."""

    def test_requires_admin_role(self, client, recruiter_token, candidate):
        """DELETE /candidates/{id}/permanent with recruiter token returns 403."""

    def test_valid_deletion_reasons_only(self, client, admin_token, candidate):
        """deletion_reason='user_request' returns 400. Only 'gdpr_request'
        and 'dpdpa_request' are accepted."""

    def test_s3_failure_aborts_deletion(self, client, admin_token, candidate, mock_s3_failure):
        """If S3 deletion fails, the database rows are not deleted
        and the response is 500."""
```

---

## 6. Internal module structure

```
candidate-management/
├── api.py                  # Public interface (FastAPI router + Pydantic models)
├── service.py              # Business logic layer
├── repository.py           # Database queries (SQLAlchemy)
├── models.py               # SQLAlchemy ORM models
├── schemas.py              # Pydantic request/response schemas
├── tasks.py                # Celery tasks (bulk upload processing)
├── exceptions.py           # Service-specific exception classes
├── constants.py            # Enums, valid values, config
├── schema.sql              # Database migration source
├── tests/
│   ├── conftest.py         # Fixtures (test DB, mock S3, mock AI, tokens)
│   ├── test_create.py
│   ├── test_upload.py
│   ├── test_bulk_upload.py
│   ├── test_search.py
│   ├── test_interactions.py
│   ├── test_merge.py
│   └── test_delete.py
└── README.md               # Developer onboarding for this service
```

Only `api.py` and `schemas.py` are importable by other services. Everything else is internal.

---

## 7. Dependencies and constraints

**Internal service dependencies**:

- `ai-services/parse_resume(s3_key: str) -> ParsedResume`: Called during single and bulk upload. Must handle timeout (30s) and service unavailability gracefully.
- `ai-services/smart_search(query: str, limit: int) -> list[ScoredCandidateId]`: Called during natural language search. Must handle timeout (3s) and return empty results on failure.
- `storage/upload(file_bytes, s3_key) -> str`: Called to store resume files. Returns the confirmed S3 key.
- `storage/delete(s3_key) -> bool`: Called during hard delete. Must succeed before database deletion proceeds.

**External dependencies**:

- PostgreSQL 15+: Primary data store. Requires `gen_random_uuid()` (pgcrypto or built-in).
- Redis + Celery: Async task queue for bulk uploads.
- AWS S3: Resume file storage at bucket `airis-resumes-{environment}`.

**Performance targets**:

| Operation | Target | Measured at |
|-----------|--------|-------------|
| Create candidate | < 200ms | API response time |
| Single resume upload + parse | < 30s | End-to-end including AI call |
| Bulk upload acceptance | < 2s | API response (processing is async) |
| Search (structured filters) | < 500ms | For up to 10,000 candidates |
| Search (smart/NLP) | < 3s | Including AI service round-trip |
| Get candidate | < 100ms | API response time |
| Merge candidates | < 1s | Including transaction commit |

**Security**:

- All endpoints require a valid JWT.
- Hard delete requires `role: admin` in JWT claims.
- Candidate email and phone are encrypted at rest using AES-256. Decryption happens at the application layer for search and display.
- All write operations (create, update, delete, merge) generate an audit log entry.

---

## 8. Out of scope

- Fuzzy duplicate detection (name similarity, resume content fingerprinting). Phase 2.
- Candidate self-service profile management. Phase 2+.
- Resume versioning (multiple resume uploads per candidate tracked over time). Phase 2.
- Candidate-job matching logic. Owned by `ai-services/`. This service provides candidate data.
- Pipeline stage management. Owned by `pipeline/`. That service calls `add_interaction` here when stages change.
- Email sending and receiving. Owned by `communication/`. That service calls `add_interaction` here to log emails.
- Structured `years_of_experience` field (currently extracted heuristically from `experience_summary`). Phase 2 adds a dedicated column with AI extraction.

---

## 9. Verification

```bash
cd candidate-management/
pytest tests/ -v --tb=short
```

All tests must pass. Additionally, verify these end-to-end scenarios manually or via integration tests:

1. Create a candidate manually, retrieve it by ID, update the location, and confirm the update is reflected.
2. Upload a PDF resume. Confirm the profile is created with parsed skills, the resume file exists in S3, and the parse confidence is recorded.
3. Upload a resume whose email matches an existing candidate. Confirm the duplicate is detected and no new profile is created.
4. Bulk upload 5 files (including one corrupt .doc). Confirm the job completes with 4 successful and 1 failed, and the failed item has a clear error code.
5. Search for candidates by skill. Confirm results include only candidates with that skill and exclude soft-deleted candidates.
6. Search using natural language ('Python developers in Chennai'). Confirm results are returned in ranked order.
7. Merge two candidates. Confirm interactions are combined, primary fields are retained, duplicate is soft-deleted, and the audit log records the merge.
8. Hard delete a candidate as Admin. Confirm the S3 file is removed, all database rows are gone, and the audit log entry exists.
9. Attempt hard delete as Recruiter. Confirm 403 is returned and no data is deleted.
