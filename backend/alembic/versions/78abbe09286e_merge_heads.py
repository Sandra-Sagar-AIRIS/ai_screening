"""merge heads

Revision ID: 78abbe09286e
Revises: 20260423_0025, 20260422_1000
Create Date: 2026-04-24 14:50:40.390267
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78abbe09286e'
down_revision: str | None = ('20260423_0025', '20260422_1000')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

