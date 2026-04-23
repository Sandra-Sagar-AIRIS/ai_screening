"""Sync pipeline missing columns.

Revision ID: 20260421_0021
Revises: 20260421_0020
Create Date: 2026-04-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from app.core.config import get_settings

revision: str = "20260421_0021"
down_revision: str | None = "20260421_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(schema: str | None) -> set[str]:
    bind = op.get_bind()
    inspector = inspect(bind)
    return {col["name"] for col in inspector.get_columns("pipelines", schema=schema)}


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    existing = _column_names(schema)

    if "notes" not in existing:
        op.add_column("pipelines", sa.Column("notes", sa.Text(), nullable=True), schema=schema)
    if "updated_at" not in existing:
        op.add_column(
            "pipelines",
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            schema=schema,
        )


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    existing = _column_names(schema)

    if "updated_at" in existing:
        op.drop_column("pipelines", "updated_at", schema=schema)
    if "notes" in existing:
        op.drop_column("pipelines", "notes", schema=schema)
