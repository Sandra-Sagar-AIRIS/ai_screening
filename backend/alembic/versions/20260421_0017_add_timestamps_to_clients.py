"""Add timestamps to clients.

Revision ID: 20260421_0017
Revises: 20260421_0016
Create Date: 2026-04-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from app.core.config import get_settings

revision: str = "20260421_0017"
down_revision: str | None = "20260421_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(schema: str | None) -> set[str]:
    bind = op.get_bind()
    inspector = inspect(bind)
    return {col["name"] for col in inspector.get_columns("clients", schema=schema)}


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    existing = _column_names(schema)

    if "created_at" not in existing:
        op.add_column(
            "clients",
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            schema=schema,
        )

    if "updated_at" not in existing:
        op.add_column(
            "clients",
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            schema=schema,
        )


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    existing = _column_names(schema)

    if "updated_at" in existing:
        op.drop_column("clients", "updated_at", schema=schema)
    if "created_at" in existing:
        op.drop_column("clients", "created_at", schema=schema)
