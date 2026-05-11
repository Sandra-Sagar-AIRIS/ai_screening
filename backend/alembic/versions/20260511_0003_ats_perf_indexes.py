"""Add ATS performance indexes for pair status lookups.

Revision ID: 20260511_0003
Revises: 20260511_0002
Create Date: 2026-05-11
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect

from app.core.config import get_settings

revision: str = "20260511_0003"
down_revision: str | None = "20260511_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    schema = get_settings().db_schema
    inspector = inspect(op.get_bind())
    if "candidate_job_matches" not in inspector.get_table_names(schema=schema):
        return
    indexes = {idx["name"] for idx in inspector.get_indexes("candidate_job_matches", schema=schema)}
    if "ix_cjm_org_candidate_job" not in indexes:
        op.create_index(
            "ix_cjm_org_candidate_job",
            "candidate_job_matches",
            ["organization_id", "candidate_id", "job_id"],
            unique=False,
            schema=schema,
        )
    if "ix_cjm_org_status_updated" not in indexes:
        op.create_index(
            "ix_cjm_org_status_updated",
            "candidate_job_matches",
            ["organization_id", "ats_pipeline_status", "updated_at"],
            unique=False,
            schema=schema,
        )


def downgrade() -> None:
    schema = get_settings().db_schema
    inspector = inspect(op.get_bind())
    if "candidate_job_matches" not in inspector.get_table_names(schema=schema):
        return
    indexes = {idx["name"] for idx in inspector.get_indexes("candidate_job_matches", schema=schema)}
    if "ix_cjm_org_status_updated" in indexes:
        op.drop_index("ix_cjm_org_status_updated", table_name="candidate_job_matches", schema=schema)
    if "ix_cjm_org_candidate_job" in indexes:
        op.drop_index("ix_cjm_org_candidate_job", table_name="candidate_job_matches", schema=schema)

