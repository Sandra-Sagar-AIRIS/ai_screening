"""Add meeting_provider, started_at, ended_at to interviews.

Revision ID: 20260512_0005
Revises: 20260512_0004
Create Date: 2026-05-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from app.core.config import get_settings

revision: str = "20260512_0005"
down_revision: str | None = "20260512_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _col_names(schema: str | None, table: str) -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns(table, schema=schema)}


def _table_exists(schema: str | None, table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names(schema=schema)


def upgrade() -> None:
    schema = get_settings().db_schema

    if _table_exists(schema, "interviews"):
        existing = _col_names(schema, "interviews")
        if "meeting_provider" not in existing:
            op.add_column(
                "interviews",
                sa.Column("meeting_provider", sa.String(32), nullable=True),
                schema=schema,
            )
        if "started_at" not in existing:
            op.add_column(
                "interviews",
                sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
                schema=schema,
            )
        if "ended_at" not in existing:
            op.add_column(
                "interviews",
                sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
                schema=schema,
            )


def downgrade() -> None:
    schema = get_settings().db_schema

    if _table_exists(schema, "interviews"):
        existing = _col_names(schema, "interviews")
        for col in ("meeting_provider", "started_at", "ended_at"):
            if col in existing:
                op.drop_column("interviews", col, schema=schema)
