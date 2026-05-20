"""PIPE-004: Add stage_updated_at column to pipelines table.

stage_updated_at is set by the pipeline service whenever a stage
transition is applied (transition_stage).  It enables efficient
sorting by "when did this candidate last move stage".

Existing rows are backfilled to updated_at so sort-by-stage-updated
still produces sensible results for historical records.

Revision ID: 20260519_0003
Revises: 20260519_0002
Create Date: 2026-05-19
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260519_0003"
down_revision: str = "20260519_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add column as nullable first so the backfill can run.
    op.add_column(
        "pipelines",
        sa.Column(
            "stage_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Backfill existing rows from updated_at.
    op.execute(
        "UPDATE pipelines SET stage_updated_at = updated_at WHERE stage_updated_at IS NULL"
    )

    # Composite index for paginated stage-sorted queries scoped by org.
    op.create_index(
        "ix_pipelines_org_stage_updated_at",
        "pipelines",
        ["organization_id", "stage_updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_pipelines_org_stage_updated_at", table_name="pipelines")
    op.drop_column("pipelines", "stage_updated_at")
