# AIRIS PRD Index

## 1. System Overview

AIRIS is an AI-powered recruiting platform built for staffing and recruiting agencies.  
It unifies candidate management, job management, pipeline tracking, interview scheduling, communication, AI services, and analytics in one system.  
The platform is designed to support multi-client agency workflows with role-based access and workspace boundaries.  
Its architecture is modular, so teams can build features by domain while preserving shared contracts.  
AI is integrated directly into operational flows, including resume parsing, candidate matching, and screening support.  
This PRD documentation set is the canonical reference for both developers and AI coding assistants.

---

## 2. How to Use These Docs (IMPORTANT)

- Start with `summary.md` to get the fastest high-level context.
- Use `architecture.md` to understand module boundaries, dependencies, and shared rules before implementation.
- Move into specific module docs (for example `candidate-management.md`, `pipeline.md`) for API, data, and behavior details.
- Combine multiple docs when implementing cross-module features (for example scheduling + communication + pipeline).
- Use `design-system.md` for any UI-related work to keep patterns, components, and token usage consistent.
- Use `setup.md` for project conventions, workflow setup, and environment-level expectations.

---

## 3. Recommended Reading Order

1. `summary.md` (high-level understanding)  
2. `architecture.md` (system design)  
3. `design-system.md` (UI consistency)  
4. Core modules:
   - `candidate-management.md`
   - `job-management.md`
   - `pipeline.md`
   - `scheduling.md`
   - `communication.md`
5. `ai-services.md` (AI features)  
6. `analytics.md`  
7. `setup.md`

---

## 4. Module Map

- `candidate-management.md` -> handles candidate data, resumes, profiles, skills, interactions, and deletion/merge workflows.
- `job-management.md` -> owns job postings, requirements, job lifecycle, submissions, and match result caching.
- `pipeline.md` -> manages hiring stages, candidate movement, stage history, and placement transitions.
- `scheduling.md` -> handles interview booking links, calendar coordination, reminders, rescheduling, and cancellation.
- `communication.md` -> manages recruiter-candidate messaging flows, primarily email integration and templates (WhatsApp is future scope).
- `ai-services.md` -> defines AI logic like parsing, matching, screening support, summarization, and provider abstraction.
- `analytics.md` -> powers reporting and operational insights (dashboard metrics, recruiter productivity, job metrics).
- `design-system.md` -> defines UI styling rules, tokens, components, and consistency constraints.
- `setup.md` -> outlines environment setup, repo standards, and implementation workflow guidance.

---

## 5. Key System Flows

- Candidate -> Job matching  
- Candidate -> Pipeline -> Interview -> Offer  
- AI screening before recruiter review

---

## 6. Prompting Guide (VERY IMPORTANT)

Use explicit doc references in prompts so AI tools stay aligned with AIRIS contracts:

- `Using docs/prd/candidate-management.md, generate FastAPI endpoints`
- `Based on docs/prd/summary.md and docs/prd/ai-services.md, implement resume parsing logic`
- `Refer to docs/prd/pipeline.md and docs/prd/scheduling.md to design interview workflow`
- `Using docs/prd/job-management.md and docs/prd/analytics.md, design job performance metrics APIs`
- `Follow docs/prd/design-system.md while creating recruiter dashboard UI components`

For cross-functional features, mention all relevant docs in one prompt to avoid partial implementations.
