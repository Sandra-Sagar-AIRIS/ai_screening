"""Merge heads for Job Management

Revision ID: bf75cbe46e05
Revises: 20260427_0026, 5123f0495d59
Create Date: 2026-04-29 17:09:49.634874
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bf75cbe46e05'
down_revision: str | None = ('20260427_0026', '5123f0495d59')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

