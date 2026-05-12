"""Interview workspace: add interview_notes table; extend feedback with system_design/leadership scores.

Revision ID: 20260512_0004
Revises: 20260512_0003
Create Date: 2026-05-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260512_0004"
down_revision: str | None = "20260512_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _col_names(schema: str | None, table: str) -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns(table, schema=schema)}


def _table_exists(schema: str | None, table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names(schema=schema)


def upgrade() -> None:
    schema = get_settings().db_schema

    # ── Extend interview_feedback with 2 new score dimensions ───────────
    if _table_exists(schema, "interview_feedback"):
        existing = _col_names(schema, "interview_feedback")
        for col_name in ("system_design_score", "leadership_score"):
            if col_name not in existing:
                op.add_column(
                    "interview_feedback",
                    sa.Column(col_name, sa.Integer(), nullable=True),
                    schema=schema,
                )

    # ── Create interview_notes table ─────────────────────────────────────
    if not _table_exists(schema, "interview_notes"):
        interviews_ref = f"{schema}.interviews.id" if schema else "interviews.id"
        op.create_table(
            "interview_notes",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("interview_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("interviewer_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("section", sa.String(64), nullable=True),
            sa.Column("content", sa.Text(), nullable=False, server_default=""),
            sa.Column("autosaved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finalized", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["interview_id"],
                [interviews_ref],
                name="fk_interview_notes_interview_id",
                ondelete="CASCADE",
            ),
            schema=schema,
        )
        op.create_index("ix_interview_notes_interview_id", "interview_notes", ["interview_id"], schema=schema)
        op.create_index("ix_interview_notes_interviewer_id", "interview_notes", ["interviewer_id"], schema=schema)
        op.create_index("ix_interview_notes_organization_id", "interview_notes", ["organization_id"], schema=schema)


def downgrade() -> None:
    schema = get_settings().db_schema

    if _table_exists(schema, "interview_notes"):
        op.drop_table("interview_notes", schema=schema)

    if _table_exists(schema, "interview_feedback"):
        existing = _col_names(schema, "interview_feedback")
        for col in ("system_design_score", "leadership_score"):
            if col in existing:
                op.drop_column("interview_feedback", col, schema=schema)
