"""Add safe parsing metadata to jobs

Revision ID: c7bbc63c49c7
Revises: e50ad960f737
Create Date: 2026-04-30 11:37:51.467283
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'c7bbc63c49c7'
down_revision: str | None = 'e50ad960f737'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Idempotent: another branch (e.g. extend_jobs) may have added these already.
    inspector = inspect(op.get_bind())
    existing = {col["name"] for col in inspector.get_columns("jobs")}
    if "raw_jd_text" not in existing:
        op.add_column("jobs", sa.Column("raw_jd_text", sa.Text(), nullable=True))
    if "parsing_source" not in existing:
        op.add_column("jobs", sa.Column("parsing_source", sa.String(length=20), nullable=True))
    if "parsing_status" not in existing:
        op.add_column("jobs", sa.Column("parsing_status", sa.String(length=20), nullable=True))


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    existing = {col["name"] for col in inspector.get_columns("jobs")}
    if "parsing_status" in existing:
        op.drop_column("jobs", "parsing_status")
    if "parsing_source" in existing:
        op.drop_column("jobs", "parsing_source")
    if "raw_jd_text" in existing:
        op.drop_column("jobs", "raw_jd_text")

