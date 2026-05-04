from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ApplicationCreate(BaseModel):
    candidate_id: UUID
    job_id: UUID

    model_config = ConfigDict(extra="forbid")


class ApplicationUpdate(BaseModel):
    stage: str | None = Field(default=None, max_length=80)
    status: str | None = Field(default=None, max_length=32)
    notes: str | None = None

    model_config = ConfigDict(extra="forbid")


class ApplicationResponse(BaseModel):
    id: UUID
    organization_id: UUID
    candidate_id: UUID
    job_id: UUID
    stage: str
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
