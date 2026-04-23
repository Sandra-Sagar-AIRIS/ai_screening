"""Add index on interviews.scheduled_at for time-ordered queries.

Revision ID: 20260421_0006
Revises: 20260421_0005
Create Date: 2026-04-21
"""

from collections.abc import Sequence

from alembic import op

from app.core.config import get_settings

revision: str = "20260421_0006"
down_revision: str | None = "20260421_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema

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

    op.drop_index("ix_interviews_scheduled_at", table_name="interviews", schema=schema)
