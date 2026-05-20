"""Pydantic schemas for AI sourcing endpoints."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Request schemas ───────────────────────────────────────────────────────────


class StartSourcingSessionRequest(BaseModel):
    job_id: UUID | None = None
    jd_text: str = Field(..., min_length=20, max_length=20000)
    providers: list[str] = Field(default_factory=lambda: ["airis", "naukri_stub"])
    overrides: dict = Field(default_factory=dict)


class UpdateResultActionRequest(BaseModel):
    action: str = Field(..., pattern="^(shortlisted|rejected|imported)$")
    reject_reason: str | None = None
    pipeline_stage_id: UUID | None = None


# ── Response schemas ──────────────────────────────────────────────────────────


class StartSourcingSessionResponse(BaseModel):
    session_id: UUID


class SourcingSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    job_id: UUID | None
    created_by: UUID | None
    status: str
    providers_used: list[str] | None
    total_results: int
    error_detail: str | None
    created_at: datetime
    updated_at: datetime


class SourcingSessionStatusOut(BaseModel):
    session_id: UUID
    status: str
    total_results: int


class SourcingResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    source: str
    external_id: str | None
    first_name: str | None
    last_name: str | None
    email: str | None
    phone: str | None
    location: str | None
    title: str | None
    skills: list[str] | None
    ats_score: float | None
    ats_tier: str | None
    semantic_score: float | None
    recruiter_summary: str | None
    matched_skills: list[str] | None
    action: str
    reject_reason: str | None
    candidate_id: UUID | None
    is_duplicate: bool
    created_at: datetime


class PaginatedSourcingResults(BaseModel):
    items: list[SourcingResultOut]
    total: int
    page: int
    page_size: int
    has_more: bool
