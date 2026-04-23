"""Initial baseline for existing Supabase schema.

Revision ID: 20260420_0001
Revises:
Create Date: 2026-04-20
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260420_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Baseline only: existing database schema is already in place.
    # Use `alembic stamp head` to mark current DB state as managed.
    pass


def downgrade() -> None:
    pass

