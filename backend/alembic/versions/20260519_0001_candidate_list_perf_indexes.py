"""Add candidate list/filter performance indexes (safe, idempotent).

Revision ID: 20260519_0001
Revises: 20260514_0001
Create Date: 2026-05-19
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect

from app.core.config import get_settings

revision: str = "20260519_0001"
down_revision: str | None = "20260514_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {idx["name"] for idx in inspector.get_indexes(table, schema=schema)}


def _column_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {col["name"] for col in inspector.get_columns(table, schema=schema)}


def upgrade() -> None:
    schema = get_settings().db_schema
    inspector = inspect(op.get_bind())
    if "candidates" not in inspector.get_table_names(schema=schema):
        return

    columns = _column_names("candidates", schema)
    if "org_id" not in columns or "workspace_id" not in columns:
        return

    indexes = _index_names("candidates", schema)

    if "ix_candidates_org_workspace_stage" not in indexes and "stage" in columns:
        op.create_index(
            "ix_candidates_org_workspace_stage",
            "candidates",
            ["org_id", "workspace_id", "stage"],
            unique=False,
            schema=schema,
        )

    if "ix_candidates_org_workspace_status" not in indexes and "status" in columns:
        op.create_index(
            "ix_candidates_org_workspace_status",
            "candidates",
            ["org_id", "workspace_id", "status"],
            unique=False,
            schema=schema,
        )

    if (
        "ix_candidates_org_workspace_created_at_desc" not in indexes
        and "created_at" in columns
        and "ix_candidates_org_workspace_created_at" not in indexes
    ):
        op.create_index(
            "ix_candidates_org_workspace_created_at_desc",
            "candidates",
            ["org_id", "workspace_id", "created_at"],
            unique=False,
            schema=schema,
            postgresql_ops={"created_at": "DESC"},
        )


def downgrade() -> None:
    schema = get_settings().db_schema
    inspector = inspect(op.get_bind())
    if "candidates" not in inspector.get_table_names(schema=schema):
        return

    indexes = _index_names("candidates", schema)
    for name in (
        "ix_candidates_org_workspace_status",
        "ix_candidates_org_workspace_stage",
        "ix_candidates_org_workspace_created_at_desc",
    ):
        if name in indexes:
            op.drop_index(name, table_name="candidates", schema=schema)
