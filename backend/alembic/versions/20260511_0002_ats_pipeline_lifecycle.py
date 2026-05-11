"""Add ATS pipeline lifecycle columns to candidate_job_matches.

Revision ID: 20260511_0002
Revises: 20260511_0001
Create Date: 2026-05-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

from app.core.config import get_settings

revision: str = "20260511_0002"
down_revision: str | None = "20260511_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {col["name"] for col in inspector.get_columns(table, schema=schema)}


def upgrade() -> None:
    schema = get_settings().db_schema
    if "candidate_job_matches" not in inspect(op.get_bind()).get_table_names(schema=schema):
        return
    cols = _column_names("candidate_job_matches", schema)

    if "ats_pipeline_status" not in cols:
        op.add_column(
            "candidate_job_matches",
            sa.Column(
                "ats_pipeline_status",
                sa.String(length=32),
                nullable=False,
                server_default="pending",
            ),
            schema=schema,
        )
    if "enrichment_started_at" not in cols:
        op.add_column(
            "candidate_job_matches",
            sa.Column("enrichment_started_at", sa.DateTime(timezone=True), nullable=True),
            schema=schema,
        )
    if "deterministic_completed_at" not in cols:
        op.add_column(
            "candidate_job_matches",
            sa.Column("deterministic_completed_at", sa.DateTime(timezone=True), nullable=True),
            schema=schema,
        )
    if "semantic_completed_at" not in cols:
        op.add_column(
            "candidate_job_matches",
            sa.Column("semantic_completed_at", sa.DateTime(timezone=True), nullable=True),
            schema=schema,
        )
    if "enrichment_error" not in cols:
        op.add_column(
            "candidate_job_matches",
            sa.Column("enrichment_error", sa.Text(), nullable=True),
            schema=schema,
        )

    tbl = f"{schema}.candidate_job_matches" if schema else "candidate_job_matches"
    op.execute(
        text(
            f"UPDATE {tbl} SET ats_pipeline_status = 'completed' "
            "WHERE ai_enrichment_status = 'complete' AND (ats_pipeline_status IS NULL OR ats_pipeline_status = 'pending')"
        )
    )
    op.execute(
        text(
            f"UPDATE {tbl} SET ats_pipeline_status = 'failed' "
            "WHERE ai_enrichment_status = 'failed' AND (ats_pipeline_status IS NULL OR ats_pipeline_status = 'pending')"
        )
    )
    op.execute(
        text(
            f"UPDATE {tbl} SET ats_pipeline_status = 'deterministic_complete' "
            "WHERE ats_pipeline_status = 'pending' AND id IS NOT NULL "
            "AND (ai_enrichment_status IS NULL OR ai_enrichment_status = 'skipped')"
        )
    )


def downgrade() -> None:
    schema = get_settings().db_schema
    if "candidate_job_matches" not in inspect(op.get_bind()).get_table_names(schema=schema):
        return
    cols = _column_names("candidate_job_matches", schema)
    for col in (
        "enrichment_error",
        "semantic_completed_at",
        "deterministic_completed_at",
        "enrichment_started_at",
        "ats_pipeline_status",
    ):
        if col in cols:
            op.drop_column("candidate_job_matches", col, schema=schema)
