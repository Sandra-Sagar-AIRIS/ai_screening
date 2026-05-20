from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PipelineOffer(Base):
    """
    PIPE-008: Offer record attached to a pipeline.

    One active offer per pipeline at any time.  Previous offers are kept for
    history; the most recent row (ordered by created_at desc) is the active one.
    """

    __tablename__ = "pipeline_offers"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )

    # ── Org scoping ──────────────────────────────────────────────────────────
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )

    # ── Pipeline reference ───────────────────────────────────────────────────
    pipeline_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pipelines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Denormalized for fast queries (avoids a join to pipelines on every list).
    candidate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)

    # ── Offer details (AC: offered_salary, offer_date, expiry_date, currency) ─
    offered_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="USD")
    offer_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)

    # ── Candidate response (AC: accepted / declined / negotiating) ───────────
    offer_response: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    # Required when offer_response == "declined".
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Stage pipeline was in immediately before moving to "offer" — stored so
    # we can optionally revert to it on decline (default is to reject).
    previous_stage: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # ── Expiry tracking ──────────────────────────────────────────────────────
    expiry_alert_sent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.text("false")
    )

    # ── Free-text notes (for negotiation revisions, internal remarks) ────────
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Audit ────────────────────────────────────────────────────────────────
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=sa.text("now()"),
    )


class PipelineOfferEvent(Base):
    """
    PIPE-008: Immutable audit log — one row per offer lifecycle event.

    Events: offer_created | offer_revised | response_updated | expiry_alert_sent
    Provides a complete timeline visible on the pipeline record / candidate history.
    """

    __tablename__ = "pipeline_offer_events"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )

    pipeline_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pipelines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    offer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pipeline_offers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # What happened: offer_created | offer_revised | response_updated |
    #                expiry_alert_sent | offer_expired
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)

    actor_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    # Response change tracking.
    previous_response: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_response: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Human-readable description / additional detail.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
