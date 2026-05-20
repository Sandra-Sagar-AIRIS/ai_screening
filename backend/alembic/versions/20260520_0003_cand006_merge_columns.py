"""CAND-006: Add is_merged and merged_into_id columns to candidates table.

Revision ID: 20260520_0003
Revises: 20260520_0002
Create Date: 2026-05-20
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.core.config import get_settings

revision: str = "20260520_0003"
down_revision: str = "20260520_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _schema() -> str | None:
    return get_settings().db_schema


def _column_names(table: str) -> set[str]:
    return {col["name"] for col in inspect(op.get_bind()).get_columns(table, schema=_schema())}


def _index_names(table: str) -> set[str]:
    return {idx["name"] for idx in inspect(op.get_bind()).get_indexes(table, schema=_schema())}


def _fk_names(table: str) -> set[str]:
    return {fk["name"] for fk in inspect(op.get_bind()).get_foreign_keys(table, schema=_schema())}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    cols = _column_names("candidates")
    schema = _schema()

    if "is_merged" not in cols:
        op.add_column(
            "candidates",
            sa.Column("is_merged", sa.Boolean, nullable=False, server_default="false"),
            schema=schema,
        )

    if "merged_into_id" not in cols:
        op.add_column(
            "candidates",
            sa.Column("merged_into_id", PGUUID(as_uuid=True), nullable=True),
            schema=schema,
        )

    # Self-referential FK — candidates.merged_into_id → candidates.id
    if "fk_candidates_merged_into_id" not in _fk_names("candidates"):
        op.create_foreign_key(
            "fk_candidates_merged_into_id",
            "candidates",
            "candidates",
            ["merged_into_id"],
            ["id"],
            ondelete="SET NULL",
            source_schema=schema,
            referent_schema=schema,
        )

    if "ix_candidates_is_merged" not in _index_names("candidates"):
        op.create_index("ix_candidates_is_merged", "candidates", ["is_merged"], schema=schema)

    if "ix_candidates_merged_into_id" not in _index_names("candidates"):
        op.create_index("ix_candidates_merged_into_id", "candidates", ["merged_into_id"], schema=schema)


def downgrade() -> None:
    schema = _schema()
    try:
        op.drop_index("ix_candidates_merged_into_id", table_name="candidates", schema=schema)
    except Exception:
        pass
    try:
        op.drop_index("ix_candidates_is_merged", table_name="candidates", schema=schema)
    except Exception:
        pass
    try:
        op.drop_constraint("fk_candidates_merged_into_id", "candidates", type_="foreignkey", schema=schema)
    except Exception:
        pass
    try:
        op.drop_column("candidates", "merged_into_id", schema=schema)
    except Exception:
        pass
    try:
        op.drop_column("candidates", "is_merged", schema=schema)
    except Exception:
        pass
