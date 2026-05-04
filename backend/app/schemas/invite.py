from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class InviteCreate(BaseModel):
    email: EmailStr
    # organization_roles.key (system or custom) for the target org
    role: str = Field(default="recruiter", min_length=1, max_length=64)
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


class InviteListItem(BaseModel):
    id: str
    email: str
    role: str
    status: str
    created_at: datetime
    expires_at: datetime


class InviteResendResponse(BaseModel):
    message: str


class InviteAcceptRequest(BaseModel):
    token: str = Field(min_length=8, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class InviteAcceptResponse(BaseModel):
    message: str
