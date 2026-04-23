"""Add missing interviews indexes.

Revision ID: 20260421_0023
Revises: 20260421_0022
Create Date: 2026-04-22
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect

from app.core.config import get_settings

revision: str = "20260421_0023"
down_revision: str | None = "20260421_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_names(schema: str | None) -> set[str]:
    bind = op.get_bind()
    inspector = inspect(bind)
    return {idx["name"] for idx in inspector.get_indexes("interviews", schema=schema)}


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    existing = _index_names(schema)

    if "ix_interviews_organization_id" not in existing:
        op.create_index(
            "ix_interviews_organization_id",
            "interviews",
            ["organization_id"],
            unique=False,
            schema=schema,
        )
    if "ix_interviews_pipeline_id" not in existing:
        op.create_index(
            "ix_interviews_pipeline_id",
            "interviews",
            ["pipeline_id"],
            unique=False,
            schema=schema,
        )


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    existing = _index_names(schema)

    if "ix_interviews_pipeline_id" in existing:
        op.drop_index("ix_interviews_pipeline_id", table_name="interviews", schema=schema)
    if "ix_interviews_organization_id" in existing:
        op.drop_index("ix_interviews_organization_id", table_name="interviews", schema=schema)
