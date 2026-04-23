# Service spec: scheduling

**Version**: 1.0
**Date**: 2026-04-18
**Parent PRD**: AIRIS Phase 1 MVP PRD v1

---

## 1. Service boundary

**Folder**: `scheduling/`

This service owns all interview scheduling: calendar integrations, booking link generation, availability management, reminders, rescheduling, and cancellation. All interview-related state and calendar operations flow through this service's public API.

**Owns**: `interviews` table, `booking_links` table, `calendar_connections` table, `interview_reminders` table.

**Depends on**:

- `candidate-management/` reads candidate contact info (email, phone) for booking link invites and to create interaction records
- `job-management/` reads job title and details for calendar event descriptions
- `communication/` sends booking confirmations, reminder emails, and cancellation notifications
- `auth/` provides OAuth tokens for Google Calendar and Microsoft Graph (Outlook) integration

**Depended on by**:

- `analytics/` reads interview counts and completion rates for dashboard metrics
- `pipeline/` reads interview scheduling status for stage progression; writes interview_scheduled interactions via `candidate-management/`

---

## 2. Database schema

```sql
-- scheduling/schema.sql

CREATE TABLE calendar_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recruiter_user_id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    provider VARCHAR(20) NOT NULL,                -- 'google' | 'outlook'
    provider_account_email VARCHAR(255) NOT NULL, -- email of the calendar owner
    access_token TEXT NOT NULL,                    -- encrypted JWT from OAuth provider
    refresh_token TEXT,                            -- encrypted refresh token (Outlook/Google)
    token_expires_at TIMESTAMPTZ,
    connection_status VARCHAR(20) DEFAULT 'active', -- 'active' | 'expired' | 'revoked'
    calendar_id VARCHAR(500),                      -- provider-specific calendar ID
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT calendar_connections_unique UNIQUE (recruiter_user_id, workspace_id, provider)
);

CREATE INDEX idx_calendar_connections_recruiter ON calendar_connections (recruiter_user_id);
CREATE INDEX idx_calendar_connections_status ON calendar_connections (connection_status);

CREATE TABLE booking_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recruiter_user_id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    job_id UUID NOT NULL,
    candidate_id UUID,                             -- NULL if link is not yet tied to a specific candidate
    slug VARCHAR(100) UNIQUE NOT NULL,             -- public-facing identifier for the link
    availability_timezone VARCHAR(100) NOT NULL,  -- e.g. 'Asia/Kolkata', 'America/New_York'
    default_duration_minutes INT DEFAULT 45,       -- 30 | 45 | 60 | 90
    working_hours_start TIME NOT NULL,             -- 09:00
    working_hours_end TIME NOT NULL,               -- 18:00
    calendar_connection_id UUID REFERENCES calendar_connections(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_booking_links_slug ON booking_links (slug);
CREATE INDEX idx_booking_links_recruiter ON booking_links (recruiter_user_id);
CREATE INDEX idx_booking_links_job ON booking_links (job_id);
CREATE INDEX idx_booking_links_candidate ON booking_links (candidate_id);
CREATE INDEX idx_booking_links_active ON booking_links (is_active);

CREATE TABLE interviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_link_id UUID NOT NULL REFERENCES booking_links(id),
    candidate_id UUID NOT NULL,
    recruiter_user_id UUID NOT NULL,
    job_id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    scheduled_at TIMESTAMPTZ NOT NULL,
    duration_minutes INT NOT NULL,
    recruiter_calendar_event_id VARCHAR(500),      -- provider-specific event ID
    candidate_calendar_event_id VARCHAR(500),      -- provider-specific event ID (if sent)
    interview_status VARCHAR(20) DEFAULT 'scheduled', -- 'scheduled' | 'completed' | 'cancelled' | 'no_show'
    cancellation_reason VARCHAR(255),              -- recorded when cancelled
    cancelled_by_role VARCHAR(20),                 -- 'recruiter' | 'candidate'
    cancelled_at TIMESTAMPTZ,
    candidate_rsvp_status VARCHAR(20) DEFAULT 'pending', -- 'pending' | 'accepted' | 'declined'
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_interviews_candidate ON interviews (candidate_id, created_at DESC);
CREATE INDEX idx_interviews_recruiter ON interviews (recruiter_user_id, created_at DESC);
CREATE INDEX idx_interviews_scheduled_at ON interviews (scheduled_at);
CREATE INDEX idx_interviews_status ON interviews (interview_status);

CREATE TABLE interview_reminders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    recipient_email VARCHAR(255) NOT NULL,        -- recruiter or candidate
    recipient_role VARCHAR(20) NOT NULL,          -- 'recruiter' | 'candidate'
    send_before_minutes INT NOT NULL,             -- 1440 (24h) or 60 (1h)
    scheduled_send_at TIMESTAMPTZ NOT NULL,
    sent_at TIMESTAMPTZ,
    delivery_status VARCHAR(20) DEFAULT 'pending', -- 'pending' | 'sent' | 'failed'
    failure_reason VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_reminders_interview ON interview_reminders (interview_id);
CREATE INDEX idx_reminders_scheduled_send ON interview_reminders (scheduled_send_at);
CREATE INDEX idx_reminders_status ON interview_reminders (delivery_status);
```

---

## 3. REST API endpoints

All endpoints require authentication via JWT in the `Authorization` header. The JWT carries `user_id`, `role`, and `workspace_ids`.

### 3.1 Initiate OAuth calendar connection

```
POST /api/v1/calendar/connect
```

**Request body**:
```json
{
  "provider": "google",
  "workspace_id": "workspace-123"
}
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
  }
}
```

Redirects the user to the provider's OAuth consent screen. Returns a URL for the frontend to redirect to.

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 400 | `INVALID_PROVIDER` | Provider is not 'google' or 'outlook'. |
| 401 | `UNAUTHORIZED` | Missing or invalid JWT. |
| 403 | `WORKSPACE_ACCESS_DENIED` | User does not have access to the workspace. |

### 3.2 OAuth callback handler

```
GET /api/v1/calendar/callback?code=AUTH_CODE&state=STATE&provider=google
```

**Query parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `code` | string | Authorization code from the OAuth provider. |
| `state` | string | State token (CSRF protection). Must match the session state. |
| `provider` | string | 'google' or 'outlook'. |

**Success response** (302 Found):
```
Location: /dashboard?calendar_connected=true
```

Redirects to the dashboard on success.

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 400 | `INVALID_STATE` | State token does not match session. |
| 400 | `AUTH_CODE_EXCHANGE_FAILED` | OAuth provider rejected the code. |
| 500 | `CALENDAR_SYNC_FAILED` | Token exchange succeeded but calendar sync failed. Redirect includes `calendar_connected=false`. |

### 3.3 Check calendar connection status

```
GET /api/v1/calendar/status
```

**Query parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `workspace_id` | UUID | (Optional) Filter by workspace. If not provided, returns all connections for the user. |

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "connections": [
      {
        "id": "conn-123",
        "provider": "google",
        "provider_account_email": "recruiter@company.com",
        "connection_status": "active",
        "token_expires_at": "2026-05-18T10:30:00Z",
        "workspace_id": "workspace-123"
      }
    ]
  }
}
```

Returns all calendar connections for the authenticated user, or filtered by workspace.

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 401 | `UNAUTHORIZED` | Missing or invalid JWT. |

### 3.4 Generate booking link

```
POST /api/v1/interviews/booking-link
```

**Request body**:
```json
{
  "job_id": "job-456",
  "candidate_id": "candidate-789",
  "workspace_id": "workspace-123",
  "default_duration_minutes": 45,
  "working_hours_start": "09:00",
  "working_hours_end": "18:00",
  "availability_timezone": "Asia/Kolkata"
}
```

**Success response** (201 Created):
```json
{
  "success": true,
  "data": {
    "booking_link_id": "bl-abc123",
    "slug": "priya-kumar-backend-dev-xy7z",
    "public_url": "https://airis.siprahub.com/book/priya-kumar-backend-dev-xy7z",
    "candidate_email": "priya.kumar@example.com",
    "job_title": "Backend Developer",
    "created_at": "2026-04-18T10:30:00Z"
  }
}
```

Creates a new booking link and returns the public URL to share with the candidate.

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 400 | `VALIDATION_ERROR` | Missing required fields or invalid timezone. Response includes `fields` array. |
| 404 | `JOB_NOT_FOUND` | The job ID does not exist or recruiter lacks access. |
| 404 | `CANDIDATE_NOT_FOUND` | The candidate ID does not exist. |
| 404 | `NO_CALENDAR_CONNECTION` | User has no active calendar connection for this workspace. |
| 401 | `UNAUTHORIZED` | Missing or invalid JWT. |

### 3.5 Get available time slots

```
GET /api/v1/interviews/booking-link/{slug}/availability?date_from=2026-04-20&date_to=2026-04-30
```

**Query parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `date_from` | ISO 8601 | Start date for availability window. |
| `date_to` | ISO 8601 | End date for availability window. |

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "booking_link_slug": "priya-kumar-backend-dev-xy7z",
    "candidate_name": "Priya Kumar",
    "job_title": "Backend Developer",
    "default_duration_minutes": 45,
    "timezone": "Asia/Kolkata",
    "available_slots": [
      {
        "start_time": "2026-04-20T09:00:00+05:30",
        "end_time": "2026-04-20T09:45:00+05:30",
        "available": true
      },
      {
        "start_time": "2026-04-20T10:00:00+05:30",
        "end_time": "2026-04-20T10:45:00+05:30",
        "available": true
      },
      {
        "start_time": "2026-04-20T11:00:00+05:30",
        "end_time": "2026-04-20T11:45:00+05:30",
        "available": false,
        "reason": "conflict"
      }
    ]
  }
}
```

Public endpoint (no authentication required). Fetches real-time availability from the calendar provider.

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 404 | `BOOKING_LINK_NOT_FOUND` | Slug does not exist or is inactive. |
| 503 | `CALENDAR_API_UNAVAILABLE` | Calendar provider is unreachable. Returns with cached slots (if available) or empty list. |

### 3.6 Book an interview slot

```
POST /api/v1/interviews/booking-link/{slug}/book
```

**Request body**:
```json
{
  "candidate_email": "priya.kumar@example.com",
  "candidate_name": "Priya Kumar",
  "selected_slot": "2026-04-20T09:00:00+05:30"
}
```

**Success response** (201 Created):
```json
{
  "success": true,
  "data": {
    "interview_id": "int-def456",
    "scheduled_at": "2026-04-20T09:00:00+05:30",
    "recruiter_name": "Arun Sharma",
    "recruiter_email": "arun@company.com",
    "confirmation_email_sent": true
  }
}
```

Creates an interview, adds it to both recruiter and candidate calendars, and sends confirmation emails.

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 404 | `BOOKING_LINK_NOT_FOUND` | Slug does not exist or is inactive. |
| 409 | `SLOT_CONFLICT` | Slot was just booked by another candidate or recruiter. Response includes `alternative_slots` array. |
| 400 | `INVALID_SLOT_TIME` | Selected slot is outside working hours or before now. |
| 503 | `CALENDAR_API_ERROR` | Calendar event creation failed. No interview is created. |

### 3.7 List interviews

```
GET /api/v1/interviews?workspace_id=workspace-123&status=scheduled&date_from=2026-04-20&date_to=2026-04-30&limit=50&offset=0
```

**Query parameters** (all optional):

| Param | Type | Description |
|-------|------|-------------|
| `workspace_id` | UUID | Filter by workspace. Required for non-Admin users. |
| `status` | string | Filter by status: 'scheduled', 'completed', 'cancelled', 'no_show'. |
| `date_from` | ISO 8601 | Filter by scheduled_at start date. |
| `date_to` | ISO 8601 | Filter by scheduled_at end date. |
| `limit` | int | Results per page (default 50, max 200). |
| `offset` | int | Pagination offset. |

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "interviews": [
      {
        "id": "int-def456",
        "candidate_name": "Priya Kumar",
        "candidate_email": "priya.kumar@example.com",
        "job_title": "Backend Developer",
        "scheduled_at": "2026-04-20T09:00:00Z",
        "duration_minutes": 45,
        "status": "scheduled",
        "candidate_rsvp_status": "accepted",
        "created_at": "2026-04-18T10:30:00Z"
      }
    ],
    "total_count": 24,
    "limit": 50,
    "offset": 0
  }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 401 | `UNAUTHORIZED` | Missing or invalid JWT. |
| 403 | `WORKSPACE_ACCESS_DENIED` | User does not have access to the requested workspace. |

### 3.8 Get interview details

```
GET /api/v1/interviews/{interview_id}
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "id": "int-def456",
    "booking_link_id": "bl-abc123",
    "candidate_id": "candidate-789",
    "candidate_name": "Priya Kumar",
    "candidate_email": "priya.kumar@example.com",
    "recruiter_name": "Arun Sharma",
    "recruiter_email": "arun@company.com",
    "job_id": "job-456",
    "job_title": "Backend Developer",
    "workspace_id": "workspace-123",
    "scheduled_at": "2026-04-20T09:00:00Z",
    "duration_minutes": 45,
    "interview_status": "scheduled",
    "candidate_rsvp_status": "accepted",
    "cancellation_reason": null,
    "cancelled_by_role": null,
    "cancelled_at": null,
    "notes": "Discussion on system design experience.",
    "created_at": "2026-04-18T10:30:00Z"
  }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 404 | `INTERVIEW_NOT_FOUND` | Interview ID does not exist or user lacks access. |
| 401 | `UNAUTHORIZED` | Missing or invalid JWT. |

### 3.9 Reschedule interview

```
POST /api/v1/interviews/{interview_id}/reschedule
```

**Request body**:
```json
{
  "new_scheduled_time": "2026-04-22T14:00:00Z"
}
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "interview_id": "int-def456",
    "old_scheduled_at": "2026-04-20T09:00:00Z",
    "new_scheduled_at": "2026-04-22T14:00:00Z",
    "confirmation_emails_sent": true
  }
}
```

Rescheduling is allowed up to 4 hours before the scheduled time. Updates calendar events and sends notifications.

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 404 | `INTERVIEW_NOT_FOUND` | Interview ID does not exist or user lacks access. |
| 400 | `RESCHEDULING_NOT_ALLOWED` | Interview is within 4 hours of start time or already completed/cancelled. |
| 400 | `INVALID_TIME` | New time is before now or outside working hours. |
| 409 | `NEW_SLOT_CONFLICT` | New time conflicts with recruiter's calendar. Response includes `alternative_slots`. |
| 503 | `CALENDAR_API_ERROR` | Calendar event update failed. Interview time is not changed. |
| 401 | `UNAUTHORIZED` | Missing or invalid JWT. |

### 3.10 Cancel interview

```
POST /api/v1/interviews/{interview_id}/cancel
```

**Request body**:
```json
{
  "reason": "Candidate no longer interested in the role"
}
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "interview_id": "int-def456",
    "status": "cancelled",
    "cancellation_reason": "Candidate no longer interested in the role",
    "cancelled_by_role": "recruiter",
    "cancelled_at": "2026-04-18T11:00:00Z",
    "notification_emails_sent": true
  }
}
```

Cancellation is always allowed. Removes the calendar event and sends notification emails to both recruiter and candidate.

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 404 | `INTERVIEW_NOT_FOUND` | Interview ID does not exist or user lacks access. |
| 400 | `INVALID_STATUS_FOR_CANCELLATION` | Interview is already completed or cancelled. |
| 401 | `UNAUTHORIZED` | Missing or invalid JWT. |

---

## 4. Behaviour requirements

### OAuth calendar connection

- Given a valid OAuth code from the provider, exchanges the code for access and refresh tokens. Stores both tokens encrypted at rest.
- Given an invalid or expired code, returns 400 with `AUTH_CODE_EXCHANGE_FAILED`. No tokens are stored.
- For Google Calendar: stores the Calendar API `calendar_id` (usually 'primary'). For Outlook: stores the user's mailbox address as `calendar_id`.
- Sets `token_expires_at` based on the provider's expiration (Google typically 1 hour, Outlook variable). Refresh tokens are stored securely.
- On callback success, creates or updates the `calendar_connections` row with `connection_status = 'active'`.

### booking_link_generation

- Given valid inputs (job_id, candidate_id, workspace_id, timezone, working hours), creates a `booking_links` row and generates a unique slug.
- The slug format is lowercase, kebab-cased: `{candidate_first_name}-{candidate_last_name}-{job_slug}-{random_suffix}`. Example: `priya-kumar-backend-dev-xy7z`.
- Slug uniqueness is enforced by database UNIQUE constraint. On collision (extremely rare), regenerate the suffix and retry.
- Does not validate the calendar connection at link creation time. If the connection expires later, the link is marked inactive via status checks.
- Returns the public URL: `https://airis.siprahub.com/book/{slug}`.

### get_available_slots (real-time availability)

- Fetches recruiter's calendar for the date range using the provider API (Google Calendar API or Microsoft Graph).
- For each 30-minute interval within working hours, checks if a slot of `default_duration_minutes` is available (no conflicts).
- Returns all available slots within the date range, in chronological order.
- If calendar API call fails, retries 3 times with exponential backoff (1s, 2s, 4s). After 3 failures, returns error status 503 with `CALENDAR_API_UNAVAILABLE`. The response includes empty `available_slots` or cached data if available.
- Performs the API call on every request (real-time, not cached).
- Does not require authentication (public endpoint).

### book_interview

- Before confirming, re-checks the calendar for conflicts at the selected time. If a conflict is detected, returns 409 `SLOT_CONFLICT` with alternative available slots.
- Creates an `interviews` row with `interview_status = 'scheduled'` and `candidate_rsvp_status = 'pending'`.
- Creates a calendar event on recruiter's calendar with title format: "Interview: {candidate_name} - {job_title}". Duration is `default_duration_minutes`.
- Sends a booking confirmation email to the candidate via `communication/` service.
- If candidate email was provided in the booking request, uses it; otherwise reads from `candidate-management/`.
- Creates an interaction record in `candidate-management/` with type `interview_scheduled` and metadata including job_id and scheduled_at.
- Creates two `interview_reminders` rows: one for 24 hours before, one for 1 hour before.
- If calendar event creation fails, the interview row is not created and error 503 is returned.

### reschedule_interview

- Allowed only if the interview is currently `scheduled` and more than 4 hours remain until `scheduled_at`.
- If within 4 hours, returns 400 `RESCHEDULING_NOT_ALLOWED`.
- Re-checks the new time for conflicts. If conflict found, returns 409 with alternative slots.
- Updates the calendar event and the `interviews` row.
- Cancels and recreates the reminder rows with the new send times.
- Sends notifications to both recruiter and candidate.
- Entire operation must be atomic: if calendar update fails, the interview time is not changed in the database.

### cancel_interview

- Allowed at any time. If already `cancelled`, still returns success (idempotent).
- If already `completed`, returns 400 `INVALID_STATUS_FOR_CANCELLATION`.
- Records the cancellation reason and the role of the person who cancelled (inferred from JWT claims).
- Removes the calendar event from recruiter's calendar.
- If candidate's event exists (was sent), removes it too.
- Sends cancellation notification emails to both recruiter and candidate via `communication/`.
- Marks all pending reminders for this interview as `delivery_status = 'cancelled'` (or deletes them).
- Updates the `interviews` status to `cancelled` and sets `cancelled_at`.

### list_interviews

- Returns interviews for the authenticated recruiter, filtered by status, date range, and workspace.
- Admin users can view all interviews across all workspaces if no `workspace_id` filter is provided.
- Results are ordered by `scheduled_at` DESC.
- Soft-deleted candidates are not returned (joined query on candidate-management).

### interview_status_enum

- `scheduled`: Interview is confirmed and on the calendar.
- `completed`: Interview has been marked as completed (via a separate manual endpoint or timestamp check after scheduled_at).
- `cancelled`: Interview was cancelled (reason recorded).
- `no_show`: Interview was neither cancelled nor completed by scheduled_at + 1 hour (auto-marked, or manually marked by recruiter).

### reminder scheduling and delivery

- Two reminders are created for each interview: one at `scheduled_at - 24 hours`, one at `scheduled_at - 1 hour`.
- Reminders are scheduled as Celery beat tasks (not executed immediately).
- The task queries the `interview_reminders` table for rows with `delivery_status = 'pending'` and `scheduled_send_at <= NOW()`.
- For each row, calls `communication/` service to send an email. If the service returns an error (email bounce, invalid address), the reminder row is marked `delivery_status = 'failed'` with the `failure_reason` recorded. No retry is performed.
- If the reminder delivery succeeds, `delivery_status = 'sent'` and `sent_at` is set.
- If an interview is cancelled, all pending reminders are marked cancelled or deleted.

### double-booking prevention

- Before confirming a booking or rescheduling, the system fetches the recruiter's calendar from the provider API and checks for any events that overlap the requested time slot.
- If an overlap is found, the operation is rejected with a 409 response and a list of alternative available times in the date range.
- The check is synchronous and happens in the request path.

### calendar token expiration

- When the system calls the calendar provider API and receives a token-expired error (e.g., HTTP 401 from Google API), the `calendar_connections` row is marked `connection_status = 'expired'`.
- The recruiter is notified (via `communication/` or in-app notification) to re-authenticate.
- Existing interviews are not affected; the cancellation of reminders or deletion of calendar events is not triggered automatically.
- Future booking link generations check for expired connections and return error 404 `NO_CALENDAR_CONNECTION`.

### API call retry logic

- Calendar API calls (get_available_slots, create_event, update_event, delete_event) retry 3 times with exponential backoff: 1s, 2s, 4s.
- If all 3 retries fail, the endpoint returns error 503 with a fallback suggestion (e.g., "Please contact support" or "Try again later").
- Transient failures (network timeout, 5xx response) trigger retry. Permanent failures (4xx except 401/403 token errors) do not retry.

### role-based access

- Recruiter role: can create booking links and manage interviews for their assigned workspace(s).
- Admin role: can view and manage all interviews across all workspaces.
- Client Viewer role: no direct endpoint access (pipeline service mediates access to interview status).

---

## 5. Acceptance criteria as tests

```python
# scheduling/tests/test_oauth.py

class TestOAuthConnection:

    def test_initiate_google_oauth_flow(self, client, recruiter_token):
        """POST /calendar/connect with provider='google' returns 200
        with an authorization_url that redirects to Google's OAuth consent screen."""

    def test_initiate_outlook_oauth_flow(self, client, recruiter_token):
        """POST /calendar/connect with provider='outlook' returns 200
        with an authorization_url for Microsoft login."""

    def test_callback_exchanges_code_for_token(self, client, recruiter_token, mock_google_oauth):
        """GET /calendar/callback with a valid code creates a calendar_connections row
        with access_token and token_expires_at populated."""

    def test_callback_invalid_state_returns_400(self, client, recruiter_token):
        """GET /calendar/callback with mismatched state returns 400 INVALID_STATE."""

    def test_callback_failed_token_exchange_returns_400(self, client, recruiter_token, mock_google_oauth_failure):
        """GET /calendar/callback when OAuth provider rejects the code returns 400 AUTH_CODE_EXCHANGE_FAILED."""

    def test_connection_status_active(self, client, recruiter_token, calendar_connected):
        """GET /calendar/status returns connection_status='active' and token_expires_at."""

    def test_connection_status_expired_marked_on_api_error(self, client, recruiter_token, calendar_connection, mock_google_expired):
        """When get_available_slots calls the calendar API and receives 401,
        the calendar_connections row is marked connection_status='expired'."""

    def test_password_encryption_at_rest(self, db, calendar_connection):
        """The access_token field in the database is encrypted and not readable as plaintext."""


# scheduling/tests/test_booking_link.py

class TestBookingLinkGeneration:

    def test_create_booking_link(self, client, recruiter_token, job, candidate):
        """POST /booking-link with valid job_id, candidate_id, and timezone
        creates a booking_links row and returns a unique slug and public URL."""

    def test_slug_format_is_kebab_case(self, client, recruiter_token, job, candidate):
        """Generated slug is lowercase with format {first}-{last}-{job_slug}-{suffix}."""

    def test_slug_uniqueness_enforced(self, client, recruiter_token, job, candidate_1, candidate_2):
        """Two booking links for the same candidate-job pair have different slugs."""

    def test_no_calendar_connection_returns_404(self, client, recruiter_token, job, candidate):
        """POST /booking-link when recruiter has no active calendar connection
        returns 404 NO_CALENDAR_CONNECTION."""

    def test_invalid_timezone_returns_400(self, client, recruiter_token, job, candidate):
        """POST with availability_timezone='Invalid/Zone' returns 400 VALIDATION_ERROR."""

    def test_missing_candidate_returns_404(self, client, recruiter_token, job):
        """POST with a non-existent candidate_id returns 404 CANDIDATE_NOT_FOUND."""


# scheduling/tests/test_availability.py

class TestGetAvailableSlots:

    def test_fetches_recruiter_calendar(self, client, mock_google_calendar, booking_link):
        """GET /booking-link/{slug}/availability fetches the recruiter's calendar
        from the Google Calendar API."""

    def test_returns_available_slots_within_working_hours(self, client, booking_link, mock_google_calendar):
        """GET returns slots that fit within the configured working hours
        (e.g., 09:00-18:00) and have no conflicts."""

    def test_slot_duration_matches_booking_link_config(self, client, booking_link_45min, mock_google_calendar):
        """For a link with default_duration_minutes=45, returned slots are 45 minutes long."""

    def test_timezone_conversion_in_response(self, client, booking_link_kolkata, mock_google_calendar):
        """Slot times in the response are converted to the link's availability_timezone."""

    def test_api_retry_on_transient_failure(self, client, booking_link, mock_google_api_timeout):
        """On first API call timeout, retries 2 more times. After 3 failures, returns 503."""

    def test_returns_empty_slots_on_calendar_api_error(self, client, booking_link, mock_google_api_failure):
        """After 3 retries fail, returns 503 CALENDAR_API_UNAVAILABLE with empty available_slots."""

    def test_no_auth_required(self, client, booking_link):
        """GET /booking-link/{slug}/availability does not require an Authorization header."""

    def test_invalid_slug_returns_404(self, client):
        """GET with a non-existent slug returns 404 BOOKING_LINK_NOT_FOUND."""

    def test_chronological_order(self, client, booking_link, mock_google_calendar):
        """Returned slots are in chronological order."""


# scheduling/tests/test_book_interview.py

class TestBookInterview:

    def test_creates_interview_record(self, client, booking_link, mock_google_calendar):
        """POST /booking-link/{slug}/book creates an interviews row
        with candidate_id, scheduled_at, and interview_status='scheduled'."""

    def test_creates_calendar_event(self, client, booking_link, mock_google_calendar):
        """After booking, a calendar event exists in the recruiter's calendar
        with title format 'Interview: {candidate_name} - {job_title}'."""

    def test_double_booking_detection(self, client, booking_link, existing_interview, mock_google_calendar):
        """When the selected slot conflicts with an existing event, returns 409
        SLOT_CONFLICT with alternative_slots."""

    def test_sends_confirmation_email(self, client, booking_link, mock_google_calendar, mock_communication):
        """After booking, communication/ service is called to send
        a confirmation email to the candidate."""

    def test_creates_interaction_record(self, client, booking_link, mock_google_calendar):
        """After booking, candidate-management/ has an interaction with
        type='interview_scheduled' and metadata including job_id and scheduled_at."""

    def test_creates_reminder_rows(self, client, booking_link, mock_google_calendar):
        """Two interview_reminders rows are created: one for 24h before, one for 1h before."""

    def test_reminder_scheduled_send_times_correct(self, client, booking_link, mock_google_calendar):
        """If interview is at 09:00, reminders are scheduled for 09:00-24h and 09:00-1h."""

    def test_calendar_api_failure_aborts_booking(self, client, booking_link, mock_google_calendar_failure):
        """If calendar event creation fails, the interviews row is not created
        and error 503 is returned."""

    def test_outside_working_hours_rejected(self, client, booking_link):
        """Requesting a slot at 22:00 when working hours end at 18:00 returns 400 INVALID_SLOT_TIME."""

    def test_candidate_email_from_request(self, client, booking_link):
        """POST with candidate_email in the body uses that email for the booking
        (not the email from candidate-management/)."""


# scheduling/tests/test_reschedule.py

class TestRescheduleInterview:

    def test_reschedule_allows_more_than_4_hours_away(self, client, interview_in_5_days, mock_google_calendar):
        """POST /interviews/{id}/reschedule with a new time 5 days in the future succeeds."""

    def test_reschedule_denied_within_4_hours(self, client, interview_in_2_hours, mock_google_calendar):
        """POST when the current time is less than 4 hours before scheduled_at
        returns 400 RESCHEDULING_NOT_ALLOWED."""

    def test_updates_calendar_event(self, client, interview_in_5_days, mock_google_calendar):
        """The recruiter's calendar event is updated to the new time."""

    def test_updates_reminders(self, client, interview_in_5_days):
        """The reminder rows' scheduled_send_at times are recalculated for the new time."""

    def test_double_booking_check_on_new_time(self, client, interview_in_5_days, existing_interview, mock_google_calendar):
        """If the new time conflicts with another event, returns 409 SLOT_CONFLICT."""

    def test_sends_notification_emails(self, client, interview_in_5_days, mock_communication):
        """After rescheduling, both recruiter and candidate receive notification emails."""

    def test_reschedule_completed_returns_400(self, client, completed_interview):
        """POST to reschedule a 'completed' interview returns 400 INVALID_STATUS_FOR_CANCELLATION."""

    def test_reschedule_cancelled_returns_400(self, client, cancelled_interview):
        """POST to reschedule a 'cancelled' interview returns 400 INVALID_STATUS_FOR_CANCELLATION."""

    def test_atomicity_on_calendar_failure(self, client, interview_in_5_days, mock_google_calendar_failure):
        """If calendar update fails, the database interview record is not changed."""


# scheduling/tests/test_cancel_interview.py

class TestCancelInterview:

    def test_cancel_scheduled_interview(self, client, scheduled_interview, mock_google_calendar):
        """POST /interviews/{id}/cancel sets status='cancelled' and records the reason."""

    def test_removes_calendar_event(self, client, scheduled_interview, mock_google_calendar):
        """The calendar event is removed from the recruiter's calendar."""

    def test_sends_cancellation_emails(self, client, scheduled_interview, mock_communication):
        """Both recruiter and candidate receive cancellation notification emails."""

    def test_cancel_already_cancelled_is_idempotent(self, client, cancelled_interview):
        """POST to cancel an already-cancelled interview returns 200 (idempotent)."""

    def test_cancel_completed_returns_400(self, client, completed_interview):
        """POST to cancel a 'completed' interview returns 400 INVALID_STATUS_FOR_CANCELLATION."""

    def test_clears_pending_reminders(self, client, scheduled_interview):
        """All pending interview_reminders rows for this interview are deleted or marked cancelled."""

    def test_reason_recorded(self, client, scheduled_interview):
        """POST with reason='Candidate no longer interested' records that exact reason."""

    def test_cancelled_by_role_recorded(self, client, scheduled_interview, recruiter_token):
        """POST records cancelled_by_role='recruiter' based on JWT claims."""


# scheduling/tests/test_list_interviews.py

class TestListInterviews:

    def test_returns_recruiter_interviews(self, client, recruiter_token, recruiter_with_interviews):
        """GET /interviews returns interviews for the authenticated recruiter."""

    def test_filter_by_status(self, client, recruiter_token, recruiter_with_mixed_statuses):
        """GET /interviews?status=scheduled returns only interviews with that status."""

    def test_filter_by_date_range(self, client, recruiter_token, recruiter_with_interviews_various_dates):
        """GET /interviews?date_from=2026-04-20&date_to=2026-04-30 returns only interviews in that range."""

    def test_pagination(self, client, recruiter_token, recruiter_with_many_interviews):
        """GET with limit=20&offset=40 returns 20 interviews starting at position 40."""

    def test_total_count_reflects_full_set(self, client, recruiter_token, recruiter_with_100_interviews):
        """total_count in the response reflects the full matching count, not just the page."""

    def test_admin_can_view_all_workspaces(self, client, admin_token, interviews_across_workspaces):
        """GET without workspace_id filter returns interviews from all workspaces for Admin."""

    def test_recruiter_requires_workspace_filter_or_own_workspace(self, client, recruiter_token):
        """GET without workspace_id returns only interviews in the recruiter's assigned workspaces."""

    def test_excludes_soft_deleted_candidates(self, client, recruiter_token, soft_deleted_candidate_interview):
        """If a candidate has is_deleted=TRUE, their interviews are not returned."""

    def test_ordered_by_scheduled_at_desc(self, client, recruiter_token, recruiter_with_interviews):
        """Results are ordered by scheduled_at DESC (most recent first)."""


# scheduling/tests/test_reminders.py

class TestInterviewReminders:

    def test_reminders_created_on_booking(self, client, booking_link, mock_google_calendar):
        """POST /book creates interview_reminders rows for 24h and 1h before."""

    def test_celery_task_sends_pending_reminders(self, client, celery_worker, interview_with_pending_reminders):
        """When the Celery beat task runs, pending reminders with scheduled_send_at <= NOW()
        are sent via communication/ service."""

    def test_failed_reminder_recorded(self, client, celery_worker, interview_with_pending_reminders, mock_communication_failure):
        """If communication/ returns an error, the reminder is marked delivery_status='failed'
        with the error message recorded."""

    def test_no_reminder_retry(self, client, celery_worker, failed_reminder):
        """After a reminder fails once, it is not retried automatically."""

    def test_pending_reminders_cleared_on_cancel(self, client, scheduled_interview):
        """When an interview is cancelled, all pending reminders are deleted or marked cancelled."""

    def test_reminder_not_sent_if_interview_cancelled(self, client, cancelled_interview, celery_worker):
        """If an interview is cancelled before the reminder is sent, the reminder is not sent."""


# scheduling/tests/test_calendar_token_expiration.py

class TestCalendarTokenExpiration:

    def test_token_expiration_marked_on_api_error(self, client, recruiter_token, calendar_connection, mock_google_expired_token):
        """When get_available_slots calls the Google API and receives HTTP 401,
        the calendar_connections row is marked connection_status='expired'."""

    def test_expired_connection_blocks_new_booking_link(self, client, recruiter_token, expired_calendar_connection, job, candidate):
        """POST /booking-link when connection is 'expired' returns 404 NO_CALENDAR_CONNECTION."""

    def test_existing_interviews_not_affected(self, client, expired_calendar_connection, scheduled_interview):
        """Marking a connection as expired does not cancel or modify existing interviews."""

    def test_recruiter_notified_to_reconnect(self, client, recruiter_token, calendar_connection, mock_google_expired_token, mock_communication):
        """When token expiration is detected, communication/ is called to notify the recruiter."""
```

---

## 6. Internal module structure

```
scheduling/
├── api.py                  # Public interface (FastAPI router + Pydantic models)
├── service.py              # Business logic layer
├── repository.py           # Database queries (SQLAlchemy)
├── models.py               # SQLAlchemy ORM models
├── schemas.py              # Pydantic request/response schemas
├── calendar_provider.py     # Adapter for Google Calendar API and Microsoft Graph
├── oauth_handler.py        # OAuth flow and token exchange logic
├── tasks.py                # Celery tasks (reminder delivery, token refresh)
├── exceptions.py           # Service-specific exception classes
├── constants.py            # Enums, status values, config
├── schema.sql              # Database migration source
├── tests/
│   ├── conftest.py         # Fixtures (test DB, mock calendar API, mock communication, tokens)
│   ├── test_oauth.py
│   ├── test_booking_link.py
│   ├── test_availability.py
│   ├── test_book_interview.py
│   ├── test_reschedule.py
│   ├── test_cancel_interview.py
│   ├── test_list_interviews.py
│   ├── test_reminders.py
│   └── test_calendar_token_expiration.py
└── README.md               # Developer onboarding for this service
```

Only `api.py` and `schemas.py` are importable by other services. Everything else is internal.

---

## 7. Dependencies and constraints

**Internal service dependencies**:

- `candidate-management/add_interaction(candidate_id, type, content, metadata)`: Called after booking, rescheduling, and cancellation to log interaction events.
- `candidate-management/get_candidate(candidate_id)`: Called during booking link generation to fetch candidate email and name. Also called when booking without a pre-specified candidate_id.
- `job-management/get_job(job_id)`: Called during booking link generation to fetch job title and details for the booking link and calendar event description.
- `communication/send_email(to, template, context)`: Called to send booking confirmations, reminders, rescheduling notifications, and cancellation notifications.
- `auth/get_token_claims(jwt)`: Called to extract user_id, role, and workspace_ids from the JWT.

**External dependencies**:

- PostgreSQL 15+: Primary data store for calendar connections, interviews, booking links, reminders.
- Redis + Celery: Task queue for asynchronous reminder delivery and scheduled tasks.
- Google Calendar API v3: Real-time availability and calendar event management for Google Workspace users.
- Microsoft Graph API (Outlook): Real-time availability and calendar event management for Outlook users.
- AWS Secrets Manager or encrypted key store: Storage for OAuth tokens (access and refresh).

**Performance targets**:

| Operation | Target | Measured at |
|-----------|--------|-------------|
| Generate booking link | < 200ms | API response time |
| Get available slots (24-day window) | < 2s | Including calendar API round-trip |
| Book interview | < 1.5s | Including calendar event creation |
| Reschedule interview | < 1.5s | Including calendar event update |
| Cancel interview | < 1s | Including calendar event deletion |
| List interviews | < 500ms | For up to 1,000 interviews |
| Get interview details | < 100ms | API response time |
| Send reminder | < 500ms | Per reminder (async Celery task) |

**Security**:

- All endpoints require a valid JWT (except `/booking-link/{slug}/availability` and `/booking-link/{slug}/book`, which are public).
- OAuth tokens (access and refresh) are encrypted at rest using AES-256. Decryption happens at the application layer only when calling the calendar provider.
- Booking links have a unique slug and are not enumerable; a user must know the slug to view availability or book.
- Interview operations (reschedule, cancel) require the requester to be the interview's recruiter or an Admin.
- All state-changing operations (booking, rescheduling, cancellation) generate an interaction record for audit trail.

---

## 8. Out of scope

- Video conferencing integration (Zoom, Google Meet). Future phase.
- Recurring interviews or interview series. Phase 2.
- Attendee limits or multi-recruiter interviews. Phase 1 assumes 1-on-1 interviews.
- Candidate availability submission (candidates cannot directly tell the system their preferred times). Phase 2.
- Interview notes or debrief recording. Owned by separate service or future enhancement.
- Calendar event sync from external sources (one-way write only in Phase 1).
- Undo/rollback of operations. Not supported; only forward-moving state changes.
- Custom calendar event metadata (color, categories, custom fields).

---

## 9. Verification

```bash
cd scheduling/
pytest tests/ -v --tb=short
```

All tests must pass. Additionally, verify these end-to-end scenarios manually or via integration tests:

1. Connect a Google Calendar account via OAuth. Verify the token is stored and marked active.
2. Generate a booking link for a candidate and job. Verify the slug is unique, the URL is shareable, and the availability check returns real-time slots.
3. Book an interview via the public booking endpoint. Verify the calendar event is created, the interview record exists, and confirmation email is sent.
4. Verify two reminder rows are created with correct scheduled_send_at times.
5. Run the Celery beat task at the reminder send time. Verify the email is delivered and the reminder is marked `delivery_status='sent'`.
6. Reschedule an interview to a new time 5 days away. Verify the calendar event is updated and reminders are recalculated.
7. Attempt to reschedule within 4 hours of the interview time. Verify 400 error is returned.
8. Cancel an interview. Verify the calendar event is removed, notification emails are sent, and the status is 'cancelled'.
9. Verify that soft-deleted candidates' interviews do not appear in list views.
10. Trigger a calendar API token expiration (mock HTTP 401 response). Verify the connection is marked 'expired' and a notification is sent to the recruiter.
11. List interviews with filters (status, date range). Verify pagination and total_count are correct.
