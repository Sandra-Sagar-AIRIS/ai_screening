"""Seed ATS permissions and assign to admin/recruiter roles.

Revision ID: 4e30c8cdfed5
Revises: c418d80c8924
Create Date: 2026-05-07
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "4e30c8cdfed5"
down_revision: str | Sequence[str] | None = "c418d80c8924"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_PERMS: tuple[tuple[str, str, str], ...] = (
    ("ats:read", "ats", "ATS Read"),
    ("ats:rescore", "ats", "ATS Rescore"),
)


def upgrade() -> None:
    bind = op.get_bind()
    for code, module, display in _PERMS:
        bind.execute(
            sa.text(
                """
                INSERT INTO permissions (code, module, display_name)
                VALUES (:code, :module, :display_name)
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {"code": code, "module": module, "display_name": display},
        )
    bind.execute(
        sa.text(
            """
            INSERT INTO role_permissions (organization_id, role_id, permission)
            SELECT r.organization_id, r.id, p.permission
            FROM organization_roles r
            CROSS JOIN (VALUES ('ats:read'), ('ats:rescore')) AS p(permission)
            WHERE r.key IN ('admin', 'recruiter')
            ON CONFLICT (organization_id, role_id, permission) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM role_permissions WHERE permission IN ('ats:read', 'ats:rescore')")
    )
    bind.execute(
        sa.text("DELETE FROM permissions WHERE code IN ('ats:read', 'ats:rescore')")
    )

