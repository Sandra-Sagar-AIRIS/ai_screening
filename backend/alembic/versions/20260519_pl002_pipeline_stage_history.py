"""Add pipeline_stage_history table (PIPE-002).

Revision ID: 20260519_pl002_pipeline_stage_history
Revises: 20260514_0001
Create Date: 2026-05-19

Adds an immutable audit log for pipeline stage transitions.
One row is written per transition, recording the actor, the stage change,
and an optional rejection reason.

Note: Formerly incorrectly shared revision id 20260519_0001 with candidate_list_perf_indexes.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260519_pl002_pipeline_stage_history"
down_revision: str | None = "20260514_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(connection, table_name: str) -> bool:
    schema = get_settings().db_schema or None
    inspector = inspect(connection)
    return inspector.has_table(table_name, schema=schema)


def upgrade() -> None:
    schema = get_settings().db_schema
    bind = op.get_bind()

    if not _table_exists(bind, "pipeline_stage_history"):
        op.create_table(
            "pipeline_stage_history",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column(
                "pipeline_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("previous_stage", sa.String(80), nullable=True),
            sa.Column("new_stage", sa.String(80), nullable=False),
            sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("reason", sa.Text, nullable=True),
            sa.Column(
                "transitioned_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            schema=schema,
        )

        op.create_index(
            "ix_pipeline_stage_history_pipeline_id",
            "pipeline_stage_history",
            ["pipeline_id"],
            schema=schema,
        )
        op.create_index(
            "ix_pipeline_stage_history_organization_id",
            "pipeline_stage_history",
            ["organization_id"],
            schema=schema,
        )
        op.create_index(
            "ix_pipeline_stage_history_transitioned_at",
            "pipeline_stage_history",
            ["transitioned_at"],
            schema=schema,
        )


def downgrade() -> None:
    schema = get_settings().db_schema
    bind = op.get_bind()

    if _table_exists(bind, "pipeline_stage_history"):
        op.drop_table("pipeline_stage_history", schema=schema)
