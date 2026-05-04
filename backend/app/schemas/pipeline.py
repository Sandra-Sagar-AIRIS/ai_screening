from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class PipelineStage(StrEnum):
    APPLIED = "applied"
    SCREENING = "screening"
    INTERVIEW = "interview"
    OFFER = "offer"
    PLACED = "placed"
    REJECTED = "rejected"


class PipelineStatus(StrEnum):
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    WITHDRAWN = "withdrawn"
    CLOSED = "closed"


class PipelineCreate(BaseModel):
    candidate_id: UUID
    job_id: UUID
    stage: PipelineStage = PipelineStage.APPLIED
    status: PipelineStatus = PipelineStatus.ACTIVE
    notes: str | None = None

    @field_validator("stage", mode="before")
    @classmethod
    def normalize_stage(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class PipelineUpdate(BaseModel):
    stage: PipelineStage | None = None
    status: PipelineStatus | None = None
    notes: str | None = None

    @field_validator("stage", mode="before")
    @classmethod
    def normalize_stage(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class PipelineResponse(BaseModel):
    id: UUID
    organization_id: UUID
    candidate_id: UUID
    job_id: UUID
    stage: PipelineStage
    status: PipelineStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
