"""ORM models for the self-service interview booking-link flow.

interview_booking_links — recruiter-created public booking page (token-based)
interview_booking_slots — candidate-selectable time slots on a booking link
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InterviewBookingLink(Base):
    __tablename__ = "interview_booking_links"
    __table_args__ = {"schema": "interview"}

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    # recruiter_id (identity.profiles), candidate_id (candidate.candidates),
    # job_id (jobs.jobs), and pipeline_id (pipeline.pipelines) are cross-schema
    # references — 0001_initial.py defines no FK for any of them; integrity
    # is enforced at the service layer.
    recruiter_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    candidate_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    job_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    pipeline_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    token: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("60"))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default=sa.text("'UTC'"))
    interview_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    meeting_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=sa.text("'active'"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class InterviewBookingSlot(Base):
    __tablename__ = "interview_booking_slots"
    __table_args__ = {"schema": "interview"}

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    booking_link_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("interview.interview_booking_links.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_booked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    booked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    interview_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("interview.interviews.id"),
        nullable=True,
    )
