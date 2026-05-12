"""Repair missing communication hub tables.

Revision ID: 20260512_0006
Revises: 20260512_0005
Create Date: 2026-05-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260512_0006"
down_revision: str | None = "20260512_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_exists(indexes: set[str], name: str) -> bool:
    return name in indexes


def upgrade() -> None:
    schema = get_settings().db_schema
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names(schema=schema))

    if "comm_connections" not in tables:
        op.create_table(
            "comm_connections",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("provider", sa.String(24), nullable=False),
            sa.Column("channel", sa.String(24), nullable=False, server_default="email"),
            sa.Column("external_account_id", sa.String(255), nullable=False),
            sa.Column("external_account_email", sa.String(320), nullable=True),
            sa.Column("access_token_encrypted", sa.Text(), nullable=True),
            sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
            sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="connected"),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                "org_id",
                "workspace_id",
                "provider",
                "external_account_id",
                name="uq_comm_connections_account_provider",
            ),
            schema=schema,
        )
        op.create_index(
            "ix_comm_connections_org_workspace_provider",
            "comm_connections",
            ["org_id", "workspace_id", "provider"],
            schema=schema,
        )
    else:
        indexes = {idx["name"] for idx in inspector.get_indexes("comm_connections", schema=schema)}
        if not _index_exists(indexes, "ix_comm_connections_org_workspace_provider"):
            op.create_index(
                "ix_comm_connections_org_workspace_provider",
                "comm_connections",
                ["org_id", "workspace_id", "provider"],
                schema=schema,
            )

    tables = set(inspector.get_table_names(schema=schema))
    if "comm_templates" not in tables:
        op.create_table(
            "comm_templates",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("channel", sa.String(24), nullable=False, server_default="email"),
            sa.Column("provider", sa.String(24), nullable=True),
            sa.Column("name", sa.String(140), nullable=False),
            sa.Column("category", sa.String(80), nullable=True),
            sa.Column("subject_template", sa.String(255), nullable=True),
            sa.Column("body_template", sa.Text(), nullable=False),
            sa.Column("placeholders", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("org_id", "workspace_id", "channel", "name", name="uq_comm_templates_name_per_channel"),
            schema=schema,
        )
        op.create_index(
            "ix_comm_templates_org_workspace_channel",
            "comm_templates",
            ["org_id", "workspace_id", "channel"],
            schema=schema,
        )
        op.create_index("ix_comm_templates_category", "comm_templates", ["category"], schema=schema)
    else:
        cols = {c["name"] for c in inspector.get_columns("comm_templates", schema=schema)}
        if "category" not in cols:
            op.add_column("comm_templates", sa.Column("category", sa.String(80), nullable=True), schema=schema)
        indexes = {idx["name"] for idx in inspector.get_indexes("comm_templates", schema=schema)}
        if not _index_exists(indexes, "ix_comm_templates_org_workspace_channel"):
            op.create_index(
                "ix_comm_templates_org_workspace_channel",
                "comm_templates",
                ["org_id", "workspace_id", "channel"],
                schema=schema,
            )
        if not _index_exists(indexes, "ix_comm_templates_category"):
            op.create_index("ix_comm_templates_category", "comm_templates", ["category"], schema=schema)

    tables = set(inspector.get_table_names(schema=schema))
    if "comm_messages" not in tables:
        op.create_table(
            "comm_messages",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("channel", sa.String(24), nullable=False, server_default="email"),
            sa.Column("provider", sa.String(24), nullable=False),
            sa.Column("direction", sa.String(24), nullable=False, server_default="outbound"),
            sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
            sa.Column("to_address", sa.String(320), nullable=True),
            sa.Column("from_address", sa.String(320), nullable=True),
            sa.Column("subject", sa.String(255), nullable=True),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column("attachments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("provider_message_id", sa.String(255), nullable=True),
            sa.Column("idempotency_key", sa.String(120), nullable=True),
            sa.Column("failure_reason", sa.Text(), nullable=True),
            sa.Column("sent_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["template_id"], ["comm_templates.id"]),
            sa.UniqueConstraint(
                "org_id",
                "workspace_id",
                "provider",
                "provider_message_id",
                name="uq_comm_messages_provider_message_id",
            ),
            schema=schema,
        )
        op.create_index(
            "ix_comm_messages_org_workspace_candidate_created",
            "comm_messages",
            ["org_id", "workspace_id", "candidate_id", "created_at"],
            schema=schema,
        )
        op.create_index(
            "ix_comm_messages_org_workspace_status",
            "comm_messages",
            ["org_id", "workspace_id", "status"],
            schema=schema,
        )
        op.create_index("ix_comm_messages_idempotency_key", "comm_messages", ["idempotency_key"], schema=schema)
    else:
        cols = {c["name"] for c in inspector.get_columns("comm_messages", schema=schema)}
        if "attachments" not in cols:
            op.add_column(
                "comm_messages",
                sa.Column("attachments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
                schema=schema,
            )

    tables = set(inspector.get_table_names(schema=schema))
    if "comm_message_events" not in tables:
        op.create_table(
            "comm_message_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("event_type", sa.String(64), nullable=False),
            sa.Column("provider_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["message_id"], ["comm_messages.id"], ondelete="CASCADE"),
            schema=schema,
        )
        op.create_index(
            "ix_comm_message_events_message_created",
            "comm_message_events",
            ["message_id", "created_at"],
            schema=schema,
        )

    tables = set(inspector.get_table_names(schema=schema))
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

    for table_name in ("comm_reminders", "comm_message_events", "comm_messages", "comm_templates", "comm_connections"):
        if table_name in tables:
            op.drop_table(table_name, schema=schema)
