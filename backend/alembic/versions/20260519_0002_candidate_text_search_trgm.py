"""Add pg_trgm GIN index for fast candidate text search (idempotent).

Revision ID: 20260519_0002
Revises: 20260519_pl002_merge_jd
Create Date: 2026-05-19
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect, text

from app.core.config import get_settings

revision: str = "20260519_0002"
down_revision: str | None = "20260519_pl002_merge_jd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_candidates_search_document_trgm"


def _index_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {idx["name"] for idx in inspector.get_indexes(table, schema=schema)}


def _column_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {col["name"] for col in inspector.get_columns(table, schema=schema)}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    schema = get_settings().db_schema
    inspector = inspect(bind)
    if "candidates" not in inspector.get_table_names(schema=schema):
        return

    columns = _column_names("candidates", schema)
    required = {
        "full_name",
        "first_name",
        "last_name",
        "email",
        "phone",
        "location",
        "headline",
        "deleted_at",
    }
    if not required.issubset(columns):
        return

    op.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    indexes = _index_names("candidates", schema)
    if INDEX_NAME in indexes:
        return

    qualified = f'"{schema}".candidates' if schema else "candidates"
    op.execute(
        text(
            f"""
            CREATE INDEX {INDEX_NAME}
            ON {qualified}
            USING gin (
              lower(
                coalesce(full_name, '') || ' ' ||
                coalesce(first_name, '') || ' ' ||
                coalesce(last_name, '') || ' ' ||
                coalesce(email, '') || ' ' ||
                coalesce(phone, '') || ' ' ||
                coalesce(location, '') || ' ' ||
                coalesce(headline, '')
              ) gin_trgm_ops
            )
            WHERE deleted_at IS NULL
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    schema = get_settings().db_schema
    inspector = inspect(bind)
    if "candidates" not in inspector.get_table_names(schema=schema):
        return

    indexes = _index_names("candidates", schema)
    if INDEX_NAME in indexes:
        op.drop_index(INDEX_NAME, table_name="candidates", schema=schema)
