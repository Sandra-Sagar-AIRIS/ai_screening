"""add_dashboard_indexes

Revision ID: 4598e5be69f7
Revises: df1b27d06925
Create Date: 2026-06-01 13:19:03.507829
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4598e5be69f7'
down_revision: str | None = 'df1b27d06925'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(op.f('ix_candidates_created_at'), 'candidates', ['created_at'], unique=False)
    op.create_index(op.f('ix_jobs_created_at'), 'jobs', ['created_at'], unique=False)
    op.create_index(op.f('ix_pipelines_created_at'), 'pipelines', ['created_at'], unique=False)
    op.create_index('ix_pipelines_org_updated', 'pipelines', ['organization_id', 'updated_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_pipelines_org_updated', table_name='pipelines')
    op.drop_index(op.f('ix_pipelines_created_at'), table_name='pipelines')
    op.drop_index(op.f('ix_jobs_created_at'), table_name='jobs')
    op.drop_index(op.f('ix_candidates_created_at'), table_name='candidates')
