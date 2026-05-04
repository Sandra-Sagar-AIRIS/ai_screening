"""merge_heads

Revision ID: f29daa89b7cc
Revises: 20260430_0004, c7bbc63c49c7
Create Date: 2026-04-30 22:39:28.382486
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f29daa89b7cc'
down_revision: str | None = ('20260430_0004', 'c7bbc63c49c7')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

