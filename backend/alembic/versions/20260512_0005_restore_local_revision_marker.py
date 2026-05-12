"""Restore local revision marker for databases stamped at 20260512_0005.

Revision ID: 20260512_0005
Revises: 20260511_0003, 20260512_0002
Create Date: 2026-05-12
"""

from collections.abc import Sequence

revision: str = "20260512_0005"
down_revision: str | tuple[str, str] | None = ("20260511_0003", "20260512_0002")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op marker; the live DB is already stamped at this missing revision."""


def downgrade() -> None:
    """No-op marker."""
