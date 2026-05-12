"""Extend interviews domain: add interview_type, duration, meeting fields,
created_by to interviews; create interview_participants and
interview_feedback tables; seed new RBAC permissions.

Revision ID: 20260512_0001
Revises: 20260511_0004
Create Date: 2026-05-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260512_0001"
down_revision: str | None = "20260511_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _col_names(schema: str | None, table: str) -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns(table, schema=schema)}


def _table_exists(schema: str | None, table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names(schema=schema)


def upgrade() -> None:
    schema = get_settings().db_schema

    # ── Extend interviews ───────────────────────────────────────────────
    if _table_exists(schema, "interviews"):
        existing = _col_names(schema, "interviews")

        if "interview_type" not in existing:
            op.add_column(
                "interviews",
                sa.Column("interview_type", sa.String(length=32), nullable=True),
                schema=schema,
            )
        if "duration_minutes" not in existing:
            op.add_column(
                "interviews",
                sa.Column("duration_minutes", sa.Integer(), nullable=True),
                schema=schema,
            )
        if "meeting_link" not in existing:
            op.add_column(
                "interviews",
                sa.Column("meeting_link", sa.String(length=512), nullable=True),
                schema=schema,
            )
        if "location" not in existing:
            op.add_column(
                "interviews",
                sa.Column("location", sa.String(length=255), nullable=True),
                schema=schema,
            )
        if "created_by" not in existing:
            op.add_column(
                "interviews",
                sa.Column(
                    "created_by",
                    postgresql.UUID(as_uuid=True),
                    nullable=True,
                ),
                schema=schema,
            )

    # ── interview_participants ──────────────────────────────────────────
    if not _table_exists(schema, "interview_participants"):
        op.create_table(
            "interview_participants",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("interview_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "role",
                sa.String(length=32),
                nullable=False,
                server_default=sa.text("'interviewer'"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["interview_id"],
                [f"{schema}.interviews.id" if schema else "interviews.id"],
                name="fk_interview_participants_interview_id",
                ondelete="CASCADE",
            ),
            schema=schema,
        )
        op.create_index(
            "ix_interview_participants_interview_id",
            "interview_participants",
            ["interview_id"],
            schema=schema,
        )
        op.create_index(
            "ix_interview_participants_user_id",
            "interview_participants",
            ["user_id"],
            schema=schema,
        )

    # ── interview_feedback ─────────────────────────────────────────────
    if not _table_exists(schema, "interview_feedback"):
        op.create_table(
            "interview_feedback",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("interview_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("rating", sa.Integer(), nullable=True),
            sa.Column("recommendation", sa.String(length=32), nullable=True),
            sa.Column("strengths", sa.Text(), nullable=True),
            sa.Column("weaknesses", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["interview_id"],
                [f"{schema}.interviews.id" if schema else "interviews.id"],
                name="fk_interview_feedback_interview_id",
                ondelete="CASCADE",
            ),
            schema=schema,
        )
        op.create_index(
            "ix_interview_feedback_interview_id",
            "interview_feedback",
            ["interview_id"],
            schema=schema,
        )

    # ── Seed new RBAC permissions ───────────────────────────────────────
    # Add interviews:delete and interviews:feedback to every role that
    # already has interviews:create (i.e. internal recruiting roles).
    # Uses raw SQL to stay migration-safe (no ORM dependency).
    conn = op.get_bind()
    new_perms = ("interviews:delete", "interviews:feedback")
    for perm_code in new_perms:
        # Upsert: only insert if the permission row doesn't exist yet.
        # Use :perm (SQLAlchemy sa.text bind syntax), NOT %(perm)s (psycopg driver syntax).
        conn.execute(
            sa.text(
                """
                INSERT INTO role_permissions (id, organization_id, role_id, permission)
                SELECT gen_random_uuid(), rp.organization_id, rp.role_id, CAST(:perm AS VARCHAR)
                FROM   role_permissions rp
                WHERE  rp.permission = 'interviews:create'
                  AND  NOT EXISTS (
                    SELECT 1
                    FROM   role_permissions x
                    WHERE  x.organization_id = rp.organization_id
                      AND  x.role_id = rp.role_id
                      AND  x.permission = CAST(:perm AS VARCHAR)
                  )
                """
            ),
            {"perm": perm_code},
        )


def downgrade() -> None:
    schema = get_settings().db_schema

    # Drop feedback table
    if _table_exists(schema, "interview_feedback"):
        op.drop_index("ix_interview_feedback_interview_id", table_name="interview_feedback", schema=schema)
        op.drop_table("interview_feedback", schema=schema)

    # Drop participants table
    if _table_exists(schema, "interview_participants"):
        op.drop_index("ix_interview_participants_user_id", table_name="interview_participants", schema=schema)
        op.drop_index("ix_interview_participants_interview_id", table_name="interview_participants", schema=schema)
        op.drop_table("interview_participants", schema=schema)

    # Remove added columns from interviews
    if _table_exists(schema, "interviews"):
        existing = _col_names(schema, "interviews")
        for col in ("created_by", "location", "meeting_link", "duration_minutes", "interview_type"):
            if col in existing:
                op.drop_column("interviews", col, schema=schema)
