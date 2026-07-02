"""ORM model for screening.ai_screening_reminders (self-service invite reminder sweep)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AIScreeningReminder(Base):
    __tablename__ = "ai_screening_reminders"
    __table_args__ = {"schema": "screening"}

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    screening_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("screening.ai_screenings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reminder_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=sa.text("'pending'"))
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
