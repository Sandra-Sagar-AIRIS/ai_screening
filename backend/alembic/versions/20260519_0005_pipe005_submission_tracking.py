"""PIPE-005: Submission Tracking — add vendor_id, outcome, client_feedback to job_submissions.

vendor_id  — denormalized submitter profile ID for fast vendor-isolation queries.
             Backfilled from submitted_by so existing rows are immediately correct.
outcome    — recruiter/client outcome verdict: pending | accepted | rejected.
             Defaults to 'pending' so existing rows are valid.
client_feedback — free-text feedback from the client.

Revision ID: 20260519_0005
Revises: 20260519_0004
Create Date: 2026-05-19
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260519_0005"
down_revision: str = "20260519_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. vendor_id ──────────────────────────────────────────────────────────
    op.add_column(
        "job_submissions",
        sa.Column(
            "vendor_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    # Backfill from submitted_by — for vendor-submitted rows this is the vendor's profile ID.
    op.execute("UPDATE job_submissions SET vendor_id = submitted_by WHERE vendor_id IS NULL")
    op.create_index("ix_job_submissions_vendor_id", "job_submissions", ["vendor_id"])

    # ── 2. outcome ────────────────────────────────────────────────────────────
    op.add_column(
        "job_submissions",
        sa.Column(
            "outcome",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
    )

    # ── 3. client_feedback ────────────────────────────────────────────────────
    op.add_column(
        "job_submissions",
        sa.Column("client_feedback", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("job_submissions", "client_feedback")
    op.drop_column("job_submissions", "outcome")
    op.drop_index("ix_job_submissions_vendor_id", table_name="job_submissions")
    op.drop_column("job_submissions", "vendor_id")
