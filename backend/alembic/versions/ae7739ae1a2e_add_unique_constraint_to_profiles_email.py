"""add unique constraint to profiles.email

Revision ID: ae7739ae1a2e
Revises: 78abbe09286e
Create Date: 2026-04-27 00:58:24.158757
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

from app.core.config import get_settings


# revision identifiers, used by Alembic.
revision: str = 'ae7739ae1a2e'
down_revision: str | None = '20260423_0025'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    inspector = inspect(op.get_bind())
    constraint_names = {c["name"] for c in inspector.get_unique_constraints("profiles", schema=schema)}
    index_map = {i["name"]: i for i in inspector.get_indexes("profiles", schema=schema)}

    if "uq_profiles_email" not in constraint_names:
        existing_index = index_map.get("ix_profiles_email")
        if existing_index and existing_index.get("unique"):
            op.drop_index("ix_profiles_email", table_name="profiles", schema=schema)
        op.create_unique_constraint(
            "uq_profiles_email",
            "profiles",
            ["email"],
            schema=schema,
        )


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    inspector = inspect(op.get_bind())
    constraint_names = {c["name"] for c in inspector.get_unique_constraints("profiles", schema=schema)}
    index_names = {i["name"] for i in inspector.get_indexes("profiles", schema=schema)}

    if "uq_profiles_email" in constraint_names:
        op.drop_constraint(
            "uq_profiles_email",
            "profiles",
            type_="unique",
            schema=schema,
        )
    if "ix_profiles_email" not in index_names:
        op.create_index("ix_profiles_email", "profiles", ["email"], unique=True, schema=schema)

