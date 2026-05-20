"""SQLAlchemy models for AI candidate sourcing sessions and results."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


sourcing_session_status_enum = sa.Enum(
    "pending",
    "running",
    "complete",
    "failed",
    name="sourcing_session_status",
    create_type=False,
)

sourcing_result_action_enum = sa.Enum(
    "pending",
    "shortlisted",
    "rejected",
    "imported",
    name="sourcing_result_action",
    create_type=False,
)


class SourcingSession(Base):
    """Tracks one AI sourcing run (job + query + providers + status)."""

    __tablename__ = "sourcing_sessions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        sourcing_session_status_enum,
        nullable=False,
        server_default=sa.text("'pending'"),
        index=True,
    )
    query_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    providers_used: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    total_results: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SourcingResult(Base):
    """One candidate result within a sourcing session."""

    __tablename__ = "sourcing_results"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sourcing_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)

    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    skills: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    ats_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ats_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    semantic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    recruiter_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_skills: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    action: Mapped[str] = mapped_column(
        sourcing_result_action_enum,
        nullable=False,
        server_default=sa.text("'pending'"),
        index=True,
    )
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_duplicate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
