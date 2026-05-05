"""Add vendor role + scoped vendor access.

Revision ID: 20260429_0002
Revises: 20260429_0001
Create Date: 2026-04-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from app.core.permissions import (
    CANDIDATES_READ_OWN,
    JOBS_READ_LIMITED,
    SUBMISSIONS_CREATE,
    SUBMISSIONS_READ_OWN,
)

revision: str = "20260429_0002"
down_revision: str | None = "20260429_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VENDOR_ROLE = "vendor"

ROLE_CHECK_NAME = "ck_profiles_role_allowed"
ROLE_ALLOWED = ("admin", "recruiter", "client_viewer", "vendor")

SOURCE_TYPE_ENUM_NAME = "candidate_source_type"
SOURCE_TYPE_VALUES = ("internal", "vendor")

VENDOR_PERMISSION_SET: tuple[str, ...] = (
    CANDIDATES_READ_OWN,
    JOBS_READ_LIMITED,
    SUBMISSIONS_CREATE,
    SUBMISSIONS_READ_OWN,
)


def _table_names(schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return set(inspector.get_table_names(schema=schema))


def _column_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table, schema=schema)}


def _check_constraint_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {constraint["name"] for constraint in inspector.get_check_constraints(table, schema=schema)}

def _index_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    try:
        return {idx["name"] for idx in inspector.get_indexes(table, schema=schema)}
    except Exception:
        return set()


def _ensure_candidate_source_type_enum() -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{SOURCE_TYPE_ENUM_NAME}') THEN
                    CREATE TYPE {SOURCE_TYPE_ENUM_NAME} AS ENUM ({", ".join(repr(v) for v in SOURCE_TYPE_VALUES)});
                END IF;
            END $$;
            """
        )
    )


def _seed_vendor_role_permissions(schema: str | None) -> None:
    """
    Seed vendor role_permissions for *existing* organizations.
    New organizations are handled by `signup_permissions.py`.
    """
    tables = _table_names(schema)
    if "role_permissions" not in tables or "organizations" not in tables:
        return

    schema_prefix = f"{schema}." if schema else ""
    quoted_permissions = ", ".join(f"('{permission}')" for permission in VENDOR_PERMISSION_SET)

    op.execute(
        sa.text(
            f"""
            WITH permission_list(permission) AS (
              VALUES {quoted_permissions}
            )
            INSERT INTO {schema_prefix}role_permissions (organization_id, role, permission)
            SELECT o.id, '{VENDOR_ROLE}', p.permission
            FROM {schema_prefix}organizations o
            CROSS JOIN permission_list p
            ON CONFLICT (organization_id, role, permission) DO NOTHING;
            """
        )
    )


def upgrade() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    schema = settings.db_schema

    _ensure_candidate_source_type_enum()

    candidates_columns = _column_names("candidates", schema)
    candidate_indexes = _index_names("candidates", schema)
    if "created_by" not in candidates_columns:
        op.add_column(
            "candidates",
            sa.Column(
                "created_by",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("profiles.id", ondelete="SET NULL"),
                nullable=True,
            ),
            schema=schema,
        )
    if "ix_candidates_created_by" not in candidate_indexes:
        op.create_index("ix_candidates_created_by", "candidates", ["created_by"], unique=False, schema=schema)

    if "source_type" not in candidates_columns:
        op.add_column(
            "candidates",
            sa.Column(
                "source_type",
                sa.Enum("internal", "vendor", name=SOURCE_TYPE_ENUM_NAME, create_type=False),
                nullable=False,
                server_default=sa.text("'internal'"),
            ),
            schema=schema,
        )

    tables = _table_names(schema)
    if "job_vendors" not in tables:
        op.create_table(
            "job_vendors",
            sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("vendor_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name="fk_job_vendors_job_id", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["vendor_id"], ["profiles.id"], name="fk_job_vendors_vendor_id", ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("job_id", "vendor_id", name="pk_job_vendors_job_vendor"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            schema=schema,
        )
    job_vendor_indexes = _index_names("job_vendors", schema)
    if "ix_job_vendors_job_id" not in job_vendor_indexes:
        op.create_index("ix_job_vendors_job_id", "job_vendors", ["job_id"], unique=False, schema=schema)
    if "ix_job_vendors_vendor_id" not in job_vendor_indexes:
        op.create_index("ix_job_vendors_vendor_id", "job_vendors", ["vendor_id"], unique=False, schema=schema)

    _seed_vendor_role_permissions(schema)

    # Allow the new `vendor` role in profiles (existing DB constraint blocks it otherwise).
    checks = _check_constraint_names("profiles", schema)
    if ROLE_CHECK_NAME in checks:
        op.drop_constraint(ROLE_CHECK_NAME, "profiles", type_="check", schema=schema)
    op.create_check_constraint(
        ROLE_CHECK_NAME,
        "profiles",
        f"role IN {ROLE_ALLOWED}",
        schema=schema,
    )


def downgrade() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    schema = settings.db_schema
    tables = _table_names(schema)

    if "job_vendors" in tables:
        job_vendor_indexes = _index_names("job_vendors", schema)
        if "ix_job_vendors_vendor_id" in job_vendor_indexes:
            op.drop_index("ix_job_vendors_vendor_id", table_name="job_vendors", schema=schema)
        if "ix_job_vendors_job_id" in job_vendor_indexes:
            op.drop_index("ix_job_vendors_job_id", table_name="job_vendors", schema=schema)
        op.drop_table("job_vendors", schema=schema)

    candidates_columns = _column_names("candidates", schema)
    if "source_type" in candidates_columns:
        op.drop_column("candidates", "source_type", schema=schema)

    if "created_by" in candidates_columns:
        op.drop_column("candidates", "created_by", schema=schema)

    # Drop enum only if unused.
    op.execute(
        sa.text(
            f"""
            DO $$
            DECLARE
                typ_oid oid;
            BEGIN
                SELECT oid INTO typ_oid FROM pg_type WHERE typname = '{SOURCE_TYPE_ENUM_NAME}';
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
                    EXECUTE 'DROP TYPE {SOURCE_TYPE_ENUM_NAME}';
                END IF;
            END $$;
            """
        )
    )

    # Revert profiles.role check constraint (remove `vendor`).
    checks = _check_constraint_names("profiles", schema)
    if ROLE_CHECK_NAME in checks:
        op.drop_constraint(ROLE_CHECK_NAME, "profiles", type_="check", schema=schema)
    op.create_check_constraint(
        ROLE_CHECK_NAME,
        "profiles",
        f"role IN {('admin', 'recruiter', 'client_viewer')}",
        schema=schema,
    )

