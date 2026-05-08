"""Add job_vendors.job_id index for reverse lookups.

Revision ID: 20260429_0103
Revises: 20260429_0102
Create Date: 2026-04-29

Renumbered from 20260429_0003 (duplicate id).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect

from app.core.config import get_settings

revision: str = "20260429_0103"
down_revision: str | None = "20260429_0102"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names(schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return set(inspector.get_table_names(schema=schema))


def _index_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    try:
        return {idx["name"] for idx in inspector.get_indexes(table, schema=schema)}
    except Exception:
        return set()


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    tables = _table_names(schema)

    if "job_vendors" not in tables:
        return

    index_names = _index_names("job_vendors", schema)
    if "ix_job_vendors_job_id" not in index_names:
        op.create_index("ix_job_vendors_job_id", "job_vendors", ["job_id"], unique=False, schema=schema)


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    tables = _table_names(schema)
    if "job_vendors" not in tables:
        return

    index_names = _index_names("job_vendors", schema)
    if "ix_job_vendors_job_id" in index_names:
        op.drop_index("ix_job_vendors_job_id", table_name="job_vendors", schema=schema)

