"""Create candidate_job_matches table for ATS scoring.

Revision ID: c418d80c8924
Revises: 607b31166d1f
Create Date: 2026-05-07
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision: str = "c418d80c8924"
down_revision: str | Sequence[str] | None = "607b31166d1f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "candidate_job_matches" not in tables:
        op.create_table(
            "candidate_job_matches",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("match_score", sa.Integer(), nullable=False),
            sa.Column("category_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("matched_skills", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("missing_skills", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column(
                "matched_preferred_skills",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
            sa.Column("recommendation", sa.String(length=20), nullable=False),
            sa.Column("confidence_score", sa.Numeric(precision=4, scale=3), nullable=True),
            sa.Column(
                "evaluated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "candidate_id",
                "job_id",
                name="uq_candidate_job_matches_candidate_job",
            ),
        )

    indexes = {idx["name"] for idx in inspector.get_indexes("candidate_job_matches")} if "candidate_job_matches" in inspector.get_table_names() else set()

    if "ix_candidate_job_matches_organization_id" not in indexes:
        op.create_index(
            "ix_candidate_job_matches_organization_id",
            "candidate_job_matches",
            ["organization_id"],
            unique=False,
        )
    if "ix_candidate_job_matches_candidate_id" not in indexes:
        op.create_index(
            "ix_candidate_job_matches_candidate_id",
            "candidate_job_matches",
            ["candidate_id"],
            unique=False,
        )
    if "ix_candidate_job_matches_job_id" not in indexes:
        op.create_index(
            "ix_candidate_job_matches_job_id",
            "candidate_job_matches",
            ["job_id"],
            unique=False,
        )
    if "ix_candidate_job_matches_org_job_score" not in indexes:
        op.create_index(
            "ix_candidate_job_matches_org_job_score",
            "candidate_job_matches",
            ["organization_id", "job_id", "match_score"],
            unique=False,
        )
    if "ix_candidate_job_matches_org_candidate_score" not in indexes:
        op.create_index(
            "ix_candidate_job_matches_org_candidate_score",
            "candidate_job_matches",
            ["organization_id", "candidate_id", "match_score"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "candidate_job_matches" not in tables:
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("candidate_job_matches")}
    for name in (
        "ix_candidate_job_matches_org_candidate_score",
        "ix_candidate_job_matches_org_job_score",
        "ix_candidate_job_matches_job_id",
        "ix_candidate_job_matches_candidate_id",
        "ix_candidate_job_matches_organization_id",
    ):
        if name in indexes:
            op.drop_index(name, table_name="candidate_job_matches")
    op.drop_table("candidate_job_matches")
