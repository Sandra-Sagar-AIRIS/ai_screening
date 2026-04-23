# Pipeline

## Overview
The pipeline domain manages the job-specific candidate funnel as a Kanban-style process. It owns stage configuration, candidate card movement, optimistic concurrency for collaborative editing, and immutable transition history.

## Responsibilities
Primary responsibilities:
- Serve per-job pipeline views grouped by ordered stages.
- Move candidates between stages with conflict detection.
- Capture transition audit history, including rejection reasons.
- Manage workspace-level stage configuration, including default and custom stages.
- Record placement transitions for downstream analytics.

## Data Model
Core tables:
- `pipeline_stages`: workspace stage definitions, ordering, escape-stage flags.
- `pipeline_cards`: candidate position in a job's pipeline with version for OCC.
- `pipeline_stage_history`: immutable movement log with actor and reason.
- `pipeline_placements`: placement event records used for time-to-fill metrics.

Key constraints:
- Unique stage names per workspace.
- Unique `(job_id, candidate_id)` card.
- Rejection reason required when moving into rejected stage.
- Stage order must remain contiguous when reconfigured.

## API Endpoints
Representative endpoints:
- `GET /api/v1/pipelines/{job_id}` pipeline board view
- `POST /api/v1/pipelines/{job_id}/move` move candidate stage
- `GET /api/v1/workspaces/{workspace_id}/stages` list stage config
- `PUT /api/v1/workspaces/{workspace_id}/stages` update stage config
- `GET /api/v1/pipelines/{job_id}/history` job transition history
- `GET /api/v1/pipelines/{job_id}/candidates/{candidate_id}/history` candidate journey in job

## Business Logic
- Move operations enforce optimistic concurrency using `current_version`; stale clients receive conflict payloads.
- Rejected and placed stages are treated as escape stages and can bypass standard linear flow.
- On every stage move, service writes transition history and calls candidate-management to append a `stage_change` interaction.
- Moving to placed creates placement records for analytics.
- Stage config updates are admin-gated and must preserve required terminal stages (`Placed`, `Rejected`).
- Stage config changes do not retroactively reposition existing cards.

## Notes / Constraints
- Pipeline is process-state owner; job/candidate profile ownership remains in job-management and candidate-management.
- Communication triggers on stage changes are downstream concerns.
- Bulk moves, stage-specific validation rules, and auto-progression are deferred.
- For UI collaboration safety, client apps must always pass latest card version when moving cards.
