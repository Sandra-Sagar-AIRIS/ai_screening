from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

InviteRole = Literal["admin", "recruiter", "client_viewer"]


class InviteCreate(BaseModel):
    email: EmailStr
    role: InviteRole = "recruiter"
    expires_in_days: int = Field(default=7, ge=1, le=30)


class InviteResponse(BaseModel):
    id: str
    email: str
    organization_id: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime


class InviteCreateResponse(BaseModel):
    message: str
    invite: InviteResponse
    token: str


class InviteAcceptRequest(BaseModel):
    token: str = Field(min_length=8, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class InviteAcceptResponse(BaseModel):
    message: str
