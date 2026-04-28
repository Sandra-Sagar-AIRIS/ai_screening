"""Add organization-level role permissions and client job access.

Revision ID: 20260423_0025
Revises: 20260423_0024
Create Date: 2026-04-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings
from app.core.permissions import ALL_PERMISSIONS

revision: str = "20260423_0025"
down_revision: str | None = "20260423_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROFILE_TYPE_CHECK = "ck_profiles_type_allowed"
PROFILE_TYPE_ALLOWED = ("internal", "client")


def _table_names(schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return set(inspector.get_table_names(schema=schema))


def _column_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table, schema=schema)}


def _check_constraint_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {constraint["name"] for constraint in inspector.get_check_constraints(table, schema=schema)}


def _seed_default_permissions(schema: str | None) -> None:
    schema_prefix = f"{schema}." if schema else ""
    quoted_permissions = ", ".join(f"('{permission}')" for permission in ALL_PERMISSIONS)
    op.execute(
        sa.text(
            f"""
            WITH permission_list(permission) AS (
              VALUES {quoted_permissions}
            )
            INSERT INTO {schema_prefix}role_permissions (organization_id, role, permission)
            SELECT o.id, 'admin', p.permission
            FROM {schema_prefix}organizations o
            CROSS JOIN permission_list p
            ON CONFLICT (organization_id, role, permission) DO NOTHING;
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            WITH permission_list(permission) AS (
              VALUES
                ('clients:read'),
                ('candidates:read'),
                ('jobs:read'),
                ('pipeline:read'),
                ('interviews:read')
            )
            INSERT INTO {schema_prefix}role_permissions (organization_id, role, permission)
            SELECT o.id, 'client_viewer', p.permission
            FROM {schema_prefix}organizations o
            CROSS JOIN permission_list p
            ON CONFLICT (organization_id, role, permission) DO NOTHING;
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            WITH permission_list(permission) AS (
              VALUES
                ('clients:create'),
                ('clients:read'),
                ('clients:update'),
                ('candidates:create'),
                ('candidates:read'),
                ('candidates:update'),
                ('jobs:create'),
                ('jobs:read'),
                ('jobs:update'),
                ('pipeline:create'),
                ('pipeline:read'),
                ('pipeline:update'),
                ('interviews:create'),
                ('interviews:read'),
                ('interviews:update')
            )
            INSERT INTO {schema_prefix}role_permissions (organization_id, role, permission)
            SELECT o.id, 'recruiter', p.permission
            FROM {schema_prefix}organizations o
            CROSS JOIN permission_list p
            ON CONFLICT (organization_id, role, permission) DO NOTHING;
            """
        )
    )


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    tables = _table_names(schema)
    profile_columns = _column_names("profiles", schema)
    profile_checks = _check_constraint_names("profiles", schema)

    if "type" not in profile_columns:
        op.add_column(
            "profiles",
            sa.Column("type", sa.String(length=32), nullable=False, server_default=sa.text("'internal'")),
            schema=schema,
        )

    if PROFILE_TYPE_CHECK not in profile_checks:
        op.create_check_constraint(
            PROFILE_TYPE_CHECK,
            "profiles",
            f"type IN {PROFILE_TYPE_ALLOWED}",
            schema=schema,
        )

    if "role_permissions" not in tables:
        op.create_table(
            "role_permissions",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("role", sa.String(length=64), nullable=False),
            sa.Column("permission", sa.String(length=128), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_role_permissions_organization_id"),
            sa.UniqueConstraint("organization_id", "role", "permission", name="uq_role_permissions_org_role_permission"),
            schema=schema,
        )
        op.create_index(
            "ix_role_permissions_organization_id",
            "role_permissions",
            ["organization_id"],
            unique=False,
            schema=schema,
        )
        op.create_index("ix_role_permissions_role", "role_permissions", ["role"], unique=False, schema=schema)
        op.create_index("ix_role_permissions_permission", "role_permissions", ["permission"], unique=False, schema=schema)

    if "client_job_access" not in tables:
        op.create_table(
            "client_job_access",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], name="fk_client_job_access_user_id"),
            sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name="fk_client_job_access_job_id"),
            sa.UniqueConstraint("user_id", "job_id", name="uq_client_job_access_user_job"),
            schema=schema,
        )
        op.create_index("ix_client_job_access_user_id", "client_job_access", ["user_id"], unique=False, schema=schema)
        op.create_index("ix_client_job_access_job_id", "client_job_access", ["job_id"], unique=False, schema=schema)

    _seed_default_permissions(schema)


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    tables = _table_names(schema)
    profile_columns = _column_names("profiles", schema)
    profile_checks = _check_constraint_names("profiles", schema)

    if "client_job_access" in tables:
        op.drop_index("ix_client_job_access_job_id", table_name="client_job_access", schema=schema)
        op.drop_index("ix_client_job_access_user_id", table_name="client_job_access", schema=schema)
        op.drop_table("client_job_access", schema=schema)

    if "role_permissions" in tables:
        op.drop_index("ix_role_permissions_permission", table_name="role_permissions", schema=schema)
        op.drop_index("ix_role_permissions_role", table_name="role_permissions", schema=schema)
        op.drop_index("ix_role_permissions_organization_id", table_name="role_permissions", schema=schema)
        op.drop_table("role_permissions", schema=schema)

    if PROFILE_TYPE_CHECK in profile_checks:
        op.drop_constraint(PROFILE_TYPE_CHECK, "profiles", type_="check", schema=schema)
    if "type" in profile_columns:
        op.drop_column("profiles", "type", schema=schema)
