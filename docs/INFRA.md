# AIRIS Infrastructure & Environment Guide

> **Audience:** engineers deploying, operating, or onboarding to the AIRIS recruitment platform.  
> **Last updated:** 2026-05-20

---

## Table of Contents

1. [Repository Layout](#repository-layout)
2. [Environment Files Quick-Reference](#environment-files-quick-reference)
3. [Backend Configuration Reference](#backend-configuration-reference)
4. [Frontend Configuration Reference](#frontend-configuration-reference)
5. [Secret Generation Cheat-Sheet](#secret-generation-cheat-sheet)
6. [Secret Rotation Procedures](#secret-rotation-procedures)
7. [Database Setup](#database-setup)
8. [Running Locally](#running-locally)
9. [Deployment Checklist](#deployment-checklist)
10. [AWS / IAM Notes](#aws--iam-notes)

---

## Repository Layout

```
AIRIS/
├── backend/                    FastAPI Python service
│   ├── app/
│   │   └── core/config.py      Pydantic-Settings configuration class
│   ├── alembic/                Database migrations
│   ├── .env.example            Full variable reference (committed)
│   ├── .env.development.example  Dev-specific defaults (committed)
│   ├── .env.staging.example      Staging template (committed)
│   └── .env.production.example   Production template (committed)
├── frontend/                   Next.js 15 application
│   ├── .env.example            Full variable reference (committed)
│   ├── .env.development.example  Dev defaults (committed)
│   ├── .env.staging.example      Staging template (committed)
│   └── .env.production.example   Production template (committed)
└── docs/
    └── INFRA.md                This file
```

### Gitignore rules

The root `.gitignore` contains:

```
.env
.env.*
!.env.example
!.env.*.example
```

This means:
- `.env` and any `.env.*` file (e.g., `.env.local`, `.env.production.local`) are **never committed**.
- Only files ending in `.example` are tracked and safe to commit.

---

## Environment Files Quick-Reference

| File | Purpose | Committed? |
|------|---------|------------|
| `backend/.env` | Active local config | ❌ Never |
| `backend/.env.example` | Full variable catalogue with descriptions | ✅ Yes |
| `backend/.env.development.example` | Local dev defaults | ✅ Yes |
| `backend/.env.staging.example` | Staging template | ✅ Yes |
| `backend/.env.production.example` | Production template | ✅ Yes |
| `frontend/.env.local` | Active local config | ❌ Never |
| `frontend/.env.example` | Full variable catalogue | ✅ Yes |
| `frontend/.env.development.example` | Local dev defaults | ✅ Yes |
| `frontend/.env.staging.example` | Staging template | ✅ Yes |
| `frontend/.env.production.example` | Production template | ✅ Yes |

### Getting started locally

```bash
# Backend
cp backend/.env.development.example backend/.env
# Edit backend/.env — fill in DATABASE_URL, OPENAI_API_KEY, etc.

# Frontend
cp frontend/.env.development.example frontend/.env.local
# Edit if needed (defaults work for standard local dev)
```

---

## Backend Configuration Reference

All settings live in `backend/app/core/config.py` as a `pydantic_settings.BaseSettings` class.
Variable names are case-insensitive. The `.env` file is loaded automatically.

### Required for startup

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | SQLAlchemy PostgreSQL URL (`postgresql+psycopg://...`). Supabase session-mode port 5432 is automatically rewritten to transaction-mode 6543. |
| `JWT_SECRET_KEY` | **Min 32 chars, cryptographically random.** Startup raises in production/staging if still at the insecure default. |

### External services summary

| Service | Variables | Required? |
|---------|-----------|-----------|
| Supabase Storage | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET` | Yes (resume uploads) |
| Brevo SMTP | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Yes (invite emails) |
| OpenAI | `OPENAI_API_KEY`, `OPENAI_SCREENING_MODEL` | Yes (AI screening) |
| Groq | `GROQ_API_KEY`, `GROQ_API_KEY_ATS` | Yes (JD parsing, ATS enrichment) |
| xAI Grok | `GROK_API_KEY`, `GROK_MODEL`, `RESUME_GROK_INTELLIGENCE` | Optional |
| AssemblyAI | `ASSEMBLYAI_API_KEY` | Yes (interview transcription) |
| LiveKit | `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_WS_URL` | Yes (video interviews) |
| Twilio | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER` | Optional (WhatsApp) |
| Google OAuth | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | Optional (Gmail integration) |
| Microsoft OAuth | `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_REDIRECT_URI`, `MS_TENANT_ID` | Optional (Outlook integration) |
| Celery / Redis | `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Required if `CELERY_DISPATCH_ENABLED=true` |

---

## Frontend Configuration Reference

Next.js environment variables:

| Variable | Scope | Description |
|----------|-------|-------------|
| `NEXT_PUBLIC_API_BASE_URL` | Browser + SSR | REST API base URL. Use `/api/v1` (proxy) in dev; full URL in production. |
| `NEXT_PUBLIC_API_BACKEND_URL` | SSR only | Explicit backend URL for server-side fetch when base URL is relative. |
| `API_BACKEND_URL` | Server / build | Used by `next.config.ts` to configure the `/api/v1/*` rewrite proxy. |
| `NEXT_PUBLIC_WS_API_BASE_URL` | Browser | WebSocket base (e.g. `wss://api.yourdomain.com/api/v1`). Derived from REST URL if omitted. |
| `NEXT_PUBLIC_USE_CANDIDATE_MANAGEMENT` | Browser | Feature flag for the candidate management module. Default `false`. |

> **Note on `NEXT_PUBLIC_` variables:** These are embedded in the browser bundle at _build time_.  
> Changing them requires a full rebuild — it is not sufficient to update the runtime environment.

---

## Secret Generation Cheat-Sheet

```bash
# JWT secret key (64 hex chars = 32 bytes entropy)
python -c "import secrets; print(secrets.token_hex(32))"

# COMM_TOKEN_ENCRYPTION_KEY (32 bytes, base64url-encoded)
python -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"

# COMM_OAUTH_STATE_SECRET (random hex)
python -c "import secrets; print(secrets.token_hex(32))"

# Any generic random string
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Secret Rotation Procedures

### JWT_SECRET_KEY

**Effect of rotation:** All existing access and refresh tokens are immediately invalidated. All users are logged out.

**Procedure:**
1. Generate a new value: `python -c "import secrets; print(secrets.token_hex(32))"`
2. Update the secret in your secrets manager (Doppler / AWS SSM).
3. Deploy a new backend instance with the updated value.
4. Notify users that they will need to log in again (optional but recommended for production).

**Zero-downtime option:** A dual-key approach (validate old + new, sign with new) is not currently implemented. Plan a brief maintenance window or accept brief session disruption.

---

### OpenAI API Key (`OPENAI_API_KEY`)

1. Generate a new key at [platform.openai.com/account/api-keys](https://platform.openai.com/account/api-keys).
2. Add the new key to your secrets manager.
3. Deploy the new key to production (hot-reload supported — no restart required for environment variable injection on most platforms).
4. Verify AI screening endpoints respond normally.
5. Revoke the old key in the OpenAI dashboard.

---

### Groq API Keys (`GROQ_API_KEY`, `GROQ_API_KEY_ATS`)

1. Generate replacement keys at [console.groq.com/keys](https://console.groq.com/keys).
2. Update secrets manager.
3. Deploy. Groq connections are per-request; no warm connections to flush.
4. Revoke old keys.

---

### LiveKit Credentials (`LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`)

1. Create new API keys in the [LiveKit Cloud dashboard](https://cloud.livekit.io).
2. Update secrets manager with both `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`.
3. Deploy the new backend. LiveKit JWTs are short-lived (typically 6 hours), so active rooms will eventually renegotiate. Forcing reconnect requires token reissuance.
4. Delete old API keys in the LiveKit dashboard once all existing JWT TTLs have expired.

---

### SMTP Credentials (Brevo)

1. Generate a new SMTP key at [app.brevo.com/settings/keys/smtp](https://app.brevo.com/settings/keys/smtp).
2. Update `SMTP_USER` and `SMTP_PASSWORD` in secrets manager.
3. Deploy. Verify a test transactional email is delivered.
4. Revoke the old key in Brevo.

---

### Supabase Service Role Key (`SUPABASE_SERVICE_ROLE_KEY`)

> ⚠ The service role key bypasses Row Level Security — treat it with extra care.

1. In the Supabase Dashboard → Project Settings → API, roll the service role secret.
2. Update secrets manager immediately (the old key is revoked the moment you roll it).
3. Deploy. Storage operations (resume uploads) will fail until the new key is live.

---

### Twilio Credentials

1. In the [Twilio Console](https://console.twilio.com), navigate to Account → API keys & tokens.
2. Create a new Auth Token or API key.
3. Update `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` in secrets manager.
4. Deploy and verify a test WhatsApp message is sent.
5. Revoke the old credential.

---

### Google OAuth (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`)

> Rotating OAuth client secrets disconnects all users who have granted Gmail access.
> Their tokens in the database become undecryptable until they re-authorize.

1. In [Google Cloud Console → APIs & Credentials](https://console.cloud.google.com/apis/credentials), select the AIRIS OAuth 2.0 client.
2. Add a new client secret (Google allows multiple active secrets temporarily).
3. Update `GOOGLE_CLIENT_SECRET` in secrets manager and deploy.
4. Once verified, delete the old secret from Google Cloud Console.

---

### Microsoft OAuth (`MS_CLIENT_ID`, `MS_CLIENT_SECRET`)

> Same caveat as Google OAuth — active Outlook tokens are tied to the client secret.

1. In [Azure Portal → App registrations](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps), select the AIRIS app.
2. Under Certificates & secrets → Client secrets, add a new secret.
3. Update `MS_CLIENT_SECRET` in secrets manager with the new value (copy immediately — Azure only shows it once).
4. Deploy and verify Outlook OAuth flow.
5. Delete the old secret from Azure once confirmed working.

---

### COMM_TOKEN_ENCRYPTION_KEY

> ⚠ **Critical:** This key encrypts OAuth tokens stored in the `communication_oauth_tokens` table.
> Rotating it requires a data migration — all stored tokens must be re-encrypted with the new key.

**Procedure (with migration):**
1. Generate a new key: `python -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"`.
2. Write a migration script that:
   - Reads each row's encrypted token using the **old** key.
   - Re-encrypts it with the **new** key.
   - Writes back the new ciphertext.
3. Run the migration against a point-in-time backup first.
4. Run the migration in production during a low-traffic window.
5. Update secrets manager and deploy the new backend.
6. Verify OAuth-connected users can still send emails.

**Emergency (accept data loss):** If the old key is lost, delete all rows from `communication_oauth_tokens`. Users will need to re-authorize their Gmail / Outlook integrations.

---

## Database Setup

### Supabase (recommended)

1. Create a project at [supabase.com](https://supabase.com).
2. Copy the **Transaction pooler** connection string (port **6543**) from Project Settings → Database → Connection string.
3. Set `DATABASE_URL` — the app automatically upgrades `postgresql://` to `postgresql+psycopg://`.
4. Run migrations:

```bash
cd backend
alembic upgrade head
```

### Local PostgreSQL (Docker)

```bash
docker run --name airis-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=airis_dev -p 5432:5432 -d postgres:16
```

Set `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/airis_dev`.

---

## Running Locally

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Deployment Checklist

Before deploying to **staging or production**, verify:

- [ ] `JWT_SECRET_KEY` is set to a cryptographically random value (not the development default).
- [ ] `DATABASE_URL` uses the Supabase **transaction-mode pooler** (port 6543).
- [ ] `CORS_ORIGINS` lists only the actual frontend domain(s) — no `localhost`.
- [ ] `FRONTEND_URL` is set to the production URL (used in invite emails).
- [ ] `SMTP_FROM` is a verified sender in Brevo.
- [ ] `DEBUG=false` in staging and production.
- [ ] `APP_ENV=staging` or `APP_ENV=production` — triggers JWT secret validation at startup.
- [ ] `COMM_TOKEN_ENCRYPTION_KEY` is set and backed up in the secrets manager.
- [ ] Alembic migrations have been applied: `alembic upgrade head`.
- [ ] No `.env` file is committed to git (check with `git status`).
- [ ] `NEXT_PUBLIC_*` frontend variables are set in the deployment platform **before the build step** (they are baked in at build time).

---

## AWS / IAM Notes

AIRIS currently uses **Supabase Storage** for file uploads rather than AWS S3. AWS services are not active.

If AWS services are introduced in the future:

- **ECS:** attach an IAM task role with the required policies.
- **EC2:** use an instance profile.
- **Lambda:** use an execution role.
- **GitHub Actions CI/CD:** use OIDC federation (no long-lived access keys).

**Never** commit `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` to source control or hardcode them in application code. Long-lived access keys are provided only for local development and must never reach production.
