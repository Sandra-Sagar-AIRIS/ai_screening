"""JOB-002 job status lifecycle and history.

Revision ID: 20260506_0001
Revises: 20260505_0002, 7a1e224d2be6
Create Date: 2026-05-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "20260506_0001"
down_revision: str | Sequence[str] | None = ("20260505_0002", "7a1e224d2be6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    schema = settings.db_schema
    schema_prefix = f"{schema}." if schema else ""
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names(schema=schema))
    if "jobs" not in tables:
        return

    op.execute(sa.text(f"UPDATE {schema_prefix}jobs SET status = 'paused' WHERE status = 'on_hold'"))
    op.execute(sa.text(f"UPDATE {schema_prefix}jobs SET status = 'closed' WHERE status = 'cancelled'"))

    columns = {c["name"] for c in inspector.get_columns("jobs", schema=schema)}
    if "paused_reason" not in columns:
        op.add_column("jobs", sa.Column("paused_reason", sa.Text(), nullable=True), schema=schema)

    op.execute(
        sa.text(
            """
            ALTER TABLE jobs
            DROP CONSTRAINT IF EXISTS ck_jobs_status_lifecycle;
            """
        )
    )
    op.create_check_constraint(
        "ck_jobs_status_lifecycle",
        "jobs",
        "status IN ('draft', 'open', 'paused', 'closed', 'filled')",
        schema=schema,
    )

    job_indexes = {idx["name"] for idx in inspector.get_indexes("jobs", schema=schema)}
    if "ix_jobs_status" not in job_indexes:
        op.create_index("ix_jobs_status", "jobs", ["status"], unique=False, schema=schema)

    if "job_status_history" not in tables:
        op.create_table(
            "job_status_history",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("previous_status", sa.String(length=32), nullable=False),
            sa.Column("new_status", sa.String(length=32), nullable=False),
            sa.Column("changed_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            schema=schema,
        )
        op.create_index("ix_job_status_history_job_id", "job_status_history", ["job_id"], unique=False, schema=schema)


def downgrade() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    schema = settings.db_schema
    schema_prefix = f"{schema}." if schema else ""
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names(schema=schema))
    if "jobs" not in tables:
        return

    if "job_status_history" in tables:
        op.drop_index("ix_job_status_history_job_id", table_name="job_status_history", schema=schema)
        op.drop_table("job_status_history", schema=schema)

    job_indexes = {idx["name"] for idx in inspector.get_indexes("jobs", schema=schema)}
    if "ix_jobs_status" in job_indexes:
        op.drop_index("ix_jobs_status", table_name="jobs", schema=schema)

    op.execute(sa.text(f"ALTER TABLE {schema_prefix}jobs DROP CONSTRAINT IF EXISTS ck_jobs_status_lifecycle;"))

    columns = {c["name"] for c in inspector.get_columns("jobs", schema=schema)}
    if "paused_reason" in columns:
        op.drop_column("jobs", "paused_reason", schema=schema)

    op.execute(sa.text(f"UPDATE {schema_prefix}jobs SET status = 'on_hold' WHERE status = 'paused'"))
