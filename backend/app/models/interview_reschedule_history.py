"""ORM model for interview.interview_reschedule_history (audit trail of reschedules)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InterviewRescheduleHistory(Base):
    __tablename__ = "interview_reschedule_history"
    __table_args__ = {"schema": "interview"}

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    interview_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("interview.interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    new_scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    changed_by_type: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=sa.text("'recruiter'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
