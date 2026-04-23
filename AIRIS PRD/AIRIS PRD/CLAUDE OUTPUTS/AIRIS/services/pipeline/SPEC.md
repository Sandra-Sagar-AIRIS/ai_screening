# Service spec: pipeline

**Version**: 1.0
**Date**: 2026-04-18
**Parent PRD**: AIRIS Phase 1 MVP PRD v1

---

## 1. Service boundary

**Folder**: `pipeline/`

This service owns visual pipeline management: the Kanban-style board where recruiters track candidates through hiring stages per job. No other service writes to pipeline stage or card state directly. All pipeline reads and writes flow through this service's public API.

**Owns**: `pipeline_stages` table, `pipeline_cards` table, `pipeline_stage_history` table.

**Depends on**:

- `candidate-management/` reads candidate profiles for card display, writes stage_change interactions via `add_interaction`
- `job-management/` reads job data for pipeline context

**Depended on by**:

- `analytics/` reads `pipeline_stage_history` for time-in-stage and time-to-fill metrics
- `communication/` listens for stage change events and triggers automated notifications

---

## 2. Database schema

```sql
-- pipeline/schema.sql

CREATE TABLE pipeline_stages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    stage_name VARCHAR(100) NOT NULL,
    stage_order INT NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,           -- TRUE for 'Applied', 'Screening', etc.
    is_escape_stage BOOLEAN DEFAULT FALSE,      -- TRUE for 'Placed' and 'Rejected'
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT pipeline_stages_unique UNIQUE (workspace_id, stage_name)
);

CREATE INDEX idx_pipeline_stages_workspace ON pipeline_stages (workspace_id, stage_order);

CREATE TABLE pipeline_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL,
    candidate_id UUID NOT NULL,
    current_stage_id UUID NOT NULL REFERENCES pipeline_stages(id),
    version INT DEFAULT 1,                      -- Optimistic concurrency control
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT pipeline_cards_unique UNIQUE (job_id, candidate_id)
);

CREATE INDEX idx_pipeline_cards_job ON pipeline_cards (job_id, current_stage_id);
CREATE INDEX idx_pipeline_cards_candidate ON pipeline_cards (candidate_id);

CREATE TABLE pipeline_stage_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL,
    candidate_id UUID NOT NULL,
    from_stage_id UUID REFERENCES pipeline_stages(id),  -- NULL for first stage
    to_stage_id UUID NOT NULL REFERENCES pipeline_stages(id),
    rejection_reason VARCHAR(50),               -- 'not_qualified' | 'salary_mismatch' | 'location_mismatch' | 'no_show' | 'client_declined' | 'candidate_withdrew' | 'other'
    rejection_reason_text TEXT,                 -- optional free-text explanation
    moved_by UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT pipeline_history_rejection_reason_check CHECK (
        (to_stage_id != 'rejected_stage_id') OR (rejection_reason IS NOT NULL)
    )
);

CREATE INDEX idx_pipeline_history_job ON pipeline_stage_history (job_id, created_at DESC);
CREATE INDEX idx_pipeline_history_candidate_job ON pipeline_stage_history (candidate_id, job_id, created_at DESC);

CREATE TABLE pipeline_placements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL,
    candidate_id UUID NOT NULL,
    placed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT pipeline_placements_unique UNIQUE (job_id, candidate_id)
);

CREATE INDEX idx_pipeline_placements_job ON pipeline_placements (job_id);
CREATE INDEX idx_pipeline_placements_candidate ON pipeline_placements (candidate_id);
```

---

## 3. REST API endpoints

All endpoints require authentication. The `Authorization` header carries a JWT issued by `auth/`. The user's role and assigned workspaces are encoded in the token claims.

### 3.1 Get pipeline view for job

```
GET /api/v1/pipelines/{job_id}
```

**Query parameters** (all optional):

| Param | Type | Description |
|-------|------|-------------|
| `include_history` | boolean | If `true`, include stage history for each card (default `false`). |

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "job_id": "job-id-789",
    "job_title": "Senior Backend Engineer",
    "stages": [
      {
        "id": "stage-001",
        "stage_name": "Applied",
        "stage_order": 1,
        "cards": [
          {
            "id": "card-abc",
            "job_id": "job-id-789",
            "candidate_id": "cand-123",
            "candidate_name": "Priya Kumar",
            "candidate_email": "priya.kumar@example.com",
            "candidate_skills": ["Python", "FastAPI"],
            "candidate_location": "Chennai",
            "version": 2,
            "moved_at": "2026-04-18T10:30:00Z"
          }
        ]
      },
      {
        "id": "stage-002",
        "stage_name": "Screening",
        "stage_order": 2,
        "cards": [
          {
            "id": "card-def",
            "job_id": "job-id-789",
            "candidate_id": "cand-456",
            "candidate_name": "Arun Sharma",
            "candidate_email": "arun.sharma@example.com",
            "candidate_skills": ["Python", "Django"],
            "candidate_location": "Bangalore",
            "version": 1,
            "moved_at": "2026-04-17T14:22:00Z"
          }
        ]
      },
      {
        "id": "stage-007",
        "stage_name": "Rejected",
        "stage_order": 7,
        "cards": [
          {
            "id": "card-ghi",
            "job_id": "job-id-789",
            "candidate_id": "cand-789",
            "candidate_name": "Maya Patel",
            "candidate_email": "maya.patel@example.com",
            "candidate_skills": ["Java"],
            "candidate_location": "Delhi",
            "version": 3,
            "moved_at": "2026-04-16T09:15:00Z",
            "rejection_reason": "not_qualified"
          }
        ]
      }
    ]
  }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 404 | `JOB_NOT_FOUND` | Job ID does not exist or user lacks access to the job. |
| 401 | `UNAUTHORIZED` | Missing or invalid auth token. |

### 3.2 Move candidate between stages

```
POST /api/v1/pipelines/{job_id}/move
```

**Request body**:
```json
{
  "candidate_id": "cand-123",
  "to_stage_id": "stage-002",
  "current_version": 2,
  "rejection_reason": null,
  "rejection_reason_text": null
}
```

If moving to a Rejected stage, `rejection_reason` is required. The response includes a `rejection_reason` enum in error messages.

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "card": {
      "id": "card-abc",
      "job_id": "job-id-789",
      "candidate_id": "cand-123",
      "candidate_name": "Priya Kumar",
      "current_stage_id": "stage-002",
      "version": 3,
      "moved_at": "2026-04-18T10:35:00Z"
    },
    "history_entry": {
      "id": "hist-001",
      "from_stage_name": "Applied",
      "to_stage_name": "Screening",
      "rejection_reason": null,
      "moved_by": "rec-user-001",
      "created_at": "2026-04-18T10:35:00Z"
    }
  }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 409 | `CONFLICT_VERSION_MISMATCH` | Card version does not match `current_version`. Another recruiter moved the candidate. Response includes current card state. |
| 400 | `VALIDATION_ERROR` | `to_stage_id` is invalid, or moving to Rejected without `rejection_reason`. Response includes `fields` array with details. |
| 404 | `CANDIDATE_NOT_FOUND` | Candidate does not exist in this job's pipeline. |
| 403 | `FORBIDDEN` | User lacks permission to move candidates in this job's workspace. |
| 401 | `UNAUTHORIZED` | Missing or invalid auth token. |

### 3.3 Get stage configuration for workspace

```
GET /api/v1/workspaces/{workspace_id}/stages
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "workspace_id": "ws-999",
    "stages": [
      {
        "id": "stage-001",
        "stage_name": "Applied",
        "stage_order": 1,
        "is_default": true,
        "is_escape_stage": false
      },
      {
        "id": "stage-002",
        "stage_name": "Screening",
        "stage_order": 2,
        "is_default": true,
        "is_escape_stage": false
      },
      {
        "id": "stage-003",
        "stage_name": "Shortlisted",
        "stage_order": 3,
        "is_default": true,
        "is_escape_stage": false
      },
      {
        "id": "stage-004",
        "stage_name": "Interview",
        "stage_order": 4,
        "is_default": true,
        "is_escape_stage": false
      },
      {
        "id": "stage-005",
        "stage_name": "Offer",
        "stage_order": 5,
        "is_default": true,
        "is_escape_stage": false
      },
      {
        "id": "stage-006",
        "stage_name": "Placed",
        "stage_order": 6,
        "is_default": true,
        "is_escape_stage": true
      },
      {
        "id": "stage-007",
        "stage_name": "Rejected",
        "stage_order": 7,
        "is_default": true,
        "is_escape_stage": true
      }
    ]
  }
}
```

### 3.4 Update stage configuration for workspace

```
PUT /api/v1/workspaces/{workspace_id}/stages
```

**Request body**:
```json
{
  "stages": [
    {
      "id": "stage-001",
      "stage_name": "Applied",
      "stage_order": 1
    },
    {
      "id": "stage-002",
      "stage_name": "Phone Screen",
      "stage_order": 2
    },
    {
      "id": "stage-custom-1",
      "stage_name": "Technical Eval",
      "stage_order": 3
    },
    {
      "id": "stage-006",
      "stage_name": "Placed",
      "stage_order": 4
    },
    {
      "id": "stage-007",
      "stage_name": "Rejected",
      "stage_order": 5
    }
  ]
}
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "workspace_id": "ws-999",
    "stages": [ "...updated stages array..." ]
  }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 400 | `VALIDATION_ERROR` | Missing required stages ('Placed', 'Rejected'), or duplicate stage names, or invalid stage_order sequence. |
| 403 | `FORBIDDEN` | User is not an Admin. Only Admins can modify stage configuration. |
| 401 | `UNAUTHORIZED` | Missing or invalid auth token. |

### 3.5 Get stage change history for job

```
GET /api/v1/pipelines/{job_id}/history?limit=100&offset=0&candidate_id=optional-filter
```

**Query parameters** (all optional):

| Param | Type | Description |
|-------|------|-------------|
| `limit` | int | Results per page (default 50, max 200). |
| `offset` | int | Pagination offset. |
| `candidate_id` | UUID | Filter history to a single candidate. |

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "job_id": "job-id-789",
    "history": [
      {
        "id": "hist-005",
        "candidate_id": "cand-123",
        "candidate_name": "Priya Kumar",
        "from_stage_name": "Screening",
        "to_stage_name": "Shortlisted",
        "rejection_reason": null,
        "moved_by": "rec-user-001",
        "created_at": "2026-04-18T10:35:00Z"
      },
      {
        "id": "hist-004",
        "candidate_id": "cand-456",
        "candidate_name": "Arun Sharma",
        "from_stage_name": "Applied",
        "to_stage_name": "Rejected",
        "rejection_reason": "salary_mismatch",
        "rejection_reason_text": "Candidate asking for 25L, our budget is 20L max",
        "moved_by": "rec-user-002",
        "created_at": "2026-04-18T10:30:00Z"
      }
    ],
    "total_count": 42,
    "limit": 100,
    "offset": 0
  }
}
```

### 3.6 Get stage history for specific candidate in job

```
GET /api/v1/pipelines/{job_id}/candidates/{candidate_id}/history
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "job_id": "job-id-789",
    "candidate_id": "cand-123",
    "candidate_name": "Priya Kumar",
    "history": [
      {
        "id": "hist-003",
        "from_stage_name": "Applied",
        "to_stage_name": "Screening",
        "rejection_reason": null,
        "moved_by": "rec-user-001",
        "created_at": "2026-04-16T14:20:00Z"
      },
      {
        "id": "hist-005",
        "from_stage_name": "Screening",
        "to_stage_name": "Shortlisted",
        "rejection_reason": null,
        "moved_by": "rec-user-001",
        "created_at": "2026-04-18T10:35:00Z"
      }
    ]
  }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 404 | `CANDIDATE_NOT_FOUND` | Candidate is not in this job's pipeline. |
| 401 | `UNAUTHORIZED` | Missing or invalid auth token. |

---

## 4. Behaviour requirements

### get_pipeline_view

- Given a valid `job_id`, returns all stages configured for the job's workspace in `stage_order` sequence. Each stage includes all candidate cards currently in that stage, ordered by `moved_at` (most recent first).
- Each card includes the candidate's name, email, skills (from `candidate-management/`), and location.
- If `include_history=true`, each card also includes the full stage change history for that candidate in this job.
- Returns 404 if the job does not exist or the user lacks access to the job's workspace.

### move_candidate_between_stages

- Given `job_id`, `candidate_id`, `to_stage_id`, and the candidate's current `version`, validates that the card's version matches. If mismatch, returns 409 `CONFLICT_VERSION_MISMATCH` with the current card state and version.
- Validates that `to_stage_id` is a valid stage in the job's workspace.
- If `to_stage_id` is a Rejected escape stage and `rejection_reason` is null or empty, returns 400 `VALIDATION_ERROR` listing `rejection_reason` as a required field. Valid reasons are: `not_qualified`, `salary_mismatch`, `location_mismatch`, `no_show`, `client_declined`, `candidate_withdrew`, `other`.
- If `to_stage_id` is a Placed escape stage, creates a row in `pipeline_placements` with `placed_at = NOW()`. This record is used by `analytics/` for time-to-fill calculation.
- Updates `pipeline_cards` to set `current_stage_id = to_stage_id`, increments `version` by 1, and sets `updated_at = NOW()`.
- Inserts a row into `pipeline_stage_history` with `from_stage_id` (or NULL if moving from Applied), `to_stage_id`, `rejection_reason`, `moved_by`, and `created_at = NOW()`.
- Calls `candidate-management/add_interaction()` with `interaction_type = 'stage_change'` and `content` describing the move (e.g., "Moved from Screening to Shortlisted"). The `metadata` field includes `job_id`, `from_stage`, `to_stage`.
- Returns the updated card and history entry.
- Returns 403 if the user is not in the job's workspace or lacks Recruiter+ role.

### get_stage_configuration

- Returns all stages for the given `workspace_id` in `stage_order` sequence.
- Each stage includes `id`, `stage_name`, `stage_order`, `is_default`, and `is_escape_stage`.
- Default stages are: Applied (1), Screening (2), Shortlisted (3), Interview (4), Offer (5), Placed (6, escape), Rejected (7, escape).

### update_stage_configuration

- Given a list of stages with `stage_name` and `stage_order`, validates that:
  - Both 'Placed' and 'Rejected' escape stages are present.
  - Stage names are unique within the workspace.
  - `stage_order` values are contiguous (1, 2, 3, ... N) with no gaps.
  - The user has `admin` role (from JWT).
- Replaces all non-default stages with the new configuration. Default stages are updated if present in the request.
- All existing `pipeline_cards` retain their current stage assignment. Stage configuration changes do not retroactively move candidates.
- Returns the updated stage list.
- Returns 400 if validation fails. Returns 403 if the user is not an Admin.

### get_stage_change_history

- Returns all stage history entries for the job, ordered by `created_at DESC` (most recent first).
- If `candidate_id` query parameter is present, filters to only that candidate.
- Supports pagination via `limit` and `offset`.
- Includes candidate name, from and to stage names, rejection reason, and who moved the candidate.

### get_candidate_history_in_job

- Returns the complete stage transition history for a specific candidate in a specific job.
- Ordered by `created_at` (chronological order, oldest first, showing the candidate's journey).
- Returns 404 if the candidate is not in the job's pipeline.

---

## 5. Acceptance criteria as tests

```python
# pipeline/tests/test_pipeline_view.py

class TestGetPipelineView:

    def test_returns_all_stages_in_order(self, client, recruiter_token, job_with_candidates):
        """GET /api/v1/pipelines/{job_id} returns stages ordered by stage_order.
        Each stage includes all candidate cards in that stage."""

    def test_cards_include_candidate_details(self, client, recruiter_token, job_with_candidate):
        """A card includes candidate_name, candidate_email, candidate_skills,
        candidate_location from candidate-management/."""

    def test_cards_ordered_by_moved_at(self, client, recruiter_token, job_with_multiple_cards_in_stage):
        """Cards within a stage are ordered by moved_at DESC (most recent first)."""

    def test_include_history_parameter(self, client, recruiter_token, job_with_candidate_and_history):
        """GET with include_history=true includes stage_change history for each card."""

    def test_unauthorized_user_returns_403(self, client, recruiter_token, job_in_different_workspace):
        """GET for a job in a different workspace returns 403 or 404."""


# pipeline/tests/test_move_candidate.py

class TestMoveCandidateBetweenStages:

    def test_valid_move_updates_card_and_creates_history(self, client, recruiter_token, job_with_candidate):
        """POST /move with valid to_stage_id updates pipeline_cards and inserts
        a row in pipeline_stage_history."""

    def test_version_mismatch_returns_409(self, client, recruiter_token, job_with_candidate):
        """POST with current_version=1 when card is at version=3 returns 409
        CONFLICT_VERSION_MISMATCH with current card state."""

    def test_version_incremented_on_move(self, client, recruiter_token, job_with_candidate):
        """After a successful move, the card's version is incremented by 1."""

    def test_rejection_reason_required_for_rejected_stage(self, client, recruiter_token, job_with_candidate):
        """Moving to Rejected stage without rejection_reason returns 400
        VALIDATION_ERROR with rejection_reason in fields."""

    def test_valid_rejection_reasons_only(self, client, recruiter_token, job_with_candidate):
        """Moving to Rejected with rejection_reason='invalid_reason' returns 400.
        Only specific enum values are accepted."""

    def test_placement_record_created_on_placed_move(self, client, recruiter_token, job_with_candidate, db):
        """Moving to Placed stage creates a pipeline_placements row."""

    def test_stage_change_interaction_created(self, client, recruiter_token, job_with_candidate, mock_candidate_mgmt):
        """After move, candidate-management/add_interaction is called
        with type='stage_change'."""

    def test_from_stage_null_on_first_move(self, client, recruiter_token, job_with_candidate_in_applied, db):
        """Moving from Applied for the first time has from_stage_id=NULL
        in the history entry."""

    def test_escape_stages_always_allowed(self, client, recruiter_token, job_with_candidate_in_offer):
        """Can move directly from Offer to Rejected or Placed (escape stages
        are always allowed, regardless of normal stage sequence)."""

    def test_unauthorized_user_cannot_move(self, client, recruiter_token_different_workspace, job_in_other_workspace):
        """POST from a recruiter in a different workspace returns 403."""


# pipeline/tests/test_stage_configuration.py

class TestStageConfiguration:

    def test_get_default_stages(self, client, recruiter_token, workspace):
        """GET /stages returns 7 default stages: Applied, Screening, Shortlisted,
        Interview, Offer, Placed (escape), Rejected (escape)."""

    def test_update_stage_order(self, client, admin_token, workspace):
        """PUT /stages with reordered stages updates stage_order for all stages."""

    def test_add_custom_stage(self, client, admin_token, workspace):
        """PUT /stages with a new custom stage (not default) adds it to the config."""

    def test_remove_custom_stage(self, client, admin_token, workspace):
        """PUT /stages without a previously added custom stage removes it."""

    def test_escape_stages_always_required(self, client, admin_token, workspace):
        """PUT without 'Placed' or 'Rejected' returns 400 VALIDATION_ERROR."""

    def test_stage_order_contiguous_validation(self, client, admin_token, workspace):
        """PUT with stage_order [1, 2, 4] (gap at 3) returns 400 VALIDATION_ERROR."""

    def test_duplicate_stage_names_validation(self, client, admin_token, workspace):
        """PUT with two stages named 'Screening' returns 400 VALIDATION_ERROR."""

    def test_requires_admin_role(self, client, recruiter_token, workspace):
        """PUT /stages from a non-Admin recruiter returns 403."""

    def test_existing_cards_retain_stage(self, client, admin_token, workspace, job_with_candidate):
        """After updating stage config, existing candidate cards stay in their
        current stages. No retroactive moves."""


# pipeline/tests/test_history.py

class TestPipelineHistory:

    def test_get_history_for_job(self, client, recruiter_token, job_with_multiple_moves):
        """GET /history returns all stage changes for the job in reverse
        chronological order (created_at DESC)."""

    def test_filter_by_candidate(self, client, recruiter_token, job_with_multiple_candidates_moved):
        """GET /history?candidate_id={id} returns only moves for that candidate."""

    def test_pagination(self, client, recruiter_token, job_with_many_moves):
        """GET /history?limit=10&offset=20 returns 10 items, total_count
        reflects all moves for the job."""

    def test_candidate_history_in_job(self, client, recruiter_token, job_with_candidate_moved_multiple_times):
        """GET /candidates/{cand_id}/history returns moves for that candidate
        in this job in chronological order (oldest first)."""

    def test_rejection_reason_included_in_history(self, client, recruiter_token, job_with_rejected_candidate):
        """History entry for a Rejected move includes rejection_reason."""

    def test_candidate_not_in_pipeline_returns_404(self, client, recruiter_token, job, candidate_not_in_job):
        """GET /candidates/{cand_id}/history for a candidate not in this job
        returns 404 CANDIDATE_NOT_FOUND."""
```

---

## 6. Internal module structure

```
pipeline/
├── api.py                  # Public interface (FastAPI router + Pydantic models)
├── service.py              # Business logic layer
├── repository.py           # Database queries (SQLAlchemy)
├── models.py               # SQLAlchemy ORM models
├── schemas.py              # Pydantic request/response schemas
├── exceptions.py           # Service-specific exception classes
├── constants.py            # Enums, valid values, config
├── schema.sql              # Database migration source
├── tests/
│   ├── conftest.py         # Fixtures (test DB, mock candidate-management, tokens)
│   ├── test_pipeline_view.py
│   ├── test_move_candidate.py
│   ├── test_stage_configuration.py
│   └── test_history.py
└── README.md               # Developer onboarding for this service
```

Only `api.py` and `schemas.py` are importable by other services. Everything else is internal.

---

## 7. Dependencies and constraints

**Internal service dependencies**:

- `candidate-management/add_interaction(candidate_id, interaction_type='stage_change', content, metadata)`: Called whenever a candidate moves between stages. Must succeed before the move endpoint returns. If the call fails, return 500 (rollback the pipeline card update).
- `job-management/get_job(job_id)`: Called to validate job ID and fetch job title for pipeline context. Must resolve within 1s. Returns 404 if job not found.

**External dependencies**:

- PostgreSQL 15+: Primary data store. Requires `gen_random_uuid()`.

**Performance targets**:

| Operation | Target | Measured at |
|-----------|--------|-------------|
| Get pipeline view | < 500ms | For 50+ candidates across 7 stages |
| Move candidate | < 300ms | Including interaction write to candidate-management |
| Get stage configuration | < 100ms | API response time |
| Update stage configuration | < 200ms | API response time |
| Get history (job) | < 500ms | For 100+ history entries with pagination |
| Get history (candidate in job) | < 200ms | API response time |

**Security**:

- All endpoints require a valid JWT.
- Move operations require `recruiter` or `admin` role and workspace membership.
- Stage configuration updates require `admin` role.
- All write operations generate a history entry (immutable log).

---

## 8. Out of scope

- Automatic stage progression based on time or events. Phase 2.
- Custom validation rules per stage (e.g., "cannot move to Interview without 3+ interactions"). Phase 2.
- Bulk candidate moves (move multiple candidates at once). Phase 2.
- Stage-specific templates or forms. Phase 2.
- Duplicate candidate detection within a pipeline. Owned by `candidate-management/`.
- Email notifications on stage changes. Owned by `communication/`.
- Time-in-stage and time-to-fill analytics. Owned by `analytics/`.
- Job creation and management. Owned by `job-management/`.

---

## 9. Verification

```bash
cd pipeline/
pytest tests/ -v --tb=short
```

All tests must pass. Additionally, verify these end-to-end scenarios manually or via integration tests:

1. View a job's pipeline. Confirm all stages are displayed in order, with candidate cards organized per stage.
2. Drag a candidate from Applied to Screening. Confirm the card moves, the version increments, and the history entry is created.
3. Move a candidate to Rejected. Confirm rejection_reason is required and the history captures the reason.
4. Move a candidate to Placed. Confirm a placement record is created in `pipeline_placements`.
5. Attempt to move a candidate with an outdated version. Confirm 409 CONFLICT_VERSION_MISMATCH is returned with current state.
6. As Admin, update stage configuration by adding a custom stage. Confirm existing candidates remain in their current stages.
7. Get stage history for a job. Confirm all moves are listed in reverse chronological order.
8. Get stage history for a specific candidate in a job. Confirm the timeline shows only moves for that candidate, in chronological order.
9. Attempt to move candidates as a Recruiter without workspace access. Confirm 403 is returned.
10. Verify that a stage_change interaction is written to `candidate-management/` for each move.
```

