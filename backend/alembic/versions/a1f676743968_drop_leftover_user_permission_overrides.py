"""drop leftover user permission overrides

Revision ID: a1f676743968
Revises: 74887ee20e0e
Create Date: 2026-04-30 15:32:29.771584
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'a1f676743968'
down_revision: str | None = '74887ee20e0e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    schema = settings.db_schema
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names(schema=schema))

    if "user_permission_overrides" in tables:
        op.drop_table("user_permission_overrides", schema=schema)

    # Best-effort cleanup: enum may linger after table drop.
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'permission_effect') THEN
                    DROP TYPE permission_effect;
                END IF;
            END $$;
            """
        )
    )


def downgrade() -> None:
    raise NotImplementedError("Downgrade not supported for this cleanup migration.")

