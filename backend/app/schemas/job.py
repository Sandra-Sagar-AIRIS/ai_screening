from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JobParseResponse(BaseModel):
    """Response model for POST /jobs/parse-jd — fields extracted by Groq from a JD."""
    title: str | None = None
    location: str | None = None
    employment_type: str | None = None
    experience_min_years: int | None = None
    experience_max_years: int | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = "USD"
    urgency: str = "normal"
    description: str | None = None
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    key_responsibilities: list[str] = []
    # The raw source text (from paste or extracted from PDF) stored for "Raw JD" view.
    raw_jd_text: str | None = None



class JobStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"
    FILLED = "filled"


class JobSubmissionStatus(StrEnum):
    PENDING = "pending"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"
    INTERVIEWING = "interviewing"
    OFFERED = "offered"
    HIRED = "hired"


class JobCreate(BaseModel):
    client_id: UUID | str
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: JobStatus = JobStatus.OPEN

    # Optional Phase 1 fields (kept optional so current frontend payloads work).
    location: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = "USD"
    experience_min_years: int | None = None
    experience_max_years: int | None = None
    employment_type: str | None = None
    urgency: str | None = "standard"

    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    key_responsibilities: list[str] | None = None

    # Parsing metadata
    raw_jd_text: str | None = None
    parsing_source: str | None = None
    parsing_status: str | None = None


class JobUpdate(BaseModel):
    client_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: JobStatus | None = None

    # Optional Phase 1 fields.
    location: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    experience_min_years: int | None = None
    experience_max_years: int | None = None
    employment_type: str | None = None
    urgency: str | None = None

    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    key_responsibilities: list[str] | None = None

    raw_jd_text: str | None = None
    parsing_source: str | None = None
    parsing_status: str | None = None


class JobStatusTransition(BaseModel):
    status: JobStatus
    reason: str | None = None


class JobSubmissionCreate(BaseModel):
    candidate_id: UUID
    notes: str | None = None


class JobSubmissionStatusUpdate(BaseModel):
    """Payload for PATCH /jobs/{job_id}/submissions/{submission_id} (Task 7)."""
    status: JobSubmissionStatus


class JobSubmissionResponse(BaseModel):
    id: UUID
    job_id: UUID
    candidate_id: UUID
    submission_status: JobSubmissionStatus
    submitted_at: datetime
    submitted_by: UUID
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class HybridScoreBreakdown(BaseModel):
    """Persisted under category_scores.hybrid JSON (deterministic + semantic blend)."""

    model_config = ConfigDict(extra="ignore")

    deterministic_score: int | float | None = None
    semantic_score: int | float | None = None
    final_score: int | float | None = None
    weights: dict[str, float] | None = None


class JobMatchCategoryScores(BaseModel):
    required_skills: int
    preferred_skills: int
    experience: int
    title: int
    education: int
    hybrid: HybridScoreBreakdown | None = None


class JobMatchEntry(BaseModel):
    """fit_score is hybrid (70% deterministic + 30% semantic when AI succeeds)."""

    rank: int
    candidate_id: UUID
    candidate_name: str | None = None
    fit_score: int
    deterministic_match_score: int | None = None
    semantic_match_score: int | None = None
    ai_enrichment_status: str | None = None
    ats_pipeline_status: str | None = None
    enrichment_started_at: datetime | None = None
    deterministic_completed_at: datetime | None = None
    semantic_completed_at: datetime | None = None
    enrichment_error: str | None = None
    recruiter_summary: str | None = None
    confidence_reasoning: str | None = None
    semantic_skill_matches: list[str] = Field(default_factory=list)
    transferable_skills: list[str] = Field(default_factory=list)
    inferred_strengths: list[str] = Field(default_factory=list)
    inferred_gaps: list[str] = Field(default_factory=list)
    category_scores: JobMatchCategoryScores
    already_submitted: bool
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    recommendation: str = "Weak Match"
    confidence_score: float = 0.0
    evaluated_at: datetime | None = None


class JobMatchTriggerRequest(BaseModel):
    refresh: bool = False


class JobMatchTriggerResponse(BaseModel):
    job_id: UUID
    match_count: int
    generated_at: datetime
    refresh_requested: bool
    semantic_enrichment: str | None = None
    """queued | disabled | none — background semantic pipeline after fast deterministic write."""


class AtsCandidateRescoreResponse(BaseModel):
    status: str
    candidate_id: UUID
    pairs_scored: int
    semantic_enrichment: str
    """queued | disabled | none | inline_full (sync=true full pipeline)."""

    mode: str = "fast"
    """fast (deterministic + async semantic) or full_sync."""


class AtsPairStatusResponse(BaseModel):
    candidate_id: UUID
    job_id: UUID
    processing_state: str
    progress: int = 0
    last_updated: datetime | None = None
    deterministic_score: int | None = None
    semantic_score: int | None = None
    final_score: int | None = None
    semantic_completion_status: str | None = None
    enrichment_error: str | None = None
    enqueue_delay_ms: int | None = None


class JobMatchesResponse(BaseModel):
    job_id: UUID
    matches: list[JobMatchEntry]
    total_count: int
    generated_at: datetime
    limit: int
    offset: int


class CandidateMatchEntry(BaseModel):
    job_id: UUID
    fit_score: int
    deterministic_match_score: int | None = None
    semantic_match_score: int | None = None
    ai_enrichment_status: str | None = None
    ats_pipeline_status: str | None = None
    enrichment_started_at: datetime | None = None
    deterministic_completed_at: datetime | None = None
    semantic_completed_at: datetime | None = None
    enrichment_error: str | None = None
    recruiter_summary: str | None = None
    confidence_reasoning: str | None = None
    semantic_skill_matches: list[str] = Field(default_factory=list)
    transferable_skills: list[str] = Field(default_factory=list)
    inferred_strengths: list[str] = Field(default_factory=list)
    inferred_gaps: list[str] = Field(default_factory=list)
    category_scores: JobMatchCategoryScores
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    recommendation: str = "Weak Match"
    confidence_score: float = 0.0
    evaluated_at: datetime | None = None


class CandidateMatchesResponse(BaseModel):
    candidate_id: UUID
    matches: list[CandidateMatchEntry]
    total_count: int
    limit: int
    offset: int
    pipeline_job_count: int = 0
    """Number of pipeline rows for this candidate in the org (applied jobs)."""

    ats_hint: str | None = None
    """UI hint when matches are empty: NO_PIPELINE_JOBS | NO_SCORE_ROWS_YET."""


class JobResponse(BaseModel):
    """Full job representation returned by GET /jobs and GET /jobs/{id}."""

    id: UUID
    organization_id: UUID
    client_id: UUID | None = None
    title: str
    description: str | None
    status: JobStatus
    paused_reason: str | None = None

    # Rich spec fields (Task 1 – previously missing from API response).
    location: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    experience_min_years: int | None = None
    experience_max_years: int | None = None
    employment_type: str | None = None
    urgency: str | None = None
    created_by: UUID | None = None
    filled_at: datetime | None = None

    # Embedded skills from job_skills table (Task 4 – pre-fills edit form).
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    key_responsibilities: list[str] = Field(default_factory=list)

    # Parsing metadata
    raw_jd_text: str | None = None
    parsing_source: str | None = None
    parsing_status: str | None = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
