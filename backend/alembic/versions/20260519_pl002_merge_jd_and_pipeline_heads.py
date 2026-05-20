"""Merge pipeline PL-002 line with jd_document_storage line.

Revision ID: 20260519_pl002_merge_jd
Revises: 20260519_pl002_candidate_list_perf_indexes, 20260513_0001

Empty merge revision — aligns branches before candidate text-search (20260519_0002).

Note: Former revision id duplicated 20260519_0002 with candidate_text_search_trgm.py.
"""

from collections.abc import Sequence

revision: str = "20260519_pl002_merge_jd"
down_revision: tuple[str, ...] = (
    "20260519_pl002_candidate_list_perf_indexes",
    "20260513_0001",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
