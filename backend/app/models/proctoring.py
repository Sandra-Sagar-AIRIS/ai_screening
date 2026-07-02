"""SQLAlchemy ORM models for the Proctoring layer (schema `proctoring`).

Proctoring FKs to screening.ai_screenings, not interview.interviews — it is a
sub-module of AI Screening, not Interview (per 0001_initial.py comments).

  proctoring_sessions      — one session per AI screening (hardware check, baseline image)
  proctoring_events        — timestamped anomaly events during a session
  proctoring_risk_scores   — computed trust/risk rollup per session
  proctoring_evidence      — captured frame/evidence files per event
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProctoringSession(Base):
    __tablename__ = "proctoring_sessions"
    __table_args__ = {"schema": "proctoring"}

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    # screening_id is a cross-schema reference (screening.ai_screenings) —
    # 0001_initial.py defines no FK for it; integrity is enforced at the
    # service layer.
    screening_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, unique=True, index=True)
    is_hardware_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    baseline_image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProctoringEvent(Base):
    __tablename__ = "proctoring_events"
    __table_args__ = {"schema": "proctoring"}

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("proctoring.proctoring_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class ProctoringRiskScore(Base):
    __tablename__ = "proctoring_risk_scores"
    __table_args__ = {"schema": "proctoring"}

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("proctoring.proctoring_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    trust_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=sa.text("100"))
    risk_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=sa.text("0"))
    risk_level: Mapped[str] = mapped_column(String(8), nullable=False, server_default=sa.text("'low'"))
    tab_switches: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=sa.text("0"))
    fullscreen_exits: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=sa.text("0"))
    window_blurs: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=sa.text("0"))
    face_missing_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=sa.text("0"))
    multiple_person_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=sa.text("0"))
    mobile_detected_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=sa.text("0"))
    copy_paste_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=sa.text("0"))
    identity_mismatch_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=sa.text("0"))
    voice_mismatch_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=sa.text("0"))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProctoringEvidence(Base):
    __tablename__ = "proctoring_evidence"
    __table_args__ = {"schema": "proctoring"}

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("proctoring.proctoring_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("proctoring.proctoring_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    frame_index: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=sa.text("0"))
    width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upload_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=sa.text("'pending'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
