"""Add updated_at to organizations.

Revision ID: 20260421_0008
Revises: 20260421_0007
Create Date: 2026-04-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.config import get_settings

revision: str = "20260421_0008"
down_revision: str | None = "20260421_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    op.add_column(
        "organizations",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema=schema,
    )


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    op.drop_column("organizations", "updated_at", schema=schema)
