"""normalize rbac in public schema

Revision ID: 4deaa48d319f
Revises: fe22a3555441
Create Date: 2026-04-30 15:44:46.763355
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '4deaa48d319f'
down_revision: str | None = 'fe22a3555441'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    schema = "public"
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names(schema=schema))

    if "permissions" in tables:
        cols = {c["name"] for c in inspector.get_columns("permissions", schema=schema)}
        if "module" not in cols:
            op.add_column("permissions", sa.Column("module", sa.String(length=128), nullable=True), schema=schema)
        if "display_name" not in cols:
            op.add_column("permissions", sa.Column("display_name", sa.String(length=255), nullable=True), schema=schema)
        op.execute(
            sa.text(
                """
                UPDATE public.permissions
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
                """
                UPDATE public.permissions
                SET module = coalesce(module, 'general'),
                    display_name = coalesce(display_name, code);
                """
            )
        )
        op.alter_column("permissions", "module", existing_type=sa.String(length=128), nullable=False, schema=schema)
        op.alter_column("permissions", "display_name", existing_type=sa.String(length=255), nullable=False, schema=schema)

    if "organization_roles" not in tables:
        op.create_table(
            "organization_roles",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("key", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_organization_roles_organization_id"),
            sa.UniqueConstraint("organization_id", "key", name="uq_organization_roles_org_key"),
            schema=schema,
        )
        op.create_index("ix_organization_roles_organization_id", "organization_roles", ["organization_id"], unique=False, schema=schema)
        op.create_index("ix_organization_roles_key", "organization_roles", ["key"], unique=False, schema=schema)

    op.execute(
        sa.text(
            """
            INSERT INTO public.organization_roles (organization_id, name, key)
            SELECT o.id, v.name, v.key
            FROM public.organizations o
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

    inspector = inspect(bind)
    rp_cols = {c["name"] for c in inspector.get_columns("role_permissions", schema=schema)}
    if "role_id" not in rp_cols:
        op.add_column("role_permissions", sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=True), schema=schema)
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
                """
                UPDATE public.role_permissions AS rp
                SET role_id = r.id
                FROM public.organization_roles AS r
                WHERE rp.organization_id = r.organization_id
                  AND lower(rp.role) = lower(r.key);
                """
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE public.role_permissions AS rp
                SET role_id = r.id
                FROM public.organization_roles AS r
                WHERE rp.role_id IS NULL
                  AND rp.organization_id = r.organization_id
                  AND lower(rp.role) = 'client'
                  AND r.key = 'client_viewer';
                """
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE public.role_permissions AS rp
                SET role_id = r.id
                FROM public.organization_roles AS r
                WHERE rp.role_id IS NULL
                  AND rp.organization_id = r.organization_id
                  AND r.key = 'recruiter';
                """
            )
        )
        op.alter_column("role_permissions", "role_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False, schema=schema)
        unique_names = {u["name"] for u in inspector.get_unique_constraints("role_permissions", schema=schema)}
        if "uq_role_permissions_org_role_permission" in unique_names:
            op.drop_constraint("uq_role_permissions_org_role_permission", "role_permissions", type_="unique", schema=schema)
        index_names = {i["name"] for i in inspector.get_indexes("role_permissions", schema=schema)}
        if "ix_role_permissions_role" in index_names:
            op.drop_index("ix_role_permissions_role", table_name="role_permissions", schema=schema)
        op.drop_column("role_permissions", "role", schema=schema)
        op.create_unique_constraint(
            "uq_role_permissions_org_role_id_permission",
            "role_permissions",
            ["organization_id", "role_id", "permission"],
            schema=schema,
        )
        op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"], unique=False, schema=schema)

    inspector = inspect(bind)
    p_cols = {c["name"] for c in inspector.get_columns("profiles", schema=schema)}
    if "role_id" not in p_cols:
        op.add_column("profiles", sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=True), schema=schema)
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
                """
                UPDATE public.profiles AS p
                SET role_id = r.id
                FROM public.organization_roles AS r
                WHERE p.organization_id = r.organization_id
                  AND lower(p.role) = lower(r.key);
                """
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE public.profiles AS p
                SET role_id = r.id
                FROM public.organization_roles AS r
                WHERE p.role_id IS NULL
                  AND p.organization_id = r.organization_id
                  AND lower(p.role) = 'client'
                  AND r.key = 'client_viewer';
                """
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE public.profiles AS p
                SET role_id = r.id, role = r.key
                FROM public.organization_roles AS r
                WHERE p.role_id IS NULL
                  AND p.organization_id = r.organization_id
                  AND r.key = 'recruiter';
                """
            )
        )
        op.alter_column("profiles", "role_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False, schema=schema)

    op.alter_column("profiles", "role", existing_type=sa.String(length=32), type_=sa.String(length=64), existing_nullable=False, schema=schema)
    checks = {c["name"] for c in inspector.get_check_constraints("profiles", schema=schema)}
    if "ck_profiles_role_allowed" in checks:
        op.drop_constraint("ck_profiles_role_allowed", "profiles", type_="check", schema=schema)


def downgrade() -> None:
    raise NotImplementedError("Downgrade not supported for forward-only normalization.")

