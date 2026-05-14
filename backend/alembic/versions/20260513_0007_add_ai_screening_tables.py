"""Add AI screening tables.

Revision ID: 20260513_0007
Revises: 20260512_0006
Create Date: 2026-05-13

Tables created:
  ai_screenings              — top-level screening session
  ai_screening_questions     — AI-generated questions
  ai_screening_answers       — candidate answers (recruiter-entered)
  ai_screening_evaluations   — per-answer AI evaluations
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260513_0007"
down_revision: str | None = "20260512_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    schema = get_settings().db_schema
    inspector = inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names(schema=schema))

    # ── ai_screenings ─────────────────────────────────────────────────────────
    if "ai_screenings" not in existing_tables:
        op.create_table(
            "ai_screenings",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "candidate_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("candidates.id"),
                nullable=False,
            ),
            sa.Column(
                "job_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("jobs.id"),
                nullable=True,
            ),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("screening_type", sa.String(32), nullable=False, server_default="technical"),
            sa.Column("ai_model", sa.String(64), nullable=True),
            sa.Column("overall_score", sa.Numeric(5, 2), nullable=True),
            sa.Column("communication_score", sa.Numeric(5, 2), nullable=True),
            sa.Column("technical_score", sa.Numeric(5, 2), nullable=True),
            sa.Column("confidence_score", sa.Numeric(5, 2), nullable=True),
            sa.Column("recommendation", sa.String(32), nullable=True),
            sa.Column("ai_summary", sa.Text(), nullable=True),
            sa.Column("recruiter_summary", sa.Text(), nullable=True),
            sa.Column("recruiter_decision", sa.String(32), nullable=True),
            sa.Column("recruiter_notes", sa.Text(), nullable=True),
            sa.Column(
                "generation_context",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
            sa.Column("prompt_tokens_used", sa.Integer(), nullable=True),
            sa.Column("completion_tokens_used", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            schema=schema,
        )
        op.create_index(
            "ix_ai_screenings_organization_id",
            "ai_screenings",
            ["organization_id"],
            schema=schema,
        )
        op.create_index(
            "ix_ai_screenings_candidate_id",
            "ai_screenings",
            ["candidate_id"],
            schema=schema,
        )
        op.create_index(
            "ix_ai_screenings_job_id",
            "ai_screenings",
            ["job_id"],
            schema=schema,
        )
        op.create_index(
            "ix_ai_screenings_status",
            "ai_screenings",
            ["status"],
            schema=schema,
        )

    # ── ai_screening_questions ────────────────────────────────────────────────
    if "ai_screening_questions" not in existing_tables:
        op.create_table(
            "ai_screening_questions",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "screening_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("ai_screenings.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("category", sa.String(64), nullable=False),
            sa.Column("difficulty", sa.String(16), nullable=False, server_default="medium"),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column(
                "expected_signals",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
            sa.Column(
                "generated_by_ai",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            schema=schema,
        )
        op.create_index(
            "ix_ai_screening_questions_screening_id",
            "ai_screening_questions",
            ["screening_id"],
            schema=schema,
        )

    # ── ai_screening_answers ──────────────────────────────────────────────────
    if "ai_screening_answers" not in existing_tables:
        op.create_table(
            "ai_screening_answers",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "screening_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("ai_screenings.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "question_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("ai_screening_questions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("answer_text", sa.Text(), nullable=False),
            sa.Column(
                "recruiter_entered",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column("source_type", sa.String(32), nullable=False, server_default="manual"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            schema=schema,
        )
        op.create_index(
            "ix_ai_screening_answers_screening_id",
            "ai_screening_answers",
            ["screening_id"],
            schema=schema,
        )
        op.create_index(
            "ix_ai_screening_answers_question_id",
            "ai_screening_answers",
            ["question_id"],
            schema=schema,
        )

    # ── ai_screening_evaluations ──────────────────────────────────────────────
    if "ai_screening_evaluations" not in existing_tables:
        op.create_table(
            "ai_screening_evaluations",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "screening_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("ai_screenings.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "question_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("ai_screening_questions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("ai_score", sa.Integer(), nullable=True),
            sa.Column("communication_rating", sa.Integer(), nullable=True),
            sa.Column("technical_rating", sa.Integer(), nullable=True),
            sa.Column(
                "strengths",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
            sa.Column(
                "concerns",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
            sa.Column("reasoning", sa.Text(), nullable=True),
            sa.Column("follow_up_suggestion", sa.Text(), nullable=True),
            sa.Column("confidence", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            schema=schema,
        )
        op.create_index(
            "ix_ai_screening_evaluations_screening_id",
            "ai_screening_evaluations",
            ["screening_id"],
            schema=schema,
        )
        op.create_index(
            "ix_ai_screening_evaluations_question_id",
            "ai_screening_evaluations",
            ["question_id"],
            schema=schema,
        )


def downgrade() -> None:
    schema = get_settings().db_schema
    for table in [
        "ai_screening_evaluations",
        "ai_screening_answers",
        "ai_screening_questions",
        "ai_screenings",
    ]:
        op.drop_table(table, schema=schema)
