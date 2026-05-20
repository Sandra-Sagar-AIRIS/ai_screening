from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ── Enumerations ──────────────────────────────────────────────────────────────

class OfferResponse(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    NEGOTIATING = "negotiating"


class OfferEventType(StrEnum):
    OFFER_CREATED = "offer_created"
    OFFER_REVISED = "offer_revised"
    RESPONSE_UPDATED = "response_updated"
    EXPIRY_ALERT_SENT = "expiry_alert_sent"
    OFFER_EXPIRED = "offer_expired"


# ── Request schemas ───────────────────────────────────────────────────────────

class OfferCreate(BaseModel):
    """Payload to capture offer details when a candidate reaches the Offer stage."""

    offered_salary: Decimal = Field(..., gt=0, description="Salary in the given currency.")
    currency: str = Field(..., min_length=3, max_length=3, description="ISO 4217 code, e.g. USD.")
    offer_date: date = Field(..., description="Date the offer was made.")
    expiry_date: date = Field(..., description="Date by which the candidate must respond.")
    notes: str | None = Field(default=None, description="Optional internal notes.")

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @model_validator(mode="after")
    def validate_dates(self) -> "OfferCreate":
        if self.expiry_date < self.offer_date:
            raise ValueError("expiry_date must be on or after offer_date.")
        return self


class OfferRevise(BaseModel):
    """Partial update while the offer is in 'negotiating' state."""

    offered_salary: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    expiry_date: date | None = None
    notes: str | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value


class OfferRespondRequest(BaseModel):
    """Submit candidate response to an outstanding offer."""

    response: OfferResponse

    # Required when response == declined.
    decline_reason: str | None = Field(
        default=None,
        description="Mandatory reason when declining (≥ 10 characters).",
    )

    # When declined: move to 'rejected' (default) or the stored previous_stage.
    revert_to_previous_stage: bool = Field(
        default=False,
        description=(
            "If True and response=declined, revert to the stage before the offer "
            "instead of moving to 'rejected'."
        ),
    )

    @model_validator(mode="after")
    def validate_decline_reason(self) -> "OfferRespondRequest":
        if self.response == OfferResponse.DECLINED:
            if not self.decline_reason or len(self.decline_reason.strip()) < 10:
                raise ValueError(
                    "A decline reason of at least 10 characters is required when declining."
                )
        return self


# ── Response schemas ──────────────────────────────────────────────────────────

class OfferResponse_(BaseModel):
    """Full offer record returned to clients. (Named with trailing _ to avoid clash with StrEnum.)"""

    id: UUID
    organization_id: UUID
    pipeline_id: UUID
    candidate_id: UUID
    job_id: UUID

    offered_salary: Decimal
    currency: str
    offer_date: date
    expiry_date: date

    offer_response: OfferResponse
    decline_reason: str | None
    previous_stage: str | None

    expiry_alert_sent: bool
    notes: str | None

    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    # Computed helpers (not in DB — set by service layer before serialization).
    days_until_expiry: int | None = None
    is_expired: bool = False

    model_config = ConfigDict(from_attributes=True)


class OfferEventResponse(BaseModel):
    """One row in the offer event audit log."""

    id: UUID
    organization_id: UUID
    pipeline_id: UUID
    offer_id: UUID
    event_type: OfferEventType
    actor_user_id: UUID | None
    previous_response: str | None
    new_response: str | None
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
