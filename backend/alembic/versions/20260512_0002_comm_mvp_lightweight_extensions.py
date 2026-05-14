"""Lightweight Communication Hub MVP extensions.

Revision ID: 20260512_comm_0002
Revises: 20260512_comm_0001
Create Date: 2026-05-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260512_comm_0002"
down_revision: str | None = "20260512_comm_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    schema = get_settings().db_schema
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names(schema=schema))

    if "comm_templates" in tables:
        cols = {c["name"] for c in inspector.get_columns("comm_templates", schema=schema)}
        if "category" not in cols:
            op.add_column("comm_templates", sa.Column("category", sa.String(length=80), nullable=True), schema=schema)
            op.create_index("ix_comm_templates_category", "comm_templates", ["category"], schema=schema)

    if "comm_messages" in tables:
        cols = {c["name"] for c in inspector.get_columns("comm_messages", schema=schema)}
        if "attachments" not in cols:
            op.add_column(
                "comm_messages",
                sa.Column("attachments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
                schema=schema,
            )

    if "comm_reminders" not in tables:
        op.create_table(
            "comm_reminders",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("channel", sa.String(24), nullable=False, server_default="email"),
            sa.Column("provider", sa.String(24), nullable=False),
            sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("to_address", sa.String(320), nullable=True),
            sa.Column("subject", sa.String(255), nullable=True),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column("template_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
            sa.Column("failure_reason", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["template_id"], ["comm_templates.id"]),
            schema=schema,
        )
        op.create_index(
            "ix_comm_reminders_org_workspace_due",
            "comm_reminders",
            ["org_id", "workspace_id", "scheduled_for"],
            schema=schema,
        )
        op.create_index(
            "ix_comm_reminders_status_scheduled",
            "comm_reminders",
            ["status", "scheduled_for"],
            schema=schema,
        )


def downgrade() -> None:
    schema = get_settings().db_schema
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names(schema=schema))

    if "comm_reminders" in tables:
        op.drop_table("comm_reminders", schema=schema)

    if "comm_messages" in tables:
        cols = {c["name"] for c in inspector.get_columns("comm_messages", schema=schema)}
        if "attachments" in cols:
            op.drop_column("comm_messages", "attachments", schema=schema)

    if "comm_templates" in tables:
        cols = {c["name"] for c in inspector.get_columns("comm_templates", schema=schema)}
        if "category" in cols:
            indexes = {idx["name"] for idx in inspector.get_indexes("comm_templates", schema=schema)}
            if "ix_comm_templates_category" in indexes:
                op.drop_index("ix_comm_templates_category", table_name="comm_templates", schema=schema)
            op.drop_column("comm_templates", "category", schema=schema)
