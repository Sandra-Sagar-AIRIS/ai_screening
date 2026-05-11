"""merge_hybrid_ats_and_auth_sessions_heads

Revision ID: 11c997092c10
Revises: 20260510_0001, 20260510_0002
Create Date: 2026-05-10 15:35:55.066258

Joins the candidate-management branch (20260510_0001) with the bootstrap branch
(20260510_0002 after b91f8d6a2c13). Both parent revisions apply the same ATS
columns; at most one performs work per database (20260510_0002 is idempotent).

Because Alembic runs the full ancestry of BOTH parents when using ``upgrade head``,
bootstrap-only databases (at b91f8d6a2c13) must NOT run ``upgrade head`` to reach
this merge — that would replay the unrelated vendor/RBAC branch.

Bootstrap DB (current revision b91f8d6a2c13)::

    alembic upgrade 20260510_0002
    alembic stamp 11c997092c10

Candidate-management DB (already at or before 20260510_0001)::

    alembic upgrade 11c997092c10
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "11c997092c10"
down_revision: str | Sequence[str] | None = ("20260510_0001", "20260510_0002")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

