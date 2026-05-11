"""ORM model for ATS per-pair candidate-job match results.

This is the source of truth. `JobMatchCache` (legacy single-row-per-job
JSONB) is rebuilt from this table after each rescore so existing read paths
keep working without schema breakage.

Indexes are tuned for two access patterns the API serves:
- "Top N candidates for job X by score" -> (org, job_id, match_score DESC)
- "All jobs candidate Y has been scored for" -> (org, candidate_id, match_score DESC)
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CandidateJobMatch(Base):
    __tablename__ = "candidate_job_matches"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "job_id",
            name="uq_candidate_job_matches_candidate_job",
        ),
        Index(
            "ix_candidate_job_matches_org_job_score",
            "organization_id",
            "job_id",
            "match_score",
        ),
        Index(
            "ix_candidate_job_matches_org_candidate_score",
            "organization_id",
            "candidate_id",
            "match_score",
        ),
        Index(
            "ix_cjm_org_candidate_job",
            "organization_id",
            "candidate_id",
            "job_id",
        ),
        Index(
            "ix_cjm_org_status_updated",
            "organization_id",
            "ats_pipeline_status",
            "updated_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Scores: match_score is hybrid (deterministic + semantic) 0..100 for ranking.
    # deterministic_match_score is the explainable rules-based score before AI blend.
    match_score: Mapped[int] = mapped_column(Integer, nullable=False)
    deterministic_match_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    semantic_match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    ai_enrichment_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ats_pipeline_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="pending",
    )
    enrichment_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deterministic_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    semantic_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    enrichment_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    recruiter_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    semantic_skill_matches: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    transferable_skills: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    inferred_strengths: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    inferred_gaps: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    category_scores: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    matched_skills: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    missing_skills: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    matched_preferred_skills: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    recommendation: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)

    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
