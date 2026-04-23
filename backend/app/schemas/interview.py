from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InterviewStatus(StrEnum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"


class InterviewCreate(BaseModel):
    pipeline_id: UUID
    scheduled_at: datetime = Field(
        description="Interview start time in ISO 8601; normalized to UTC for storage.",
    )
    status: InterviewStatus = InterviewStatus.SCHEDULED
    interviewer_name: str | None = Field(default=None, max_length=255)
    notes: str | None = None

    @field_validator("scheduled_at")
    @classmethod
    def scheduled_at_to_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)


class InterviewUpdate(BaseModel):
    pipeline_id: UUID | None = None
    scheduled_at: datetime | None = Field(
        default=None,
        description="If set, normalized to UTC; must not be in the past.",
    )
    status: InterviewStatus | None = None
    interviewer_name: str | None = Field(default=None, max_length=255)
    notes: str | None = None

    @field_validator("scheduled_at")
    @classmethod
    def scheduled_at_to_utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)


class InterviewResponse(BaseModel):
    id: UUID
    organization_id: UUID
    pipeline_id: UUID
    scheduled_at: datetime
    status: InterviewStatus
    interviewer_name: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
