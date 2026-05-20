"""PIPE-003: Pipeline status tracking — status history table + status_changed_at column.

Adds:
  - pipelines.status_changed_at  (timestamptz, nullable, backfilled from updated_at)
  - pipeline_status_history table with immutable audit rows for every status change

Revision ID: 20260519_0004
Revises: 20260519_0003
Create Date: 2026-05-19
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260519_0004"
down_revision: str = "20260519_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. status_changed_at on pipelines ────────────────────────────────────
    op.add_column(
        "pipelines",
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE pipelines SET status_changed_at = updated_at WHERE status_changed_at IS NULL"
    )
    op.create_index(
        "ix_pipelines_org_status_changed_at",
        "pipelines",
        ["organization_id", "status_changed_at"],
    )

    # ── 2. pipeline_status_history table ─────────────────────────────────────
    op.create_table(
        "pipeline_status_history",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "pipeline_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("previous_status", sa.String(32), nullable=True),
        sa.Column("new_status", sa.String(32), nullable=False),
        sa.Column("actor_user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column(
            "changed_at",
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
    )
    op.create_index(
        "ix_pipeline_status_history_pipeline_id",
        "pipeline_status_history",
        ["pipeline_id"],
    )
    op.create_index(
        "ix_pipeline_status_history_org_id",
        "pipeline_status_history",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_pipeline_status_history_org_id", table_name="pipeline_status_history")
    op.drop_index("ix_pipeline_status_history_pipeline_id", table_name="pipeline_status_history")
    op.drop_table("pipeline_status_history")
    op.drop_index("ix_pipelines_org_status_changed_at", table_name="pipelines")
    op.drop_column("pipelines", "status_changed_at")
