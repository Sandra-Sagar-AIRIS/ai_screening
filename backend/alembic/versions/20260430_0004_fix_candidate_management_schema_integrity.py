"""Fix candidate_management schema integrity.

Revision ID: 20260430_0004
Revises: 20260430_0003
Create Date: 2026-04-30

Adds missing unique constraints and multi-column foreign keys to align DB with ORM models.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

from app.core.config import get_settings

revision: str = "20260430_0004"
down_revision: str | None = "20260430_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _constraint_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {c["name"] for c in inspector.get_unique_constraints(table, schema=schema)}


def _fk_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {fk["name"] for fk in inspector.get_foreign_keys(table, schema=schema)}


def upgrade() -> None:
    schema = get_settings().db_schema
    
    # 1. Add UniqueConstraint to candidates (required for multi-column FKs)
    c_constraints = _constraint_names("candidates", schema)
    if "uq_candidates_id_org_workspace" not in c_constraints:
        op.create_unique_constraint(
            "uq_candidates_id_org_workspace",
            "candidates",
            ["id", "org_id", "workspace_id"],
            schema=schema
        )

    # 2. Fix candidate_skills FK
    s_fks = _fk_names("candidate_skills", schema)
    # Drop old single-column FK if it exists under generic names
    for fk in list(s_fks):
        if "candidate_id" in fk or "fk_candidate_skills" in fk:
            op.drop_constraint(fk, "candidate_skills", type_="foreignkey", schema=schema)
    
    op.create_foreign_key(
        "fk_candidate_skills_candidate_tenant",
        "candidate_skills",
        "candidates",
        ["candidate_id", "org_id", "workspace_id"],
        ["id", "org_id", "workspace_id"],
        ondelete="CASCADE",
        source_schema=schema,
        referent_schema=schema
    )

    # 3. Fix candidate_interactions FK
    i_fks = _fk_names("candidate_interactions", schema)
    for fk in list(i_fks):
        if "candidate_id" in fk or "fk_candidate_interactions" in fk:
            op.drop_constraint(fk, "candidate_interactions", type_="foreignkey", schema=schema)

    op.create_foreign_key(
        "fk_candidate_interactions_candidate_tenant",
        "candidate_interactions",
        "candidates",
        ["candidate_id", "org_id", "workspace_id"],
        ["id", "org_id", "workspace_id"],
        ondelete="CASCADE",
        source_schema=schema,
        referent_schema=schema
    )

    # 4. Fix candidate_audit_logs FK
    a_fks = _fk_names("candidate_audit_logs", schema)
    for fk in list(a_fks):
        if "candidate_id" in fk or "fk_candidate_audit_logs" in fk:
            op.drop_constraint(fk, "candidate_audit_logs", type_="foreignkey", schema=schema)

    op.create_foreign_key(
        "fk_candidate_audit_logs_candidate_tenant",
        "candidate_audit_logs",
        "candidates",
        ["candidate_id", "org_id", "workspace_id"],
        ["id", "org_id", "workspace_id"],
        ondelete="CASCADE",
        source_schema=schema,
        referent_schema=schema
    )


def downgrade() -> None:
    schema = get_settings().db_schema
    
    # Reverting to single column FKs is complex and probably not desired, 
    # but we can drop the multi-column ones.
    op.drop_constraint("fk_candidate_audit_logs_candidate_tenant", "candidate_audit_logs", type_="foreignkey", schema=schema)
    op.drop_constraint("fk_candidate_interactions_candidate_tenant", "candidate_interactions", type_="foreignkey", schema=schema)
    op.drop_constraint("fk_candidate_skills_candidate_tenant", "candidate_skills", type_="foreignkey", schema=schema)
    op.drop_constraint("uq_candidates_id_org_workspace", "candidates", type_="unique", schema=schema)
