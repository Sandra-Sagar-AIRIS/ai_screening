# Scheduling

## Overview
The scheduling domain owns interview coordination end-to-end: recruiter calendar OAuth, booking link generation, slot discovery, booking, rescheduling, cancellation, and reminder delivery.

It bridges recruiter workflows with candidate self-service booking while keeping interview state consistent with calendars and communication channels.

## Responsibilities
Primary responsibilities:
- Manage Google/Outlook calendar connections and token lifecycle.
- Generate secure booking links with configurable working windows.
- Compute real-time available slots from provider calendars.
- Create and maintain interview records and provider event IDs.
- Schedule and deliver reminder notifications.
- Handle rescheduling/cancellation with conflict checks and side effects.

## Data Model
Core tables:
- `calendar_connections`: provider tokens, account metadata, connection status.
- `booking_links`: public scheduling links and availability configuration.
- `interviews`: scheduled interview state, status, cancellation metadata.
- `interview_reminders`: pending/sent reminder jobs and delivery outcomes.

Key constraints:
- One calendar connection per recruiter/workspace/provider.
- Booking slug uniqueness.
- Interview state machine: `scheduled`, `completed`, `cancelled`, `no_show`.
- Reminders derived from interview schedule timestamps.

## API Endpoints
Representative endpoints:
- `POST /api/v1/calendar/connect` start OAuth flow
- `GET /api/v1/calendar/callback` OAuth callback
- `GET /api/v1/calendar/status` connection health
- `POST /api/v1/interviews/booking-link` create link
- `GET /api/v1/interviews/booking-link/{slug}/availability` public slot lookup
- `POST /api/v1/interviews/booking-link/{slug}/book` public booking
- `GET /api/v1/interviews` list interviews
- `GET /api/v1/interviews/{interview_id}` details
- `POST /api/v1/interviews/{interview_id}/reschedule` reschedule
- `POST /api/v1/interviews/{interview_id}/cancel` cancel

## Business Logic
- Availability and booking conflict checks are performed against live calendar provider data.
- Booking writes interview rows only after provider event creation succeeds.
- Booking creates candidate timeline interactions and two default reminders (24h and 1h).
- Rescheduling is blocked within 4 hours of start time; update must be atomic with external calendar update.
- Cancellation is idempotent for already-cancelled interviews and clears pending reminders.
- Token expiration from provider API marks connection as expired and blocks new booking-link generation until reconnection.
- Provider calls use bounded retries with exponential backoff for transient failures.

## Notes / Constraints
- Public booking endpoints are intentionally unauthenticated; slug secrecy and active-state checks are required controls.
- Multi-interviewer panel orchestration and conferencing integrations are out of Phase 1 scope.
- Role access: recruiter/admin manage interviews; client viewer has no direct endpoint access.
- Keep calendar operations and DB updates transactionally safe to prevent double-booking drift.
