"""SQLAlchemy ORM models for the AI Interview Copilot layer.

Three tables form the copilot entity graph:
  interview_copilot_sessions    — one session per interview, tracks lifecycle + summary
  interview_transcript_segments — growing log of transcript utterances
  interview_ai_suggestions      — AI-generated follow-up question suggestions
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InterviewCopilotSession(Base):
    """One copilot session per interview.  Created lazily on first use."""

    __tablename__ = "interview_copilot_sessions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    interview_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Lifecycle: active | completed | summarized
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="active", index=True
    )

    # Post-interview AI-generated summary (JSON blob with structured sections)
    summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Skill-coverage map: {"Python": true, "System Design": false, ...}
    skills_covered: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # AI usage tracking
    prompt_tokens_used: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    completion_tokens_used: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=sa.text("now()"),
    )
    summarized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class InterviewTranscriptSegment(Base):
    """One row per transcript utterance — appended in real time during the interview."""

    __tablename__ = "interview_transcript_segments"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("interview_copilot_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    interview_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )

    # "interviewer" | "candidate" | "unknown"
    speaker: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="unknown"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Millisecond offset from interview start (optional, from transcription provider)
    offset_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Source: "manual" | "assemblyai" | "paste"
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="manual"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class InterviewAISuggestion(Base):
    """AI-generated question suggestion — one row per suggestion emitted."""

    __tablename__ = "interview_ai_suggestions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("interview_copilot_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    interview_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )

    # Type of suggestion: "follow_up" | "clarification" | "skill_gap" | "deep_dive" | "closing"
    suggestion_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="follow_up"
    )

    # The suggested question text
    question_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Rationale for the suggestion (shown to recruiter)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Skills this question probes
    target_skills: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Difficulty hint: "easy" | "medium" | "hard"
    difficulty: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Whether the recruiter clicked "Use this question"
    used: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.text("false")
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Dismissed by recruiter
    dismissed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.text("false")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
