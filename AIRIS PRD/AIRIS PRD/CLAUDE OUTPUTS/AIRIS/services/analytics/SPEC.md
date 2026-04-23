# Service spec: analytics

**Version**: 1.0
**Date**: 2026-04-18
**Parent PRD**: AIRIS Phase 1 MVP PRD v1

---

## 1. Service boundary

**Folder**: `analytics/`

This service owns all real-time operational dashboard data and auto-tracked KPI calculations. No other service writes to analytics tables. The analytics service reads from upstream services and computes aggregated metrics on demand or from cache. All reads flow through this service's public API.

**Owns**: `dashboard_snapshots` table, `placement_records` table, `metric_cache` table.

**Depends on**:

- `candidate-management/` reads candidate counts and candidate IDs for pipeline analysis
- `job-management/` reads job counts, submission counts, and job creation timestamps
- `pipeline/` reads stage history and placement records (when candidates reach 'Placed' stage)
- `scheduling/` reads interview counts and scheduled interview timestamps
- `auth/` reads user activity data and recruiter assignments

**Depended on by**:

- Frontend dashboard consumes all endpoints from this service to render the operational UI

---

## 2. Database schema

```sql
-- analytics/schema.sql

CREATE TABLE dashboard_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    snapshot_timestamp TIMESTAMPTZ DEFAULT NOW(),
    recruiter_id UUID,                           -- NULL for workspace-wide snapshots
    open_jobs_count INT DEFAULT 0,
    open_jobs_by_urgency JSONB DEFAULT '{}',    -- {"high": 3, "medium": 5, "low": 2}
    candidates_in_pipeline_count INT DEFAULT 0,
    candidates_by_stage JSONB DEFAULT '{}',     -- {"Applied": 12, "Shortlisted": 5, "Interviewing": 3}
    interviews_scheduled_this_week INT DEFAULT 0,
    placements_this_week INT DEFAULT 0,
    placements_this_month INT DEFAULT 0,
    placements_this_quarter INT DEFAULT 0,
    time_to_shortlist_days FLOAT,                -- rolling 30-day average
    time_to_shortlist_trend VARCHAR(20),         -- 'improving' | 'stable' | 'declining'
    time_to_fill_days FLOAT,                     -- rolling 30-day average
    time_to_fill_trend VARCHAR(20),
    has_data BOOLEAN DEFAULT FALSE,              -- false for new accounts
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT dashboard_snapshots_pkey PRIMARY KEY (id)
);

CREATE INDEX idx_dashboard_workspace_time ON dashboard_snapshots (workspace_id, snapshot_timestamp DESC);
CREATE INDEX idx_dashboard_recruiter_time ON dashboard_snapshots (recruiter_id, snapshot_timestamp DESC) WHERE recruiter_id IS NOT NULL;

CREATE TABLE placement_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    job_id UUID NOT NULL,
    candidate_id UUID NOT NULL,
    recruiter_id UUID NOT NULL,
    job_created_at TIMESTAMPTZ NOT NULL,
    placed_at TIMESTAMPTZ NOT NULL,             -- timestamp when candidate moved to 'Placed' stage
    time_to_fill_days FLOAT,                    -- calculated from job_created_at to placed_at
    job_title VARCHAR(255),
    candidate_name VARCHAR(255),
    placement_week INT,                          -- ISO week number for grouping
    placement_month INT,
    placement_quarter INT,
    placement_year INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT placement_records_pkey PRIMARY KEY (id)
);

CREATE INDEX idx_placement_workspace ON placement_records (workspace_id);
CREATE INDEX idx_placement_recruiter ON placement_records (recruiter_id);
CREATE INDEX idx_placement_job ON placement_records (job_id);
CREATE INDEX idx_placement_candidate ON placement_records (candidate_id);
CREATE INDEX idx_placement_date ON placement_records (placed_at DESC);

CREATE TABLE shortlist_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    job_id UUID NOT NULL,
    candidate_id UUID NOT NULL,
    recruiter_id UUID NOT NULL,
    job_created_at TIMESTAMPTZ NOT NULL,
    shortlisted_at TIMESTAMPTZ NOT NULL,        -- timestamp when candidate moved to 'Shortlisted' stage
    time_to_shortlist_days FLOAT,               -- calculated from job_created_at to shortlisted_at
    job_title VARCHAR(255),
    candidate_name VARCHAR(255),
    shortlist_week INT,
    shortlist_month INT,
    shortlist_year INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT shortlist_records_pkey PRIMARY KEY (id)
);

CREATE INDEX idx_shortlist_workspace ON shortlist_records (workspace_id);
CREATE INDEX idx_shortlist_recruiter ON shortlist_records (recruiter_id);
CREATE INDEX idx_shortlist_job ON shortlist_records (job_id);
CREATE INDEX idx_shortlist_date ON shortlist_records (shortlisted_at DESC);

CREATE TABLE recruiter_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    recruiter_id UUID NOT NULL,
    metric_period_start TIMESTAMPTZ NOT NULL,
    metric_period_end TIMESTAMPTZ NOT NULL,
    candidates_added INT DEFAULT 0,
    submissions_made INT DEFAULT 0,
    interviews_scheduled INT DEFAULT 0,
    placements_completed INT DEFAULT 0,
    avg_time_to_shortlist_days FLOAT,
    avg_time_to_fill_days FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT recruiter_metrics_unique UNIQUE (recruiter_id, metric_period_start, metric_period_end)
);

CREATE INDEX idx_recruiter_metrics_workspace ON recruiter_metrics (workspace_id);
CREATE INDEX idx_recruiter_metrics_recruiter ON recruiter_metrics (recruiter_id);
CREATE INDEX idx_recruiter_metrics_period ON recruiter_metrics (metric_period_start DESC, metric_period_end DESC);

CREATE TABLE metric_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key VARCHAR(500) NOT NULL UNIQUE,     -- e.g., 'dashboard:workspace:uuid:period'
    cached_data JSONB NOT NULL,
    cache_version INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,            -- 5 minutes after creation
    CONSTRAINT metric_cache_unique_key UNIQUE (cache_key)
);

CREATE INDEX idx_metric_cache_expires ON metric_cache (expires_at);
```

---

## 3. REST API endpoints

All endpoints require authentication. The `Authorization` header carries a JWT issued by `auth/`. The user's role and assigned workspaces are encoded in the token claims.

### 3.1 Get dashboard data

```
GET /api/v1/analytics/dashboard
```

**Query parameters** (all optional):

| Param | Type | Description |
|-------|------|-------------|
| `workspace_id` | UUID | Filter to specific workspace. Defaults to user's primary workspace. |
| `recruiter_id` | UUID | Filter to recruiter's own metrics. Recruiters can only view their own; admins can view any. |
| `date_from` | ISO 8601 | Start date for period analysis (default: 30 days ago). |
| `date_to` | ISO 8601 | End date for period analysis (default: today). |

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "has_data": true,
    "workspace_id": "workspace-uuid-123",
    "snapshot_timestamp": "2026-04-18T10:30:00Z",
    "open_jobs": {
      "count": 15,
      "by_urgency": {
        "high": 3,
        "medium": 7,
        "low": 5
      }
    },
    "candidates_in_pipeline": {
      "count": 47,
      "by_stage": {
        "Applied": 20,
        "Shortlisted": 15,
        "Interviewing": 8,
        "Offered": 4
      }
    },
    "interviews_scheduled_this_week": 12,
    "placements": {
      "this_week": 2,
      "this_month": 8,
      "this_quarter": 24
    },
    "time_to_shortlist": {
      "days": 4.2,
      "trend": "improving",
      "previous_period_days": 5.1
    },
    "time_to_fill": {
      "days": 18.5,
      "trend": "stable",
      "previous_period_days": 18.3
    },
    "recruiter_leaderboard": [
      {
        "recruiter_id": "recruiter-001",
        "recruiter_name": "Arun Sharma",
        "placements_this_period": 5,
        "submissions_this_period": 42,
        "interviews_scheduled": 8,
        "avg_time_to_shortlist_days": 3.8
      },
      {
        "recruiter_id": "recruiter-002",
        "recruiter_name": "Priya Kumar",
        "placements_this_period": 4,
        "submissions_this_period": 38,
        "interviews_scheduled": 6,
        "avg_time_to_shortlist_days": 4.5
      }
    ]
  }
}
```

**Empty state response** (200 OK, `has_data: false`):
```json
{
  "success": true,
  "data": {
    "has_data": false,
    "workspace_id": "workspace-uuid-123",
    "suggested_actions": [
      "create_workspace_settings",
      "create_job",
      "upload_candidates"
    ]
  }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 401 | `UNAUTHORIZED` | Missing or invalid auth token. |
| 403 | `FORBIDDEN` | Recruiter attempting to access a different workspace or recruiter_id they're not assigned to. |
| 404 | `WORKSPACE_NOT_FOUND` | workspace_id does not exist or user has no access. |

### 3.2 Get recruiter productivity table

```
GET /api/v1/analytics/recruiters
```

**Query parameters** (all optional):

| Param | Type | Description |
|-------|------|-------------|
| `workspace_id` | UUID | Filter to specific workspace (required for non-admin users). |
| `date_from` | ISO 8601 | Start date for metrics (default: 30 days ago). |
| `date_to` | ISO 8601 | End date for metrics (default: today). |
| `order_by` | string | Sort column: 'placements' (default), 'submissions', 'interviews', 'time_to_shortlist'. |
| `limit` | int | Results per page (default 50, max 200). |
| `offset` | int | Pagination offset (default 0). |

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "recruiters": [
      {
        "recruiter_id": "recruiter-001",
        "recruiter_name": "Arun Sharma",
        "candidates_added": 12,
        "submissions_made": 42,
        "interviews_scheduled": 8,
        "placements_completed": 5,
        "avg_time_to_shortlist_days": 3.8,
        "avg_time_to_fill_days": 16.2
      },
      {
        "recruiter_id": "recruiter-002",
        "recruiter_name": "Priya Kumar",
        "candidates_added": 10,
        "submissions_made": 38,
        "interviews_scheduled": 6,
        "placements_completed": 4,
        "avg_time_to_shortlist_days": 4.5,
        "avg_time_to_fill_days": 19.0
      }
    ],
    "total_count": 2,
    "limit": 50,
    "offset": 0
  }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 403 | `FORBIDDEN` | Recruiter role does not have workspace access. Admins can see all workspaces. |

### 3.3 Get individual recruiter metrics

```
GET /api/v1/analytics/recruiters/{recruiter_id}
```

**Query parameters** (all optional):

| Param | Type | Description |
|-------|------|-------------|
| `workspace_id` | UUID | Filter to specific workspace (default: primary workspace). |
| `date_from` | ISO 8601 | Start date for metrics (default: 30 days ago). |
| `date_to` | ISO 8601 | End date for metrics (default: today). |

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "recruiter_id": "recruiter-001",
    "recruiter_name": "Arun Sharma",
    "workspace_id": "workspace-uuid-123",
    "metric_period": {
      "start": "2026-03-19T00:00:00Z",
      "end": "2026-04-18T23:59:59Z"
    },
    "candidates_added": 12,
    "submissions_made": 42,
    "interviews_scheduled": 8,
    "placements_completed": 5,
    "avg_time_to_shortlist_days": 3.8,
    "avg_time_to_fill_days": 16.2,
    "submissions_by_week": [
      { "week": 15, "submissions": 11 },
      { "week": 16, "submissions": 13 },
      { "week": 17, "submissions": 10 },
      { "week": 18, "submissions": 8 }
    ]
  }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 404 | `RECRUITER_NOT_FOUND` | recruiter_id does not exist. |
| 403 | `FORBIDDEN` | Recruiter attempting to view metrics for a different recruiter. |

### 3.4 Get job-level metrics

```
GET /api/v1/analytics/jobs/{job_id}/metrics
```

**Query parameters** (all optional):

| Param | Type | Description |
|-------|------|-------------|
| `date_from` | ISO 8601 | For filtering related activities (default: job creation date). |

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "job_id": "job-uuid-456",
    "job_title": "Senior Backend Engineer",
    "workspace_id": "workspace-uuid-123",
    "recruiter_id": "recruiter-001",
    "job_created_at": "2026-03-15T10:00:00Z",
    "time_to_shortlist_days": 4,
    "time_to_fill_days": 18,
    "first_placed_at": "2026-04-02T14:30:00Z",
    "total_submissions": 23,
    "candidates_by_stage": {
      "Applied": 5,
      "Shortlisted": 3,
      "Interviewing": 1,
      "Offered": 1,
      "Placed": 1
    },
    "submissions_by_week": [
      { "week": 11, "submissions": 8 },
      { "week": 12, "submissions": 10 },
      { "week": 13, "submissions": 5 }
    ]
  }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 404 | `JOB_NOT_FOUND` | job_id does not exist. |

### 3.5 Force cache refresh

```
POST /api/v1/analytics/refresh
```

**Request body** (optional):
```json
{
  "workspace_id": "workspace-uuid-123"
}
```

If `workspace_id` is omitted, refreshes all workspaces (admin only).

**Success response** (202 Accepted):
```json
{
  "success": true,
  "data": {
    "refresh_job_id": "refresh-job-001",
    "status": "queued",
    "workspace_id": "workspace-uuid-123"
  }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 403 | `FORBIDDEN` | Non-admin user attempting to refresh. |
| 404 | `WORKSPACE_NOT_FOUND` | workspace_id does not exist. |

---

## 4. Behaviour requirements

### dashboard_data

- Given a valid workspace_id and no recruiter_id filter, returns aggregated metrics for the entire workspace (all recruiters' submissions, placements, etc.).
- Given a valid recruiter_id filter, returns metrics filtered to submissions/placements/interviews created by that recruiter. Admins can filter on any recruiter; recruiters can only filter on themselves.
- Given no workspace_id, defaults to the user's primary workspace (from JWT claims).
- Given date_from and date_to, calculates rolling averages (time_to_shortlist, time_to_fill) and counts (placements_this_week, etc.) within that date range. Trend indicators compare the current period's average against the previous period of the same length.
- Given a new workspace with no candidates, jobs, or submissions, returns `has_data: false` with `suggested_actions: ['create_workspace_settings', 'create_job', 'upload_candidates']`.
- Returns cached data by default (< 100ms response). The cache is refreshed every 5 minutes via Celery beat and is at most 5 minutes stale. If the client has reason to believe data is stale, they can call POST /refresh to force an immediate recalculation.
- Trend calculation: compare current 30-day average against previous 30-day average. If current is >10% better, trend is 'improving'. If current is >10% worse, trend is 'declining'. Otherwise 'stable'.
- Recruiter leaderboard is ranked by placements_completed (descending), then by submissions_made (descending). Returns top 10 by default.
- Client viewers (role: client_viewer) receive a simplified dashboard with no recruiter leaderboard, only workspace-level metrics.

### recruiter_productivity_table

- Returns all recruiters in the specified workspace, ranked by the `order_by` parameter.
- Supports pagination via `limit` and `offset`. Default limit is 50.
- Non-admin recruiters can only view their own workspace.
- Metrics are calculated from placement_records and recruiter_metrics tables for the specified date range.

### recruiter_individual_metrics

- Given a recruiter_id, returns detailed metrics for that recruiter for the specified date range (default: last 30 days).
- Includes a week-by-week breakdown of submissions and placements.
- Recruiter role can only view own metrics (own recruiter_id from JWT). Returns 403 if attempting to view another recruiter.
- Admin role can view any recruiter's metrics.

### job_metrics

- Given a job_id, returns time_to_shortlist and time_to_fill calculated from the job's creation timestamp to the first candidate reaching 'Shortlisted' and 'Placed' stages, respectively.
- Returns total_submissions count (distinct candidates submitted to this job).
- Returns candidates grouped by pipeline stage for this specific job.
- If job has never had a shortlist or placement, the corresponding time fields are NULL.

### cache_refresh

- Forces a recalculation of all metrics for the specified workspace.
- Enqueues a Celery task that recalculates placement_records, shortlist_records, recruiter_metrics, and invalidates all relevant cache entries.
- Returns immediately (202 Accepted) with a refresh_job_id. The client can poll or use WebSocket to monitor progress.
- Only admin role can force a global refresh (all workspaces). Recruiters cannot refresh.

---

## 5. Acceptance criteria as tests

```python
# analytics/tests/test_dashboard.py

class TestDashboardData:

    def test_returns_aggregated_metrics(self, client, admin_token, workspace_with_jobs_and_candidates):
        """GET /api/v1/analytics/dashboard returns aggregated metrics including
        open_jobs_count, candidates_in_pipeline count by stage, and placements_this_week."""

    def test_filters_by_workspace(self, client, recruiter_token, workspace_a, workspace_b):
        """GET /dashboard?workspace_id=workspace-a returns metrics only for workspace A.
        Metrics for workspace B are excluded."""

    def test_filters_by_recruiter(self, client, recruiter_token, recruiter_a, recruiter_b, workspace):
        """GET /dashboard?recruiter_id=recruiter-a returns submissions, placements, and
        interviews created by recruiter A only."""

    def test_recruiter_cannot_view_other_recruiter(self, client, recruiter_token, other_recruiter):
        """Recruiter attempting GET /dashboard?recruiter_id=other-recruiter returns 403."""

    def test_admin_can_view_any_recruiter(self, client, admin_token, recruiter_a):
        """Admin can GET /dashboard?recruiter_id=recruiter-a for any recruiter."""

    def test_empty_state_for_new_account(self, client, recruiter_token, empty_workspace):
        """GET /dashboard for a workspace with no candidates, jobs, or submissions
        returns has_data=false and suggested_actions array."""

    def test_trend_improving(self, client, admin_token, workspace, historical_metrics):
        """When current 30-day avg time_to_shortlist (3 days) is >10% better than
        previous period (4 days), trend is 'improving'."""

    def test_trend_declining(self, client, admin_token, workspace, historical_metrics):
        """When current avg is >10% worse than previous period, trend is 'declining'."""

    def test_trend_stable(self, client, admin_token, workspace, historical_metrics):
        """When current avg is within 10% of previous period, trend is 'stable'."""

    def test_cache_returns_fast(self, client, admin_token, workspace):
        """GET /dashboard response time is < 100ms (from cache, not fresh calculation)."""

    def test_cache_expires_at_5_minutes(self, client, admin_token, workspace, time_travel_mock):
        """After first request, cached data is returned for subsequent requests within 5 minutes.
        After 5 minutes, cache expires and fresh data is calculated."""

    def test_leaderboard_ranked_by_placements(self, client, admin_token, workspace, multiple_recruiters):
        """Recruiter leaderboard in dashboard is ranked by placements_completed DESC,
        then by submissions_made DESC."""

    def test_recruiter_leaderboard_limited_to_top_10(self, client, admin_token, workspace, fifteen_recruiters):
        """Dashboard leaderboard shows top 10 recruiters by placements."""

    def test_client_viewer_no_recruiter_data(self, client, client_viewer_token, workspace):
        """Client viewer role receives workspace metrics but no recruiter_leaderboard field."""

    def test_date_range_filtering(self, client, admin_token, workspace, historical_placement_records):
        """GET /dashboard?date_from=2026-03-01&date_to=2026-03-31 calculates
        metrics only for that period."""


# analytics/tests/test_recruiter_metrics.py

class TestRecruiterProductivityTable:

    def test_returns_all_recruiters(self, client, admin_token, workspace_with_recruiters):
        """GET /api/v1/analytics/recruiters returns list of all recruiters in the workspace."""

    def test_ranked_by_placements(self, client, admin_token, workspace_with_recruiters):
        """GET /recruiters?order_by=placements returns list ordered by placements DESC."""

    def test_ranked_by_submissions(self, client, admin_token, workspace_with_recruiters):
        """GET /recruiters?order_by=submissions returns list ordered by submissions DESC."""

    def test_pagination(self, client, admin_token, many_recruiters):
        """GET /recruiters?limit=10&offset=20 returns 10 recruiters starting from index 20."""

    def test_recruiter_cannot_view_other_workspace(self, client, recruiter_token, workspace_b):
        """Recruiter with access to workspace A cannot GET /recruiters for workspace B."""

    def test_admin_can_view_any_workspace(self, client, admin_token, workspace_a, workspace_b):
        """Admin can GET /recruiters for any workspace."""

    def test_includes_all_metrics(self, client, admin_token, workspace_with_recruiters):
        """Each recruiter in the list includes candidates_added, submissions_made,
        interviews_scheduled, placements_completed, avg_time_to_shortlist_days, avg_time_to_fill_days."""


# analytics/tests/test_individual_recruiter.py

class TestIndividualRecruiterMetrics:

    def test_returns_recruiter_metrics(self, client, recruiter_token, recruiter_with_history):
        """GET /api/v1/analytics/recruiters/{recruiter_id} returns detailed metrics."""

    def test_recruiter_can_only_view_self(self, client, recruiter_token, other_recruiter):
        """Recruiter attempting GET for other_recruiter returns 403."""

    def test_admin_can_view_any_recruiter(self, client, admin_token, recruiter_a):
        """Admin can GET metrics for any recruiter."""

    def test_includes_weekly_breakdown(self, client, admin_token, recruiter_with_weekly_data):
        """Response includes submissions_by_week array with week number and submission count."""

    def test_default_period_is_30_days(self, client, admin_token, recruiter_with_history):
        """GET /recruiters/{id} with no date params uses last 30 days."""

    def test_custom_date_range(self, client, admin_token, recruiter_with_history):
        """GET /recruiters/{id}?date_from=2026-03-01&date_to=2026-03-31 filters to that period."""


# analytics/tests/test_job_metrics.py

class TestJobMetrics:

    def test_returns_job_metrics(self, client, recruiter_token, job_with_pipeline_activity):
        """GET /api/v1/analytics/jobs/{job_id}/metrics returns time_to_shortlist,
        time_to_fill, submissions, and stage distribution."""

    def test_time_to_shortlist_calculated(self, client, recruiter_token, job_placed_on_day_4):
        """For a job created on day 0 with first shortlist on day 4,
        time_to_shortlist_days is 4."""

    def test_time_to_fill_calculated(self, client, recruiter_token, job_placed_on_day_18):
        """For a job created on day 0 with first placement on day 18,
        time_to_fill_days is 18."""

    def test_null_if_never_shortlisted(self, client, recruiter_token, job_no_shortlists):
        """For a job with no shortlists, time_to_shortlist_days is null."""

    def test_null_if_never_placed(self, client, recruiter_token, job_no_placements):
        """For a job with no placements, time_to_fill_days is null."""

    def test_candidates_by_stage(self, client, recruiter_token, job_with_candidates_in_all_stages):
        """candidates_by_stage returns count of candidates in each stage for this job only."""

    def test_includes_submission_count(self, client, recruiter_token, job_with_submissions):
        """total_submissions is the count of distinct candidates submitted to this job."""


# analytics/tests/test_cache_refresh.py

class TestCacheRefresh:

    def test_forces_immediate_refresh(self, client, admin_token, workspace):
        """POST /api/v1/analytics/refresh enqueues a refresh task and returns 202."""

    def test_refresh_job_queued(self, client, admin_token, workspace):
        """POST /refresh returns refresh_job_id that can be polled for status."""

    def test_recruiter_cannot_force_refresh(self, client, recruiter_token, workspace):
        """Recruiter attempting POST /refresh returns 403."""

    def test_admin_can_refresh_global(self, client, admin_token):
        """Admin POST /refresh with no workspace_id refreshes all workspaces."""

    def test_invalid_workspace_returns_404(self, client, admin_token):
        """POST /refresh?workspace_id=invalid returns 404."""


# analytics/tests/test_authorization.py

class TestAuthorizationEnforcement:

    def test_all_endpoints_require_auth(self, client):
        """GET /analytics/dashboard without Authorization header returns 401."""

    def test_recruiter_sees_assigned_workspace_only(self, client, recruiter_token, workspace_a, workspace_b):
        """Recruiter with access to workspace A cannot see metrics for workspace B."""

    def test_admin_sees_all_workspaces(self, client, admin_token, workspace_a, workspace_b, workspace_c):
        """Admin can request metrics for any workspace."""

    def test_client_viewer_sees_workspace_only(self, client, client_viewer_token, workspace):
        """Client viewer for workspace X can see metrics for X but no recruiter details."""
```

---

## 6. Internal module structure

```
analytics/
├── api.py                  # Public interface (FastAPI router + Pydantic models)
├── service.py              # Business logic layer (metric calculation, cache management)
├── repository.py           # Database queries (SQLAlchemy ORM operations)
├── models.py               # SQLAlchemy ORM models
├── schemas.py              # Pydantic request/response schemas
├── tasks.py                # Celery tasks (scheduled refresh, on-demand refresh)
├── cache_manager.py        # Caching logic (Redis TTL, invalidation)
├── metrics_calculator.py   # Core calculations (time_to_fill, time_to_shortlist, trends)
├── exceptions.py           # Service-specific exception classes
├── constants.py            # Enums, cache TTL, metric periods, config
├── schema.sql              # Database migration source
├── tests/
│   ├── conftest.py         # Fixtures (test DB, mock upstream services, tokens)
│   ├── test_dashboard.py
│   ├── test_recruiter_metrics.py
│   ├── test_individual_recruiter.py
│   ├── test_job_metrics.py
│   ├── test_cache_refresh.py
│   └── test_authorization.py
└── README.md               # Developer onboarding for this service
```

Only `api.py` and `schemas.py` are importable by other services. Everything else is internal.

---

## 7. Dependencies and constraints

**Internal service dependencies**:

- `candidate-management/` (read-only via API): Provides candidate counts, candidate IDs for searching in pipeline. Calls: `GET /api/v1/candidates/search` (for historical queries on candidate creation dates).
- `job-management/` (read-only via API): Provides job counts, job creation timestamps, job urgency levels. Calls: `GET /api/v1/jobs`, `GET /api/v1/jobs/{job_id}`.
- `pipeline/` (read-only via direct database): Reads stage history from `pipeline_stage_history` table to calculate time_to_shortlist and time_to_fill. In Phase 1, direct table access via shared database. Phase 2 adds a dedicated endpoint.
- `scheduling/` (read-only via API): Provides interview counts and scheduled interview timestamps. Calls: `GET /api/v1/interviews/scheduled`.
- `auth/` (indirect via JWT): Extracts workspace_id, recruiter_id, role from JWT claims in Authorization header.

**External dependencies**:

- PostgreSQL 15+: Primary data store. Hosts analytics tables.
- Redis + Celery: Scheduled refresh jobs (every 5 minutes via beat) and on-demand refresh tasks.
- Shared database with `pipeline/` service: Direct read access to `pipeline_stage_history` table for stage change timestamps.

**Performance targets**:

| Operation | Target | Measured at |
|-----------|--------|-------------|
| Get dashboard (from cache) | < 100ms | API response time |
| Get dashboard (cache miss, fresh calc) | < 1s | API response time |
| Get recruiter productivity table | < 500ms | API response time (paginated, from cache) |
| Get individual recruiter metrics | < 300ms | API response time |
| Get job metrics | < 200ms | API response time |
| Cache refresh (full workspace) | < 10s | Celery task end-to-end |
| Scheduled cache refresh (every 5 min) | < 5s | Celery beat task |

**Security**:

- All endpoints require a valid JWT with workspace and role claims.
- Recruiter role is restricted to their assigned workspace(s) and can only view their own metrics.
- Admin role can view any workspace and any recruiter's metrics.
- Client viewer role is restricted to their workspace and receives simplified metrics (no recruiter-level data).
- The `POST /refresh` endpoint is admin-only.

---

## 8. Out of scope

- Cohort analysis (e.g., "placements from candidates uploaded in March"). Phase 2.
- Custom time periods beyond the standard 30-day rolling window. Phase 2.
- Drill-down into individual candidate records from leaderboard. Owned by `candidate-management/`. Analytics surfaces aggregate metrics only.
- Real-time WebSocket updates for dashboard metrics. Phase 2 enhancement.
- Predictive metrics (forecasted placements, ETA for pipeline). Phase 2 (requires AI service integration).
- Recruiter ratings or performance scores. Phase 2 (requires business logic and policy decisions).
- Geographic or skill-based analytics. Phase 2.
- A/B testing infrastructure for dashboard layout changes. Phase 2.

---

## 9. Verification

```bash
cd analytics/
pytest tests/ -v --tb=short
```

All tests must pass. Additionally, verify these end-to-end scenarios manually or via integration tests:

1. Create a new workspace with no data. Confirm GET /dashboard returns `has_data: false` with suggested_actions.
2. Create a job, upload candidates, and submit some to the job. Confirm dashboard shows job count, candidates in pipeline by stage, and submission count.
3. Move a candidate to 'Shortlisted' stage. Confirm dashboard time_to_shortlist is calculated from job creation to shortlist timestamp.
4. Move a candidate to 'Placed' stage. Confirm dashboard time_to_fill is calculated and placement counts (this_week, this_month, this_quarter) increment.
5. Create a second recruiter and assign jobs to both. Confirm GET /analytics/recruiters shows both recruiters with their own metrics, ranked by placements.
6. As the first recruiter, verify GET /analytics/dashboard?recruiter_id={my_id} shows only my submissions and placements. Verify GET ?recruiter_id={other_id} returns 403.
7. As an admin, verify GET /dashboard?recruiter_id={any_recruiter} works for any recruiter in the workspace.
8. Call POST /analytics/refresh as admin and confirm it returns 202 with a refresh_job_id.
9. Verify cache is working: call GET /dashboard twice in quick succession and confirm response times are < 100ms both times. Wait 5 minutes, call again and confirm a fresh calculation occurred (response time longer, data is fresh).
10. Test trend calculation: after 30 days of activity with time_to_shortlist avg 4 days, then 30 days with avg 3.5 days, confirm trend is 'improving'. Repeat with declining scenario.
11. Test client_viewer role: confirm GET /dashboard returns metrics but no recruiter_leaderboard field.
12. Test pagination: GET /recruiters?limit=10&offset=0 and ?limit=10&offset=10 confirm different results with correct total_count.
```

---

## Analytics Service Integration Notes

The analytics service relies on near-real-time data from upstream services. To ensure fresh metrics:

- **Pipeline stage changes**: When `pipeline/` service moves a candidate to a new stage, it creates a row in `pipeline_stage_history` (owned by pipeline service). The analytics service reads this table directly to calculate time_to_shortlist and time_to_fill.
- **Submission records**: When `job-management/` records a candidate submission (via the `submissions` table), the analytics service queries this table to count submissions per job and per recruiter.
- **Interview scheduling**: When `scheduling/` creates an interview record, the analytics service reads the `interviews` table to count interviews scheduled this week.
- **Candidate creation**: When `candidate-management/` creates a candidate, the `candidates` table records the created_at timestamp. Analytics uses this for recruiter productivity (candidates_added metric).
- **Placement records**: The `placement_records` table is written by analytics service itself (triggered by a stage change to 'Placed' in the pipeline). This is the single source of truth for historical placements.

**Phase 1 Architecture**: Analytics queries upstream tables directly. Phase 2 adds dedicated events/webhooks to avoid tight coupling.
