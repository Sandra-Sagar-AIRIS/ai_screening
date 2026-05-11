"""Add jobs.enrichment_status for async ATS pipeline visibility.

Revision ID: 20260511_0004
Revises: 20260511_0003
Create Date: 2026-05-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from app.core.config import get_settings

revision: str = "20260511_0004"
down_revision: str | None = "20260511_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    schema = get_settings().db_schema
    inspector = inspect(op.get_bind())
    if "jobs" not in inspector.get_table_names(schema=schema):
        return
    cols = {c["name"] for c in inspector.get_columns("jobs", schema=schema)}
    if "enrichment_status" not in cols:
        op.add_column(
            "jobs",
            sa.Column("enrichment_status", sa.String(length=32), nullable=True),
            schema=schema,
        )


def downgrade() -> None:
    schema = get_settings().db_schema
    inspector = inspect(op.get_bind())
    if "jobs" not in inspector.get_table_names(schema=schema):
        return
    cols = {c["name"] for c in inspector.get_columns("jobs", schema=schema)}
    if "enrichment_status" in cols:
        op.drop_column("jobs", "enrichment_status", schema=schema)
