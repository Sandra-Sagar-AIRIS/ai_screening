"""Add hybrid AI ATS columns (bootstrap branch after auth sessions).

Same schema as 20260510_0001, but depends on b91f8d6a2c13 so bootstrap databases
do not replay the alternate Alembic branch.

Revision ID: 20260510_0002
Revises: b91f8d6a2c13

Idempotent: safe if columns already exist (e.g. DB applied 20260510_0001 first,
then upgrades through merge 11c997092c10).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260510_0002"
down_revision: str | None = "b91f8d6a2c13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _qualified_table(name: str) -> str:
    schema = get_settings().db_schema
    return f'"{schema}"."{name}"' if schema else f'"{name}"'


def _column_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {col["name"] for col in inspector.get_columns(table, schema=schema)}


def upgrade() -> None:
    schema = get_settings().db_schema
    cols = _column_names("candidate_job_matches", schema)

    if "deterministic_match_score" not in cols:
        op.add_column(
            "candidate_job_matches",
            sa.Column("deterministic_match_score", sa.Integer(), nullable=True),
            schema=schema,
        )
    if "semantic_match_score" not in cols:
        op.add_column(
            "candidate_job_matches",
            sa.Column("semantic_match_score", sa.Integer(), nullable=True),
            schema=schema,
        )
    if "ai_enrichment_status" not in cols:
        op.add_column(
            "candidate_job_matches",
            sa.Column("ai_enrichment_status", sa.String(length=32), nullable=True),
            schema=schema,
        )
    if "recruiter_summary" not in cols:
        op.add_column(
            "candidate_job_matches",
            sa.Column("recruiter_summary", sa.Text(), nullable=True),
            schema=schema,
        )
    if "confidence_reasoning" not in cols:
        op.add_column(
            "candidate_job_matches",
            sa.Column("confidence_reasoning", sa.Text(), nullable=True),
            schema=schema,
        )
    if "semantic_skill_matches" not in cols:
        op.add_column(
            "candidate_job_matches",
            sa.Column("semantic_skill_matches", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            schema=schema,
        )
    if "transferable_skills" not in cols:
        op.add_column(
            "candidate_job_matches",
            sa.Column("transferable_skills", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            schema=schema,
        )
    if "inferred_strengths" not in cols:
        op.add_column(
            "candidate_job_matches",
            sa.Column("inferred_strengths", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            schema=schema,
        )
    if "inferred_gaps" not in cols:
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
    cols = _column_names("candidate_job_matches", schema)
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
        if col in cols:
            op.drop_column("candidate_job_matches", col, schema=schema)
