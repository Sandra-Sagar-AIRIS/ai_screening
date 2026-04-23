# AIRIS — AI-Powered Recruiting Platform
## Product Requirements Document v1.0
**Date:** April 2026 | **Market:** India (primary) | **Author:** Product Team

---

## Problem Statement

Recruiting agencies in India operate across dozens of simultaneous client engagements, managing hundreds of candidates through fragmented, manual toolsets — spreadsheets, WhatsApp groups, email threads, and disconnected point solutions. Unlike corporate HR departments, agencies treat candidates as long-term assets who are placed across multiple clients over months or years. Existing platforms are built for in-house corporate hiring, not the agency model, creating critical gaps:

- **No unified candidate database** that persists across client engagements — context is lost between placements
- **No multi-client workspace isolation** — data bleeds between competing clients in the same industry
- **No AI-powered screening at scale** — recruiters manually review hundreds of CVs per role
- **No branded client experience** — agencies cannot present a professional, white-labelled service
- **No 24/7 automated candidate engagement** — recruiters are the bottleneck for every touchpoint
- **No credible assessments** — verifying candidate skills requires expensive third-party tools
- **No consolidated analytics** — agencies cannot prove their speed or quality to retain clients

The result: recruiting agencies lose margin to manual work, lose clients to competitors with better tooling, and lose candidates to poor communication experiences.

---

## Solution

AIRIS is an AI-first SaaS recruiting platform purpose-built for staffing and recruiting agencies targeting the Indian market and beyond. It provides:

1. **A multi-client agency workspace** with role-based access, data isolation, and branded client portals
2. **A universal candidate database** that survives across placements, clients, and time
3. **AI-powered screening and assessment** that qualifies candidates 24/7 before any human involvement
4. **Automated communication** across email, SMS, and WhatsApp that keeps candidates engaged without recruiter effort
5. **Deep analytics** that prove agency value to clients and surface operational bottlenecks

Development is structured into three phases:
- **Phase 1 (MVP — weeks):** Core recruiting infrastructure for pilot agencies
- **Phase 2 (AI + Communications):** AI screening, assessments, video interviews, and WhatsApp automation
- **Phase 3 (Scale + Integrations + Compliance):** White-label portals, ATS connectors, open API, billing models, and DPDPA compliance

---

## Recommended Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Frontend** | Next.js 15 (App Router), TypeScript, Tailwind CSS v4, Shadcn UI | Production-grade SSR/SSG, type safety, rapid UI development |
| **Backend** | Next.js API Routes + Supabase Edge Functions | Serverless, co-located with frontend, scales to zero |
| **Database** | Supabase (PostgreSQL + Row Level Security) | Multi-tenant isolation via RLS, real-time subscriptions, managed |
| **Auth** | Supabase Auth | Supports email/password, OAuth, magic link; SAML SSO-ready for Phase 3 |
| **File Storage** | Supabase Storage | Integrated with RLS, signed URLs, direct CV/resume uploads |
| **AI / LLM** | Anthropic Claude API | Conversational interviewer, scoring, summaries, bias detection |
| **Video (Phase 2)** | Daily.co | Embeddable SDK, recording, transcription, low-latency in India |
| **CV Parsing** | Affinda API | India-friendly CV formats, structured extraction, REST API |
| **Email** | Resend | Simple transactional API, great deliverability, React email templates |
| **SMS** | MSG91 | India-first SMS provider, best deliverability on Indian networks |
| **WhatsApp (Phase 2)** | Interakt (WhatsApp Business API) | India-focused, template management, two-way messaging, lower cost |
| **Payments** | Razorpay | India-first, supports subscriptions, UPI, net banking, cards |
| **Deployment** | Vercel | Zero-config Next.js deployment, edge functions, preview environments |
| **Testing** | Vitest + Playwright | Unit/integration + E2E, works seamlessly with Next.js |
| **Real-time** | Supabase Realtime | Pipeline updates, notifications without polling |

---

## User Stories

### Agency Admin

1. As an agency admin, I want to create a new agency account with my organisation name and logo, so that my team can start using the platform under our brand identity.
2. As an agency admin, I want to invite team members via email and assign them roles (recruiter, manager), so that I can control who has access to what.
3. As an agency admin, I want to create a separate workspace for each client, so that candidate data and job pipelines are fully isolated between competing clients.
4. As an agency admin, I want to define custom pipeline stages per client or role type, so that our workflow matches each client's hiring process.
5. As an agency admin, I want to view agency-wide analytics including time-to-fill, placement rates, and recruiter performance, so that I can identify bottlenecks and top performers.
6. As an agency admin, I want to manage subscription billing and seat counts, so that I can control platform costs as we grow.
7. As an agency admin, I want to deactivate a recruiter's account without losing their candidate or job history, so that offboarding does not cause data loss.
8. As an agency admin, I want to set global email and SMS notification templates for candidate communication, so that all outreach maintains a consistent agency voice.
9. As an agency admin, I want to export all data for a specific client engagement as a report, so that I can present results during quarterly business reviews.

### Recruiter

10. As a recruiter, I want to create a new candidate profile by uploading a CV/resume, so that the system automatically extracts name, contact, skills, and experience without manual data entry.
11. As a recruiter, I want to search the universal candidate database by skills, location, experience level, and availability, so that I can surface existing candidates before sourcing new ones.
12. As a recruiter, I want to see a candidate's full history — jobs they were submitted to, interview outcomes, placement history, and all communication — in one profile view, so that I have full context before re-engaging them.
13. As a recruiter, I want to be alerted when I try to add a candidate who already exists in the database, so that I avoid duplicate profiles and embarrassing double-submissions.
14. As a recruiter, I want to move candidates between pipeline stages using a drag-and-drop Kanban board, so that I can manage pipeline flow intuitively without navigating multiple screens.
15. As a recruiter, I want to create a job requisition by filling in a structured intake form, so that all role requirements, compensation, and skills are captured consistently.
16. As a recruiter, I want to track which candidates have been submitted to which clients and in which roles, so that I never accidentally double-submit a candidate to the same client.
17. As a recruiter, I want to send interview invitations and scheduling links directly from the platform, so that candidates can self-book without back-and-forth email chains.
18. As a recruiter, I want to receive automated reminders when I have not moved a candidate in a pipeline stage for more than X days, so that pipeline stagnation is surfaced automatically.
19. As a recruiter, I want to tag candidates with skills, industries, and custom labels, so that I can segment and retrieve them efficiently for future roles.
20. As a recruiter, I want to add private notes to candidate profiles that are not visible to clients, so that I can record sensitive context without exposing it externally.
21. As a recruiter, I want to send bulk emails or SMS to a filtered set of candidates, so that I can broadcast role openings or updates efficiently.
22. As a recruiter, I want to see which candidates have opened my emails and clicked links, so that I can prioritise follow-up with engaged candidates.
23. As a recruiter, I want to create and save reusable email and SMS templates, so that common communications are consistent and fast to send.
24. As a recruiter, I want to schedule interviews across multiple interviewers by matching their calendar availability, so that panel interviews are coordinated without manual back-and-forth.
25. As a recruiter, I want to receive structured feedback from interviewers via scorecards with a deadline, so that I am not chasing feedback manually after every interview.
26. As a recruiter, I want to see AI-generated summaries of candidate interviews, so that I can review outcomes without watching full interview recordings.
27. As a recruiter, I want the AI to rank and score candidates against job requirements, so that I can shortlist the most relevant profiles without reading every CV manually.
28. As a recruiter, I want to assign a pre-built skills assessment or coding test to a candidate, so that I can validate their claims before presenting them to clients.
29. As a recruiter, I want to see a candidate's assessment score alongside their profile and interview summary, so that I have a complete picture when making a shortlist decision.
30. As a recruiter, I want to generate a structured set of interview questions from a job description using AI, so that every interviewer is asking consistent, role-relevant questions.

### Client Hiring Manager

31. As a client hiring manager, I want to log in to a client portal and see only the candidates submitted to my company, so that I have pipeline visibility without access to other clients' data.
32. As a client hiring manager, I want to view candidate profiles, CVs, and interview summaries from the portal, so that I can review shortlists without the recruiter manually sending documents.
33. As a client hiring manager, I want to submit structured feedback on candidates directly in the portal, so that my feedback is captured in a standardised format rather than in email.
34. As a client hiring manager, I want to see the current stage of each candidate in real time, so that I know where the pipeline stands without chasing the recruiter.
35. As a client hiring manager, I want to mark a candidate as selected, rejected, or on-hold directly in the portal, so that decisions are captured instantly.
36. As a client hiring manager, I want to receive automated weekly pipeline summary emails, so that I stay informed without logging into the portal every day.

### Candidate

37. As a candidate, I want to receive a clear, professional communication when I apply for a role, so that I know my application has been received.
38. As a candidate, I want to receive an automated screening questionnaire (availability, salary, visa, notice period) via email, SMS, or WhatsApp, so that I can respond at my convenience without scheduling a call.
39. As a candidate, I want to self-schedule my interview by picking from available time slots, so that I can book at a time that suits me without back-and-forth.
40. As a candidate, I want to receive interview reminders via email and SMS, so that I do not miss my interview due to a forgotten calendar entry.
41. As a candidate, I want to complete skills assessments and coding tests in a browser without installing any software, so that the process is frictionless.
42. As a candidate, I want to participate in an AI-led screening interview via video, voice, or chat, so that I can be screened at any time without waiting for a recruiter.
43. As a candidate, I want to receive a clear notification of the outcome of each stage, so that I am not left in the dark about my application status.
44. As a candidate, I want to easily reschedule my interview with one click if I cannot make the original time, so that the process does not break down over scheduling conflicts.

### Platform / AI Automation

45. As the platform, I want to automatically parse an uploaded CV into a structured candidate profile (name, email, phone, skills, education, work history), so that recruiter data entry is eliminated.
46. As the platform, I want to detect and flag duplicate candidates when a new profile is created, so that the database stays clean without manual deduplication.
47. As the platform, I want to automatically match candidates in the database to a newly posted job and rank them by relevance score, so that recruiters see the best-fit existing candidates immediately.
48. As the platform, I want to conduct an AI conversational screening interview (video, voice, or chat) using the job description as context, so that candidates are pre-qualified before any human review.
49. As the platform, I want to generate an explainable composite candidate score from CV, assessment results, and interview responses, so that recruiters and clients can understand the ranking rationale.
50. As the platform, I want to generate a structured post-interview summary (strengths, concerns, skill gaps, recommended next steps) from the interview transcript, so that recruiters have a structured debrief output.
51. As the platform, I want to send automated multi-step candidate nurture sequences via email and SMS (Phase 1) and WhatsApp (Phase 2) without recruiter intervention, so that candidate engagement is maintained at scale.
52. As the platform, I want to generate a set of structured interview questions (technical, behavioural, situational) from a job description, so that interviewers are prepared without hours of manual prep.
53. As the platform, I want to monitor scoring outputs for adverse impact across protected categories and surface anomalies, so that agencies can demonstrate fair, auditable hiring processes to enterprise clients.
54. As the platform, I want to enforce anti-cheating measures during assessments (tab-switch detection, copy-paste monitoring, AI-response detection), so that assessment results are credible.

---

## Implementation Decisions

### Phase 1 — Core Recruiting Infrastructure (MVP)

**Modules to build:**

1. **Workspace & Tenancy Module**
   - Each agency is a tenant; each client is a sub-workspace within the tenant
   - Supabase RLS enforces data isolation at the database level — no cross-tenant data leakage
   - Workspace settings: name, logo, timezone, default pipeline stages

2. **Identity & Access Control Module**
   - Roles: `agency_admin`, `recruiter`, `client_hiring_manager`, `candidate`
   - Permissions matrix enforced server-side via Supabase RLS + middleware
   - Invite flow: email invite → accept → role assigned
   - Session management via Supabase Auth (JWT)

3. **Candidate CRM Module**
   - Universal candidate table shared across all client workspaces within a tenant
   - Candidate profile: personal info, skills taxonomy, work history, education, tags, notes, interaction history, placement history
   - CV upload → Affinda API → structured profile auto-population
   - Duplicate detection: fuzzy match on email + phone + name combination
   - Submission tracker: many-to-many table linking candidates to jobs with status and feedback

4. **Pipeline (Kanban) Module**
   - Per-client, per-job configurable pipeline stages (drag-and-drop)
   - Stage transitions logged with timestamps for time-in-stage analytics
   - Stagnation alerts: configurable thresholds per stage
   - Candidate cards: name, current stage, last activity, key skills, score (Phase 2)

5. **Job Requisition Module**
   - Structured job intake form: title, department, client, location, work type, skills required, compensation range, number of openings
   - Job status lifecycle: `draft → open → on_hold → closed → filled`
   - Application ingestion: manual add, bulk CSV upload, or email forwarding
   - CV parsing on application ingestion

6. **Interview Scheduling Module**
   - Google Calendar + Outlook/Exchange OAuth integration
   - Self-service booking links with timezone auto-detection
   - Panel scheduling: match availability across multiple interviewers
   - Automated reminders: D-1 and H-2 before interview via email + SMS
   - One-click reschedule link in reminder messages
   - Feedback scorecard: sent to interviewer after interview with deadline + nudge

7. **Communication Hub Module (Phase 1: Email + SMS)**
   - Outbound email via Resend with tracking (open, click)
   - Outbound SMS via MSG91 (India)
   - Unified inbox: all candidate communication history in one thread view
   - Template engine: saved templates with variable substitution
   - Bulk send: filter candidates → compose → schedule

8. **Analytics & Reporting Module**
   - Pipeline metrics: time-to-fill, time-in-stage, pass-through rate by stage
   - Source effectiveness: which source produces the most placements
   - Recruiter performance: submissions, placements, response times
   - Client report: exportable PDF/CSV pipeline snapshot

9. **Billing Module (Phase 1: Subscription)**
   - Razorpay subscription integration
   - Plans: per-seat or per-agency monthly/annual pricing
   - Usage metering groundwork for Phase 3 per-placement billing

**Database Schema (key tables):**

```
agencies              — tenant root (id, name, logo, plan, created_at)
agency_members        — (agency_id, user_id, role, invited_at, joined_at)
clients               — sub-workspaces (id, agency_id, name, logo, domain)
client_members        — (client_id, user_id, role)
candidates            — universal (id, agency_id, name, email, phone, skills[], tags[], source, created_at)
candidate_profiles    — extended (candidate_id, cv_url, parsed_data jsonb, work_history jsonb, education jsonb)
jobs                  — (id, agency_id, client_id, title, status, requirements jsonb, created_by)
pipeline_stages       — (id, client_id OR job_id, name, order, stagnation_threshold_days)
pipeline_entries      — (id, candidate_id, job_id, stage_id, entered_at, recruiter_id)
pipeline_history      — (id, entry_id, from_stage, to_stage, changed_by, changed_at)
submissions           — (id, candidate_id, job_id, submitted_by, submitted_at, status, client_feedback)
interviews            — (id, candidate_id, job_id, scheduled_at, type, interviewers[], status, booking_link)
interview_feedback    — (id, interview_id, interviewer_id, scorecard jsonb, submitted_at)
communications        — (id, agency_id, candidate_id, channel, direction, subject, body, status, sent_at)
templates             — (id, agency_id, name, channel, subject, body, variables[])
subscriptions         — (id, agency_id, razorpay_subscription_id, plan, status, current_period_end)
```

**API Design (REST, Next.js API Routes):**
- `/api/workspaces` — CRUD agency workspaces
- `/api/clients` — CRUD client sub-workspaces
- `/api/candidates` — CRUD + search + duplicate check
- `/api/candidates/[id]/parse-cv` — trigger Affinda CV parse
- `/api/jobs` — CRUD job requisitions
- `/api/pipeline` — stage transitions, Kanban state
- `/api/interviews` — scheduling, booking link generation, feedback
- `/api/communications` — send email/SMS, inbox, templates
- `/api/analytics` — pipeline metrics, recruiter stats
- `/api/billing/webhook` — Razorpay webhook handler

---

### Phase 2 — AI Features + WhatsApp Business

**Additional modules to build:**

10. **AI Conversational Interviewer Module**
    - LLM agent (Claude API) ingests JD → generates adaptive question set
    - Supports three modes: video (Daily.co), voice, or chat
    - Real-time follow-up questions based on candidate responses
    - Designed for pre-screening (not final rounds)
    - Transcript stored per session; triggers summary generation on completion

11. **AI Scoring & Matching Module**
    - Composite score: CV relevance (40%) + assessment score (30%) + interview score (30%)
    - Each score component is explainable (rationale shown to recruiter)
    - Automatic candidate-to-job matching on job creation — surfaces top 10 from existing DB
    - Scoring results stored on `submissions` table, visible in pipeline card

12. **AI Question Generator Module**
    - Input: job description text or job requisition ID
    - Output: structured question bank (technical, behavioural, situational) in JSON
    - Questions saved to job; assignable to interviewers

13. **AI Interview Summary Module**
    - Input: interview transcript (from AI interviewer or manual upload)
    - Output: structured summary — strengths, concerns, skill gaps, recommended next steps
    - Summary attached to candidate profile; shareable with client via portal

14. **Automated Screening Chatbot Module**
    - Triggers on new application
    - Screens: availability, current salary, expected salary, notice period, visa/work authorisation, minimum qualifications
    - Delivered via email (Phase 1), WhatsApp + SMS (Phase 2)
    - Responses parsed and stored; candidate auto-advances or auto-rejects based on criteria

15. **Live Video Interview Module**
    - Daily.co embedded SDK — no candidate app download required
    - Recording stored in Supabase Storage
    - Automated transcription via Daily.co or Whisper API
    - Scorecard overlay visible to interviewer during live session
    - Anti-cheating: tab-switch detection, AI-response pattern flagging

16. **Assessment Module**
    - Skills assessment library: technical, cognitive, language proficiency, personality
    - Coding assessments: browser-based IDE, 30+ languages, test case execution
    - Structured scorecards: custom rubrics, weighted scoring per criterion
    - Anti-cheating: tab-switch detection, copy-paste monitoring, webcam proctoring (optional)
    - Results attached to candidate profile

17. **WhatsApp Business Module**
    - Interakt integration (WhatsApp Business API)
    - Template messages: interview reminders, screening questionnaire, status updates
    - Two-way messaging: candidate replies captured in communication hub
    - Opt-in/opt-out management per candidate

---

### Phase 3 — Scale, Integrations & Compliance

**Additional modules to build:**

18. **White-Label Portal Module**
    - Custom domain per client (CNAME)
    - Client logo, brand colours, custom email sender domain
    - Agency can toggle which portal features are visible to each client

19. **ATS / HRIS Integration Module**
    - Connectors: Greenhouse, Lever, Workday, iCIMS, Zoho Recruit, Keka, Darwinbox
    - Bidirectional sync: jobs pushed from client ATS, candidates pushed back on placement
    - OAuth-based connector auth, configurable field mapping

20. **Open API & Webhooks Module**
    - Public RESTful API with API key authentication
    - Webhooks for: candidate created, stage changed, interview scheduled, placement made
    - Developer portal with OpenAPI spec documentation

21. **Multi-Entity Billing Module**
    - Billing models: per-placement fee, monthly retainer, hourly, or subscription
    - Per-client usage tracking: interviews conducted, placements made, platform activity
    - Invoicing export: PDF invoices per client per billing period
    - Razorpay supports all models; custom billing logic in platform

22. **Compliance & DPDPA Module**
    - Consent capture and management per candidate (India DPDPA + GDPR)
    - Data retention policies: configurable per agency, auto-deletion workflows
    - Immutable audit log: all data access, stage changes, communications
    - Right-to-erasure workflow: candidate requests data deletion

23. **DEI & Bias Reporting Module**
    - Adverse impact analysis: pass-through rates by gender, age group (where disclosed)
    - AI bias detection: monitors scoring distributions for statistical anomalies
    - Audit-ready exports compliant with NYC LL144 and EU AI Act

24. **SSO & Enterprise Security Module**
    - SAML 2.0 and OAuth SSO
    - Two-factor authentication enforcement at workspace level
    - Data encryption at rest (Supabase) and in transit (TLS)
    - SOC 2 Type II readiness checklist

---

## Testing Decisions

**What makes a good test:**
- Tests exercise external behaviour (API contracts, UI flows, data outcomes) — not internal implementation details
- Tests are deterministic and do not depend on external AI model responses (mock the Claude API in unit/integration tests)
- Tests cover happy paths, error states, and edge cases (duplicate detection, malformed CVs, scheduling conflicts)
- E2E tests simulate real user journeys from login to placement

**Modules to test:**

| Module | Test Type | What to verify |
|--------|-----------|----------------|
| Workspace & Tenancy | Integration | RLS enforcement — recruiter from Agency A cannot read Agency B's candidates |
| Candidate CRM | Unit + Integration | CV parsing output structure, duplicate detection logic, search filtering accuracy |
| Pipeline (Kanban) | Integration + E2E | Stage transitions logged correctly, stagnation alert threshold triggers, drag-and-drop state persists |
| Job Requisition | Unit + Integration | Form validation, job lifecycle status transitions, CV parse on application |
| Interview Scheduling | Integration | Calendar availability matching, booking link generation, reminder dispatch timing |
| Communication Hub | Integration | Email/SMS send via provider, template variable substitution, inbox aggregation |
| AI Scoring Module | Unit (mocked) | Score calculation formula, weights applied correctly, explainability fields present |
| AI Interview Summary | Integration (mocked) | Summary structure correct, all required fields populated, stored on correct candidate |
| Assessment Module | Integration + E2E | Test case execution, score calculation, anti-cheat event logging |
| Analytics Module | Unit | Metric calculation correctness (time-to-fill formula, pass-through rate) |
| Billing | Integration | Razorpay webhook signature verification, subscription status transitions |

**Testing patterns:**
- Vitest for unit and integration tests
- Playwright for E2E flows (candidate applies → screened → scheduled → scored → placed)
- Supabase local dev environment for database tests with real RLS
- Mock Anthropic Claude API responses using `msw` (Mock Service Worker) for AI module tests

---

## Phase Summary

### Phase 1 — Core Recruiting Infrastructure (MVP, weeks)
**Goal:** Ship a working recruiting platform to pilot agencies in India.

| Module | Features |
|--------|----------|
| Workspace & Tenancy | Agency account creation, client workspaces, data isolation |
| Identity & Access | Roles (admin, recruiter, client manager, candidate), invite flow |
| Candidate CRM | Universal DB, CV parsing, duplicate detection, submission tracking |
| Pipeline (Kanban) | Configurable stages, drag-and-drop, stagnation alerts |
| Job Requisition | Structured intake, application ingestion, CV parsing |
| Interview Scheduling | Calendar sync, self-service booking, reminders, scorecard |
| Communication Hub | Email (Resend) + SMS (MSG91), templates, bulk send, inbox |
| Analytics | Pipeline metrics, recruiter stats, client report export |
| Billing | Razorpay subscription (per-seat or per-agency) |

### Phase 2 — AI Features + WhatsApp Business
**Goal:** Differentiate with AI screening, 24/7 automation, and India-preferred WhatsApp channel.

| Module | Features |
|--------|----------|
| AI Conversational Interviewer | LLM-led video/voice/chat pre-screening, adaptive follow-ups |
| AI Scoring & Matching | Composite scoring, explainable rationale, DB matching on job creation |
| AI Question Generator | JD → structured question bank (technical, behavioural, situational) |
| AI Interview Summary | Transcript → strengths, concerns, skill gaps, next steps |
| Screening Chatbot | Automated pre-qualification via email + WhatsApp + SMS |
| Live Video Interviewing | Daily.co, recording, transcription, scorecard overlay |
| Assessments | Skills library, coding IDE, scorecards, anti-cheating, proctoring |
| WhatsApp Business | Interakt integration, templates, two-way messaging, opt-out |

### Phase 3 — Scale, Integrations & Compliance
**Goal:** Enterprise-readiness, ATS ecosystem, compliance, and flexible billing.

| Module | Features |
|--------|----------|
| White-Label Portals | Custom domain, branding, per-client feature toggles |
| ATS/HRIS Connectors | Greenhouse, Lever, Workday, Zoho, Keka, Darwinbox |
| Open API & Webhooks | Public API, webhook events, developer portal |
| Multi-Entity Billing | Per-placement, retainer, hourly, invoicing, per-client tracking |
| DPDPA Compliance | Consent management, data retention, audit log, right-to-erasure |
| DEI & Bias Reporting | Adverse impact analysis, AI bias detection, audit exports |
| SSO & Security | SAML/OAuth SSO, 2FA enforcement, SOC 2 readiness |

---

## Out of Scope

The following are explicitly out of scope for all three phases unless separately specified:

- **Corporate/in-house HR features:** Performance management, onboarding, payroll, employee engagement — AIRIS is exclusively for recruiting agencies, not internal HR departments
- **Job board posting:** Direct job board integrations (LinkedIn, Naukri, Indeed) — candidates arrive via agency sourcing, not inbound job board applications
- **Candidate-facing mobile app:** Mobile-responsive web is sufficient; a native iOS/Android app is not in scope
- **AI final-round interviewing:** The AI interviewer is designed for pre-screening only; it does not replace human interviewers in final rounds
- **Automated offer management:** Offer letters, e-signature, and salary negotiation workflows are out of scope
- **Background verification integration:** BGV vendor integrations are not in scope
- **Payroll and contractor management:** Payment to placed candidates is not in scope
- **Headhunting CRM:** LinkedIn scraping, automated outreach campaigns, and talent intelligence are not in scope for Phase 1 or 2

---

## Further Notes

- **India-first design decisions:** MSG91 is preferred over Twilio for SMS due to significantly better deliverability on Indian networks and lower cost. Interakt is preferred over Twilio WhatsApp for the same reasons. Razorpay handles INR natively including UPI, NEFT, and cards.

- **AI provider strategy:** Anthropic Claude API is recommended as the primary LLM for the conversational interviewer, scoring, summaries, and question generation. Claude's large context window is particularly valuable for processing full CV + JD pairs simultaneously.

- **Multi-tenancy approach:** Supabase RLS (Row Level Security) enforces multi-tenant isolation at the database query level rather than the application level. This is a critical architectural decision — application-level tenant filtering is fragile and audit-unfriendly.

- **CV parsing strategy:** Affinda supports Indian CV formats natively (including formats common on Naukri). As a fallback for Phase 2, Claude API can be used to parse CVs with a structured prompt, reducing third-party dependency.

- **Billing model recommendation for Phase 1:** Start with a simple per-agency subscription (flat monthly fee covering up to N recruiters and N active jobs). Avoid per-placement billing in Phase 1 — it requires placement verification logic that delays the MVP. Introduce per-placement as an optional billing model in Phase 3.

- **Pilot agency strategy:** Onboard 2–3 pilot agencies with white-glove support during Phase 1. Use their real workflows to validate pipeline stage configurations, communication preferences, and reporting needs before scaling Phase 2 features.

- **Regulatory timeline:** DPDPA (India's Digital Personal Data Protection Act) enforcement is progressing in 2025–2026. Phase 3 compliance work should be scoped to begin no later than 6 months post-Phase 1 launch to avoid regulatory risk.

- **Phase 2 AI cost management:** AI conversational interviews and scoring will incur per-token costs. Design the AI modules with usage metering from day one so that AI costs can be attributed to specific agencies and factored into pricing.
