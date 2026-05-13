"""Add persisted original JD document metadata to jobs.

Revision ID: 20260513_0001
Revises: 20260512_0006
Create Date: 2026-05-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20260513_0001"
down_revision: str | None = "20260512_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("jobs")}
    if "jd_document_key" not in cols:
        op.add_column("jobs", sa.Column("jd_document_key", sa.String(length=1024), nullable=True))
    if "jd_file_name" not in cols:
        op.add_column("jobs", sa.Column("jd_file_name", sa.String(length=512), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("jobs")}
    if "jd_file_name" in cols:
        op.drop_column("jobs", "jd_file_name")
    if "jd_document_key" in cols:
        op.drop_column("jobs", "jd_document_key")
