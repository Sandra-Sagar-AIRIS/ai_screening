"""Add pipeline:read (and pipeline:create) to recruiter role for existing orgs.

Revision ID: 20260505_0001
Revises: 4deaa48d319f
Create Date: 2026-05-05

New signups already get these via signup_permissions._RECRUITER_DEFAULTS; this backfills tenants
seeded earlier when recruiters only had pipeline:update.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20260505_0001"
down_revision: str | None = "4deaa48d319f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RECRUITER_PIPELINE_PERMS: tuple[str, ...] = ("pipeline:read", "pipeline:create")


def upgrade() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    schema = settings.db_schema
    schema_prefix = f"{schema}." if schema else ""
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names(schema=schema))
    if "role_permissions" not in tables or "organization_roles" not in tables:
        return

    for perm in _RECRUITER_PIPELINE_PERMS:
        op.execute(
            sa.text(
                f"""
                INSERT INTO {schema_prefix}role_permissions (organization_id, role_id, permission)
                SELECT r.organization_id, r.id, '{perm}'
                FROM {schema_prefix}organization_roles r
                WHERE lower(r.key) = 'recruiter'
                ON CONFLICT (organization_id, role_id, permission) DO NOTHING;
                """
            )
        )


def downgrade() -> None:
    # Irreversible by design:
    # we cannot safely distinguish rows inserted by this migration from rows that may have
    # existed before, so deleting would risk removing legitimate pre-existing permissions.
    raise NotImplementedError("Downgrade is intentionally unsupported for this data backfill migration.")
