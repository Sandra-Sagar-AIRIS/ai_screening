"""Add user-level permission overrides (grant/deny).

Revision ID: 20260429_0101
Revises: 20260427_0026
Create Date: 2026-04-29

Renumbered from 20260429_0001 (duplicate id) to avoid Alembic graph ambiguity.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings
from app.core.permissions import ALL_PERMISSIONS

revision: str = "20260429_0101"
down_revision: str | None = "20260427_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSION_EFFECT_ENUM_NAME = "permission_effect"
PERMISSION_EFFECT_VALUES = ("grant", "deny")


def _table_names(schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return set(inspector.get_table_names(schema=schema))


def _ensure_permission_effect_enum() -> None:
    # PostgreSQL doesn't support CREATE TYPE ... IF NOT EXISTS, so we wrap it.
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{PERMISSION_EFFECT_ENUM_NAME}') THEN
                    CREATE TYPE {PERMISSION_EFFECT_ENUM_NAME} AS ENUM ({", ".join(repr(v) for v in PERMISSION_EFFECT_VALUES)});
                END IF;
            END $$;
            """
        )
    )


def _ensure_permissions_table(schema: str | None) -> None:
    # Your conceptual model expects a global permission catalog. In this repo, permissions are currently
    # stored as strings in role_permissions; we add a minimal `permissions` catalog to support FK-backed
    # overrides without changing existing RBAC tables.
    tables = _table_names(schema)
    if "permissions" in tables:
        return

    schema_prefix = f"{schema}." if schema else ""

    op.create_table(
        "permissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
        schema=schema,
    )

    # Seed known permission codes (idempotent).
    quoted_permissions = ", ".join(f"('{code}')" for code in ALL_PERMISSIONS)
    op.execute(
        sa.text(
            f"""
            WITH permission_list(code) AS (
              VALUES {quoted_permissions}
            )
            INSERT INTO {schema_prefix}permissions (code)
            SELECT p.code
            FROM permission_list p
            ON CONFLICT (code) DO NOTHING;
            """
        )
    )


def _ensure_user_permission_overrides(schema: str | None) -> None:
    tables = _table_names(schema)
    if "user_permission_overrides" not in tables:
        # Important: make sure SQLAlchemy does *not* attempt to create the enum type again
        # when building the table DDL. If the type already exists (e.g., from a partially
        # applied migration), native enum DDL can otherwise fail with DuplicateObject.
        permission_effect_enum = postgresql.ENUM(
            *PERMISSION_EFFECT_VALUES,
            name=PERMISSION_EFFECT_ENUM_NAME,
            create_type=False,
        )
        op.create_table(
            "user_permission_overrides",
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("profiles.id", ondelete="CASCADE"),
                primary_key=True,
                nullable=False,
            ),
            sa.Column(
                "permission_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("permissions.id", ondelete="CASCADE"),
                primary_key=True,
                nullable=False,
            ),
            sa.Column(
                "effect",
                permission_effect_enum,
                nullable=False,
            ),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "created_by",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("profiles.id", ondelete="SET NULL"),
                nullable=True,
            ),
            schema=schema,
        )

    # Create indexes only if table exists (safe even if some indexes already exist).
    # If indexes already exist, create_index will error; so we probe via inspector.
    if "user_permission_overrides" in _table_names(schema):
        inspector = inspect(op.get_bind())
        existing_index_names = set()
        try:
            existing_index_names = {
                idx["name"] for idx in inspector.get_indexes("user_permission_overrides", schema=schema)
            }
        except Exception:
            existing_index_names = set()

        indexes_to_create = [
            (
                "ix_user_permission_overrides_user_effect_permission_id",
                ("user_id", "effect", "permission_id"),
            ),
            ("ix_user_permission_overrides_user_expires_at", ("user_id", "expires_at")),
        ]

        for index_name, columns in indexes_to_create:
            if index_name in existing_index_names:
                continue
            op.create_index(
                index_name,
                "user_permission_overrides",
                list(columns),
                unique=False,
                schema=schema,
            )


def _drop_enum_if_unused() -> None:
    # Drop enum only when there are no remaining columns using it.
    op.execute(
        sa.text(
            f"""
            DO $$
            DECLARE
                typ_oid oid;
            BEGIN
                SELECT oid INTO typ_oid FROM pg_type WHERE typname = '{PERMISSION_EFFECT_ENUM_NAME}';
                IF typ_oid IS NULL THEN
                    RETURN;
                END IF;

                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_attribute a
                    WHERE a.atttypid = typ_oid
                      AND a.attnum > 0
                      AND NOT a.attisdropped
                ) THEN
                    EXECUTE 'DROP TYPE {PERMISSION_EFFECT_ENUM_NAME}';
                END IF;
            END $$;
            """
        )
    )


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema

    _ensure_permission_effect_enum()
    _ensure_permissions_table(schema)
    _ensure_user_permission_overrides(schema)


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    tables = _table_names(schema)

    if "user_permission_overrides" in tables:
        inspector = inspect(op.get_bind())
        existing_index_names = set()
        try:
            existing_index_names = {
                idx["name"] for idx in inspector.get_indexes("user_permission_overrides", schema=schema)
            }
        except Exception:
            existing_index_names = set()

        for index_name in [
            "ix_user_permission_overrides_user_effect_permission_id",
            "ix_user_permission_overrides_user_expires_at",
        ]:
            if index_name in existing_index_names:
                op.drop_index(index_name, table_name="user_permission_overrides", schema=schema)

        op.drop_table("user_permission_overrides", schema=schema)

    _drop_enum_if_unused()

