from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    FILLED = "filled"


class JobCreate(BaseModel):
    client_id: UUID
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: JobStatus = JobStatus.DRAFT


class JobUpdate(BaseModel):
    client_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: JobStatus | None = None


class JobResponse(BaseModel):
    id: UUID
    organization_id: UUID
    client_id: UUID
    title: str
    description: str | None
    status: JobStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
