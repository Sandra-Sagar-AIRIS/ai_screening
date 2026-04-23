# AI Services

## Overview
The AI services domain is AIRIS's internal AI abstraction layer. It wraps external providers (OpenAI and Anthropic) behind typed internal interfaces and standardizes model usage, fallback behavior, logging, and cost tracking.

No other service should call external AI APIs directly.

## Responsibilities
Primary responsibilities:
- Provide reusable AI capabilities:
  - resume parsing
  - candidate-job matching
  - interview question generation
  - interview summary generation
  - natural-language candidate search interpretation and reranking
- Handle provider fallback and timeout behavior.
- Log every AI call for observability, governance, and cost control.
- Keep structured outputs stable for upstream modules.

## Data Model
Core table:
- `ai_request_log`: function name, provider/model, token usage, latency, cost estimate, status, fallback metadata, user context.

Key model-level constraints:
- Functions return typed objects (not raw model text).
- Allowed statuses: `success`, `error`, `timeout`, `fallback`.
- Metadata may include domain IDs (job/candidate/user) without persisting full prompt/response payloads.

## API Endpoints
Not applicable as external REST.

Internal interface functions (Python):
- `parse_resume(s3_key, user_id?)`
- `match_candidates(job_requirements, candidate_profiles, user_id?)`
- `generate_interview_questions(job_description, required_skills, user_id?)`
- `generate_interview_summary(interview_notes, job_description?, candidate_name?, user_id?)`
- `smart_search(query, candidate_count=100, user_id?)`

## Business Logic
- Provider routing is capability-specific (e.g., Claude primary for some generation flows, OpenAI primary elsewhere) with fallback where defined.
- Timeouts are function-specific and enforced strictly.
- Resume parsing returns per-field confidence and `low_confidence_fields` for UI review workflows.
- Matching computes transparent weighted scoring across skills, location, and experience.
- Smart search extracts intent from NL query, then performs structured filtering and relevance reranking.
- Every invocation writes a costed request log row for monitoring and monthly budget control.

## Notes / Constraints
- AI services do not own candidate/job source data; they consume input and return scored/structured outputs.
- Keep outputs deterministic enough for API contract stability across frontend/backend features.
- Streaming responses, fine-tuning, vector DB, and multilingual support are deferred.
- Cost governance is mandatory; monthly spend anomalies should trigger investigation.
