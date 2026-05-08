"""Add candidate parse_status, parse_error, parsed_at columns.

Revision ID: 607b31166d1f
Revises: 20260506_0001
Create Date: 2026-05-07
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "607b31166d1f"
down_revision: str | Sequence[str] | None = "20260506_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "candidates" not in tables:
        return
    existing = {col["name"] for col in inspector.get_columns("candidates")}

    if "parse_status" not in existing:
        op.add_column(
            "candidates",
            sa.Column(
                "parse_status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'pending'"),
            ),
        )
    if "parse_error" not in existing:
        op.add_column(
            "candidates",
            sa.Column("parse_error", sa.Text(), nullable=True),
        )
    if "parsed_at" not in existing:
        op.add_column(
            "candidates",
            sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        )

    indexes = {idx["name"] for idx in inspector.get_indexes("candidates")}
    if "ix_candidates_parse_status" not in indexes:
        op.create_index(
            "ix_candidates_parse_status",
            "candidates",
            ["parse_status"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "candidates" not in tables:
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("candidates")}
    if "ix_candidates_parse_status" in indexes:
        op.drop_index("ix_candidates_parse_status", table_name="candidates")

    existing = {col["name"] for col in inspector.get_columns("candidates")}
    if "parsed_at" in existing:
        op.drop_column("candidates", "parsed_at")
    if "parse_error" in existing:
        op.drop_column("candidates", "parse_error")
    if "parse_status" in existing:
        op.drop_column("candidates", "parse_status")
