"""Add jobs table with FK to clients.

Revision ID: 20260421_0003
Revises: 20260421_0002
Create Date: 2026-04-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260421_0003"
down_revision: str | None = "20260421_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema

    op.create_table(
        "jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
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
        "fk_jobs_client_id_clients",
        "jobs",
        "clients",
        ["client_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_index(
        "ix_jobs_organization_id",
        "jobs",
        ["organization_id"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        "ix_jobs_client_id",
        "jobs",
        ["client_id"],
        unique=False,
        schema=schema,
    )


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema

    op.drop_index("ix_jobs_client_id", table_name="jobs", schema=schema)
    op.drop_index("ix_jobs_organization_id", table_name="jobs", schema=schema)
    op.drop_constraint(
        "fk_jobs_client_id_clients",
        "jobs",
        schema=schema,
        type_="foreignkey",
    )
    op.drop_table("jobs", schema=schema)
