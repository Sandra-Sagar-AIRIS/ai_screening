"""Remove profiles id foreign key to users.

Revision ID: 20260421_0012
Revises: 20260421_0011
Create Date: 2026-04-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from app.core.config import get_settings

revision: str = "20260421_0012"
down_revision: str | None = "20260421_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    bind = op.get_bind()
    inspector = inspect(bind)
    fks = inspector.get_foreign_keys("profiles", schema=schema)
    if any(fk.get("name") == "profiles_id_fkey" for fk in fks):
        op.drop_constraint("profiles_id_fkey", "profiles", type_="foreignkey", schema=schema)


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    bind = op.get_bind()
    inspector = inspect(bind)
    fks = inspector.get_foreign_keys("profiles", schema=schema)
    if not any(fk.get("name") == "profiles_id_fkey" for fk in fks):
        op.create_foreign_key(
            "profiles_id_fkey",
            "profiles",
            "users",
            ["id"],
            ["id"],
            source_schema=schema,
            referent_schema=schema,
        )
