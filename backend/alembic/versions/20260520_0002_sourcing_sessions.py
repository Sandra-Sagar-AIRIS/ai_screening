"""AI-SOURCE-001: Create sourcing_sessions and sourcing_results tables.

Revision ID: 20260520_0002
Revises: 20260520_0001
Create Date: 2026-05-20
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB, UUID as PGUUID

from app.core.config import get_settings

revision: str = "20260520_0002"
down_revision: str = "20260520_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SESSION_STATUS = ("pending", "running", "complete", "failed")
_RESULT_ACTION = ("pending", "shortlisted", "rejected", "imported")


def _schema() -> str | None:
    return get_settings().db_schema


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names(schema=_schema()))


def _index_names(table: str) -> set[str]:
    return {idx["name"] for idx in inspect(op.get_bind()).get_indexes(table, schema=_schema())}


def _ensure_enum(type_name: str, values: tuple[str, ...]) -> None:
    quoted = ", ".join(repr(v) for v in values)
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{type_name}') THEN
                    CREATE TYPE {type_name} AS ENUM ({quoted});
                END IF;
            END $$;
            """
        )
    )


def _ensure_index(name: str, table: str, columns: list[str]) -> None:
    if name in _index_names(table):
        return
    op.create_index(name, table, columns, schema=_schema())


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    _ensure_enum("sourcing_session_status", _SESSION_STATUS)
    _ensure_enum("sourcing_result_action", _RESULT_ACTION)

    session_status_enum = ENUM(
        *_SESSION_STATUS,
        name="sourcing_session_status",
        create_type=False,
    )
    result_action_enum = ENUM(
        *_RESULT_ACTION,
        name="sourcing_result_action",
        create_type=False,
    )

    tables = _table_names()

    if "sourcing_sessions" not in tables:
        op.create_table(
            "sourcing_sessions",
            sa.Column(
                "id",
                PGUUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "organization_id",
                PGUUID(as_uuid=True),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("job_id", PGUUID(as_uuid=True), nullable=True),
            sa.Column(
                "created_by",
                PGUUID(as_uuid=True),
                sa.ForeignKey("profiles.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "status",
                session_status_enum,
                nullable=False,
                server_default=sa.text("'pending'"),
            ),
            sa.Column("query_snapshot", JSONB, nullable=True),
            sa.Column("providers_used", ARRAY(sa.String), nullable=True),
            sa.Column("total_results", sa.Integer, nullable=False, server_default="0"),
            sa.Column("error_detail", sa.Text, nullable=True),
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
            schema=_schema(),
        )

    _ensure_index("ix_sourcing_sessions_organization_id", "sourcing_sessions", ["organization_id"])
    _ensure_index("ix_sourcing_sessions_job_id", "sourcing_sessions", ["job_id"])
    _ensure_index("ix_sourcing_sessions_created_by", "sourcing_sessions", ["created_by"])
    _ensure_index("ix_sourcing_sessions_status", "sourcing_sessions", ["status"])

    if "sourcing_results" not in tables:
        op.create_table(
            "sourcing_results",
            sa.Column(
                "id",
                PGUUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "session_id",
                PGUUID(as_uuid=True),
                sa.ForeignKey("sourcing_sessions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("organization_id", PGUUID(as_uuid=True), nullable=False),
            sa.Column("external_id", sa.String(255), nullable=True),
            sa.Column("source", sa.String(64), nullable=False),
            sa.Column("first_name", sa.String(100), nullable=True),
            sa.Column("last_name", sa.String(100), nullable=True),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("phone", sa.String(50), nullable=True),
            sa.Column("location", sa.String(255), nullable=True),
            sa.Column("title", sa.String(255), nullable=True),
            sa.Column("skills", ARRAY(sa.String), nullable=True),
            sa.Column("ats_score", sa.Float, nullable=True),
            sa.Column("ats_tier", sa.String(32), nullable=True),
            sa.Column("semantic_score", sa.Float, nullable=True),
            sa.Column("recruiter_summary", sa.Text, nullable=True),
            sa.Column("matched_skills", ARRAY(sa.String), nullable=True),
            sa.Column(
                "action",
                result_action_enum,
                nullable=False,
                server_default=sa.text("'pending'"),
            ),
            sa.Column("reject_reason", sa.Text, nullable=True),
            sa.Column(
                "candidate_id",
                PGUUID(as_uuid=True),
                sa.ForeignKey("candidates.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("is_duplicate", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("raw_data", JSONB, nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            schema=_schema(),
        )

    _ensure_index("ix_sourcing_results_session_id", "sourcing_results", ["session_id"])
    _ensure_index("ix_sourcing_results_organization_id", "sourcing_results", ["organization_id"])
    _ensure_index("ix_sourcing_results_action", "sourcing_results", ["action"])
    _ensure_index("ix_sourcing_results_email", "sourcing_results", ["email"])
    _ensure_index(
        "ix_sourcing_results_org_action",
        "sourcing_results",
        ["organization_id", "action"],
    )


def downgrade() -> None:
    schema = _schema()
    tables = _table_names()
    if "sourcing_results" in tables:
        op.drop_table("sourcing_results", schema=schema)
    if "sourcing_sessions" in tables:
        op.drop_table("sourcing_sessions", schema=schema)
    op.execute(sa.text("DROP TYPE IF EXISTS sourcing_result_action"))
    op.execute(sa.text("DROP TYPE IF EXISTS sourcing_session_status"))
