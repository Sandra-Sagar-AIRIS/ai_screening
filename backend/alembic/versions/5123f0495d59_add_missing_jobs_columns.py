"""add_missing_jobs_columns

Revision ID: 5123f0495d59
Revises: 20260429_0001
Create Date: 2026-04-29 14:55:32.616607
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '5123f0495d59'
down_revision: str | None = '20260429_0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Guard every add_column — 20260429_0001 may have already added these.
    inspector = inspect(op.get_bind())
    existing_cols = {col["name"] for col in inspector.get_columns("jobs")}

    if "location" not in existing_cols:
        op.add_column('jobs', sa.Column('location', sa.String(), nullable=True))
    if "salary_min" not in existing_cols:
        op.add_column('jobs', sa.Column('salary_min', sa.Numeric(), nullable=True))
    if "salary_max" not in existing_cols:
        op.add_column('jobs', sa.Column('salary_max', sa.Numeric(), nullable=True))
    if "salary_currency" not in existing_cols:
        op.add_column('jobs', sa.Column('salary_currency', sa.String(), nullable=True, server_default='USD'))
    if "experience_min_years" not in existing_cols:
        op.add_column('jobs', sa.Column('experience_min_years', sa.Integer(), nullable=True))
    if "experience_max_years" not in existing_cols:
        op.add_column('jobs', sa.Column('experience_max_years', sa.Integer(), nullable=True))
    if "employment_type" not in existing_cols:
        op.add_column('jobs', sa.Column('employment_type', sa.String(), nullable=True))
    if "urgency" not in existing_cols:
        op.add_column('jobs', sa.Column('urgency', sa.String(), nullable=True, server_default='normal'))
    if "filled_at" not in existing_cols:
        op.add_column('jobs', sa.Column('filled_at', sa.TIMESTAMP(timezone=True), nullable=True))
    if "created_by" not in existing_cols:
        op.add_column('jobs', sa.Column('created_by', sa.UUID(), nullable=True))


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    existing_cols = {col["name"] for col in inspector.get_columns("jobs")}

    for col in ('created_by', 'filled_at', 'urgency', 'employment_type',
                'experience_max_years', 'experience_min_years',
                'salary_currency', 'salary_max', 'salary_min', 'location'):
        if col in existing_cols:
            op.drop_column('jobs', col)
