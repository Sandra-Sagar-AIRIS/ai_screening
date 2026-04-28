"""Add invites table for organization user invites.

Revision ID: 20260427_0026
Revises: ae7739ae1a2e
Create Date: 2026-04-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260427_0026"
down_revision: str | None = "ae7739ae1a2e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INVITE_STATUS_CHECK = "ck_invites_status_allowed"
INVITE_STATUS_ALLOWED = ("pending", "accepted")


def _table_names(schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return set(inspector.get_table_names(schema=schema))


def _check_constraint_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {constraint["name"] for constraint in inspector.get_check_constraints(table, schema=schema)}


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    tables = _table_names(schema)

    if "invites" not in tables:
        op.create_table(
            "invites",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("token", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'pending'")),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_invites_organization_id"),
            sa.UniqueConstraint("token", name="uq_invites_token"),
            schema=schema,
        )
        op.create_index("ix_invites_email", "invites", ["email"], unique=False, schema=schema)
        op.create_index("ix_invites_organization_id", "invites", ["organization_id"], unique=False, schema=schema)
        op.create_index("ix_invites_role", "invites", ["role"], unique=False, schema=schema)
        op.create_index("ix_invites_token", "invites", ["token"], unique=True, schema=schema)
        op.create_index("ix_invites_expires_at", "invites", ["expires_at"], unique=False, schema=schema)

    checks = _check_constraint_names("invites", schema) if "invites" in _table_names(schema) else set()
    if INVITE_STATUS_CHECK not in checks:
        op.create_check_constraint(
            INVITE_STATUS_CHECK,
            "invites",
            f"status IN {INVITE_STATUS_ALLOWED}",
            schema=schema,
        )


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    tables = _table_names(schema)

    if "invites" in tables:
        checks = _check_constraint_names("invites", schema)
        if INVITE_STATUS_CHECK in checks:
            op.drop_constraint(INVITE_STATUS_CHECK, "invites", type_="check", schema=schema)
        op.drop_index("ix_invites_expires_at", table_name="invites", schema=schema)
        op.drop_index("ix_invites_token", table_name="invites", schema=schema)
        op.drop_index("ix_invites_role", table_name="invites", schema=schema)
        op.drop_index("ix_invites_organization_id", table_name="invites", schema=schema)
        op.drop_index("ix_invites_email", table_name="invites", schema=schema)
        op.drop_table("invites", schema=schema)
