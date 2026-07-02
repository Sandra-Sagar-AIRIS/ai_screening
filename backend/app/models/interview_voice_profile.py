"""ORM model for interview.interview_voice_profiles (proctoring voice-match baseline)."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import DateTime, SmallInteger, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InterviewVoiceProfile(Base):
    __tablename__ = "interview_voice_profiles"
    __table_args__ = {"schema": "interview"}

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    # screening_id is a cross-schema reference (screening.ai_screenings) —
    # 0001_initial.py defines no FK for it; integrity is enforced at the
    # service layer.
    screening_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, unique=True, index=True)
    embedding: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    mismatch_streak: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=sa.text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
