"""merge bootstrap and main heads

Revision ID: 74887ee20e0e
Revises: 20260430_0001, 78abbe09286e
Create Date: 2026-04-30 15:25:16.051778
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '74887ee20e0e'
down_revision: str | None = ('20260430_0001', '78abbe09286e')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

