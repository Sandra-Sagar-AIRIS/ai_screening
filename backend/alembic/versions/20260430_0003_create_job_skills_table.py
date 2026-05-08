"""Create job_skills table (idempotent).

Revision ID: 20260430_0003
Revises: 20260430_0002
Create Date: 2026-04-30

Ensures the job_skills table exists.  The table was declared in
20260429_0001 (extend jobs migration) but may have been skipped if the table appeared to exist
at that time.  This migration re-checks and creates it if absent.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260430_0003"
down_revision: str | None = "20260430_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema

    inspector = inspect(op.get_bind())
    existing = set(inspector.get_table_names(schema=schema))

    if "job_skills" not in existing:
        op.create_table(
            "job_skills",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "job_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("jobs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("skill", sa.String(length=100), nullable=False),
            sa.Column(
                "is_required",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.UniqueConstraint("job_id", "skill", name="uq_job_skills_job_id_skill"),
            schema=schema,
        )
        op.create_index(
            "ix_job_skills_job_id",
            "job_skills",
            ["job_id"],
            unique=False,
            schema=schema,
        )
        op.create_index(
            "ix_job_skills_skill",
            "job_skills",
            ["skill"],
            unique=False,
            schema=schema,
        )


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema

    inspector = inspect(op.get_bind())
    existing = set(inspector.get_table_names(schema=schema))

    if "job_skills" in existing:
        op.drop_index("ix_job_skills_skill", table_name="job_skills", schema=schema)
        op.drop_index("ix_job_skills_job_id", table_name="job_skills", schema=schema)
        op.drop_table("job_skills", schema=schema)
