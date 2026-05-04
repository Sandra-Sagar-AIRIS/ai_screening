"""Create all candidate_management supporting tables.

Revision ID: 20260430_0002
Revises: 20260430_0001
Create Date: 2026-04-30

Creates: candidate_skills, candidate_interactions, candidate_audit_logs,
         bulk_upload_jobs, bulk_upload_items
All creates are guarded with table-existence checks.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260430_0002"
down_revision: str | None = "20260430_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    schema = get_settings().db_schema
    inspector = inspect(op.get_bind())
    existing = set(inspector.get_table_names(schema=schema))

    if "candidate_skills" not in existing:
        op.create_table(
            "candidate_skills",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("normalized_name", sa.String(120), nullable=False),
            sa.Column("proficiency", sa.String(30), nullable=True),
            sa.Column("years_experience", sa.Integer(), nullable=True),
            sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
            sa.Column("source", sa.String(40), nullable=False, server_default="manual"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
            schema=schema,
        )
        op.create_index("ix_candidate_skills_org_workspace_name", "candidate_skills", ["org_id", "workspace_id", "normalized_name"], schema=schema)

    if "candidate_interactions" not in existing:
        op.create_table(
            "candidate_interactions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
            sa.Column("type", sa.String(40), nullable=False),
            sa.Column("title", sa.String(255), nullable=True),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("actor_role", sa.String(40), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
            schema=schema,
        )

    if "candidate_audit_logs" not in existing:
        op.create_table(
            "candidate_audit_logs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
            sa.Column("action", sa.String(80), nullable=False),
            sa.Column("field_name", sa.String(80), nullable=True),
            sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("actor_role", sa.String(40), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
            schema=schema,
        )

    if "bulk_upload_jobs" not in existing:
        op.create_table(
            "bulk_upload_jobs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
            sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
            sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("processed_items", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("success_items", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_items", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("skipped_items", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )

    if "bulk_upload_items" not in existing:
        op.create_table(
            "bulk_upload_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
            sa.Column("row_number", sa.Integer(), nullable=False),
            sa.Column("resume_s3_key", sa.String(1024), nullable=True),
            sa.Column("original_file_name", sa.String(512), nullable=True),
            sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
            sa.Column("extracted_email", sa.String(320), nullable=True),
            sa.Column("extracted_phone", sa.String(40), nullable=True),
            sa.Column("ai_confidence", sa.Numeric(4, 3), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["job_id"], ["bulk_upload_jobs.id"], ondelete="CASCADE"),
            schema=schema,
        )


def downgrade() -> None:
    schema = get_settings().db_schema
    inspector = inspect(op.get_bind())
    existing = set(inspector.get_table_names(schema=schema))
    for table in ["bulk_upload_items", "bulk_upload_jobs", "candidate_audit_logs", "candidate_interactions", "candidate_skills"]:
        if table in existing:
            op.drop_table(table, schema=schema)
