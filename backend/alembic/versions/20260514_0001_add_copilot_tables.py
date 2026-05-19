"""Add AI Interview Copilot tables.

Revision ID: 20260514_0001
Revises: 20260513_0007
Create Date: 2026-05-14

Tables created:
  interview_copilot_sessions    — one session per interview (lifecycle, summary, skill coverage)
  interview_transcript_segments — growing log of transcript utterances
  interview_ai_suggestions      — AI-generated follow-up question suggestions
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260514_0001"
down_revision: str | None = "20260513_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _schema_prefix() -> str:
    schema = get_settings().db_schema
    return f"{schema}." if schema else ""


def _table_exists(connection, table_name: str) -> bool:
    schema = get_settings().db_schema or None
    inspector = inspect(connection)
    return inspector.has_table(table_name, schema=schema)


def upgrade() -> None:
    schema = get_settings().db_schema
    bind = op.get_bind()

    # ── interview_copilot_sessions ────────────────────────────────────────────
    if not _table_exists(bind, "interview_copilot_sessions"):
        op.create_table(
            "interview_copilot_sessions",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "interview_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("interviews.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
            sa.Column("summary", postgresql.JSONB, nullable=True),
            sa.Column("skills_covered", postgresql.JSONB, nullable=True),
            sa.Column("prompt_tokens_used", sa.Integer, nullable=False, server_default="0"),
            sa.Column("completion_tokens_used", sa.Integer, nullable=False, server_default="0"),
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
            sa.Column("summarized_at", sa.DateTime(timezone=True), nullable=True),
            schema=schema,
        )
        op.create_index(
            "ix_interview_copilot_sessions_organization_id",
            "interview_copilot_sessions",
            ["organization_id"],
            schema=schema,
        )
        op.create_index(
            "ix_interview_copilot_sessions_interview_id",
            "interview_copilot_sessions",
            ["interview_id"],
            schema=schema,
        )
        op.create_index(
            "ix_interview_copilot_sessions_status",
            "interview_copilot_sessions",
            ["status"],
            schema=schema,
        )

    # ── interview_transcript_segments ─────────────────────────────────────────
    if not _table_exists(bind, "interview_transcript_segments"):
        op.create_table(
            "interview_transcript_segments",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column(
                "session_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("interview_copilot_sessions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "interview_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("interviews.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("speaker", sa.String(32), nullable=False, server_default="unknown"),
            sa.Column("content", sa.Text, nullable=False),
            sa.Column("offset_ms", sa.Integer, nullable=True),
            sa.Column("duration_ms", sa.Integer, nullable=True),
            sa.Column("source", sa.String(32), nullable=False, server_default="manual"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            schema=schema,
        )
        op.create_index(
            "ix_interview_transcript_segments_session_id",
            "interview_transcript_segments",
            ["session_id"],
            schema=schema,
        )
        op.create_index(
            "ix_interview_transcript_segments_interview_id",
            "interview_transcript_segments",
            ["interview_id"],
            schema=schema,
        )
        op.create_index(
            "ix_interview_transcript_segments_organization_id",
            "interview_transcript_segments",
            ["organization_id"],
            schema=schema,
        )
        op.create_index(
            "ix_interview_transcript_segments_created_at",
            "interview_transcript_segments",
            ["created_at"],
            schema=schema,
        )

    # ── interview_ai_suggestions ──────────────────────────────────────────────
    if not _table_exists(bind, "interview_ai_suggestions"):
        op.create_table(
            "interview_ai_suggestions",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column(
                "session_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("interview_copilot_sessions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "interview_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("interviews.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "suggestion_type",
                sa.String(32),
                nullable=False,
                server_default="follow_up",
            ),
            sa.Column("question_text", sa.Text, nullable=False),
            sa.Column("rationale", sa.Text, nullable=True),
            sa.Column("target_skills", postgresql.JSONB, nullable=True),
            sa.Column("difficulty", sa.String(16), nullable=True),
            sa.Column(
                "used",
                sa.Boolean,
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "dismissed",
                sa.Boolean,
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            schema=schema,
        )
        op.create_index(
            "ix_interview_ai_suggestions_session_id",
            "interview_ai_suggestions",
            ["session_id"],
            schema=schema,
        )
        op.create_index(
            "ix_interview_ai_suggestions_interview_id",
            "interview_ai_suggestions",
            ["interview_id"],
            schema=schema,
        )
        op.create_index(
            "ix_interview_ai_suggestions_organization_id",
            "interview_ai_suggestions",
            ["organization_id"],
            schema=schema,
        )
        op.create_index(
            "ix_interview_ai_suggestions_created_at",
            "interview_ai_suggestions",
            ["created_at"],
            schema=schema,
        )


def downgrade() -> None:
    schema = get_settings().db_schema
    bind = op.get_bind()

    for table in (
        "interview_ai_suggestions",
        "interview_transcript_segments",
        "interview_copilot_sessions",
    ):
        if _table_exists(bind, table):
            op.drop_table(table, schema=schema)
