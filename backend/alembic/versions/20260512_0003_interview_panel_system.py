"""Interview panel system: extend interviews/participants/feedback tables;
add interviewer_profiles, interviewer_skills, interviewer_availability tables;
seed new RBAC permissions.

Revision ID: 20260512_0003
Revises: 20260512_0002
Create Date: 2026-05-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260512_0003"
down_revision: str | None = "20260512_0002"
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
        if "meeting_type" not in existing:
            op.add_column(
                "interviews",
                sa.Column("meeting_type", sa.String(32), nullable=True),
                schema=schema,
            )
        # Normalise existing status default to pending_panel (affects new rows only)
        # No data migration needed — existing scheduled rows stay scheduled.

    # ── Extend interview_participants ────────────────────────────────────
    if _table_exists(schema, "interview_participants"):
        existing = _col_names(schema, "interview_participants")
        if "organization_id" not in existing:
            op.add_column(
                "interview_participants",
                sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
                schema=schema,
            )
        if "participant_role" not in existing:
            op.add_column(
                "interview_participants",
                sa.Column(
                    "participant_role",
                    sa.String(32),
                    nullable=False,
                    server_default=sa.text("'panel'"),
                ),
                schema=schema,
            )
        if "status" not in existing:
            op.add_column(
                "interview_participants",
                sa.Column(
                    "status",
                    sa.String(32),
                    nullable=False,
                    server_default=sa.text("'accepted'"),
                ),
                schema=schema,
            )
        if "joined_at" not in existing:
            op.add_column(
                "interview_participants",
                sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
                schema=schema,
            )

    # ── Extend interview_feedback ────────────────────────────────────────
    if _table_exists(schema, "interview_feedback"):
        existing = _col_names(schema, "interview_feedback")
        for col_name in ("technical_score", "communication_score", "problem_solving_score", "culture_fit_score"):
            if col_name not in existing:
                op.add_column(
                    "interview_feedback",
                    sa.Column(col_name, sa.Integer(), nullable=True),
                    schema=schema,
                )
        if "submitted_at" not in existing:
            op.add_column(
                "interview_feedback",
                sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
                schema=schema,
            )

    # ── interviewer_profiles ────────────────────────────────────────────
    if not _table_exists(schema, "interviewer_profiles"):
        op.create_table(
            "interviewer_profiles",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("title", sa.String(255), nullable=True),
            sa.Column("department", sa.String(255), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("max_interviews_per_day", sa.Integer(), nullable=True),
            sa.Column("timezone", sa.String(64), nullable=True),
            sa.Column("bio", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            schema=schema,
        )
        op.create_index("ix_interviewer_profiles_org_id", "interviewer_profiles", ["organization_id"], schema=schema)
        op.create_index("ix_interviewer_profiles_user_id", "interviewer_profiles", ["user_id"], schema=schema)

    # ── interviewer_skills ──────────────────────────────────────────────
    if not _table_exists(schema, "interviewer_skills"):
        profiles_ref = f"{schema}.interviewer_profiles.id" if schema else "interviewer_profiles.id"
        op.create_table(
            "interviewer_skills",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("interviewer_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("skill", sa.String(128), nullable=False),
            sa.ForeignKeyConstraint(
                ["interviewer_profile_id"],
                [profiles_ref],
                name="fk_interviewer_skills_profile_id",
                ondelete="CASCADE",
            ),
            schema=schema,
        )
        op.create_index(
            "ix_interviewer_skills_profile_id",
            "interviewer_skills",
            ["interviewer_profile_id"],
            schema=schema,
        )

    # ── interviewer_availability ────────────────────────────────────────
    if not _table_exists(schema, "interviewer_availability"):
        profiles_ref = f"{schema}.interviewer_profiles.id" if schema else "interviewer_profiles.id"
        op.create_table(
            "interviewer_availability",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("interviewer_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("day_of_week", sa.Integer(), nullable=False),
            sa.Column("start_time", sa.Time(), nullable=False),
            sa.Column("end_time", sa.Time(), nullable=False),
            sa.Column("timezone", sa.String(64), nullable=True),
            sa.ForeignKeyConstraint(
                ["interviewer_profile_id"],
                [profiles_ref],
                name="fk_interviewer_availability_profile_id",
                ondelete="CASCADE",
            ),
            schema=schema,
        )
        op.create_index(
            "ix_interviewer_availability_profile_id",
            "interviewer_availability",
            ["interviewer_profile_id"],
            schema=schema,
        )

    # ── Seed new RBAC permissions ───────────────────────────────────────
    conn = op.get_bind()
    new_perms = ("interviews:claim", "interviews:panel")
    for perm_code in new_perms:
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

    for table in ("interviewer_availability", "interviewer_skills", "interviewer_profiles"):
        if _table_exists(schema, table):
            op.drop_table(table, schema=schema)

    if _table_exists(schema, "interview_feedback"):
        existing = _col_names(schema, "interview_feedback")
        for col in ("submitted_at", "culture_fit_score", "problem_solving_score", "communication_score", "technical_score"):
            if col in existing:
                op.drop_column("interview_feedback", col, schema=schema)

    if _table_exists(schema, "interview_participants"):
        existing = _col_names(schema, "interview_participants")
        for col in ("joined_at", "status", "participant_role", "organization_id"):
            if col in existing:
                op.drop_column("interview_participants", col, schema=schema)

    if _table_exists(schema, "interviews"):
        existing = _col_names(schema, "interviews")
        if "meeting_type" in existing:
            op.drop_column("interviews", "meeting_type", schema=schema)
