# Analytics

## Overview
The analytics domain provides AIRIS operational reporting and dashboard KPIs. It aggregates data from upstream operational services into recruiter/workspace metrics and serves cache-optimized endpoints for near-real-time decision support.

## Responsibilities
Primary responsibilities:
- Produce workspace and recruiter dashboard metrics.
- Calculate key cycle-time KPIs (`time_to_shortlist`, `time_to_fill`) and trends.
- Maintain placement/shortlist derived records for historical analytics.
- Serve recruiter productivity and job-level performance views.
- Manage cache lifecycle and forced refresh operations.

## Data Model
Core tables:
- `dashboard_snapshots`: periodic aggregate snapshots.
- `placement_records`: placement events with derived cycle times.
- `shortlist_records`: shortlist events with derived cycle times.
- `recruiter_metrics`: periodized recruiter aggregates.
- `metric_cache`: JSON cache artifacts with expiry windows.

Key constraints:
- Cache keys unique and TTL-based (`expires_at`).
- Recruiter metric uniqueness by recruiter and period.
- Analytics tables are write-owned by analytics service only.

## API Endpoints
Representative endpoints:
- `GET /api/v1/analytics/dashboard`
- `GET /api/v1/analytics/recruiters`
- `GET /api/v1/analytics/recruiters/{recruiter_id}`
- `GET /api/v1/analytics/jobs/{job_id}/metrics`
- `POST /api/v1/analytics/refresh`

## Business Logic
- Dashboard endpoint is cache-first; stale threshold is short and controlled by periodic refresh.
- Trends compare current period vs previous equivalent period with threshold-based labels (`improving`, `stable`, `declining`).
- Role-based visibility:
  - recruiter: own workspace / own metrics
  - admin: broad access
  - client viewer: simplified workspace-level output without recruiter leaderboard
- Job-level metrics derive first shortlist/placement timestamps from pipeline transitions and job creation time.
- Refresh endpoint enqueues asynchronous recalculation jobs; admin-only for global refresh.

## Notes / Constraints
- Phase 1 uses tight read coupling with upstream data; future phases should move toward event-driven integration.
- Predictive analytics, cohort analysis, and advanced drilldowns are deferred.
- Keep metric definitions stable and documented; changing KPI formulas impacts downstream reporting trust.
- Cache invalidation and refresh SLAs are critical to dashboard credibility.
