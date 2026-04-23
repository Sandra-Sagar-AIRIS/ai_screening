# Service spec: communication

**Version**: 1.0
**Date**: 2026-04-18
**Parent PRD**: AIRIS Phase 1 MVP PRD v1

---

## 1. Service boundary

**Folder**: `communication/`

This service owns all email communication: OAuth connections to Gmail and Outlook, sending emails, receiving and syncing incoming emails, managing email templates, and maintaining a unified communication timeline per candidate. WhatsApp messaging is out of scope for Phase 1. No other service sends emails directly; they request this service to do so.

**Owns**: `email_connections` table, `emails` table, `email_templates` table, `email_sync_status` table.

**Depends on**:

- `candidate-management/` to read candidate email and contact details, and to write email interactions to the timeline via `add_interaction` endpoint
- `job-management/` to read job details for template variable substitution (job title, company name, location)
- `auth/` to manage OAuth tokens for Gmail and Outlook integrations

**Depended on by**:

- `scheduling/` uses this service to send booking confirmation and reminder emails
- `pipeline/` can trigger notification emails when candidates advance to certain stages (calls this service's `POST /email/send` endpoint)

---

## 2. Database schema

```sql
-- communication/schema.sql

CREATE TABLE email_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    recruiter_id UUID NOT NULL,
    provider VARCHAR(20) NOT NULL,            -- 'gmail' | 'outlook'
    access_token_encrypted BYTEA NOT NULL,    -- AES-256 encrypted OAuth access token
    refresh_token_encrypted BYTEA,            -- AES-256 encrypted OAuth refresh token
    token_expires_at TIMESTAMPTZ,
    email_address VARCHAR(255) NOT NULL,      -- Provider email address (e.g. recruiter@company.com)
    sync_status VARCHAR(20) DEFAULT 'healthy',  -- 'healthy' | 'degraded' | 'disconnected'
    last_sync_at TIMESTAMPTZ,
    last_sync_error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT email_connections_unique UNIQUE (organization_id, recruiter_id, provider)
);

CREATE INDEX idx_email_connections_org ON email_connections (organization_id);
CREATE INDEX idx_email_connections_recruiter ON email_connections (recruiter_id);
CREATE INDEX idx_email_connections_sync_status ON email_connections (sync_status) WHERE sync_status != 'healthy';

CREATE TABLE emails (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    candidate_id UUID NOT NULL,
    direction VARCHAR(10) NOT NULL,           -- 'sent' | 'received'
    from_address VARCHAR(255) NOT NULL,
    to_address VARCHAR(255) NOT NULL,
    subject VARCHAR(500),
    body TEXT,                                 -- HTML-formatted email body
    provider_email_id VARCHAR(500),            -- Gmail: message ID, Outlook: message ID
    provider VARCHAR(20),                      -- 'gmail' | 'outlook' (provider it came from)
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    synced_at TIMESTAMPTZ,                     -- When the email was synced from provider (for received emails)
    CONSTRAINT emails_unique_provider_id UNIQUE (provider, provider_email_id)
);

CREATE INDEX idx_emails_candidate ON emails (candidate_id, created_at DESC);
CREATE INDEX idx_emails_organization ON emails (organization_id);
CREATE INDEX idx_emails_direction ON emails (direction);
CREATE INDEX idx_emails_provider_id ON emails (provider, provider_email_id);

CREATE TABLE email_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    subject VARCHAR(500) NOT NULL,
    body TEXT NOT NULL,                        -- HTML-formatted template with {{variable}} placeholders
    variables TEXT[] DEFAULT '{}',             -- Array of variable names extracted from body
    created_by UUID NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT email_templates_unique UNIQUE (organization_id, name) WHERE is_deleted = FALSE
);

CREATE INDEX idx_email_templates_org ON email_templates (organization_id) WHERE is_deleted = FALSE;
CREATE INDEX idx_email_templates_created_by ON email_templates (created_by);

CREATE TABLE email_sync_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_connection_id UUID NOT NULL REFERENCES email_connections(id) ON DELETE CASCADE,
    sync_type VARCHAR(20) NOT NULL,           -- 'incoming' | 'outgoing'
    status VARCHAR(20) NOT NULL,              -- 'pending' | 'in_progress' | 'success' | 'failed'
    last_attempted_at TIMESTAMPTZ,
    last_successful_at TIMESTAMPTZ,
    error_message TEXT,
    error_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sync_status_connection ON email_sync_status (email_connection_id);
CREATE INDEX idx_sync_status_status ON email_sync_status (status);
```

---

## 3. REST API endpoints

All endpoints require authentication. The `Authorization` header carries a JWT issued by `auth/`. The user's role and assigned workspaces are encoded in the token claims.

### 3.1 Initiate email connection (OAuth)

```
POST /api/v1/email/connect
```

**Request body**:
```json
{
  "provider": "gmail"
}
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...&redirect_uri=...&scope=..."
  }
}
```

Returns an OAuth authorization URL. The client opens this in a browser. After user grants permission, the OAuth provider redirects to `GET /api/v1/email/callback?code=...&state=...`.

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 400 | `INVALID_PROVIDER` | `provider` is not 'gmail' or 'outlook'. |
| 401 | `UNAUTHORIZED` | Missing or invalid auth token. |

### 3.2 OAuth callback handler

```
GET /api/v1/email/callback?code=AUTH_CODE&state=STATE
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "email_connection_id": "conn-uuid-001",
    "email_address": "recruiter@company.com",
    "provider": "gmail",
    "sync_status": "healthy"
  }
}
```

Exchanges the authorization code for tokens, stores them encrypted in the database, and returns the connection details.

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 400 | `INVALID_CODE` | Auth code is invalid or expired. |
| 500 | `TOKEN_EXCHANGE_FAILED` | OAuth provider API call failed. |

### 3.3 Get email connection status

```
GET /api/v1/email/status
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "connections": [
      {
        "id": "conn-uuid-001",
        "provider": "gmail",
        "email_address": "recruiter@company.com",
        "sync_status": "healthy",
        "last_sync_at": "2026-04-18T14:30:00Z",
        "last_sync_error": null
      },
      {
        "id": "conn-uuid-002",
        "provider": "outlook",
        "email_address": "recruiter.backup@company.com",
        "sync_status": "degraded",
        "last_sync_at": "2026-04-18T14:25:00Z",
        "last_sync_error": "Refresh token expired"
      }
    ]
  }
}
```

Returns all email connections for the authenticated recruiter, showing sync health.

### 3.4 Send email

```
POST /api/v1/email/send
```

**Request body**:
```json
{
  "candidate_id": "cand-uuid-001",
  "to_address": "candidate@example.com",
  "subject": "Interview Scheduled - Acme Corp",
  "body": "<p>Hi {{candidate_first_name}},</p><p>Your interview is scheduled for {{interview_date}} at {{interview_time}}.</p>",
  "template_id": null,
  "template_variables": {
    "candidate_first_name": "Priya",
    "interview_date": "2026-04-25",
    "interview_time": "2:00 PM IST"
  }
}
```

Either `body` (raw HTML) or `template_id` (with `template_variables`) must be provided, not both.

**Success response** (201 Created):
```json
{
  "success": true,
  "data": {
    "email_id": "email-uuid-001",
    "candidate_id": "cand-uuid-001",
    "to_address": "candidate@example.com",
    "subject": "Interview Scheduled - Acme Corp",
    "direction": "sent",
    "created_at": "2026-04-18T15:45:00Z"
  }
}
```

Sends the email via AIRIS SMTP. The email is immediately stored in the `emails` table. Sync to the provider's sent folder occurs asynchronously during the next sync cycle.

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 400 | `VALIDATION_ERROR` | Missing required fields or both `body` and `template_id` provided. |
| 404 | `CANDIDATE_NOT_FOUND` | Candidate ID does not exist. |
| 404 | `TEMPLATE_NOT_FOUND` | Template ID does not exist or is soft-deleted. |
| 422 | `UNRESOLVED_VARIABLES` | Template has variables with no values provided. Response includes `missing_variables` array. |
| 500 | `SMTP_FAILED` | AIRIS SMTP delivery failed. |

### 3.5 Get email thread for candidate

```
GET /api/v1/email/threads/{candidate_id}?limit=50&offset=0
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "candidate_id": "cand-uuid-001",
    "emails": [
      {
        "id": "email-uuid-001",
        "direction": "received",
        "from_address": "candidate@example.com",
        "to_address": "recruiter@company.com",
        "subject": "Re: Interview Scheduled - Acme Corp",
        "body": "<p>Thank you for the opportunity...</p>",
        "is_read": false,
        "created_at": "2026-04-18T16:30:00Z"
      },
      {
        "id": "email-uuid-002",
        "direction": "sent",
        "from_address": "recruiter@company.com",
        "to_address": "candidate@example.com",
        "subject": "Interview Scheduled - Acme Corp",
        "body": "<p>Hi Priya,</p>...",
        "is_read": true,
        "created_at": "2026-04-18T15:45:00Z"
      }
    ],
    "total_count": 2,
    "limit": 50,
    "offset": 0
  }
}
```

Returns all emails (sent and received) for a candidate, ordered most recent first. Only shows emails the recruiter has access to (via workspace membership).

**Error**: 404 `CANDIDATE_NOT_FOUND` if the candidate does not exist.

### 3.6 Create email template

```
POST /api/v1/email/templates
```

**Request body**:
```json
{
  "name": "Interview Confirmation",
  "subject": "Your Interview is Confirmed - {{company_name}}",
  "body": "<p>Hi {{candidate_first_name}},</p><p>Congratulations! Your interview with {{company_name}} is confirmed for {{interview_date}} at {{interview_time}}.</p><p>Booking link: {{booking_link}}</p><p>Best regards,<br/>{{recruiter_name}}</p>"
}
```

**Success response** (201 Created):
```json
{
  "success": true,
  "data": {
    "id": "template-uuid-001",
    "name": "Interview Confirmation",
    "subject": "Your Interview is Confirmed - {{company_name}}",
    "body": "...",
    "variables": ["candidate_first_name", "company_name", "interview_date", "interview_time", "booking_link", "recruiter_name"],
    "created_by": "recruiter-user-id-001",
    "created_at": "2026-04-18T10:00:00Z"
  }
}
```

Templates are scoped to the organization. Variables are extracted from `subject` and `body` automatically.

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 400 | `VALIDATION_ERROR` | Missing `name`, `subject`, or `body`. |
| 409 | `DUPLICATE_NAME` | Template with this name already exists in the organization. |

### 3.7 List email templates

```
GET /api/v1/email/templates?limit=50&offset=0
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "templates": [
      {
        "id": "template-uuid-001",
        "name": "Interview Confirmation",
        "subject": "Your Interview is Confirmed - {{company_name}}",
        "variables": ["candidate_first_name", "company_name", "interview_date", "interview_time", "booking_link", "recruiter_name"],
        "created_by": "recruiter-user-id-001",
        "created_at": "2026-04-18T10:00:00Z"
      }
    ],
    "total_count": 1,
    "limit": 50,
    "offset": 0
  }
}
```

Returns all non-deleted templates for the organization.

### 3.8 Update email template

```
PATCH /api/v1/email/templates/{template_id}
```

**Request body**: Partial update. Only fields present are changed.
```json
{
  "subject": "Interview Confirmed - {{company_name}}",
  "body": "<p>Hi {{candidate_first_name}},</p>..."
}
```

**Success response** (200 OK): Returns updated template.

**Error**: 404 `TEMPLATE_NOT_FOUND` if the template does not exist or is soft-deleted.

### 3.9 Soft delete email template

```
DELETE /api/v1/email/templates/{template_id}
```

**Success response** (204 No Content).

Sets `is_deleted = TRUE` and `deleted_at = NOW()`. The template is hidden from list views but retained in the database.

**Error**: 404 if not found.

### 3.10 Render template preview

```
POST /api/v1/email/templates/{template_id}/render
```

**Request body**:
```json
{
  "variables": {
    "candidate_first_name": "Priya",
    "company_name": "Acme Corp",
    "interview_date": "2026-04-25",
    "interview_time": "2:00 PM IST",
    "booking_link": "https://calendly.com/acme",
    "recruiter_name": "Rajesh Singh",
    "recruiter_email": "rajesh@staffing.com",
    "recruiter_phone": "+91-9876543210"
  }
}
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "subject": "Interview Confirmed - Acme Corp",
    "body": "<p>Hi Priya,</p><p>Congratulations! Your interview with Acme Corp is confirmed for 2026-04-25 at 2:00 PM IST.</p>...",
    "unresolved_variables": []
  }
}
```

**Validation error response** (422 Unprocessable Entity):
```json
{
  "success": false,
  "error": {
    "code": "UNRESOLVED_VARIABLES",
    "message": "The following template variables have no values.",
    "missing_variables": ["booking_link"]
  }
}
```

Returns a preview of the rendered template with all variables substituted. If any variable in the template has no value in the request, the response indicates which variables are missing.

---

## 4. Behaviour requirements

### connect_email_account

- Given a valid provider ('gmail' or 'outlook'), generates an OAuth authorization URL with appropriate scopes (Gmail: `https://www.googleapis.com/auth/gmail.send`, `https://www.googleapis.com/auth/gmail.readonly`; Outlook: `mail.send`, `mail.read`) and returns it. The state parameter is cryptographically random and stored for CSRF verification.
- Given an invalid provider, returns 400 `INVALID_PROVIDER`.
- Each recruiter can have one connection per provider. A second connection for the same provider and recruiter overwrites the first.

### oauth_callback_handler

- Validates the state parameter against the stored value to prevent CSRF attacks. If invalid, returns 400.
- Exchanges the authorization code for access and refresh tokens via the provider's token endpoint.
- Encrypts tokens using AES-256 and stores them in `email_connections` with `sync_status = 'healthy'` and `last_sync_at = NULL`.
- Calls the provider's user info endpoint to confirm the email address and stores it.
- Returns 200 with connection details.
- If the token exchange fails, returns 500 `TOKEN_EXCHANGE_FAILED`.

### send_email

- Given valid input (candidate_id, to_address, subject, and either body or template_id with template_variables), renders the body (if template), validates that all template variables have values, and sends via AIRIS SMTP.
- Creates a row in the `emails` table with direction='sent', the full rendered body, and created_at=NOW().
- Calls `candidate-management/add_interaction` with type='email_sent', content=subject, metadata={to_address, email_id}.
- The email is delivered immediately via SMTP regardless of sync status. Sync to the provider's sent folder is asynchronous and happens during the next sync cycle.
- If body contains invalid HTML, the email is still sent but the system logs a warning.
- Given a template_id that does not exist, returns 404.
- Given a template with unresolved variables, returns 422 `UNRESOLVED_VARIABLES` with the missing_variables list.
- Given a candidate_id that does not exist, returns 404.
- Given SMTP failure, returns 500 `SMTP_FAILED` and does not create an email record.

### get_email_thread

- Returns all emails in the `emails` table for the given candidate_id, ordered by created_at DESC (most recent first).
- Only returns emails where the recruiter (from JWT) has access via workspace membership (verified against candidate's workspace).
- Includes both sent and received emails.
- Returns emails with is_read as stored in the database.
- Does not auto-mark as read; this is a read-only operation.

### create_email_template

- Given valid input (name, subject, body), extracts all `{{variable_name}}` placeholders from subject and body, stores them in the `variables` array, and creates the template scoped to the organization.
- Given a name that already exists (non-deleted) in the organization, returns 409 `DUPLICATE_NAME`.
- HTML in body is stored as-is; no validation or sanitization is performed (stored as provided; rendering applies escaping if needed).
- created_by is set to the authenticating recruiter's user ID.

### render_template

- Given a template_id and a variables object, substitutes all `{{variable_name}}` placeholders in subject and body with corresponding values from the object.
- If the template has a variable that is not in the provided variables object, returns 422 `UNRESOLVED_VARIABLES` with missing_variables listing those not provided.
- Returns the rendered subject and body as plain strings (no further encoding).
- Does not modify the template or create any records.

### email_sync_cycle (asynchronous, Celery beat every 5 minutes)

- For each `email_connection` with sync_status != 'disconnected', performs a two-way sync with the provider.
- **Outgoing sync**: Queries the `emails` table for rows where direction='sent' and provider_email_id IS NULL. For each, calls the provider API to fetch the sent email ID, updates the emails row with provider_email_id, and updates the email_connections.last_sync_at.
- **Incoming sync**: Calls the provider API to fetch new emails to/from the candidate's email address (only emails involving candidates in the system; does not sync the recruiter's entire inbox). For each new email, creates a row in the `emails` table with direction='received', provider_email_id set to the provider's ID, and calls `candidate-management/add_interaction` with type='email_received'.
- On success, sets sync_status='healthy', clears last_sync_error, and updates last_sync_at.
- On transient failure (network error, rate limit), sets sync_status='degraded', increments error_count, and logs the error.
- On permanent failure (token expired, provider returns 401), sets sync_status='disconnected' and requires manual reconnection (the recruiter re-authorizes via POST /connect and the callback updates the connection).
- Only syncs emails to/from known candidate email addresses (from the `candidates` table). Emails not involving a candidate are not synced.

### template_variable_substitution

- Supports the following template variables:
  - `{{candidate_name}}` → full name (first_name + last_name from candidate-management)
  - `{{candidate_first_name}}` → first_name
  - `{{candidate_email}}` → candidate email address
  - `{{job_title}}` → from job-management
  - `{{company_name}}` → from job-management
  - `{{job_location}}` → from job-management
  - `{{interview_date}}` → date in format YYYY-MM-DD
  - `{{interview_time}}` → time string provided by caller
  - `{{booking_link}}` → URL provided by caller
  - `{{recruiter_name}}` → recruiter's full name (from auth service claims)
  - `{{recruiter_email}}` → recruiter's email address (from email_connections)
  - `{{recruiter_phone}}` → recruiter's phone (from auth service claims if available)
- If a variable is present in the template but no value is provided, rendering returns an error with the missing variable name.
- Variable names are case-sensitive. `{{Candidate_Name}}` is not the same as `{{candidate_name}}`.

---

## 5. Acceptance criteria as tests

```python
# communication/tests/test_connect.py

class TestConnectEmail:

    def test_initiate_gmail_connection(self, client, recruiter_token):
        """POST /api/v1/email/connect with provider='gmail'
        returns 200 with an auth_url containing google.com."""

    def test_initiate_outlook_connection(self, client, recruiter_token):
        """POST /api/v1/email/connect with provider='outlook'
        returns 200 with an auth_url containing microsoft.com."""

    def test_invalid_provider_returns_400(self, client, recruiter_token):
        """POST with provider='slack' returns 400 INVALID_PROVIDER."""

    def test_oauth_callback_success(self, client, mock_oauth_provider):
        """GET /callback?code=AUTH_CODE&state=STATE exchanges the code,
        stores encrypted tokens, and returns 200 with connection_id."""

    def test_callback_csrf_protection(self, client):
        """GET /callback with an invalid state returns 400."""

    def test_token_storage_encrypted(self, client, recruiter_token, mock_oauth_provider, db):
        """After callback, email_connections.access_token_encrypted contains
        non-plaintext bytes."""

    def test_invalid_code_returns_400(self, client, mock_oauth_failure):
        """GET /callback with an expired code returns 400 INVALID_CODE."""


# communication/tests/test_send.py

class TestSendEmail:

    def test_send_with_raw_body(self, client, recruiter_token, candidate):
        """POST /api/v1/email/send with body and candidate_id
        returns 201 with an email_id, creates an emails row,
        and calls candidate-management/add_interaction."""

    def test_send_with_template_variables(self, client, recruiter_token, candidate, template):
        """POST with template_id and template_variables renders the template,
        sends the email, and creates an emails row with the rendered body."""

    def test_unresolved_variables_returns_422(self, client, recruiter_token, candidate, template):
        """POST with a template that has {{missing_var}} but no value
        returns 422 with missing_variables=['missing_var']."""

    def test_candidate_not_found_returns_404(self, client, recruiter_token):
        """POST with a non-existent candidate_id returns 404 CANDIDATE_NOT_FOUND."""

    def test_template_not_found_returns_404(self, client, recruiter_token, candidate):
        """POST with a non-existent template_id returns 404 TEMPLATE_NOT_FOUND."""

    def test_smtp_failure_returns_500(self, client, recruiter_token, candidate, mock_smtp_failure):
        """POST when SMTP fails returns 500 SMTP_FAILED
        and no emails row is created."""

    def test_email_syncs_independently_of_sync_status(self, client, recruiter_token, candidate, disconnected_connection):
        """POST sends the email even though email_connections.sync_status='disconnected'.
        Sync to provider is deferred to the next cycle."""


# communication/tests/test_thread.py

class TestEmailThread:

    def test_get_sent_and_received_emails(self, client, recruiter_token, candidate_with_emails):
        """GET /api/v1/email/threads/{candidate_id} returns both sent
        and received emails ordered by created_at DESC."""

    def test_pagination(self, client, recruiter_token, candidate_with_many_emails):
        """GET /threads/{id}?limit=10&offset=20 returns 10 emails,
        total_count reflects all emails for the candidate."""

    def test_includes_is_read_flag(self, client, recruiter_token, candidate_with_unread_emails):
        """GET returns emails with is_read as stored in the database."""

    def test_candidate_not_found_returns_404(self, client, recruiter_token):
        """GET /threads/{nonexistent_id} returns 404."""

    def test_recruiter_cannot_access_other_workspace(self, client, recruiter_token_workspace_a, candidate_in_workspace_b):
        """Recruiter in workspace A cannot GET emails for a candidate in workspace B.
        Returns 403 or 404 depending on implementation."""


# communication/tests/test_templates.py

class TestEmailTemplates:

    def test_create_template(self, client, recruiter_token):
        """POST /api/v1/email/templates with name, subject, body
        returns 201 with template_id and extracted variables array."""

    def test_variables_extracted_from_subject_and_body(self, client, recruiter_token):
        """A template with {{candidate_first_name}} in subject and {{company_name}} in body
        has variables=['candidate_first_name', 'company_name']."""

    def test_duplicate_name_returns_409(self, client, recruiter_token, existing_template):
        """Creating a template with the same name in the same organization
        returns 409 DUPLICATE_NAME."""

    def test_list_templates(self, client, recruiter_token, templates):
        """GET /api/v1/email/templates returns all non-deleted templates."""

    def test_soft_delete_template(self, client, recruiter_token, template):
        """DELETE /api/v1/email/templates/{id} sets is_deleted=TRUE
        and GET /templates no longer includes it."""

    def test_update_template(self, client, recruiter_token, template):
        """PATCH /api/v1/email/templates/{id} with new subject updates
        the template and re-extracts variables."""

    def test_render_template_substitutes_variables(self, client, recruiter_token, template):
        """POST /templates/{id}/render with variables substitutes all
        {{placeholder}} with values and returns the rendered subject and body."""

    def test_render_missing_variable_returns_422(self, client, recruiter_token, template):
        """POST /render with a template variable not in the variables object
        returns 422 UNRESOLVED_VARIABLES with missing_variables list."""

    def test_templates_scoped_to_organization(self, client, recruiter_token_org_a, recruiter_token_org_b, template_org_a):
        """Recruiter in org A cannot see or use templates from org B."""


# communication/tests/test_sync.py

class TestEmailSync:

    def test_sync_fetches_incoming_emails(self, client, recruiter_token, mock_gmail_api, celery_worker, candidate):
        """After running a sync cycle, new incoming emails from the Gmail API
        are created in the emails table with direction='received'."""

    def test_sync_only_includes_candidate_emails(self, client, recruiter_token, mock_gmail_api, celery_worker, candidate):
        """The sync fetches only emails to/from the candidate's address,
        not the entire recruiter inbox."""

    def test_sync_adds_interaction_for_received_email(self, client, recruiter_token, mock_gmail_api, celery_worker, candidate):
        """When a received email is synced, candidate-management/add_interaction
        is called with type='email_received'."""

    def test_sync_outgoing_emails(self, client, recruiter_token, mock_gmail_api, celery_worker, sent_email_without_provider_id):
        """After sync, a sent email that lacks a provider_email_id is updated
        with the provider's message ID."""

    def test_sync_updates_sync_status_healthy_on_success(self, client, recruiter_token, mock_gmail_api, celery_worker, connection):
        """After a successful sync, email_connections.sync_status='healthy'."""

    def test_sync_degrades_on_transient_error(self, client, recruiter_token, mock_gmail_api_rate_limited, celery_worker, connection):
        """When the API returns a 429 (rate limit), sync_status='degraded'
        and last_sync_error is set."""

    def test_sync_disconnects_on_token_expiry(self, client, recruiter_token, mock_gmail_api_401, celery_worker, connection):
        """When the API returns 401 (token expired), sync_status='disconnected'
        and the recruiter must reconnect."""

    def test_sync_idempotent_duplicate_emails(self, client, recruiter_token, mock_gmail_api, celery_worker, candidate):
        """Running sync twice does not create duplicate emails (provider_email_id
        constraint prevents duplicates)."""

    def test_sync_runs_every_5_minutes(self, client, recruiter_token, celery_beat):
        """A Celery beat schedule is configured to run email_sync_cycle
        every 5 minutes."""


# communication/tests/test_auth.py

class TestRoleAccess:

    def test_admin_can_view_all_email_threads(self, client, admin_token, candidate):
        """Admin calling GET /threads/{candidate_id} can access it
        regardless of workspace."""

    def test_recruiter_can_view_workspace_threads(self, client, recruiter_token_workspace_a, candidate_in_workspace_a):
        """Recruiter can view threads for candidates in their workspace."""

    def test_recruiter_cannot_view_other_workspace_threads(self, client, recruiter_token_workspace_a, candidate_in_workspace_b):
        """Recruiter in workspace A cannot view threads for workspace B candidates."""

    def test_client_viewer_no_email_access(self, client, client_viewer_token):
        """Client Viewer attempting POST /send or GET /threads returns 403."""
```

---

## 6. Internal module structure

```
communication/
├── api.py                  # Public interface (FastAPI router + Pydantic models)
├── service.py              # Business logic layer (send, render, sync)
├── repository.py           # Database queries (SQLAlchemy)
├── models.py               # SQLAlchemy ORM models
├── schemas.py              # Pydantic request/response schemas
├── tasks.py                # Celery tasks (email sync cycle)
├── oauth_handler.py        # OAuth token exchange logic (Gmail & Outlook)
├── template_renderer.py    # Variable substitution and template rendering
├── smtp_client.py          # AIRIS SMTP configuration and sending
├── exceptions.py           # Service-specific exception classes
├── constants.py            # Enums, valid values, config
├── schema.sql              # Database migration source
├── tests/
│   ├── conftest.py         # Fixtures (test DB, mock OAuth, mock SMTP, tokens)
│   ├── test_connect.py
│   ├── test_send.py
│   ├── test_thread.py
│   ├── test_templates.py
│   ├── test_sync.py
│   └── test_auth.py
└── README.md               # Developer onboarding for this service
```

Only `api.py` and `schemas.py` are importable by other services. Everything else is internal.

---

## 7. Dependencies and constraints

**Internal service dependencies**:

- `candidate-management/add_interaction(candidate_id, type, content, metadata) -> InteractionRecord`: Called when an email is sent or received. Must succeed before the email operation completes for sent emails; failures on received emails are logged but do not block the sync.
- `job-management/get_job(job_id) -> JobDetails`: Called during template rendering to fetch job title, company name, location. Must handle timeout (2s) and return null gracefully.
- `auth/get_user(user_id) -> UserProfile`: Called during sync and send to fetch recruiter name and phone. Must handle timeout (1s).

**External dependencies**:

- PostgreSQL 15+: Primary data store. Requires `gen_random_uuid()`.
- Redis + Celery: Async task queue for email sync cycle.
- Gmail API (OAuth 2.0): For Gmail two-way sync. Scopes: `https://www.googleapis.com/auth/gmail.send`, `https://www.googleapis.com/auth/gmail.readonly`.
- Microsoft Graph API (OAuth 2.0): For Outlook two-way sync. Scopes: `mail.send`, `mail.read`.
- AIRIS SMTP: Internal mail server for sending emails (independent of provider sync). Must support TLS and SMTP AUTH.
- Cryptography library (e.g., PyCryptodome): For AES-256 encryption of OAuth tokens at rest.

**Performance targets**:

| Operation | Target | Measured at |
|-----------|--------|-------------|
| Send email | < 500ms | API response time (SMTP delivery) |
| Get email thread | < 300ms | API response (up to 50 emails) |
| Create template | < 100ms | API response time |
| Render template | < 100ms | API response time |
| Full sync cycle per connection | < 10s | Per-connection (5 emails received/sent) |
| Sync cycle (all connections) | < 60s | Every 5 minutes, all organizations |

**Security**:

- All endpoints require a valid JWT with user claims.
- OAuth access and refresh tokens are encrypted at rest using AES-256 with a service-level key.
- Email bodies support basic HTML; no script execution is possible (body is sent as MIME text/html).
- Sync only pulls emails to/from candidate email addresses; recruiter's entire inbox is not synced.
- Soft delete of templates prevents accidental data loss but hides them from users.
- Recruiter email access is scoped by workspace membership via candidate-management checks.

---

## 8. Out of scope

- WhatsApp, SMS, or other messaging channels. Phase 2+.
- Email scheduling (send at a future time). Phase 2.
- Email read receipts from providers. Phase 1 stores is_read from the database; provider receipts are Phase 2.
- Advanced email search (full-text search of email bodies, date range filters). Phase 2.
- Email categorization or tagging (e.g., starred, flagged). Phase 2.
- Attachment handling (receive and store attachments). Phase 1 extracts text bodies only.
- Email encryption or signature (PGP, S/MIME). Phase 2+.
- Delegate account access (recruiter A can send emails as recruiter B). Phase 2+.
- Candidate self-service email preferences (opt-in/opt-out). Phase 1 does not require this.

---

## 9. Verification

```bash
cd communication/
pytest tests/ -v --tb=short
```

All tests must pass. Additionally, verify these end-to-end scenarios manually or via integration tests:

1. Connect a Gmail account via OAuth. Confirm the auth_url is provided, the callback is successful, and email_connections shows sync_status='healthy'.
2. Connect an Outlook account. Confirm the same flow for Outlook.
3. Send an email to a candidate with a raw body. Confirm the email is created, delivered via SMTP, and an interaction is logged.
4. Send an email using a template with variables. Confirm the template is rendered, variables are substituted, and the email is sent.
5. Attempt to send a template with a missing variable. Confirm 422 is returned with the missing variable name.
6. Create a new email template with multiple variables. Confirm variables are extracted and the template is listed.
7. Update a template's subject. Confirm the change is persisted and variables are re-extracted.
8. Get the email thread for a candidate. Confirm sent and received emails are returned in reverse chronological order.
9. Run a sync cycle with a valid Gmail connection. Confirm incoming emails from the candidate are created, sync_status='healthy', and interactions are added.
10. Simulate a token expiration during sync. Confirm sync_status='disconnected' and an error is logged.
11. Simulate a rate limit during sync. Confirm sync_status='degraded', error_count increments, and the next cycle retries.
12. Access email threads as a recruiter in workspace A for a candidate in workspace B. Confirm 403 or 404 is returned.
13. Access email threads as an admin. Confirm all candidates' threads are accessible.
14. Run a soft delete on a template. Confirm it is hidden from list views but the database row is retained.
