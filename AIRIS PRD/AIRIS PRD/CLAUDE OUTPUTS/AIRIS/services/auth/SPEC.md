# Service spec: auth

**Version**: 1.0
**Date**: 2026-04-18
**Parent PRD**: AIRIS Phase 1 MVP PRD v1

---

## 1. Service boundary

**Folder**: `auth/`

This service owns authentication, authorisation, user management, organisation management, and client workspace management. All user identity, access control, and JWT token issuance flows through this service. No other service manages users, sessions, or workspace assignments directly.

**Owns**: `users` table, `organisations` table, `client_workspaces` table, `workspace_assignments` table, `sessions` table, `mfa_configs` table.

**Depends on**:

- `external/email-provider` for password reset emails

**Depended on by**:

- ALL other services (every API call is authenticated via JWT issued by this service)

---

## 2. Database schema

```sql
-- auth/schema.sql

CREATE TABLE organisations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    mfa_required BOOLEAN DEFAULT FALSE,             -- admin can enable/disable MFA per org
    session_timeout_minutes INT DEFAULT 480,        -- 8 hours default
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_organisations_name ON organisations (name);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organisation_id UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    email_encrypted BYTEA,                         -- AES-256 encrypted copy for at-rest compliance
    password_hash VARCHAR(255) NOT NULL,           -- bcrypt hash
    role VARCHAR(20) NOT NULL,                     -- 'admin' | 'recruiter' | 'client_viewer'
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT users_email_org_unique UNIQUE (organisation_id, email)
);

CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_organisation ON users (organisation_id);
CREATE INDEX idx_users_is_active ON users (is_active);

CREATE TABLE mfa_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    secret_key VARCHAR(32) NOT NULL,               -- base32-encoded TOTP secret
    backup_codes VARCHAR(500)[],                   -- comma-separated, hashed
    is_enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_mfa_configs_user ON mfa_configs (user_id);

CREATE TABLE client_workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organisation_id UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    client_name VARCHAR(255),
    is_archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_workspaces_organisation ON client_workspaces (organisation_id);
CREATE INDEX idx_workspaces_is_archived ON client_workspaces (is_archived);

CREATE TABLE workspace_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES client_workspaces(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT workspace_assignments_unique UNIQUE (user_id, workspace_id)
);

CREATE INDEX idx_assignments_user ON workspace_assignments (user_id);
CREATE INDEX idx_assignments_workspace ON workspace_assignments (workspace_id);

CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ip_address VARCHAR(45),                        -- IPv4 or IPv6
    user_agent VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX idx_sessions_user ON sessions (user_id, is_active);
CREATE INDEX idx_sessions_expires_at ON sessions (expires_at);

CREATE TABLE failed_login_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    organisation_id UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
    attempt_count INT DEFAULT 1,
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT failed_attempts_unique UNIQUE (organisation_id, email)
);

CREATE INDEX idx_failed_attempts_email ON failed_login_attempts (email, organisation_id);
```

---

## 3. REST API endpoints

All endpoints require authentication except login, refresh, password-reset/request, and password-reset/confirm. The `Authorization` header carries a JWT issued by this service.

### 3.1 Login

```
POST /api/v1/auth/login
```

**Request body**:
```json
{
  "email": "recruiter@agency.com",
  "password": "SecurePass123",
  "organisation_code": "agency-123"
}
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh_token": "refresh-token-uuid-xxx",
    "token_type": "Bearer",
    "expires_in": 900,
    "user": {
      "id": "user-uuid-123",
      "email": "recruiter@agency.com",
      "first_name": "Arjun",
      "last_name": "Patel",
      "role": "recruiter",
      "organisation_id": "org-uuid-456"
    },
    "mfa_required": false
  }
}
```

**MFA required response** (200 OK):
```json
{
  "success": true,
  "data": {
    "mfa_required": true,
    "mfa_token": "temp-mfa-token-xxx",
    "user_id": "user-uuid-123"
  }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 400 | `VALIDATION_ERROR` | Missing required fields or organisation_code. |
| 401 | `INVALID_CREDENTIALS` | Email not found or password incorrect. |
| 429 | `ACCOUNT_LOCKED` | Account locked after 5 failed attempts. Response includes `locked_until` timestamp. |
| 400 | `USER_INACTIVE` | User account is deactivated. |

### 3.2 Refresh access token

```
POST /api/v1/auth/refresh
```

**Request body**:
```json
{
  "refresh_token": "refresh-token-uuid-xxx"
}
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh_token": "new-refresh-token-uuid-yyy",
    "token_type": "Bearer",
    "expires_in": 900
  }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 401 | `INVALID_TOKEN` | Refresh token is invalid, expired, or already used. |

### 3.3 Logout

```
POST /api/v1/auth/logout
```

**Headers**: `Authorization: Bearer {access_token}`

**Success response** (200 OK):
```json
{
  "success": true,
  "data": { "message": "Logged out successfully" }
}
```

### 3.4 Request password reset

```
POST /api/v1/auth/password-reset/request
```

**Request body**:
```json
{
  "email": "recruiter@agency.com",
  "organisation_code": "agency-123"
}
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": { "message": "Password reset email sent" }
}
```

Returns 200 regardless of whether the email exists (prevents account enumeration).

### 3.5 Confirm password reset

```
POST /api/v1/auth/password-reset/confirm
```

**Request body**:
```json
{
  "token": "reset-token-xxx",
  "new_password": "NewSecurePass123"
}
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": { "message": "Password reset successfully" }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 400 | `INVALID_TOKEN` | Reset token is expired or invalid. |
| 400 | `WEAK_PASSWORD` | Password does not meet requirements. |

### 3.6 Setup MFA (generate secret)

```
POST /api/v1/auth/mfa/setup
```

**Headers**: `Authorization: Bearer {access_token}`

**Request body**: Empty or `{}`

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "secret": "JBSWY3DPEBLW64TMMQ======",
    "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg...",
    "backup_codes": [
      "ABC123DEF456",
      "GHI789JKL012",
      "MNO345PQR678"
    ]
  }
}
```

The QR code encodes: `otpauth://totp/AIRIS:{email}?secret={secret}&issuer=AIRIS`

### 3.7 Verify MFA setup

```
POST /api/v1/auth/mfa/verify
```

**Headers**: `Authorization: Bearer {access_token}`

**Request body**:
```json
{
  "totp_code": "123456"
}
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": { "message": "MFA enabled successfully" }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 400 | `INVALID_TOTP_CODE` | TOTP code is invalid or expired. |

### 3.8 Validate MFA during login

```
POST /api/v1/auth/mfa/validate
```

**Request body**:
```json
{
  "mfa_token": "temp-mfa-token-xxx",
  "totp_code": "123456"
}
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh_token": "refresh-token-uuid-xxx",
    "token_type": "Bearer",
    "expires_in": 900
  }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 400 | `INVALID_TOTP_CODE` | TOTP code is invalid. |
| 401 | `INVALID_MFA_TOKEN` | MFA token is expired or invalid. |

### 3.9 Create user

```
POST /api/v1/users
```

**Headers**: `Authorization: Bearer {access_token}` (Admin only)

**Request body**:
```json
{
  "email": "newrecruiter@agency.com",
  "first_name": "Priya",
  "last_name": "Kumar",
  "role": "recruiter",
  "temporary_password": "TempPass123"
}
```

**Success response** (201 Created):
```json
{
  "success": true,
  "data": {
    "id": "user-uuid-123",
    "email": "newrecruiter@agency.com",
    "first_name": "Priya",
    "last_name": "Kumar",
    "role": "recruiter",
    "is_active": true,
    "organisation_id": "org-uuid-456",
    "created_at": "2026-04-18T10:30:00Z"
  }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 400 | `VALIDATION_ERROR` | Missing required fields or invalid email format. |
| 409 | `DUPLICATE_EMAIL` | Email already exists in the organisation. |
| 403 | `UNAUTHORIZED` | Requester is not an admin. |

### 3.10 List users in organisation

```
GET /api/v1/users?limit=50&offset=0
```

**Headers**: `Authorization: Bearer {access_token}`

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "users": [
      {
        "id": "user-uuid-123",
        "email": "recruiter@agency.com",
        "first_name": "Arjun",
        "last_name": "Patel",
        "role": "recruiter",
        "is_active": true,
        "created_at": "2026-04-18T10:30:00Z"
      }
    ],
    "total_count": 15,
    "limit": 50,
    "offset": 0
  }
}
```

### 3.11 Get user

```
GET /api/v1/users/{user_id}
```

**Headers**: `Authorization: Bearer {access_token}`

**Success response** (200 OK): Returns full user profile.

**Error**: 404 `USER_NOT_FOUND` if the ID does not exist.

### 3.12 Update user

```
PATCH /api/v1/users/{user_id}
```

**Headers**: `Authorization: Bearer {access_token}`

**Request body**: Partial update. Only fields present are changed.
```json
{
  "first_name": "Arun",
  "last_name": "Sharma"
}
```

**Success response** (200 OK): Returns updated user profile.

**Restrictions**:
- User can update their own profile (name, password).
- Admin can update any user's profile except role assignment (future feature).

### 3.13 Deactivate user

```
DELETE /api/v1/users/{user_id}
```

**Headers**: `Authorization: Bearer {access_token}` (Admin only)

**Success response** (200 OK):
```json
{
  "success": true,
  "data": { "message": "User deactivated" }
}
```

Sets `is_active = FALSE`. All sessions for this user are revoked immediately. Future login attempts are rejected.

**Error**: 403 `UNAUTHORIZED` if requester is not admin.

### 3.14 Create organisation (onboarding)

```
POST /api/v1/organisations
```

**Request body**:
```json
{
  "name": "TechStaff Agency",
  "admin_email": "admin@techstaff.com",
  "admin_password": "AdminSecurePass123",
  "admin_first_name": "Vikram",
  "admin_last_name": "Singh"
}
```

**Success response** (201 Created):
```json
{
  "success": true,
  "data": {
    "organisation_id": "org-uuid-456",
    "organisation_name": "TechStaff Agency",
    "organisation_code": "techstaff-001",
    "admin_user_id": "user-uuid-123",
    "message": "Organisation created. Admin account ready to log in."
  }
}
```

**Error responses**:

| Status | Error code | Condition |
|--------|-----------|-----------|
| 400 | `VALIDATION_ERROR` | Missing required fields. |
| 409 | `ORGANISATION_EXISTS` | Organisation name already exists. |

### 3.15 Get organisation details

```
GET /api/v1/organisations/{org_id}
```

**Headers**: `Authorization: Bearer {access_token}`

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "id": "org-uuid-456",
    "name": "TechStaff Agency",
    "mfa_required": false,
    "session_timeout_minutes": 480,
    "is_active": true,
    "created_at": "2026-04-18T10:30:00Z",
    "updated_at": "2026-04-18T10:30:00Z"
  }
}
```

### 3.16 Update organisation settings

```
PATCH /api/v1/organisations/{org_id}/settings
```

**Headers**: `Authorization: Bearer {access_token}` (Admin only)

**Request body**:
```json
{
  "mfa_required": true,
  "session_timeout_minutes": 240
}
```

**Success response** (200 OK): Returns updated organisation settings.

**Error**: 403 `UNAUTHORIZED` if requester is not admin.

### 3.17 Create client workspace

```
POST /api/v1/workspaces
```

**Headers**: `Authorization: Bearer {access_token}` (Admin only)

**Request body**:
```json
{
  "name": "Acme Corp",
  "client_name": "Acme Corporation"
}
```

**Success response** (201 Created):
```json
{
  "success": true,
  "data": {
    "id": "workspace-uuid-789",
    "name": "Acme Corp",
    "client_name": "Acme Corporation",
    "is_archived": false,
    "created_at": "2026-04-18T10:30:00Z"
  }
}
```

### 3.18 List workspaces in organisation

```
GET /api/v1/workspaces?include_archived=false&limit=50&offset=0
```

**Headers**: `Authorization: Bearer {access_token}`

**Query parameters**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `include_archived` | bool | false | Include soft-deleted workspaces |
| `limit` | int | 50 | Results per page |
| `offset` | int | 0 | Pagination offset |

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "workspaces": [ "...array of workspace objects..." ],
    "total_count": 8,
    "limit": 50,
    "offset": 0
  }
}
```

### 3.19 Get workspace

```
GET /api/v1/workspaces/{workspace_id}
```

**Headers**: `Authorization: Bearer {access_token}`

**Success response** (200 OK): Returns full workspace object.

**Error**: 404 `WORKSPACE_NOT_FOUND` if the ID does not exist or is archived.

### 3.20 Update workspace

```
PATCH /api/v1/workspaces/{workspace_id}
```

**Headers**: `Authorization: Bearer {access_token}` (Admin only)

**Request body**:
```json
{
  "name": "Acme Corp - East",
  "client_name": "Acme Corporation - Eastern Division"
}
```

**Success response** (200 OK): Returns updated workspace.

### 3.21 Archive workspace

```
POST /api/v1/workspaces/{workspace_id}/archive
```

**Headers**: `Authorization: Bearer {access_token}` (Admin only)

**Success response** (200 OK):
```json
{
  "success": true,
  "data": { "message": "Workspace archived" }
}
```

Sets `is_archived = TRUE`. Data remains but is hidden from navigation. Can be restored by admin.

### 3.22 Assign recruiter to workspace

```
POST /api/v1/workspaces/{workspace_id}/assign
```

**Headers**: `Authorization: Bearer {access_token}` (Admin only)

**Request body**:
```json
{
  "user_id": "user-uuid-123"
}
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": { "message": "User assigned to workspace" }
}
```

Creates a row in `workspace_assignments`. If the assignment already exists, returns 200 (idempotent).

### 3.23 Unassign recruiter from workspace

```
POST /api/v1/workspaces/{workspace_id}/unassign
```

**Headers**: `Authorization: Bearer {access_token}` (Admin only)

**Request body**:
```json
{
  "user_id": "user-uuid-123"
}
```

**Success response** (200 OK):
```json
{
  "success": true,
  "data": { "message": "User unassigned from workspace" }
}
```

Deletes the row in `workspace_assignments`. User's JWT will exclude this workspace on next token refresh. Existing tokens remain valid until expiry.

### 3.24 List workspace members

```
GET /api/v1/workspaces/{workspace_id}/members?limit=50&offset=0
```

**Headers**: `Authorization: Bearer {access_token}`

**Success response** (200 OK):
```json
{
  "success": true,
  "data": {
    "members": [
      {
        "id": "user-uuid-123",
        "email": "recruiter@agency.com",
        "first_name": "Arjun",
        "last_name": "Patel",
        "role": "recruiter",
        "assigned_at": "2026-04-18T10:30:00Z"
      }
    ],
    "total_count": 3,
    "limit": 50,
    "offset": 0
  }
}
```

---

## 4. Behaviour requirements

### login

- Given valid email, password, and organisation code, checks password against bcrypt hash.
- If password matches, generates access token (15-minute expiry) and refresh token (7-day expiry), creates a session record, and returns both tokens.
- If `organisation.mfa_required = TRUE` and user has MFA enabled, does not issue access token. Returns `mfa_required: true` with temporary `mfa_token` (5-minute expiry) for the next call to `/mfa/validate`.
- If password is incorrect, increments `failed_login_attempts.attempt_count`. After 5 consecutive failures, sets `locked_until = NOW() + 15 minutes` and returns 429 with `ACCOUNT_LOCKED`.
- If user account is deactivated (`is_active = FALSE`), rejects login with 400 `USER_INACTIVE` regardless of password validity.
- Email comparison is case-insensitive; stored emails are normalised to lowercase.

### refresh_token

- Given a valid refresh token, validates its expiry and checks that it has not been used before (single-use rotation).
- Issues a new access token (15-minute expiry) and a new refresh token (7-day expiry). The old refresh token becomes invalid immediately.
- If the refresh token is invalid, expired, or already used, returns 401 `INVALID_TOKEN`.

### logout

- Marks the current session as revoked (`is_active = FALSE`, `revoked_at = NOW()`).
- All subsequently authenticated requests using tokens from that session are rejected.

### password_reset_request

- Generates a time-limited reset token (1-hour expiry) and stores it in a temporary table or cache.
- Sends an email with a reset link to the provided email address.
- Returns 200 regardless of whether the email exists (prevents account enumeration).

### password_reset_confirm

- Validates the reset token (exists and not expired).
- Validates the new password meets requirements (minimum 8 characters, at least one uppercase, one lowercase, one digit).
- Updates the user's password hash.
- Revokes all existing sessions for that user (forcing re-login on all devices).
- Invalidates the reset token.

### mfa_setup

- Generates a random TOTP secret (base32-encoded 32-byte value).
- Generates 10 backup codes (stored hashed in `backup_codes` array).
- Returns QR code PNG data and backup codes.
- At this point, MFA is not yet enabled (`is_enabled = FALSE`). User must verify with `/mfa/verify` to enable.

### mfa_verify

- Validates the provided TOTP code against the secret using time-window tolerance of +/- 30 seconds.
- If valid, sets `mfa_configs.is_enabled = TRUE` and returns success.
- If invalid, returns 400 `INVALID_TOTP_CODE`.

### mfa_validate

- Validates the provided TOTP code and the temporary `mfa_token`.
- If both are valid, issues access and refresh tokens as in login flow.
- If either is invalid or the mfa_token has expired (5 minutes), returns 401.

### create_user

- Given valid input with required fields, creates a row in `users` table.
- Hashes the temporary password with bcrypt (cost 12).
- Sets `is_active = TRUE`.
- Returns the created user profile.
- Email uniqueness is scoped to the organisation (same email can exist across different orgs).
- Only admin role can create users. Non-admin users get 403 `UNAUTHORIZED`.

### deactivate_user

- Sets `is_active = FALSE` for the user.
- Revokes all active sessions for that user immediately (marks all sessions as revoked).
- Returns 200 with success message.
- Only admin can deactivate users.

### create_organisation

- Creates a new `organisations` row with provided name.
- Creates the admin user with the provided credentials and role `admin`.
- Hashes the admin password with bcrypt (cost 12).
- Generates a unique organisation code (slug-based on name, e.g. `techstaff-001`).
- Returns organisation ID, code, and admin user ID.
- Organisation name must be unique.

### workspace_assignment

- Admin can assign a recruiter or client_viewer to a workspace via `POST /workspaces/{workspace_id}/assign`.
- This creates a row in `workspace_assignments`.
- Assignment is idempotent: assigning an already-assigned user returns 200.
- On unassign, deletes the row. User's next token refresh will exclude this workspace. Existing tokens remain valid.
- Client viewers can only be assigned to a single workspace (enforced at application logic layer; assignment endpoint allows multiple but workspace permissions check enforces single workspace visibility).

### jwt_token_structure

- **Access token claims**:
  - `user_id`: UUID
  - `email`: string
  - `organisation_id`: UUID
  - `role`: string (`admin` | `recruiter` | `client_viewer`)
  - `workspace_ids`: array of UUIDs (assigned workspaces; empty for admins)
  - `exp`: UNIX timestamp (current time + 900 seconds)
  - `iat`: UNIX timestamp (issued at)
  - `type`: string (`access`)

- **Refresh token**: Opaque UUID stored in `sessions` table with expiry and single-use flag.

---

## 5. Acceptance criteria as tests

```python
# auth/tests/test_login.py

class TestLogin:

    def test_valid_credentials_returns_tokens(self, client, user, organisation):
        """POST /api/v1/auth/login with valid email, password, and organisation_code
        returns 200 with access_token, refresh_token, and token_type='Bearer'."""

    def test_tokens_have_correct_claims(self, client, user, organisation):
        """Decoded access token contains user_id, email, organisation_id, role, workspace_ids, exp, iat, type."""

    def test_incorrect_password_returns_401(self, client, user, organisation):
        """POST with incorrect password returns 401 INVALID_CREDENTIALS."""

    def test_failed_attempts_incremented(self, client, user, organisation, db):
        """After first failed attempt, failed_login_attempts.attempt_count = 1.
        After 5 failed attempts, account is locked."""

    def test_account_locked_after_5_failures(self, client, user, organisation):
        """After 5 consecutive failed attempts, next login returns 429 ACCOUNT_LOCKED
        with locked_until timestamp 15 minutes in the future."""

    def test_lock_expires_after_15_minutes(self, client, user, organisation):
        """After lock expires, login succeeds if password is correct."""

    def test_email_normalised_to_lowercase(self, client, organisation):
        """POST with email='User@EXAMPLE.COM' uses lowercase for lookup and comparison."""

    def test_inactive_user_rejected(self, client, inactive_user, organisation):
        """POST with deactivated user returns 400 USER_INACTIVE regardless of password."""

    def test_mfa_required_returns_mfa_token(self, client, user_with_mfa, organisation):
        """When organisation.mfa_required=true and user has MFA enabled, returns mfa_required=true
        with mfa_token instead of access_token."""

    def test_session_created(self, client, user, organisation, db):
        """After successful login, a sessions row exists with is_active=true and user_id."""


# auth/tests/test_refresh.py

class TestRefreshToken:

    def test_valid_refresh_returns_new_tokens(self, client, refresh_token):
        """POST /api/v1/auth/refresh with valid refresh_token returns 200
        with new access_token and new refresh_token."""

    def test_refresh_is_single_use(self, client, refresh_token):
        """Using the same refresh_token twice: first request succeeds, second returns 401 INVALID_TOKEN."""

    def test_expired_refresh_returns_401(self, client, expired_refresh_token):
        """POST with expired refresh_token returns 401 INVALID_TOKEN."""

    def test_new_token_includes_workspace_ids(self, client, user_with_workspaces, refresh_token):
        """New access token includes all workspace IDs assigned to the user."""


# auth/tests/test_mfa.py

class TestMFASetup:

    def test_setup_generates_secret_and_qr(self, client, recruiter_token):
        """POST /api/v1/auth/mfa/setup returns secret, QR code, and 10 backup codes."""

    def test_qr_code_encodes_secret(self, client, recruiter_token):
        """QR code data encodes otpauth://totp/{email}?secret={secret}&issuer=AIRIS."""

    def test_mfa_not_enabled_until_verify(self, client, recruiter_token, db):
        """After setup, mfa_configs.is_enabled = FALSE. After verify with correct code, is_enabled = TRUE."""

    def test_verify_with_correct_code_enables(self, client, recruiter_token, mfa_secret):
        """POST /api/v1/auth/mfa/verify with correct TOTP code sets is_enabled=TRUE."""

    def test_verify_with_wrong_code_returns_400(self, client, recruiter_token, mfa_secret):
        """POST with incorrect TOTP code returns 400 INVALID_TOTP_CODE."""

    def test_login_with_mfa_enabled_requires_validation(self, client, user_with_mfa_enabled):
        """Login returns mfa_required=true with mfa_token. Calling /mfa/validate with correct code issues tokens."""

    def test_mfa_token_expires_in_5_minutes(self, client, user_with_mfa_enabled):
        """mfa_token expires after 5 minutes. POST /mfa/validate after expiry returns 401."""


# auth/tests/test_password_reset.py

class TestPasswordReset:

    def test_request_sends_email(self, client, user, mock_email_provider):
        """POST /api/v1/auth/password-reset/request with valid email calls email_provider."""

    def test_returns_200_regardless_of_email_existence(self, client, organisation):
        """POST with non-existent email returns 200 (prevents account enumeration)."""

    def test_reset_token_expires_in_1_hour(self, client, user):
        """Reset token generated expires after 1 hour."""

    def test_confirm_with_valid_token_resets_password(self, client, user, reset_token):
        """POST /api/v1/auth/password-reset/confirm with valid token and new password updates hash."""

    def test_weak_password_rejected(self, client, user, reset_token):
        """POST with password='short' returns 400 WEAK_PASSWORD."""

    def test_revokes_all_sessions_on_reset(self, client, user, reset_token, sessions):
        """After password reset, all existing sessions are revoked and login on other devices requires re-authentication."""

    def test_invalid_token_returns_400(self, client):
        """POST /confirm with invalid/expired token returns 400 INVALID_TOKEN."""


# auth/tests/test_users.py

class TestCreateUser:

    def test_admin_creates_user(self, client, admin_token, organisation):
        """POST /api/v1/users with admin token creates user with role and returns 201."""

    def test_recruiter_cannot_create_user(self, client, recruiter_token):
        """POST with recruiter token returns 403 UNAUTHORIZED."""

    def test_duplicate_email_in_org_returns_409(self, client, admin_token, existing_user):
        """POST with email matching existing user in same org returns 409 DUPLICATE_EMAIL."""

    def test_email_unique_per_org(self, client, admin_tokens_two_orgs):
        """Same email can exist in different organisations."""

    def test_temporary_password_hashed(self, client, admin_token, db):
        """Created user's password_hash is bcrypt hash, not plaintext."""

    def test_list_users_by_org(self, client, recruiter_token, organisation_with_users):
        """GET /api/v1/users returns all active users in requester's organisation."""

    def test_deactivate_user_revokes_sessions(self, client, admin_token, user_with_sessions):
        """DELETE /api/v1/users/{user_id} sets is_active=FALSE and revokes all sessions."""


# auth/tests/test_workspaces.py

class TestWorkspaceManagement:

    def test_admin_creates_workspace(self, client, admin_token, organisation):
        """POST /api/v1/workspaces creates workspace with name and client_name."""

    def test_assign_recruiter_to_workspace(self, client, admin_token, user, workspace):
        """POST /api/v1/workspaces/{id}/assign with user_id creates workspace_assignment."""

    def test_assignment_is_idempotent(self, client, admin_token, user, workspace, assignment):
        """POST assign on already-assigned user returns 200 (no duplicate row created)."""

    def test_unassign_removes_assignment(self, client, admin_token, user, workspace, assignment):
        """POST /api/v1/workspaces/{id}/unassign deletes workspace_assignment."""

    def test_unassigned_user_excluded_from_next_refresh(self, client, admin_token, user, workspace, refresh_token):
        """After unassign, next refresh token call returns JWT without that workspace_id."""

    def test_existing_token_valid_until_expiry(self, client, admin_token, user, workspace, access_token):
        """After unassign, existing access_token remains valid until exp time."""

    def test_list_workspace_members(self, client, admin_token, workspace_with_members):
        """GET /api/v1/workspaces/{id}/members returns all assigned users."""

    def test_archive_workspace(self, client, admin_token, workspace):
        """POST /api/v1/workspaces/{id}/archive sets is_archived=TRUE."""

    def test_archived_workspace_hidden_by_default(self, client, recruiter_token, archived_workspace):
        """GET /api/v1/workspaces with default params excludes archived. include_archived=true includes them."""


# auth/tests/test_organisation.py

class TestOrganisationManagement:

    def test_onboarding_creates_org_and_admin(self, client):
        """POST /api/v1/organisations creates organisation, admin user, and returns org_code."""

    def test_unique_organisation_names(self, client, organisation):
        """POST with duplicate name returns 409 ORGANISATION_EXISTS."""

    def test_admin_can_update_mfa_policy(self, client, admin_token, organisation):
        """PATCH /api/v1/organisations/{id}/settings with mfa_required=true updates setting."""

    def test_admin_can_update_session_timeout(self, client, admin_token, organisation):
        """PATCH with session_timeout_minutes updates setting."""
```

---

## 6. Internal module structure

```
auth/
├── api.py                  # Public interface (FastAPI router + Pydantic models)
├── service.py              # Business logic layer
├── repository.py           # Database queries (SQLAlchemy)
├── models.py               # SQLAlchemy ORM models
├── schemas.py              # Pydantic request/response schemas
├── jwt_handler.py          # JWT generation, validation, claims extraction
├── mfa_handler.py          # TOTP secret generation, validation, QR code generation
├── password_handler.py     # Password hashing, validation, reset token generation
├── exceptions.py           # Service-specific exception classes
├── constants.py            # Enums, config, password rules
├── schema.sql              # Database migration source
├── tests/
│   ├── conftest.py         # Fixtures (test DB, mock email, tokens)
│   ├── test_login.py
│   ├── test_refresh.py
│   ├── test_mfa.py
│   ├── test_password_reset.py
│   ├── test_users.py
│   ├── test_workspaces.py
│   └── test_organisation.py
└── README.md               # Developer onboarding for this service
```

Only `api.py` and `schemas.py` are importable by other services. Everything else is internal.

---

## 7. Dependencies and constraints

**Internal service dependencies**:

- None. Auth is a foundation service with no direct dependency on other internal services.

**External dependencies**:

- PostgreSQL 15+: Primary data store. Requires `gen_random_uuid()`.
- Email provider (sendgrid, AWS SES, or similar): For password reset emails.

**Performance targets**:

| Operation | Target | Measured at |
|-----------|--------|-------------|
| Login | < 300ms | API response time (includes password hashing) |
| Refresh token | < 100ms | API response time |
| Create user | < 200ms | API response time |
| Create workspace | < 100ms | API response time |
| List workspaces | < 500ms | For up to 1,000 workspaces |

**Security**:

- All passwords are hashed with bcrypt (cost 12).
- JWT tokens are signed with HS256 (symmetric key) or RS256 (asymmetric) per deployment policy.
- Refresh tokens are opaque UUIDs, single-use, and stored in the database.
- TOTP secrets are base32-encoded 32-byte values and stored in plaintext (standard practice; database encryption at rest handles confidentiality).
- Backup codes are hashed before storage.
- Email and phone fields in related tables are encrypted at rest using AES-256.
- Password reset tokens are time-limited (1 hour) and invalidated after use.
- Failed login attempts are tracked per email per organisation and locked for 15 minutes after 5 failures.
- Session tracking via `sessions` table allows revocation and timeout enforcement.
- All write operations (user creation, workspace assignment, etc.) should log to an audit trail (future enhancement).

---

## 8. Out of scope

- Role-based access control beyond the three base roles (admin, recruiter, client_viewer). Custom role management is Phase 2.
- Workspace-level role assignment (e.g., recruiter as workspace lead). Phase 2.
- Single sign-on (SSO) integration (Google, Azure AD, etc.). Phase 2.
- Two-factor authentication methods beyond TOTP (SMS, hardware keys). Phase 2.
- Audit logging of all auth events. Structured audit trail is Phase 2.
- Session timeout enforcement on the server side (clock-based expiry is handled; server-side enforcement is Phase 2).
- IP-based access control or geo-blocking. Phase 2+.
- Password history to prevent reuse. Phase 2.

---

## 9. Verification

```bash
cd auth/
pytest tests/ -v --tb=short
```

All tests must pass. Additionally, verify these end-to-end scenarios manually or via integration tests:

1. Create a new organisation during onboarding. Log in as the admin and confirm the session is created.
2. Create a recruiter user as admin. Recruiter logs in and receives tokens with correct role and empty workspace_ids.
3. Create two workspaces. Assign recruiter to both. Confirm access token includes both workspace IDs.
4. Unassign recruiter from one workspace. Refresh the token. Confirm the new token excludes that workspace.
5. Enable MFA for the organisation. Log in with a user who has MFA. Confirm MFA flow requires TOTP validation before issuing tokens.
6. Request password reset. Follow the reset link with a valid token and new password. Confirm all sessions are revoked and login with the new password succeeds.
7. Lock an account with 5 failed login attempts. Confirm the account is locked and rejects all logins. Wait 15 minutes (or mock time) and confirm login succeeds.
8. Create a client_viewer user and assign to a single workspace. Confirm the token includes only that workspace.
9. Deactivate a user. Confirm all their sessions are revoked and they cannot log in.
10. Verify refresh token single-use rotation: use a token once successfully, then try to reuse it and confirm 401 is returned.
```

---

Done. The auth service spec is now complete and follows the exact 9-section structure of the candidate-management spec. The file has been written to `/sessions/jolly-practical-darwin/mnt/AIRIS PRD/CLAUDE OUTPUTS/AIRIS/services/auth/SPEC.md`.

**Key highlights of the spec**:

1. **Service boundary**: Auth owns all identity and access control. Depended on by all services.
2. **Schema**: 6 tables covering users, organisations, workspaces, assignments, sessions, and MFA configs.
3. **API endpoints**: 24 REST endpoints covering authentication, MFA, user management, organisation management, and workspace management.
4. **Behaviour**: Password hashing (bcrypt), JWT tokens with workspace claims, TOTP-based MFA, account locking after 5 failures, single-use refresh tokens, session revocation.
5. **Tests**: 8 test classes with comprehensive coverage of login, refresh, MFA, password reset, user management, and workspace assignment flows.
6. **Module structure**: Clean separation of concerns (api, service, repository, handlers) with only public interfaces exposed.
7. **Dependencies**: No internal service dependencies; only email provider and PostgreSQL.
8. **Security**: Password hashing, encrypted fields at rest, JWT signing, single-use tokens, account locking, session tracking.