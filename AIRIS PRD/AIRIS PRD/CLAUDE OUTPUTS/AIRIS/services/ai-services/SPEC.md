# Service spec: ai-services

**Version**: 1.0
**Date**: 2026-04-18
**Parent PRD**: AIRIS Phase 1 MVP PRD v1

---

## 1. Service boundary

**Folder**: `ai-services/`

This service owns all AI/ML functionality and abstracts external AI providers (OpenAI, Anthropic Claude) behind a stable internal API. No other service calls external AI APIs directly. All AI requests flow through this service's Python function interface.

**Owns**: `ai_request_log` table (logs all AI API calls for cost tracking, debugging, and compliance).

**Depends on**:

- External APIs: OpenAI GPT-4 API, Anthropic Claude API
- No internal service dependencies.

**Depended on by**:

- `candidate-management/` calls `parse_resume(s3_key)` and `smart_search(query)`.
- `job-management/` calls `match_candidates(job_requirements, candidate_profiles)`, `generate_interview_questions(job_description, required_skills)`, and `generate_interview_summary(interview_notes)`.

---

## 2. Database schema

```sql
-- ai-services/schema.sql

CREATE TABLE ai_request_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    function_name VARCHAR(100) NOT NULL,        -- 'parse_resume' | 'match_candidates' | 'generate_interview_questions' | 'generate_interview_summary' | 'smart_search'
    provider VARCHAR(20) NOT NULL,              -- 'openai' | 'anthropic'
    model VARCHAR(100) NOT NULL,                -- 'gpt-4', 'gpt-4-turbo', 'claude-3-5-sonnet', etc.
    input_tokens INT NOT NULL,
    output_tokens INT NOT NULL,
    latency_ms INT NOT NULL,
    cost_estimate DECIMAL(10, 6) NOT NULL,      -- in USD
    status VARCHAR(20) NOT NULL,                -- 'success' | 'error' | 'timeout' | 'fallback'
    error_message TEXT,                         -- NULL if status='success'
    fallback_provider VARCHAR(20),              -- provider used if fallback occurred
    created_at TIMESTAMPTZ DEFAULT NOW(),
    user_id UUID,                               -- recruiter/system user ID making the request
    metadata JSONB DEFAULT '{}'                 -- request-specific context (job_id, candidate_id, etc.)
);

CREATE INDEX idx_ai_request_log_function ON ai_request_log (function_name);
CREATE INDEX idx_ai_request_log_provider ON ai_request_log (provider);
CREATE INDEX idx_ai_request_log_created_at ON ai_request_log (created_at DESC);
CREATE INDEX idx_ai_request_log_status ON ai_request_log (status);
```

---

## 3. Function interface (internal Python API)

All functions are called directly within the Python monolith. No REST endpoints are exposed externally. All functions return structured Pydantic models, never raw AI text.

### 3.1 parse_resume

**Signature**:
```python
async def parse_resume(
    s3_key: str,
    user_id: Optional[UUID] = None
) -> ParseResumeResponse
```

**Input**:
```python
class ParseResumeRequest:
    s3_key: str  # S3 path to PDF/DOCX file, e.g., 'resumes/candidate-uuid/resume.pdf'
    user_id: Optional[UUID] = None  # recruiting user ID
```

**Output**:
```python
class ParsedResumeData(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    skills: list[str]  # comma-separated from resume, deduplicated
    experience_summary: str  # concatenated job titles and durations
    education: Optional[str] = None  # degree, institution, graduation year
    field_confidence: dict[str, float]  # {'name': 0.95, 'email': 0.98, 'phone': 0.65, ...}

class ParseResumeResponse(BaseModel):
    success: bool
    data: ParsedResumeData
    confidence_score: float  # average of field_confidence values
    low_confidence_fields: list[str]  # fields where confidence < 0.7
    ai_provider: str  # which provider succeeded
    latency_ms: int

# Example request
request = ParseResumeRequest(
    s3_key="resumes/a1b2c3d4-e5f6-7890-abcd-ef1234567890/priya_resume.pdf",
    user_id=UUID("rec-user-001")
)

# Example response
{
    "success": True,
    "data": {
        "name": "Priya Kumar",
        "email": "priya.kumar@example.com",
        "phone": "+91-9876543210",
        "location": "Chennai",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        "experience_summary": "Senior Backend Engineer at TechCorp (3 years), Python Developer at StartupXYZ (2 years)",
        "education": "B.Tech in Computer Science, IIT Madras, 2018",
        "field_confidence": {
            "name": 0.98,
            "email": 0.99,
            "phone": 0.65,
            "location": 0.88,
            "skills": 0.92,
            "experience_summary": 0.85,
            "education": 0.91
        }
    },
    "confidence_score": 0.88,
    "low_confidence_fields": ["phone"],
    "ai_provider": "openai",
    "latency_ms": 2847
}
```

**Timeout**: 30 seconds.

**Error cases**:

| Condition | Response |
|-----------|----------|
| S3 key does not exist | `ParseResumeResponse.success = False`, `error: "S3_NOT_FOUND"` |
| File is not PDF/DOCX | `success = False`, `error: "INVALID_FILE_FORMAT"` |
| OpenAI API unavailable | Fall back to Claude API. Log fallback in `ai_request_log` with `fallback_provider='anthropic'`. If Claude also fails, return error. |
| Claude API unavailable | If OpenAI was primary, already attempted. Return error with `status='error'`. |
| Timeout after 30s | Return `success = False`, `error: "TIMEOUT"`, `status='timeout'` in log. |

**Behaviour**:
- Calls OpenAI GPT-4 with a structured output prompt that instructs the model to extract and return JSON with the specified fields.
- For each field, the model returns a confidence score (0.0-1.0). Fields with confidence < 0.7 are listed in `low_confidence_fields`.
- If the email or phone cannot be extracted, the field is populated with `None` and confidence is 0.0.
- Logs all calls to `ai_request_log` with timestamp, provider, model, token counts, latency, cost estimate, status, and error message (if any).
- Cost estimate is calculated as: `(input_tokens / 1000 * openai_input_price) + (output_tokens / 1000 * openai_output_price)` (or Claude equivalent).

---

### 3.2 match_candidates

**Signature**:
```python
async def match_candidates(
    job_requirements: JobRequirements,
    candidate_profiles: list[CandidateProfile],
    user_id: Optional[UUID] = None
) -> MatchCandidatesResponse
```

**Input**:
```python
class JobRequirements(BaseModel):
    job_id: UUID
    required_skills: list[str]  # e.g., ['Python', 'FastAPI', 'PostgreSQL']
    preferred_skills: Optional[list[str]] = None  # lower weight than required
    location: Optional[str] = None  # single location or None
    location_flexibility: str = "required"  # 'required' | 'preferred' | 'flexible'
    min_experience_years: int = 0
    max_experience_years: Optional[int] = None

class CandidateProfile(BaseModel):
    candidate_id: UUID
    skills: list[str]
    location: Optional[str] = None
    experience_summary: str  # free text, parsed for years of experience
```

**Output**:
```python
class CandidateMatch(BaseModel):
    candidate_id: UUID
    overall_fit_score: float  # 0-100
    skills_match_pct: float  # 0-100
    location_match_pct: float  # 0-100
    experience_match_pct: float  # 0-100
    matched_skills: list[str]  # required skills the candidate has
    unmatched_required_skills: list[str]  # required skills missing
    matched_preferred_skills: list[str]  # preferred skills present

class MatchCandidatesResponse(BaseModel):
    success: bool
    data: list[CandidateMatch]  # sorted by overall_fit_score DESC
    total_candidates_evaluated: int
    ai_provider: str
    latency_ms: int

# Example request
request = MatchCandidatesRequest(
    job_requirements=JobRequirements(
        job_id=UUID("job-123"),
        required_skills=["Python", "FastAPI", "PostgreSQL"],
        preferred_skills=["Docker", "Kubernetes"],
        location="Bangalore",
        location_flexibility="preferred",
        min_experience_years=3,
        max_experience_years=8
    ),
    candidate_profiles=[
        CandidateProfile(
            candidate_id=UUID("cand-001"),
            skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
            location="Bangalore",
            experience_summary="Senior Backend Engineer, 5 years"
        ),
        CandidateProfile(
            candidate_id=UUID("cand-002"),
            skills=["Python", "Django", "MySQL"],
            location="Chennai",
            experience_summary="Backend Engineer, 2 years"
        )
    ],
    user_id=UUID("rec-user-001")
)

# Example response
{
    "success": True,
    "data": [
        {
            "candidate_id": "cand-001",
            "overall_fit_score": 92,
            "skills_match_pct": 100,
            "location_match_pct": 100,
            "experience_match_pct": 95,
            "matched_skills": ["Python", "FastAPI", "PostgreSQL"],
            "unmatched_required_skills": [],
            "matched_preferred_skills": ["Docker"]
        },
        {
            "candidate_id": "cand-002",
            "overall_fit_score": 38,
            "skills_match_pct": 33,
            "location_match_pct": 0,
            "experience_match_pct": 40,
            "matched_skills": ["Python"],
            "unmatched_required_skills": ["FastAPI", "PostgreSQL"],
            "matched_preferred_skills": []
        }
    ],
    "total_candidates_evaluated": 2,
    "ai_provider": "openai",
    "latency_ms": 1205
}
```

**Timeout**: 60 seconds (may evaluate up to 1000 candidates).

**Error cases**:

| Condition | Response |
|-----------|----------|
| Empty candidate list | Return `success = True`, `data = []` |
| job_requirements invalid (no required skills) | Return `success = False`, `error: "INVALID_JOB_REQUIREMENTS"` |
| API unavailable | Return `success = False`, `error: "SERVICE_UNAVAILABLE"` |
| Timeout after 60s | Return `success = False`, `error: "TIMEOUT"` |

**Behaviour**:
- Uses OpenAI embeddings API to generate vector embeddings for each required skill. Compares candidate skills to embeddings using cosine similarity to compute `skills_match_pct`.
- Location matching is rule-based: if `location_flexibility = "required"`, exact match earns 100%, no match earns 0%. If `"preferred"`, exact match earns 100%, no match earns 50% (partial credit). If `"flexible"`, all candidates get 100%.
- Experience matching: parses `experience_summary` text using regex heuristics to extract years of experience. If parsed years are within `[min_experience_years, max_experience_years]`, earns 100%. Penalizes linearly outside that range.
- `overall_fit_score` = weighted average: 50% skills, 25% location, 25% experience.
- Results are sorted by `overall_fit_score` descending.
- Logs call to `ai_request_log`.

---

### 3.3 generate_interview_questions

**Signature**:
```python
async def generate_interview_questions(
    job_description: str,
    required_skills: list[str],
    user_id: Optional[UUID] = None
) -> GenerateInterviewQuestionsResponse
```

**Input**:
```python
class GenerateInterviewQuestionsRequest(BaseModel):
    job_description: str  # full job description text
    required_skills: list[str]  # e.g., ['Python', 'FastAPI', 'PostgreSQL']
    user_id: Optional[UUID] = None
```

**Output**:
```python
class InterviewQuestion(BaseModel):
    category: str  # 'technical' | 'behavioural' | 'situational'
    question: str  # full question text
    follow_up: Optional[str] = None  # optional follow-up probe
    ideal_answer_traits: list[str]  # key things the answer should demonstrate

class GenerateInterviewQuestionsResponse(BaseModel):
    success: bool
    data: list[InterviewQuestion]  # 8-12 questions total
    total_questions: int
    questions_by_category: dict[str, int]  # {'technical': 4, 'behavioural': 4, 'situational': 3}
    ai_provider: str
    latency_ms: int

# Example request
request = GenerateInterviewQuestionsRequest(
    job_description="Senior Backend Engineer for high-scale transaction processing system...",
    required_skills=["Python", "FastAPI", "PostgreSQL"],
    user_id=UUID("rec-user-001")
)

# Example response
{
    "success": True,
    "data": [
        {
            "category": "technical",
            "question": "Walk us through your experience with PostgreSQL query optimization. What's the most complex query you've optimized and what was the outcome?",
            "follow_up": "What tools did you use to identify the bottleneck?",
            "ideal_answer_traits": [
                "Understanding of EXPLAIN plans",
                "Index optimization experience",
                "Ability to explain performance tradeoffs"
            ]
        },
        {
            "category": "behavioural",
            "question": "Tell us about a time when you had to refactor a critical piece of legacy code. How did you approach it and what was the result?",
            "follow_up": "How did you handle concerns from the team about introducing risk?",
            "ideal_answer_traits": [
                "Risk mitigation mindset",
                "Collaboration with stakeholders",
                "Testing discipline"
            ]
        }
    ],
    "total_questions": 10,
    "questions_by_category": {
        "technical": 4,
        "behavioural": 4,
        "situational": 2
    },
    "ai_provider": "anthropic",
    "latency_ms": 1832
}
```

**Timeout**: 15 seconds.

**Error cases**:

| Condition | Response |
|-----------|----------|
| job_description is empty | Return `success = False`, `error: "EMPTY_JOB_DESCRIPTION"` |
| required_skills is empty | Return `success = False`, `error: "EMPTY_REQUIRED_SKILLS"` |
| API unavailable | Fall back: if primary is Claude, try OpenAI. Log fallback. If both fail, return error. |
| Timeout after 15s | Return `success = False`, `error: "TIMEOUT"` |

**Behaviour**:
- Calls Claude API with a prompt that instructs it to generate 8-12 role-specific interview questions.
- Prompt specifies: 4 technical questions, 4 behavioural questions, and 2-4 situational questions.
- Each question should reference the specific job and required skills where relevant.
- Claude outputs structured JSON with `category`, `question`, optional `follow_up`, and `ideal_answer_traits`.
- If primary provider (Claude) is unavailable, falls back to OpenAI GPT-4 with equivalent prompt.
- Logs call to `ai_request_log` with provider and fallback info if applicable.

---

### 3.4 generate_interview_summary

**Signature**:
```python
async def generate_interview_summary(
    interview_notes: str,
    job_description: Optional[str] = None,
    candidate_name: Optional[str] = None,
    user_id: Optional[UUID] = None
) -> GenerateInterviewSummaryResponse
```

**Input**:
```python
class GenerateInterviewSummaryRequest(BaseModel):
    interview_notes: str  # raw recruiter notes from the interview
    job_description: Optional[str] = None  # context about the role
    candidate_name: Optional[str] = None  # candidate name for personalization
    user_id: Optional[UUID] = None
```

**Output**:
```python
class InterviewSummary(BaseModel):
    key_strengths: list[str]  # 3-5 clear strengths demonstrated
    concerns: list[str]  # 3-5 concerns or gaps (can be empty)
    overall_assessment: str  # 1-2 paragraph summary of interview
    recommendation: str  # 'strongly_recommend' | 'recommend' | 'neutral' | 'do_not_recommend'
    reasoning: str  # brief explanation of recommendation

class GenerateInterviewSummaryResponse(BaseModel):
    success: bool
    data: InterviewSummary
    ai_provider: str
    latency_ms: int

# Example request
request = GenerateInterviewSummaryRequest(
    interview_notes="Priya was very engaged. Strong technical depth in FastAPI and database design. Spoke about her recent project optimizing queries in PostgreSQL - reduced latency by 60%. Asked great questions about system architecture. Some concern about experience with large distributed systems - mentioned working on monolithic services mostly. Quiet in group discussions at times.",
    job_description="Senior Backend Engineer for a high-scale distributed transaction processing system.",
    candidate_name="Priya Kumar",
    user_id=UUID("rec-user-001")
)

# Example response
{
    "success": True,
    "data": {
        "key_strengths": [
            "Deep FastAPI and PostgreSQL expertise with measurable impact (60% latency reduction)",
            "Proactive learner who asks thoughtful technical questions",
            "Clear communication about her work and experience"
        ],
        "concerns": [
            "Limited experience with distributed systems at scale",
            "May need mentorship on cross-team communication and visibility"
        ],
        "overall_assessment": "Priya is a solid backend engineer with strong fundamentals and a track record of optimizing critical systems. Her FastAPI and database skills directly match the role. Her primary gap is distributed systems experience, but her learning mindset and technical depth suggest she can close that quickly with the right support.",
        "recommendation": "recommend",
        "reasoning": "Strong technical fit with growth potential. Lacks distributed systems experience but demonstrates the right mindset and fundamentals to succeed."
    },
    "ai_provider": "anthropic",
    "latency_ms": 1105
}
```

**Timeout**: 15 seconds.

**Error cases**:

| Condition | Response |
|-----------|----------|
| interview_notes is empty | Return `success = False`, `error: "EMPTY_INTERVIEW_NOTES"` |
| API unavailable | Fall back: if primary is Claude, try OpenAI. If both fail, return error. |
| Timeout after 15s | Return `success = False`, `error: "TIMEOUT"` |

**Behaviour**:
- Calls Claude API with a prompt that instructs it to synthesize raw interview notes into a structured summary.
- Prompt asks for 3-5 key strengths, 3-5 concerns (can be empty), a 1-2 paragraph overall assessment, a recommendation (one of four fixed values), and reasoning.
- The recommendation should be nuanced: "strongly_recommend" if exceptional fit, "recommend" if solid fit with minor gaps, "neutral" if mixed signals, "do_not_recommend" if significant mismatches.
- If Claude unavailable, falls back to OpenAI GPT-4.
- Logs call to `ai_request_log`.

---

### 3.5 smart_search

**Signature**:
```python
async def smart_search(
    query: str,
    candidate_count: int = 100,
    user_id: Optional[UUID] = None
) -> SmartSearchResponse
```

**Input**:
```python
class SmartSearchRequest(BaseModel):
    query: str  # natural language query, e.g., "Java developers in Bangalore with 5+ years experience"
    candidate_count: int = 100  # max number of candidates to return ranked results for
    user_id: Optional[UUID] = None
```

**Output**:
```python
class ScoredCandidateId(BaseModel):
    candidate_id: UUID
    relevance_score: float  # 0-100
    reasoning: str  # brief explanation of why this candidate matched

class SmartSearchResponse(BaseModel):
    success: bool
    data: list[ScoredCandidateId]  # sorted by relevance_score DESC
    total_results: int
    interpreted_intent: dict[str, any]  # parsed query intent
    ai_provider: str
    latency_ms: int

# Example request
request = SmartSearchRequest(
    query="Java developers in Bangalore with 5+ years experience",
    candidate_count=100,
    user_id=UUID("rec-user-001")
)

# Example response
{
    "success": True,
    "data": [
        {
            "candidate_id": "cand-123",
            "relevance_score": 95,
            "reasoning": "Java expert with 7 years experience, Bangalore location, strong backend framework knowledge"
        },
        {
            "candidate_id": "cand-456",
            "relevance_score": 78,
            "reasoning": "Java developer with 6 years experience, remote but open to relocation, some Bangalore connection"
        }
    ],
    "total_results": 2,
    "interpreted_intent": {
        "skills": ["Java"],
        "location": "Bangalore",
        "min_experience_years": 5
    },
    "ai_provider": "openai",
    "latency_ms": 980
}
```

**Timeout**: 10 seconds.

**Error cases**:

| Condition | Response |
|-----------|----------|
| query is empty | Return `success = False`, `error: "EMPTY_QUERY"` |
| API unavailable | Return `success = True`, `data = []`, `total_results = 0` (graceful degradation) |
| Timeout after 10s | Return `success = True`, `data = []`, `total_results = 0` |

**Behaviour**:
- Calls OpenAI with a prompt that asks the model to interpret the natural language query and extract: skills, location, experience range, and other filters.
- Returns the interpreted intent as structured JSON.
- Using the interpreted intent, queries the `candidates` table (via `candidate-management/` service) with filters for skills, location, and experience.
- Re-ranks results using embedding similarity: each candidate's skill set is embedded, compared to the query skills embedding using cosine similarity, and scored 0-100.
- Returns candidate IDs sorted by `relevance_score` descending.
- Logs call to `ai_request_log`.

---

## 4. Behaviour requirements

### parse_resume

- Given a valid S3 key pointing to a PDF or DOCX file, downloads the file, passes it to OpenAI GPT-4 with a structured prompt, receives JSON response, and returns a `ParseResumeResponse` with confidence scores per field.
- If any field cannot be extracted, that field is `None` and its confidence is 0.0. The overall `confidence_score` is the mean of all field confidences.
- Fields with confidence < 0.7 are listed in `low_confidence_fields` but are still included in the response data (not filtered out).
- If OpenAI is unavailable, automatically falls back to Claude API with the same prompt. Logs the fallback in `ai_request_log` with `fallback_provider='anthropic'`.
- If both OpenAI and Claude fail, returns a single `ParseResumeResponse` with `success=False` and error message.
- All calls are logged to `ai_request_log` with timestamp, provider, model, token counts (estimated if unavailable), latency in milliseconds, calculated cost, status ('success' | 'error' | 'timeout' | 'fallback'), error message (if applicable), and optional user_id and metadata.
- Timeout is 30 seconds. If no response is received by then, logs with `status='timeout'` and returns error response.

### match_candidates

- Given a job requirements object and a list of candidate profiles, calculates three match percentages: skills, location, experience.
- **Skills matching**: Uses OpenAI embeddings to compare each candidate's skill list to the required skills. Cosine similarity scores are normalized to 0-100. Accounts for both required and preferred skills.
- **Location matching**: If `location_flexibility='required'`, exact match (case-insensitive) = 100%, no match = 0%. If `'preferred'`, exact match = 100%, no match = 50%. If `'flexible'`, all candidates = 100%.
- **Experience matching**: Extracts years of experience from `experience_summary` text using regex (e.g., "5 years", "5-7 years"). If parsed years are within `[min, max]`, score is 100%. If below min, linear penalty (0% at min-3 years). If above max, linear penalty (0% at max+3 years).
- `overall_fit_score` = 0.50 * skills_match_pct + 0.25 * location_match_pct + 0.25 * experience_match_pct (weights as specified).
- Results are sorted by `overall_fit_score` descending. Results include matched and unmatched skills for transparency.
- Empty candidate list returns empty results (not an error).
- Logs all calls to `ai_request_log` including candidate count, latency, and cost.
- Timeout is 60 seconds.

### generate_interview_questions

- Given a job description and a list of required skills, calls Claude API with a structured prompt instructing it to generate 8-12 role-specific interview questions.
- Questions are categorized as 'technical', 'behavioural', or 'situational'. Target is 4 technical, 4 behavioural, 2-4 situational.
- Each question includes the question text, optional follow-up probe, and a list of 3-5 key traits an ideal answer should demonstrate.
- Claude is the primary provider. If Claude times out or is unavailable, falls back to OpenAI GPT-4 with an equivalent prompt.
- Response includes a count of questions by category for transparency.
- All calls are logged to `ai_request_log` with provider and fallback details.
- Timeout is 15 seconds.

### generate_interview_summary

- Given raw recruiter interview notes (free text), calls Claude API with a prompt asking it to synthesize a structured summary.
- Returns a `InterviewSummary` with: 3-5 key strengths (list), 3-5 concerns (list, can be empty), 1-2 paragraph overall assessment, and a single-value recommendation.
- The recommendation is one of: 'strongly_recommend', 'recommend', 'neutral', 'do_not_recommend'. The output must be one of these exact strings (validated in Pydantic model).
- Optional job_description and candidate_name are passed to the prompt for context and personalization.
- Claude is primary. Falls back to OpenAI if Claude unavailable.
- All calls logged to `ai_request_log`.
- Timeout is 15 seconds.

### smart_search

- Given a natural language query string, calls OpenAI with a prompt asking it to interpret the query and extract structured intent: skills (list), location (string), min_experience_years (int), max_experience_years (int), etc.
- Once intent is extracted, calls `candidate-management/` service's internal search function with the structured filters (not via the public API).
- Takes the returned candidate list and re-ranks using embedding similarity: embeds the query, embeds each candidate's skill list, compares using cosine similarity, and scores 0-100.
- Returns candidates sorted by relevance_score descending, up to `candidate_count` total.
- If the OpenAI API is unavailable, returns empty results (graceful degradation, logs the failure).
- If timeout occurs (10 seconds), returns empty results.
- Logs the call to `ai_request_log` with interpreted intent in metadata.

---

## 5. Acceptance criteria as tests

```python
# ai-services/tests/test_parse_resume.py

class TestParseResume:

    def test_valid_pdf_returns_parsed_data(self, client, s3_mock_pdf):
        """Given a valid PDF in S3, parse_resume() returns ParseResumeResponse
        with name, email, skills populated and confidence_score > 0.8."""

    def test_low_confidence_fields_flagged(self, client, s3_mock_pdf_ambiguous):
        """When parser returns confidence < 0.7 for 'phone', the response
        includes 'phone' in low_confidence_fields and phone is still populated."""

    def test_openai_fallback_to_claude(self, client, s3_mock_pdf, openai_unavailable, claude_available):
        """When OpenAI fails, parse_resume() falls back to Claude and logs
        status='fallback' with fallback_provider='anthropic'."""

    def test_both_providers_fail_returns_error(self, client, s3_mock_pdf, all_ai_unavailable):
        """When both OpenAI and Claude fail, returns ParseResumeResponse with
        success=False and error message."""

    def test_s3_key_not_found_returns_error(self, client):
        """parse_resume('invalid/s3/key') returns success=False with error='S3_NOT_FOUND'."""

    def test_timeout_after_30_seconds(self, client, s3_mock_pdf, ai_timeout):
        """When AI API does not respond within 30s, returns success=False
        with error='TIMEOUT' and logs status='timeout'."""

    def test_ai_request_log_entry_created(self, client, s3_mock_pdf, db):
        """After calling parse_resume(), ai_request_log has one row with
        function_name='parse_resume', provider set, status='success'."""

    def test_cost_estimate_calculated(self, client, s3_mock_pdf, db):
        """ai_request_log entry includes cost_estimate (decimal > 0) calculated
        from input/output token counts and pricing."""


# ai-services/tests/test_match_candidates.py

class TestMatchCandidates:

    def test_exact_skill_match_scores_100(self, client):
        """Candidate with all required skills scores 100% on skills_match_pct."""

    def test_partial_skill_match_scores_proportionally(self, client):
        """Candidate with 2 of 3 required skills scores ~67% on skills_match_pct."""

    def test_location_flexibility_required(self, client):
        """With location='Bangalore' and flexibility='required',
        candidate in Bangalore scores 100%, candidate in Chennai scores 0%."""

    def test_location_flexibility_preferred(self, client):
        """With flexibility='preferred', candidate in Bangalore scores 100%,
        candidate in Chennai scores 50%."""

    def test_location_flexibility_flexible(self, client):
        """With flexibility='flexible', all candidates score 100% on location."""

    def test_experience_within_range(self, client):
        """Candidate with 5 years experience, min=3 max=8, scores 100%."""

    def test_experience_below_range_penalized(self, client):
        """Candidate with 1 year experience, min=3, scores < 50%."""

    def test_overall_score_is_weighted_average(self, client):
        """overall_fit_score = 0.5*skills + 0.25*location + 0.25*experience."""

    def test_results_sorted_by_overall_score(self, client):
        """Return list is sorted by overall_fit_score DESC."""

    def test_matched_unmatched_skills_listed(self, client):
        """Response includes matched_skills and unmatched_required_skills arrays."""

    def test_empty_candidate_list_returns_empty(self, client):
        """match_candidates with empty candidate_profiles returns success=True, data=[]."""

    def test_invalid_job_requirements_returns_error(self, client):
        """match_candidates with required_skills=[] returns success=False, error='INVALID_JOB_REQUIREMENTS'."""


# ai-services/tests/test_generate_interview_questions.py

class TestGenerateInterviewQuestions:

    def test_generates_8_to_12_questions(self, client):
        """generate_interview_questions() returns 8-12 InterviewQuestion objects."""

    def test_categories_distributed(self, client):
        """Response includes ~4 technical, ~4 behavioural, ~2 situational questions."""

    def test_each_question_has_follow_up(self, client):
        """Each InterviewQuestion has follow_up populated or None."""

    def test_ideal_answer_traits_populated(self, client):
        """Each question includes 3-5 ideal_answer_traits as a list."""

    def test_questions_reference_job_and_skills(self, client):
        """Generated questions mention specific skills from required_skills list."""

    def test_claude_api_called_as_primary(self, client, claude_api_spy):
        """Verify that Claude API is called first for this function."""

    def test_fallback_to_openai_on_claude_failure(self, client, claude_unavailable, openai_available):
        """When Claude fails, falls back to OpenAI and logs fallback."""

    def test_timeout_after_15_seconds(self, client, ai_timeout):
        """When AI does not respond within 15s, returns success=False, error='TIMEOUT'."""

    def test_empty_job_description_returns_error(self, client):
        """generate_interview_questions('', ['Python']) returns success=False."""

    def test_empty_required_skills_returns_error(self, client):
        """generate_interview_questions('Valid job...', []) returns success=False."""


# ai-services/tests/test_generate_interview_summary.py

class TestGenerateInterviewSummary:

    def test_returns_structured_summary(self, client):
        """generate_interview_summary() returns InterviewSummary with all fields populated."""

    def test_strengths_and_concerns_as_lists(self, client):
        """key_strengths and concerns are lists of strings (can be empty for concerns)."""

    def test_overall_assessment_is_paragraph(self, client):
        """overall_assessment is 1-2 sentences, coherent synthesis of notes."""

    def test_recommendation_is_valid_enum(self, client):
        """recommendation is one of: 'strongly_recommend', 'recommend', 'neutral', 'do_not_recommend'."""

    def test_reasoning_provided(self, client):
        """reasoning field explains the recommendation."""

    def test_empty_interview_notes_returns_error(self, client):
        """generate_interview_summary('', ...) returns success=False."""

    def test_candidate_name_used_in_response(self, client):
        """If candidate_name is provided, it may appear in overall_assessment."""

    def test_job_description_provides_context(self, client):
        """If job_description is provided, questions are tailored to that role."""

    def test_claude_api_called_as_primary(self, client, claude_api_spy):
        """Verify Claude API is called first."""

    def test_timeout_after_15_seconds(self, client, ai_timeout):
        """When AI does not respond within 15s, returns success=False."""


# ai-services/tests/test_smart_search.py

class TestSmartSearch:

    def test_parses_natural_language_query(self, client):
        """Given 'Java developers in Bangalore with 5+ years', extracts
        interpreted_intent with skills=['Java'], location='Bangalore', min_experience_years=5."""

    def test_returns_ranked_candidates(self, client, candidates_in_db):
        """Returns list of ScoredCandidateId sorted by relevance_score DESC."""

    def test_relevance_score_0_to_100(self, client):
        """All relevance_score values are between 0 and 100."""

    def test_respects_candidate_count_limit(self, client):
        """Passing candidate_count=10 returns at most 10 candidates."""

    def test_api_unavailable_returns_empty(self, client, openai_unavailable):
        """When OpenAI fails, returns success=True, data=[], total_results=0 (graceful)."""

    def test_timeout_returns_empty(self, client, ai_timeout):
        """When timeout occurs after 10s, returns success=True, data=[], total_results=0."""

    def test_empty_query_returns_error(self, client):
        """smart_search('', ...) returns success=False."""

    def test_interpreted_intent_in_response(self, client):
        """Response includes interpreted_intent with parsed skills, location, etc."""

    def test_reasoning_provided_per_candidate(self, client):
        """Each ScoredCandidateId includes reasoning explaining the match."""


# ai-services/tests/test_ai_request_logging.py

class TestAIRequestLogging:

    def test_log_entry_created_per_call(self, client, db):
        """Each AI function call creates one ai_request_log entry."""

    def test_log_includes_function_name(self, client, db):
        """Log entry includes function_name matching the function called."""

    def test_log_includes_provider_and_model(self, client, db):
        """Log entry includes provider ('openai' | 'anthropic') and model name."""

    def test_log_includes_token_counts(self, client, db):
        """Log entry includes input_tokens and output_tokens."""

    def test_log_includes_latency_ms(self, client, db):
        """Log entry includes latency_ms (integer milliseconds)."""

    def test_cost_estimate_calculated(self, client, db):
        """Log entry includes cost_estimate (decimal) calculated from tokens and pricing."""

    def test_log_status_success_on_success(self, client, db):
        """When function succeeds, log status='success' and error_message=NULL."""

    def test_log_status_error_on_failure(self, client, db):
        """When function fails, log status='error' and error_message populated."""

    def test_log_status_timeout(self, client, db):
        """When timeout occurs, log status='timeout'."""

    def test_log_fallback_provider_recorded(self, client, db):
        """When fallback occurs, fallback_provider is populated in log."""

    def test_log_metadata_optional(self, client, db):
        """metadata field is optional JSON, populated with context like job_id, candidate_id."""

    def test_log_user_id_optional(self, client, db):
        """user_id field captures the recruiter/system user making the request."""
```

---

## 6. Internal module structure

```
ai-services/
├── api.py                  # Public function interface (imported by other services)
├── service.py              # Business logic layer (calling external AI APIs)
├── models.py               # SQLAlchemy ORM models (ai_request_log)
├── schemas.py              # Pydantic request/response schemas
├── exceptions.py           # Service-specific exception classes
├── constants.py            # Enums, valid values, AI prompts, config
├── utils.py                # Helper functions (embeddings, text extraction, cost calculation)
├── providers.py            # Provider-specific integrations (OpenAI, Claude clients)
├── schema.sql              # Database migration source
├── tests/
│   ├── conftest.py         # Fixtures (test DB, mock AI APIs, tokens)
│   ├── test_parse_resume.py
│   ├── test_match_candidates.py
│   ├── test_generate_interview_questions.py
│   ├── test_generate_interview_summary.py
│   ├── test_smart_search.py
│   └── test_ai_request_logging.py
└── README.md               # Developer onboarding for this service
```

Only `api.py` and `schemas.py` are importable by other services. Everything else is internal.

**Key files**:

- `constants.py`: Houses versioned prompt templates for each AI function, pricing constants (OpenAI $/1K tokens, Claude $/1K tokens), and model names. Prompts are defined as multi-line strings with placeholders for job description, required skills, etc.
- `providers.py`: Wraps OpenAI and Claude SDK clients. Handles rate limiting, retries, token estimation, and fallover logic.
- `utils.py`: Heuristics for extracting years of experience from text, embeddings caching, cost calculation.

---

## 7. Dependencies and constraints

**External service dependencies**:

- `candidate-management/` (internal only): `smart_search` function calls `candidate-management/` to fetch candidate profiles after interpreting the query intent. Uses direct Python function import, not HTTP.

**External API dependencies**:

- OpenAI GPT-4 API: For resume parsing, interview question generation (fallback), candidate search interpretation.
- OpenAI Embeddings API: For candidate-job matching (skill similarity).
- Anthropic Claude API: For interview question generation (primary), interview summary generation (primary), and resume parsing (fallback).

**Internal database dependencies**:

- PostgreSQL 15+: Primary data store for `ai_request_log`.
- Redis: Optional. May be used for caching embeddings or API responses to reduce redundant calls.

**Performance targets**:

| Operation | Target | Measured at |
|-----------|--------|-------------|
| parse_resume | < 30s | End-to-end including AI round-trip |
| match_candidates (1000 candidates) | < 60s | End-to-end including embeddings and scoring |
| generate_interview_questions | < 15s | AI round-trip |
| generate_interview_summary | < 15s | AI round-trip |
| smart_search | < 10s | Including AI interpretation and DB query |

**Security & compliance**:

- All AI API calls use authenticated requests (API keys stored in environment variables, never hardcoded).
- `ai_request_log` table records all API calls for cost tracking, audit, and debugging. Logs do not store prompt text or response content (only token counts and status).
- Candidate and job data passed to AI APIs is never stored externally. Data flows in and out within the same request context.
- Rate limiting: Respect provider rate limits (OpenAI: 500 RPM for GPT-4, Claude: 500 RPM). Queue requests via Redis + Celery if burst exceeds limits.

**Cost constraints**:

- Cost tracking is mandatory. Every API call logs estimated cost based on token counts.
- Monthly cost reports can be generated by querying `ai_request_log`.
- Alert threshold: If monthly cost exceeds 10x baseline, an investigation is triggered.

---

## 8. Out of scope

- Streaming responses: All functions return complete responses synchronously. Streaming is Phase 2.
- Custom AI model fine-tuning: Phase 2. Current implementation uses OpenAI and Claude off-the-shelf models.
- Vector database (Pinecone, Weaviate, etc.) for embeddings: Phase 2. Current implementation uses stateless OpenAI embeddings API calls.
- Caching layer for embeddings or summaries: Phase 1 uses no caching. Phase 2 may introduce Redis caching for embeddings.
- Multi-language support: Phase 1 assumes English. Phase 2+ adds language detection and translation.
- Interview question persistence: This service generates questions on demand. `job-management/` stores generated questions if needed.
- Candidate-facing AI features: Current scope is recruiter-facing. Candidate-facing AI (resume tips, interview prep) is Phase 2+.

---

## 9. Verification

```bash
cd ai-services/
pytest tests/ -v --tb=short
```

All tests must pass. Additionally, verify these end-to-end scenarios manually or via integration tests:

1. Call `parse_resume()` with a valid S3 PDF key. Confirm structured data is returned with confidence scores and `low_confidence_fields` populated correctly.
2. Simulate OpenAI unavailability. Confirm `parse_resume()` falls back to Claude and logs the fallback.
3. Call `match_candidates()` with a list of 10 candidates and job requirements. Confirm candidates are ranked by overall_fit_score and breakdown shows skills/location/experience percentages.
4. Call `generate_interview_questions()` for a Backend Engineer role. Confirm 8-12 questions are returned with technical/behavioural/situational categories balanced.
5. Call `generate_interview_summary()` with raw interview notes. Confirm structured summary with strengths, concerns, and a recommendation are returned.
6. Call `smart_search()` with natural language query 'Python developers in Bangalore'. Confirm interpreted_intent is parsed correctly and candidates are ranked by relevance.
7. Verify `ai_request_log` has entries for all 6 calls above with provider, model, token counts, latency, cost, and status recorded.
8. Calculate total monthly cost from `ai_request_log` for the last 30 days. Confirm it matches expected usage.
9. Simulate timeout for `match_candidates()` (e.g., with 10,000 candidates). Confirm timeout is logged with `status='timeout'` after 60 seconds.
10. Test provider fallover: Disable OpenAI. Confirm `parse_resume()` succeeds using Claude fallback. Re-enable OpenAI.
```

---
