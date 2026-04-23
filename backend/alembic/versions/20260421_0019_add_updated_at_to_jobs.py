"""Add updated_at to jobs.

Revision ID: 20260421_0019
Revises: 20260421_0018
Create Date: 2026-04-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from app.core.config import get_settings

revision: str = "20260421_0019"
down_revision: str | None = "20260421_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("jobs", schema=schema)}

    if "updated_at" not in existing:
        op.add_column(
            "jobs",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=schema,
        )


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("jobs", schema=schema)}

    if "updated_at" in existing:
        op.drop_column("jobs", "updated_at", schema=schema)
