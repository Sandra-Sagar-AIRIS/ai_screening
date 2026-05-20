from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobSubmission(Base):
    __tablename__ = "job_submissions"
    __table_args__ = (sa.UniqueConstraint("job_id", "candidate_id", name="uq_job_submissions_job_id_candidate_id"),)

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    submitted_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("profiles.id"),
        nullable=False,
        index=True,
    )

    submission_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=sa.text("'pending'"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # PIPE-005: Submission Tracking
    # vendor_id — profile ID of the vendor who submitted (for vendor-isolation queries).
    # Nullable for internal/recruiter submissions; backfilled = submitted_by for existing rows.
    vendor_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # outcome — client decision on the submission.
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, server_default=sa.text("'pending'"))
    # client_feedback — free-text feedback recorded by recruiter/client.
    client_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

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

