"""Sync candidates.organization_id and org_id for ATS and legacy ORM queries.

Revision ID: 20260511_0001
Revises: 11c997092c10
Create Date: 2026-05-11

Candidate-management rows often populated org_id while legacy services filtered on
organization_id only, which caused ATS rescoring to no-op (no candidate_job_matches).
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect, text

from app.core.config import get_settings

revision: str = "20260511_0001"
down_revision: str | None = "11c997092c10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {col["name"] for col in inspector.get_columns(table, schema=schema)}


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    if "candidates" not in inspect(op.get_bind()).get_table_names(schema=schema):
        return
    cols = _column_names("candidates", schema)
    if "organization_id" not in cols or "org_id" not in cols:
        return
    tbl = f"{schema}.candidates" if schema else "candidates"
    op.execute(
        text(f"UPDATE {tbl} SET organization_id = org_id WHERE organization_id IS NULL AND org_id IS NOT NULL")
    )
    op.execute(
        text(f"UPDATE {tbl} SET org_id = organization_id WHERE org_id IS NULL AND organization_id IS NOT NULL")
    )


def downgrade() -> None:
    # Data backfill is not safely reversible.
    pass
