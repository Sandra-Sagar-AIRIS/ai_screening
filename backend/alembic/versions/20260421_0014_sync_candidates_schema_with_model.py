"""Sync candidates schema with model.

Revision ID: 20260421_0014
Revises: 20260421_0013
Create Date: 2026-04-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from app.core.config import get_settings

revision: str = "20260421_0014"
down_revision: str | None = "20260421_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(schema: str | None) -> set[str]:
    bind = op.get_bind()
    inspector = inspect(bind)
    return {col["name"] for col in inspector.get_columns("candidates", schema=schema)}


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    existing = _column_names(schema)

    if "first_name" not in existing:
        op.add_column("candidates", sa.Column("first_name", sa.String(length=100), nullable=True), schema=schema)
    if "last_name" not in existing:
        op.add_column("candidates", sa.Column("last_name", sa.String(length=100), nullable=True), schema=schema)
    if "phone" not in existing:
        op.add_column("candidates", sa.Column("phone", sa.String(length=50), nullable=True), schema=schema)
    if "location" not in existing:
        op.add_column("candidates", sa.Column("location", sa.String(length=255), nullable=True), schema=schema)
    if "experience_summary" not in existing:
        op.add_column("candidates", sa.Column("experience_summary", sa.Text(), nullable=True), schema=schema)
    if "education" not in existing:
        op.add_column("candidates", sa.Column("education", sa.Text(), nullable=True), schema=schema)
    if "notes" not in existing:
        op.add_column("candidates", sa.Column("notes", sa.Text(), nullable=True), schema=schema)
    if "is_deleted" not in existing:
        op.add_column(
            "candidates",
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            schema=schema,
        )
    if "created_at" not in existing:
        op.add_column(
            "candidates",
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
            schema=schema,
        )
    if "updated_at" not in existing:
        op.add_column(
            "candidates",
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
            schema=schema,
        )


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    existing = _column_names(schema)

    if "updated_at" in existing:
        op.drop_column("candidates", "updated_at", schema=schema)
    if "created_at" in existing:
        op.drop_column("candidates", "created_at", schema=schema)
    if "is_deleted" in existing:
        op.drop_column("candidates", "is_deleted", schema=schema)
    if "notes" in existing:
        op.drop_column("candidates", "notes", schema=schema)
    if "education" in existing:
        op.drop_column("candidates", "education", schema=schema)
    if "experience_summary" in existing:
        op.drop_column("candidates", "experience_summary", schema=schema)
    if "location" in existing:
        op.drop_column("candidates", "location", schema=schema)
    if "phone" in existing:
        op.drop_column("candidates", "phone", schema=schema)
    if "last_name" in existing:
        op.drop_column("candidates", "last_name", schema=schema)
    if "first_name" in existing:
        op.drop_column("candidates", "first_name", schema=schema)
