"""Add pipelines table linking candidates to jobs.

Revision ID: 20260421_0004
Revises: 20260421_0003
Create Date: 2026-04-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260421_0004"
down_revision: str | None = "20260421_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema

    op.create_table(
        "pipelines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "stage",
            sa.String(length=80),
            nullable=False,
            server_default=sa.text("'applied'"),
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_pipeline_candidate_job"),
        schema=schema,
    )
    op.create_foreign_key(
        "fk_pipelines_candidate_id_candidates",
        "pipelines",
        "candidates",
        ["candidate_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_foreign_key(
        "fk_pipelines_job_id_jobs",
        "pipelines",
        "jobs",
        ["job_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_index(
        "ix_pipelines_organization_id",
        "pipelines",
        ["organization_id"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        "ix_pipelines_candidate_id",
        "pipelines",
        ["candidate_id"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        "ix_pipelines_job_id",
        "pipelines",
        ["job_id"],
        unique=False,
        schema=schema,
    )


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema

    op.drop_index("ix_pipelines_job_id", table_name="pipelines", schema=schema)
    op.drop_index("ix_pipelines_candidate_id", table_name="pipelines", schema=schema)
    op.drop_index("ix_pipelines_organization_id", table_name="pipelines", schema=schema)
    op.drop_constraint(
        "fk_pipelines_job_id_jobs",
        "pipelines",
        schema=schema,
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_pipelines_candidate_id_candidates",
        "pipelines",
        schema=schema,
        type_="foreignkey",
    )
    op.drop_table("pipelines", schema=schema)
