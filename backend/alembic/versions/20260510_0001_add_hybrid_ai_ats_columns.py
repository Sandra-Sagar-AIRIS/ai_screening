"""Add hybrid AI ATS columns to candidate_job_matches.

Revision ID: 20260510_0001
Revises: 20260430_0101
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260510_0001"
down_revision: str | None = "20260430_0101"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _qualified_table(name: str) -> str:
    schema = get_settings().db_schema
    return f'"{schema}"."{name}"' if schema else f'"{name}"'


def upgrade() -> None:
    schema = get_settings().db_schema

    op.add_column(
        "candidate_job_matches",
        sa.Column("deterministic_match_score", sa.Integer(), nullable=True),
        schema=schema,
    )
    op.add_column(
        "candidate_job_matches",
        sa.Column("semantic_match_score", sa.Integer(), nullable=True),
        schema=schema,
    )
    op.add_column(
        "candidate_job_matches",
        sa.Column("ai_enrichment_status", sa.String(length=32), nullable=True),
        schema=schema,
    )
    op.add_column(
        "candidate_job_matches",
        sa.Column("recruiter_summary", sa.Text(), nullable=True),
        schema=schema,
    )
    op.add_column(
        "candidate_job_matches",
        sa.Column("confidence_reasoning", sa.Text(), nullable=True),
        schema=schema,
    )
    op.add_column(
        "candidate_job_matches",
        sa.Column("semantic_skill_matches", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=schema,
    )
    op.add_column(
        "candidate_job_matches",
        sa.Column("transferable_skills", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=schema,
    )
    op.add_column(
        "candidate_job_matches",
        sa.Column("inferred_strengths", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=schema,
    )
    op.add_column(
        "candidate_job_matches",
        sa.Column("inferred_gaps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=schema,
    )

    tbl = _qualified_table("candidate_job_matches")
    op.execute(text(f"UPDATE {tbl} SET deterministic_match_score = match_score WHERE deterministic_match_score IS NULL"))

    op.alter_column(
        "candidate_job_matches",
        "deterministic_match_score",
        nullable=False,
        server_default="0",
        schema=schema,
    )


def downgrade() -> None:
    schema = get_settings().db_schema
    for col in (
        "inferred_gaps",
        "inferred_strengths",
        "transferable_skills",
        "semantic_skill_matches",
        "confidence_reasoning",
        "recruiter_summary",
        "ai_enrichment_status",
        "semantic_match_score",
        "deterministic_match_score",
    ):
        op.drop_column("candidate_job_matches", col, schema=schema)
