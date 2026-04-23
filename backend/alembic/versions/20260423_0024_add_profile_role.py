"""Add role column to profiles for RBAC.

Revision ID: 20260423_0024
Revises: 20260421_0023
Create Date: 2026-04-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from app.core.config import get_settings

revision: str = "20260423_0024"
down_revision: str | None = "20260421_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE_CHECK_NAME = "ck_profiles_role_allowed"
ROLE_ALLOWED = ("admin", "recruiter", "client_viewer")


def _column_names(schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("profiles", schema=schema)}


def _check_constraint_names(schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {constraint["name"] for constraint in inspector.get_check_constraints("profiles", schema=schema)}


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    columns = _column_names(schema)
    checks = _check_constraint_names(schema)

    if "role" not in columns:
        op.add_column(
            "profiles",
            sa.Column("role", sa.String(length=32), nullable=False, server_default=sa.text("'recruiter'")),
            schema=schema,
        )

    if ROLE_CHECK_NAME not in checks:
        op.create_check_constraint(
            ROLE_CHECK_NAME,
            "profiles",
            f"role IN {ROLE_ALLOWED}",
            schema=schema,
        )


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    columns = _column_names(schema)
    checks = _check_constraint_names(schema)

    if ROLE_CHECK_NAME in checks:
        op.drop_constraint(ROLE_CHECK_NAME, "profiles", type_="check", schema=schema)
    if "role" in columns:
        op.drop_column("profiles", "role", schema=schema)
