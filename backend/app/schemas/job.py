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


class JobMatchCategoryScores(BaseModel):
    required_skills: int
    preferred_skills: int
    experience: int
    title: int
    education: int


class JobMatchEntry(BaseModel):
    rank: int
    candidate_id: UUID
    candidate_name: str | None = None
    fit_score: int
    category_scores: JobMatchCategoryScores
    already_submitted: bool
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    recommendation: str = "Weak Match"
    confidence_score: float = 0.0


class JobMatchTriggerRequest(BaseModel):
    refresh: bool = False


class JobMatchTriggerResponse(BaseModel):
    job_id: UUID
    match_count: int
    generated_at: datetime
    refresh_requested: bool


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
    category_scores: JobMatchCategoryScores
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    recommendation: str = "Weak Match"
    confidence_score: float = 0.0


class CandidateMatchesResponse(BaseModel):
    candidate_id: UUID
    matches: list[CandidateMatchEntry]
    total_count: int
    limit: int
    offset: int


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
