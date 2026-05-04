"""add_application_mapping

Revision ID: 7a1e224d2be6
Revises: f29daa89b7cc
Create Date: 2026-04-30 22:39:47.825739
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a1e224d2be6'
down_revision: str | None = 'f29daa89b7cc'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'applications' not in tables:
        op.create_table(
            'applications',
            sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
            sa.Column('organization_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('candidate_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('job_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('stage', sa.String(length=80), server_default='applied', nullable=False),
            sa.Column('status', sa.String(length=32), server_default='active', nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ),
            sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('candidate_id', 'job_id', name='uq_application_candidate_job')
        )
        op.create_index('idx_app_candidate', 'applications', ['candidate_id'], unique=False)
        op.create_index('idx_app_job', 'applications', ['job_id'], unique=False)
        op.create_index(op.f('ix_applications_organization_id'), 'applications', ['organization_id'], unique=False)

    columns = [col['name'] for col in inspector.get_columns('candidates')]
    if 'job_id' in columns:
        op.execute(
            """
            INSERT INTO applications (organization_id, candidate_id, job_id, stage, status)
            SELECT c.organization_id, c.id, c.job_id, 'applied', 'active'
            FROM candidates c
            WHERE c.job_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM applications a
                WHERE a.candidate_id = c.id AND a.job_id = c.job_id
            );
            """
        )
        op.alter_column('candidates', 'job_id', existing_type=sa.dialects.postgresql.UUID(), nullable=True)


def downgrade() -> None:
    pass
