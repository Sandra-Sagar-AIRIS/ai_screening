# AIRIS PRD Summary

## Overview
AIRIS is an AI-powered recruiting platform for staffing agencies operating across multiple client workspaces. It unifies candidate management, job management, hiring pipeline operations, interview scheduling, communication, AI-assisted decision support, and analytics in one system. Recruiters use AIRIS to reduce manual coordination and shorten time-to-shortlist/time-to-fill while preserving traceability and compliance controls.

### System Overview
AIRIS centralizes agency workflows from candidate intake through placement. The backend is organized into bounded service modules with shared authentication and role controls. The frontend surfaces these workflows with consistent design-system patterns. AI capabilities are embedded into core recruiter tasks (parsing, matching, screening support, summarization) rather than isolated as separate tools. Data integrity is maintained through service ownership boundaries and append-style history tracking for critical workflow events.

## Responsibilities
This summary is the quick-reference map for AI-assisted prompting and onboarding. It highlights core entities, flow relationships, and AI capabilities while deferring implementation detail to domain docs in `docs/prd/`.

### Core Entities
- **Candidate**: profile, skills, resume metadata, interactions, compliance lifecycle.
- **Job**: requisition with required/preferred skills, urgency, status, and submission context.
- **Pipeline**: stage model plus candidate progression history per job.
- **Interview**: scheduled event linked to candidate, job, recruiter, reminders, and calendar records.
- **User**: organization member with role, workspace access, and authenticated sessions.

## Data Model
At summary level, data ownership is domain-scoped:
- Identity/workspaces (`User`, `Organisation`, `Workspace`) are owned by auth.
- Candidate records and interactions are owned by candidate-management.
- Job records and submissions are owned by job-management.
- Stage movement and funnel history are owned by pipeline.
- Interview booking and reminder state are owned by scheduling.

## API Endpoints
Not exhaustive in this summary; use domain files for concrete endpoint contracts.

Representative surfaces:
- Candidate CRUD/search/upload/merge/delete
- Job CRUD/status/submissions/matching
- Pipeline view/move/history/stage config
- Scheduling booking-link availability/book/reschedule/cancel
- Communication connect/send/thread/template management
- Analytics dashboard/recruiter/job metrics/refresh

## Business Logic
### Key Flows
- **Candidate -> Job matching**: job requirements trigger ranked candidate recommendations; recruiters submit selected candidates.
- **Hiring pipeline flow**: candidates move through configured stages with version-safe updates and immutable transition history.
- **Interview scheduling**: booking links expose real-time slots; booking creates interviews, calendar events, and reminders.
- **AI screening**: parsed candidate data and AI-assisted interview tooling support shortlist decisions before final placement.

### AI Capabilities
- **Resume parsing**: extract structured profile data with confidence scoring.
- **Matching**: rank candidate-job fit with explainable score dimensions.
- **Summarization**: convert interview notes into structured decision summaries.
- **Screening support**: generate interview questions and support natural-language candidate search.

## Notes / Constraints
- This file is intentionally concise for prompt reuse and fast context loading.
- For implementation decisions, rely on module docs:
  - `architecture.md`
  - `candidate-management.md`
  - `job-management.md`
  - `pipeline.md`
  - `scheduling.md`
  - `communication.md`
  - `ai-services.md`
  - `analytics.md`
  - `design-system.md`
  - `setup.md`
- Phase 1 scope excludes several advanced capabilities; check each module's constraints section before planning features.
