"""WS-002: Client Workspace — add deleted_at/deleted_by to clients; create client_recruiter_assignments;
add partial unique index on (organization_id, lower(name)) WHERE NOT is_deleted.

Revision ID: 20260520_0001
Revises: 20260519_0006
Create Date: 2026-05-20
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "20260520_0001"
down_revision: str = "20260519_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── clients: add soft-delete tracking columns ─────────────────────────────
    op.add_column("clients", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clients", sa.Column("deleted_by", PGUUID(as_uuid=True), nullable=True))
    op.create_index("ix_clients_deleted_at", "clients", ["deleted_at"])

    # Partial unique index: org+name must be unique among non-deleted clients.
    op.create_index(
        "uq_clients_org_name_active",
        "clients",
        ["organization_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    # ── client_recruiter_assignments ──────────────────────────────────────────
    op.create_table(
        "client_recruiter_assignments",
        sa.Column(
            "id",
            PGUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "client_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recruiter_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("assigned_by", PGUUID(as_uuid=True), nullable=True),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("client_id", "recruiter_id", name="uq_client_recruiter"),
    )
    op.create_index("ix_cra_client_id", "client_recruiter_assignments", ["client_id"])
    op.create_index("ix_cra_recruiter_id", "client_recruiter_assignments", ["recruiter_id"])


def downgrade() -> None:
    op.drop_table("client_recruiter_assignments")
    op.drop_index("uq_clients_org_name_active", table_name="clients")
    op.drop_index("ix_clients_deleted_at", table_name="clients")
    op.drop_column("clients", "deleted_by")
    op.drop_column("clients", "deleted_at")
