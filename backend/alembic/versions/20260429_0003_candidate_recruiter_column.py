"""Add recruiter_id column to candidates.

Revision ID: 20260429_0003
Revises: 20260429_0002
Create Date: 2026-04-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260429_0003"
down_revision: str | None = "20260429_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {col["name"] for col in inspector.get_columns(table, schema=schema)}


def _index_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {idx["name"] for idx in inspector.get_indexes(table, schema=schema)}


def upgrade() -> None:
    schema = get_settings().db_schema
    columns = _column_names("candidates", schema)
    if "recruiter_id" not in columns:
        op.add_column(
            "candidates",
            sa.Column("recruiter_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema=schema,
        )
    idx_names = _index_names("candidates", schema)
    if "ix_candidates_recruiter_id" not in idx_names:
        op.create_index("ix_candidates_recruiter_id", "candidates", ["recruiter_id"], unique=False, schema=schema)


def downgrade() -> None:
    schema = get_settings().db_schema
    columns = _column_names("candidates", schema)
    idx_names = _index_names("candidates", schema)
    if "ix_candidates_recruiter_id" in idx_names:
        op.drop_index("ix_candidates_recruiter_id", table_name="candidates", schema=schema)
    if "recruiter_id" in columns:
        op.drop_column("candidates", "recruiter_id", schema=schema)
