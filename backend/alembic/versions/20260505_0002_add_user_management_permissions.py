"""Add users:update_role and users:delete permissions.

Revision ID: 20260505_0002
Revises: 20260505_0001
Create Date: 2026-05-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20260505_0002"
down_revision: str | None = "20260505_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS: tuple[tuple[str, str], ...] = (
    ("users:update_role", "Update Role"),
    ("users:delete", "Delete"),
)


def upgrade() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    schema = settings.db_schema
    schema_prefix = f"{schema}." if schema else ""
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names(schema=schema))
    if "permissions" not in tables or "role_permissions" not in tables or "organization_roles" not in tables:
        return

    for code, display_name in _PERMISSIONS:
        op.execute(
            sa.text(
                f"""
                INSERT INTO {schema_prefix}permissions (code, module, display_name)
                VALUES (:code, 'users', :display_name)
                ON CONFLICT (code) DO UPDATE
                SET module = EXCLUDED.module,
                    display_name = EXCLUDED.display_name;
                """
            ).bindparams(code=code, display_name=display_name)
        )

        op.execute(
            sa.text(
                f"""
                INSERT INTO {schema_prefix}role_permissions (organization_id, role_id, permission)
                SELECT r.organization_id, r.id, :code
                FROM {schema_prefix}organization_roles AS r
                WHERE lower(r.key) = 'admin'
                ON CONFLICT (organization_id, role_id, permission) DO NOTHING;
                """
            ).bindparams(code=code)
        )


def downgrade() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    schema = settings.db_schema
    schema_prefix = f"{schema}." if schema else ""
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names(schema=schema))
    if "permissions" not in tables or "role_permissions" not in tables:
        return

    codes = tuple(code for code, _ in _PERMISSIONS)
    op.execute(
        sa.text(
            f"DELETE FROM {schema_prefix}role_permissions WHERE permission IN :codes;"
        ).bindparams(sa.bindparam("codes", expanding=True, value=codes))
    )
    op.execute(
        sa.text(
            f"DELETE FROM {schema_prefix}permissions WHERE code IN :codes;"
        ).bindparams(sa.bindparam("codes", expanding=True, value=codes))
    )
