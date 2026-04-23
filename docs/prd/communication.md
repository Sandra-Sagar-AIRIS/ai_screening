# Communication

## Overview
The communication domain centralizes email operations in AIRIS: account connection via OAuth, outbound delivery, inbound sync, template management, and candidate-centric thread history.

It provides a unified recruiter communication layer and logs email events back into candidate interactions.

## Responsibilities
Primary responsibilities:
- Connect recruiter mailboxes (Gmail/Outlook) and monitor sync health.
- Send outbound emails (raw or template-rendered).
- Ingest inbound candidate emails during periodic sync cycles.
- Manage reusable templates and variable substitution.
- Serve candidate email thread timelines with access controls.

## Data Model
Core tables:
- `email_connections`: provider tokens (encrypted), mailbox identity, sync status.
- `emails`: sent/received records mapped to candidates.
- `email_templates`: organization-scoped templates with extracted placeholders.
- `email_sync_status`: per-connection sync execution health.

Key constraints:
- Unique provider message IDs per provider for idempotent sync.
- Soft delete for templates (`is_deleted`) with uniqueness on active names.
- Sync scopes restricted to known candidate addresses.

## API Endpoints
Representative endpoints:
- `POST /api/v1/email/connect` initiate OAuth
- `GET /api/v1/email/callback` OAuth callback
- `GET /api/v1/email/status` sync/connection health
- `POST /api/v1/email/send` send message
- `GET /api/v1/email/threads/{candidate_id}` candidate thread
- `POST /api/v1/email/templates` create template
- `GET /api/v1/email/templates` list templates
- `PATCH /api/v1/email/templates/{template_id}` update template
- `DELETE /api/v1/email/templates/{template_id}` soft delete template
- `POST /api/v1/email/templates/{template_id}/render` preview render

## Business Logic
- Send path validates payload mode: raw body OR template path (mutually exclusive).
- Template rendering requires all placeholders; unresolved placeholders return explicit errors.
- Sent emails are persisted immediately; provider-folder sync can occur asynchronously.
- Inbound sync runs on schedule, upserts by provider message ID, and creates `email_received` interactions.
- Sync degradation model:
  - transient errors -> `degraded`
  - token expiry/401 -> `disconnected` and reconnect required
- Workspace/organization boundaries govern thread and template visibility.

## Notes / Constraints
- Phase 1 excludes WhatsApp/SMS channels and advanced email categorization.
- OAuth tokens must remain encrypted at rest.
- Candidate timeline integrity depends on successful interaction logging for sent/received events.
- Provider APIs are integration points; keep retry and idempotency behavior deterministic.
