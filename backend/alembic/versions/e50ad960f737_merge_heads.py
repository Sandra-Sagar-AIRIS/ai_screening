"""merge heads

Revision ID: e50ad960f737
Revises: 20260430_0003, bf75cbe46e05
Create Date: 2026-04-30 11:37:02.230283
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e50ad960f737'
down_revision: str | None = ('20260430_0003', 'bf75cbe46e05')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

