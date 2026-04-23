"""Add auth columns to profiles table.

Revision ID: 20260421_0007
Revises: 20260421_0006
Create Date: 2026-04-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from app.core.config import get_settings

revision: str = "20260421_0007"
down_revision: str | None = "20260421_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(inspector: sa.Inspector, table_name: str, schema: str | None) -> bool:
    return table_name in inspector.get_table_names(schema=schema)


def _column_names(inspector: sa.Inspector, table_name: str, schema: str | None) -> set[str]:
    return {col["name"] for col in inspector.get_columns(table_name, schema=schema)}


def _qualified_profiles(schema: str | None) -> str:
    if schema:
        return f'"{schema}"."profiles"'
    return '"profiles"'


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _table_exists(inspector, "profiles", schema):
        return

    columns = _column_names(inspector, "profiles", schema)
    if "email" not in columns:
        op.add_column("profiles", sa.Column("email", sa.String(length=255), nullable=True), schema=schema)
        op.execute(
            sa.text(
                f"""
                UPDATE {_qualified_profiles(schema)}
                SET email = id::text || '@airis.local'
                WHERE email IS NULL
                """
            )
        )
        op.alter_column("profiles", "email", nullable=False, schema=schema)
    if "password_hash" not in columns:
        op.add_column("profiles", sa.Column("password_hash", sa.String(length=255), nullable=True), schema=schema)
        op.execute(sa.text(f"UPDATE {_qualified_profiles(schema)} SET password_hash = '' WHERE password_hash IS NULL"))
        op.alter_column("profiles", "password_hash", nullable=False, schema=schema)

    indexes = {idx["name"] for idx in inspector.get_indexes("profiles", schema=schema)}
    if "ix_profiles_email" not in indexes:
        op.create_index("ix_profiles_email", "profiles", ["email"], unique=True, schema=schema)


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _table_exists(inspector, "profiles", schema):
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("profiles", schema=schema)}
    if "ix_profiles_email" in indexes:
        op.drop_index("ix_profiles_email", table_name="profiles", schema=schema)

    columns = _column_names(inspector, "profiles", schema)
    if "password_hash" in columns:
        op.drop_column("profiles", "password_hash", schema=schema)
    if "email" in columns:
        op.drop_column("profiles", "email", schema=schema)
