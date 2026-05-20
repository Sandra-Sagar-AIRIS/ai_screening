"""Merge pipeline_stage_history head with jd_document_storage head.

Revision ID: 20260519_0002
Revises: 20260519_0001, 20260513_0001
Create Date: 2026-05-19
"""
from collections.abc import Sequence

revision: str = "20260519_0002"
down_revision: tuple[str, ...] = ("20260519_0001", "20260513_0001")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
