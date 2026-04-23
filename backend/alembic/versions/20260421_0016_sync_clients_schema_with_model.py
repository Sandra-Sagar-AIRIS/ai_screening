"""Sync clients schema with model.

Revision ID: 20260421_0016
Revises: 20260421_0015
Create Date: 2026-04-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from app.core.config import get_settings

revision: str = "20260421_0016"
down_revision: str | None = "20260421_0015"
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

    if "legal_name" not in existing:
        op.add_column("clients", sa.Column("legal_name", sa.String(length=255), nullable=True), schema=schema)
    if "industry" not in existing:
        op.add_column("clients", sa.Column("industry", sa.String(length=120), nullable=True), schema=schema)
    if "website" not in existing:
        op.add_column("clients", sa.Column("website", sa.String(length=500), nullable=True), schema=schema)
    if "email" not in existing:
        op.add_column("clients", sa.Column("email", sa.String(length=255), nullable=True), schema=schema)
    if "phone" not in existing:
        op.add_column("clients", sa.Column("phone", sa.String(length=50), nullable=True), schema=schema)
    if "location" not in existing:
        op.add_column("clients", sa.Column("location", sa.String(length=255), nullable=True), schema=schema)
    if "notes" not in existing:
        op.add_column("clients", sa.Column("notes", sa.Text(), nullable=True), schema=schema)
    if "is_deleted" not in existing:
        op.add_column(
            "clients",
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            schema=schema,
        )


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    existing = _column_names(schema)

    if "is_deleted" in existing:
        op.drop_column("clients", "is_deleted", schema=schema)
    if "notes" in existing:
        op.drop_column("clients", "notes", schema=schema)
    if "location" in existing:
        op.drop_column("clients", "location", schema=schema)
    if "phone" in existing:
        op.drop_column("clients", "phone", schema=schema)
    if "email" in existing:
        op.drop_column("clients", "email", schema=schema)
    if "website" in existing:
        op.drop_column("clients", "website", schema=schema)
    if "industry" in existing:
        op.drop_column("clients", "industry", schema=schema)
    if "legal_name" in existing:
        op.drop_column("clients", "legal_name", schema=schema)
