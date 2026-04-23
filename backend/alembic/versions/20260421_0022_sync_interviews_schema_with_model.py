"""Sync interviews schema with model.

Revision ID: 20260421_0022
Revises: 20260421_0021
Create Date: 2026-04-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from app.core.config import get_settings

revision: str = "20260421_0022"
down_revision: str | None = "20260421_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(schema: str | None) -> set[str]:
    bind = op.get_bind()
    inspector = inspect(bind)
    return {col["name"] for col in inspector.get_columns("interviews", schema=schema)}


def _index_names(schema: str | None) -> set[str]:
    bind = op.get_bind()
    inspector = inspect(bind)
    return {idx["name"] for idx in inspector.get_indexes("interviews", schema=schema)}


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    existing = _column_names(schema)

    if "interviewer_name" not in existing:
        op.add_column("interviews", sa.Column("interviewer_name", sa.String(length=255), nullable=True), schema=schema)
    if "notes" not in existing:
        op.add_column("interviews", sa.Column("notes", sa.Text(), nullable=True), schema=schema)
    if "updated_at" not in existing:
        op.add_column(
            "interviews",
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            schema=schema,
        )

    idx = _index_names(schema)
    if "ix_interviews_scheduled_at" not in idx:
        op.create_index(
            "ix_interviews_scheduled_at",
            "interviews",
            ["scheduled_at"],
            unique=False,
            schema=schema,
        )


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema

    idx = _index_names(schema)
    if "ix_interviews_scheduled_at" in idx:
        op.drop_index("ix_interviews_scheduled_at", table_name="interviews", schema=schema)

    existing = _column_names(schema)
    if "updated_at" in existing:
        op.drop_column("interviews", "updated_at", schema=schema)
    if "notes" in existing:
        op.drop_column("interviews", "notes", schema=schema)
    if "interviewer_name" in existing:
        op.drop_column("interviews", "interviewer_name", schema=schema)
