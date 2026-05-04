"""Organization roles (dynamic RBAC), enrich permissions catalog, drop user overrides.

Revision ID: 20260430_0001
Revises: 20260429_0003
Create Date: 2026-04-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "20260430_0001"
down_revision: str | None = "20260429_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names(schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return set(inspector.get_table_names(schema=schema))


def _column_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table, schema=schema)}


def _check_constraint_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {constraint["name"] for constraint in inspector.get_check_constraints(table, schema=schema)}


def upgrade() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    schema = settings.db_schema
    schema_prefix = f"{schema}." if schema else ""
    tables = _table_names(schema)

    # --- 1) Drop user permission overrides (feature removed) ---
    if "user_permission_overrides" in tables:
        op.drop_table("user_permission_overrides", schema=schema)
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'permission_effect') THEN
                    DROP TYPE permission_effect;
                END IF;
            END $$;
            """
        )
    )

    # --- 2) Enrich permissions catalog for UI ---
    perm_cols = _column_names("permissions", schema) if "permissions" in _table_names(schema) else set()
    if "permissions" in tables:
        if "module" not in perm_cols:
            op.add_column(
                "permissions",
                sa.Column("module", sa.String(length=128), nullable=True),
                schema=schema,
            )
        if "display_name" not in perm_cols:
            op.add_column(
                "permissions",
                sa.Column("display_name", sa.String(length=255), nullable=True),
                schema=schema,
            )
        op.execute(
            sa.text(
                f"""
                UPDATE {schema_prefix}permissions
                SET
                  module = NULLIF(split_part(lower(code), ':', 1), ''),
                  display_name = CASE
                    WHEN strpos(code, ':') > 0 THEN
                      trim(initcap(replace(split_part(lower(code), ':', 2), '_', ' ')))
                    ELSE trim(initcap(replace(lower(code), '_', ' ')))
                  END;
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                UPDATE {schema_prefix}permissions
                SET module = coalesce(module, 'general'),
                    display_name = coalesce(display_name, code);
                """
            )
        )
        op.alter_column("permissions", "module", existing_type=sa.String(length=128), nullable=False, schema=schema)
        op.alter_column("permissions", "display_name", existing_type=sa.String(length=255), nullable=False, schema=schema)

    # --- 3) organization_roles ---
    if "organization_roles" not in tables:
        op.create_table(
            "organization_roles",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("key", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(
                ["organization_id"],
                ["organizations.id"],
                name="fk_organization_roles_organization_id",
            ),
            sa.UniqueConstraint("organization_id", "key", name="uq_organization_roles_org_key"),
            schema=schema,
        )
        op.create_index(
            "ix_organization_roles_organization_id",
            "organization_roles",
            ["organization_id"],
            unique=False,
            schema=schema,
        )
        op.create_index(
            "ix_organization_roles_key",
            "organization_roles",
            ["key"],
            unique=False,
            schema=schema,
        )

    # Seed system roles per organization (idempotent).
    op.execute(
        sa.text(
            f"""
            INSERT INTO {schema_prefix}organization_roles (organization_id, name, key)
            SELECT o.id, v.name, v.key
            FROM {schema_prefix}organizations o
            CROSS JOIN (
                VALUES
                    ('Admin', 'admin'),
                    ('Recruiter', 'recruiter'),
                    ('Client viewer', 'client_viewer'),
                    ('Vendor', 'vendor')
            ) AS v(name, key)
            ON CONFLICT (organization_id, key) DO NOTHING;
            """
        )
    )

    # --- 4) role_permissions: add role_id, backfill, drop legacy `role` column ---
    rp_cols = _column_names("role_permissions", schema)
    if "role_permissions" in tables and "role_id" not in rp_cols:
        op.add_column(
            "role_permissions",
            sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema=schema,
        )
        op.create_foreign_key(
            "fk_role_permissions_role_id",
            "role_permissions",
            "organization_roles",
            ["role_id"],
            ["id"],
            source_schema=schema,
            referent_schema=schema,
        )
        op.execute(
            sa.text(
                f"""
                UPDATE {schema_prefix}role_permissions AS rp
                SET role_id = r.id
                FROM {schema_prefix}organization_roles AS r
                WHERE rp.organization_id = r.organization_id
                  AND lower(rp.role) = lower(r.key);
                """
            )
        )
        # Signup bug used "client" while RBAC uses "client_viewer"
        op.execute(
            sa.text(
                f"""
                UPDATE {schema_prefix}role_permissions AS rp
                SET role_id = r.id
                FROM {schema_prefix}organization_roles AS r
                WHERE rp.role_id IS NULL
                  AND rp.organization_id = r.organization_id
                  AND lower(rp.role) = 'client'
                  AND r.key = 'client_viewer';
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DELETE FROM {schema_prefix}role_permissions WHERE role_id IS NULL;
                """
            )
        )
        op.alter_column(
            "role_permissions",
            "role_id",
            existing_type=postgresql.UUID(as_uuid=True),
            nullable=False,
            schema=schema,
        )
        op.drop_constraint("uq_role_permissions_org_role_permission", "role_permissions", type_="unique", schema=schema)
        if "ix_role_permissions_role" in [i["name"] for i in inspect(op.get_bind()).get_indexes("role_permissions", schema=schema)]:
            op.drop_index("ix_role_permissions_role", table_name="role_permissions", schema=schema)
        op.drop_column("role_permissions", "role", schema=schema)
        op.create_unique_constraint(
            "uq_role_permissions_org_role_id_permission",
            "role_permissions",
            ["organization_id", "role_id", "permission"],
            schema=schema,
        )
        op.create_index(
            "ix_role_permissions_role_id",
            "role_permissions",
            ["role_id"],
            unique=False,
            schema=schema,
        )

    # --- 5) profiles: role_id + widen role string for custom slugs ---
    prof_cols = _column_names("profiles", schema)
    if "profiles" in tables and "role_id" not in prof_cols:
        op.add_column(
            "profiles",
            sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema=schema,
        )
        op.create_foreign_key(
            "fk_profiles_role_id",
            "profiles",
            "organization_roles",
            ["role_id"],
            ["id"],
            source_schema=schema,
            referent_schema=schema,
        )
        op.execute(
            sa.text(
                f"""
                UPDATE {schema_prefix}profiles AS p
                SET role_id = r.id
                FROM {schema_prefix}organization_roles AS r
                WHERE p.organization_id = r.organization_id
                  AND lower(p.role) = lower(r.key);
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                UPDATE {schema_prefix}profiles AS p
                SET role_id = r.id
                FROM {schema_prefix}organization_roles AS r
                WHERE p.role_id IS NULL
                  AND p.organization_id = r.organization_id
                  AND lower(p.role) = 'client'
                  AND r.key = 'client_viewer';
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                UPDATE {schema_prefix}profiles AS p
                SET
                  role_id = r.id,
                  role = r.key
                FROM {schema_prefix}organization_roles AS r
                WHERE p.role_id IS NULL
                  AND p.organization_id = r.organization_id
                  AND r.key = 'recruiter';
                """
            )
        )
        op.alter_column(
            "profiles",
            "role_id",
            existing_type=postgresql.UUID(as_uuid=True),
            nullable=False,
            schema=schema,
        )

    # Relax varchar on profiles.role for long custom keys (denormalized slug).
    if "profiles" in tables:
        op.alter_column(
            "profiles",
            "role",
            existing_type=sa.String(length=32),
            type_=sa.String(length=64),
            existing_nullable=False,
            schema=schema,
        )

    # Drop fixed role check — custom role keys are validated via organization_roles.
    checks = _check_constraint_names("profiles", schema)
    if "ck_profiles_role_allowed" in checks:
        op.drop_constraint("ck_profiles_role_allowed", "profiles", type_="check", schema=schema)


def downgrade() -> None:
    raise NotImplementedError("Downgrade not supported for this migration (data loss).")
