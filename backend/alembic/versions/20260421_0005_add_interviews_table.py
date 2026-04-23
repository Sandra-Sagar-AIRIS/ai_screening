"""Add interviews table linked to pipelines.

Revision ID: 20260421_0005
Revises: 20260421_0004
Create Date: 2026-04-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260421_0005"
down_revision: str | None = "20260421_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema

    op.create_table(
        "interviews",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'scheduled'"),
        ),
        sa.Column("interviewer_name", sa.String(length=255), nullable=True),
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
        schema=schema,
    )
    op.create_foreign_key(
        "fk_interviews_pipeline_id_pipelines",
        "interviews",
        "pipelines",
        ["pipeline_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_index(
        "ix_interviews_organization_id",
        "interviews",
        ["organization_id"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        "ix_interviews_pipeline_id",
        "interviews",
        ["pipeline_id"],
        unique=False,
        schema=schema,
    )


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema

    op.drop_index("ix_interviews_pipeline_id", table_name="interviews", schema=schema)
    op.drop_index("ix_interviews_organization_id", table_name="interviews", schema=schema)
    op.drop_constraint(
        "fk_interviews_pipeline_id_pipelines",
        "interviews",
        schema=schema,
        type_="foreignkey",
    )
    op.drop_table("interviews", schema=schema)
