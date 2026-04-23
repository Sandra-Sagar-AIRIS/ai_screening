"""Fix jobs id default uuid.

Revision ID: 20260421_0020
Revises: 20260421_0019
Create Date: 2026-04-22
"""

from collections.abc import Sequence

from alembic import op

from app.core.config import get_settings

revision: str = "20260421_0020"
down_revision: str | None = "20260421_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _qualified_table(schema: str | None, table: str) -> str:
    if schema:
        return f'"{schema}"."{table}"'
    return f'"{table}"'


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    jobs = _qualified_table(schema, "jobs")

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute(
        f"""
        ALTER TABLE {jobs}
        ALTER COLUMN id SET DEFAULT gen_random_uuid();
        """
    )


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    jobs = _qualified_table(schema, "jobs")

    op.execute(
        f"""
        ALTER TABLE {jobs}
        ALTER COLUMN id DROP DEFAULT;
        """
    )
