# Candidate Management

## Overview
The candidate management domain owns AIRIS's universal candidate database and interaction history. It supports manual candidate creation, single and bulk resume ingestion, AI-assisted parsing, duplicate detection, search, merge, and data deletion workflows.

This module is the system-of-record for candidate profile data used by jobs, pipeline, scheduling, communication, and analytics.

## Responsibilities
Primary responsibilities:
- Maintain candidate profiles, skills, notes, and interaction timeline.
- Handle resume upload lifecycle (validate, store, parse, review confidence).
- Detect duplicates by email/phone and support merge workflows.
- Expose search (structured + natural language assisted) with pagination.
- Enforce soft delete and compliant hard delete (GDPR/DPDPA).
- Maintain append-only candidate audit log.

## Data Model
Core tables:
- `candidates`: profile fields, encrypted contact fields, parse confidence, deletion state.
- `candidate_skills`: normalized skills with source (`manual`, `parsed`, `ai_suggested`).
- `candidate_interactions`: timeline (`note`, `email_sent`, `email_received`, `call`, `stage_change`, `submission`, `interview_scheduled`).
- `candidate_audit_log`: action history (`created`, `updated`, `soft_deleted`, `hard_deleted`, `merged`, `accessed`).
- `bulk_upload_jobs` / `bulk_upload_items`: asynchronous ingestion tracking.

Key constraints:
- Unique active email (`is_deleted = false`).
- Soft-deleted candidates are hidden from read/search surfaces.
- Hard delete removes profile + related records + resume object storage key.

## API Endpoints
Representative endpoints:
- `POST /api/v1/candidates` create candidate
- `POST /api/v1/candidates/upload` upload + parse one resume
- `POST /api/v1/candidates/upload/bulk` start bulk upload
- `GET /api/v1/candidates/upload/bulk/{job_id}` bulk status
- `GET /api/v1/candidates/{candidate_id}` get profile
- `PATCH /api/v1/candidates/{candidate_id}` update profile
- `GET /api/v1/candidates/search` structured/NLP-assisted search
- `POST /api/v1/candidates/{candidate_id}/interactions` add timeline interaction
- `GET /api/v1/candidates/{candidate_id}/interactions` list timeline
- `POST /api/v1/candidates/merge` merge duplicate into primary
- `DELETE /api/v1/candidates/{candidate_id}` soft delete
- `DELETE /api/v1/candidates/{candidate_id}/permanent` hard delete (admin only)

## Business Logic
- Resume parsing delegates to `ai-services/parse_resume`; low-confidence fields are flagged, not dropped.
- Duplicate detection blocks automatic create; caller must choose merge or force-create strategy.
- Bulk processing is asynchronous and file-isolated; one file failure must not fail the whole job.
- Natural language query routes to `ai-services/smart_search`, then structured filters are applied as post-filters.
- Merge behavior:
  - Primary values retained when both sides have values.
  - Duplicate fills null fields on primary.
  - Interactions and non-conflicting skills are moved.
  - Duplicate is soft-deleted in a single transaction.
- Hard delete sequence must be safe: object storage deletion first, then DB deletion, with audit trail preserved without PII.

## Notes / Constraints
- All endpoints require JWT; role controls are strict for deletion operations.
- Performance targets emphasize fast CRUD and bounded AI latency.
- Candidate module is a high-fanout dependency; schema and contract changes should be versioned carefully.
- Fuzzy duplicate detection and resume versioning are explicitly deferred beyond Phase 1.
