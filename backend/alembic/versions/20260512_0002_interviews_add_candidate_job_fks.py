"""Add candidate_id and job_id denormalized FKs to interviews table.

Revision ID: 20260512_0002
Revises: 20260512_0001
Create Date: 2026-05-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260512_0002"
down_revision: str | None = "20260512_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _col_names(schema: str | None, table: str) -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns(table, schema=schema)}


def _table_exists(schema: str | None, table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names(schema=schema)


def upgrade() -> None:
    schema = get_settings().db_schema

    if not _table_exists(schema, "interviews"):
        return

    existing = _col_names(schema, "interviews")
    candidates_ref = f"{schema}.candidates.id" if schema else "candidates.id"
    jobs_ref = f"{schema}.jobs.id" if schema else "jobs.id"

    if "candidate_id" not in existing:
        op.add_column(
            "interviews",
            sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema=schema,
        )
        op.create_foreign_key(
            "fk_interviews_candidate_id",
            "interviews",
            "candidates",
            ["candidate_id"],
            ["id"],
            source_schema=schema,
            referent_schema=schema,
        )
        op.create_index(
            "ix_interviews_candidate_id",
            "interviews",
            ["candidate_id"],
            schema=schema,
        )

    if "job_id" not in existing:
        op.add_column(
            "interviews",
            sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema=schema,
        )
        op.create_foreign_key(
            "fk_interviews_job_id",
            "interviews",
            "jobs",
            ["job_id"],
            ["id"],
            source_schema=schema,
            referent_schema=schema,
        )
        op.create_index(
            "ix_interviews_job_id",
            "interviews",
            ["job_id"],
            schema=schema,
        )


def downgrade() -> None:
    schema = get_settings().db_schema

    if not _table_exists(schema, "interviews"):
        return

    existing = _col_names(schema, "interviews")

    if "job_id" in existing:
        op.drop_index("ix_interviews_job_id", table_name="interviews", schema=schema)
        op.drop_constraint("fk_interviews_job_id", "interviews", schema=schema, type_="foreignkey")
        op.drop_column("interviews", "job_id", schema=schema)

    if "candidate_id" in existing:
        op.drop_index("ix_interviews_candidate_id", table_name="interviews", schema=schema)
        op.drop_constraint("fk_interviews_candidate_id", "interviews", schema=schema, type_="foreignkey")
        op.drop_column("interviews", "candidate_id", schema=schema)
