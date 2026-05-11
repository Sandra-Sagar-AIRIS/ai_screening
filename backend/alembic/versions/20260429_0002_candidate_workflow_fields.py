"""Add candidate workflow fields for candidate management.

Revision ID: 20260429_0002
Revises: 20260429_0001
Create Date: 2026-04-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260429_0002"
down_revision: str | None = "20260429_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {n for col in inspector.get_columns(table, schema=schema) if (n := col.get("name")) is not None}


def _index_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {n for idx in inspector.get_indexes(table, schema=schema) if (n := idx.get("name")) is not None}


def upgrade() -> None:
    schema = get_settings().db_schema
    columns = _column_names("candidates", schema)

    if "stage" not in columns:
        op.add_column(
            "candidates",
            sa.Column("stage", sa.String(length=40), nullable=False, server_default=sa.text("'applied'")),
            schema=schema,
        )
    if "job_id" not in columns:
        op.add_column(
            "candidates",
            sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema=schema,
        )
    if "source" in columns:
        op.execute("UPDATE candidates SET source='bulk_upload' WHERE source='import'")

    idx_names = _index_names("candidates", schema)
    if "ix_candidates_job_id" not in idx_names:
        op.create_index("ix_candidates_job_id", "candidates", ["job_id"], unique=False, schema=schema)
    if "ix_candidates_stage" not in idx_names:
        op.create_index("ix_candidates_stage", "candidates", ["stage"], unique=False, schema=schema)


def downgrade() -> None:
    schema = get_settings().db_schema
    columns = _column_names("candidates", schema)
    idx_names = _index_names("candidates", schema)

    if "ix_candidates_stage" in idx_names:
        op.drop_index("ix_candidates_stage", table_name="candidates", schema=schema)
    if "ix_candidates_job_id" in idx_names:
        op.drop_index("ix_candidates_job_id", table_name="candidates", schema=schema)
    if "job_id" in columns:
        op.drop_column("candidates", "job_id", schema=schema)
    if "stage" in columns:
        op.drop_column("candidates", "stage", schema=schema)
