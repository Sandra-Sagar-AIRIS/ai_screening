from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class CommunicationConnectionStatus(BaseModel):
    id: UUID
    provider: str
    channel: str
    external_account_email: str | None = None
    status: str
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommunicationConnectRequest(BaseModel):
    provider: str = Field(pattern="^(gmail|outlook)$")


class CommunicationConnectResponse(BaseModel):
    provider: str
    authorization_url: str
    state: str


class CommunicationDisconnectRequest(BaseModel):
    provider: str = Field(pattern="^(gmail|outlook)$")


class CommunicationTemplateCreate(BaseModel):
    channel: str = Field(default="email", pattern="^(email|whatsapp)$")
    provider: str | None = Field(default=None, pattern="^(gmail|outlook|whatsapp)$")
    name: str = Field(min_length=2, max_length=140)
    category: str | None = Field(default=None, max_length=80)
    subject_template: str | None = Field(default=None, max_length=255)
    body_template: str = Field(min_length=1)


class CommunicationTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=140)
    category: str | None = Field(default=None, max_length=80)
    subject_template: str | None = Field(default=None, max_length=255)
    body_template: str | None = Field(default=None, min_length=1)
    is_deleted: bool | None = None


class CommunicationTemplateResponse(BaseModel):
    id: UUID
    channel: str
    provider: str | None = None
    name: str
    category: str | None = None
    subject_template: str | None = None
    body_template: str
    placeholders: list[str] = Field(default_factory=list)
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommunicationTemplateRenderRequest(BaseModel):
    template_id: UUID
    values: dict[str, Any] = Field(default_factory=dict)


class CommunicationTemplateRenderResponse(BaseModel):
    subject: str | None = None
    body: str
    unresolved_placeholders: list[str] = Field(default_factory=list)


class CommunicationSendRequest(BaseModel):
    provider: str = Field(pattern="^(gmail|outlook)$")
    to_email: EmailStr
    subject: str | None = None
    body: str | None = None
    save_as_draft: bool = False
    quick_action: str | None = Field(default=None, max_length=80)
    attachments: list[dict[str, str]] = Field(default_factory=list)
    template_id: UUID | None = None
    template_values: dict[str, Any] | None = None
    idempotency_key: str | None = Field(default=None, min_length=6, max_length=120)

    @model_validator(mode="after")
    def validate_mode(self) -> "CommunicationSendRequest":
        raw_mode = self.body is not None
        template_mode = self.template_id is not None
        if raw_mode == template_mode:
            raise ValueError("Provide either raw body content or template_id, but not both.")
        if raw_mode and not self.subject and not self.save_as_draft:
            raise ValueError("Subject is required for raw send mode.")
        return self


class CommunicationMessageResponse(BaseModel):
    id: UUID
    candidate_id: UUID
    channel: str
    provider: str
    direction: str
    status: str
    to_address: str | None = None
    from_address: str | None = None
    subject: str | None = None
    body: str | None = None
    attachments: list[dict[str, str]] = Field(default_factory=list)
    provider_message_id: str | None = None
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("attachments", mode="before")
    @classmethod
    def normalize_attachments(cls, value: Any) -> list[dict[str, str]]:
        return value or []

    model_config = ConfigDict(from_attributes=True)


class CommunicationWhatsAppSendRequest(BaseModel):
    to_phone: str = Field(min_length=7, max_length=40)
    body: str | None = None
    template_id: UUID | None = None
    template_values: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=6, max_length=120)
    quick_action: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def validate_mode(self) -> "CommunicationWhatsAppSendRequest":
        if not self.body and not self.template_id:
            raise ValueError("Provide body or template_id.")
        return self


class CommunicationReminderCreate(BaseModel):
    channel: str = Field(pattern="^(email|whatsapp)$")
    provider: str = Field(pattern="^(gmail|outlook|whatsapp)$")
    to_address: str = Field(min_length=3, max_length=320)
    template_id: UUID | None = None
    template_values: dict[str, Any] = Field(default_factory=dict)
    subject: str | None = Field(default=None, max_length=255)
    body: str | None = None
    scheduled_for: datetime


class CommunicationReminderResponse(BaseModel):
    id: UUID
    candidate_id: UUID
    channel: str
    provider: str
    to_address: str | None = None
    subject: str | None = None
    body: str | None = None
    status: str
    failure_reason: str | None = None
    scheduled_for: datetime
    processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
