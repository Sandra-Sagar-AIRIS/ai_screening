"""Add all missing candidate_management columns to candidates table.

Revision ID: 20260430_0001
Revises: 20260429_0003
Create Date: 2026-04-30

This migration safely adds ALL columns required by the candidate_management module
using column-existence checks so it never fails if already applied.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260430_0001"
down_revision: str | None = "20260429_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {col["name"] for col in inspector.get_columns(table, schema=schema)}


def _index_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {idx["name"] for idx in inspector.get_indexes(table, schema=schema)}


def upgrade() -> None:
    schema = get_settings().db_schema
    columns = _column_names("candidates", schema)
    idx_names = _index_names("candidates", schema)

    # --- Core tenant columns ---
    if "org_id" not in columns:
        op.add_column(
            "candidates",
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema=schema,
        )
        # Backfill from organization_id if it exists
        if "organization_id" in columns:
            op.execute(
                text("UPDATE candidates SET org_id = organization_id WHERE org_id IS NULL")
            )

    if "workspace_id" not in columns:
        op.add_column(
            "candidates",
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema=schema,
        )
        # Backfill workspace_id with org_id (best effort for existing records)
        op.execute(
            text("UPDATE candidates SET workspace_id = org_id WHERE workspace_id IS NULL")
        )

    # --- Name fields ---
    if "full_name" not in columns:
        op.add_column(
            "candidates",
            sa.Column("full_name", sa.String(length=260), nullable=True),
            schema=schema,
        )
        # Backfill full_name from first_name + last_name
        op.execute(
            text(
                "UPDATE candidates SET full_name = TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) "
                "WHERE full_name IS NULL AND (first_name IS NOT NULL OR last_name IS NOT NULL)"
            )
        )
        # Make non-nullable with a safe default
        op.execute(
            text("UPDATE candidates SET full_name = 'Unknown' WHERE full_name IS NULL OR full_name = ''")
        )

    if "headline" not in columns:
        op.add_column(
            "candidates",
            sa.Column("headline", sa.String(length=255), nullable=True),
            schema=schema,
        )

    if "summary" not in columns:
        op.add_column(
            "candidates",
            sa.Column("summary", sa.Text(), nullable=True),
            schema=schema,
        )

    if "years_experience" not in columns:
        op.add_column(
            "candidates",
            sa.Column("years_experience", sa.Integer(), nullable=True),
            schema=schema,
        )

    # --- Stage ---
    if "stage" not in columns:
        op.add_column(
            "candidates",
            sa.Column("stage", sa.String(length=40), nullable=False, server_default=sa.text("'applied'")),
            schema=schema,
        )

    # --- Job link ---
    if "job_id" not in columns:
        op.add_column(
            "candidates",
            sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema=schema,
        )

    # --- Source (enum as string) ---
    if "source" not in columns:
        op.add_column(
            "candidates",
            sa.Column("source", sa.String(length=40), nullable=False, server_default=sa.text("'manual'")),
            schema=schema,
        )
        # Map source_type if it exists - handle unknown legacy enum values
        if "source_type" in columns:
            op.execute(
                text(
                    "UPDATE candidates SET source = CASE "
                    "  WHEN source_type::text = 'import' THEN 'bulk_upload' "
                    "  WHEN source_type::text IN ('manual', 'resume_upload', 'bulk_upload', 'referral', 'agency', 'merge') THEN source_type::text "
                    "  ELSE 'manual' END"
                )
            )

    # --- Status ---
    if "status" not in columns:
        op.add_column(
            "candidates",
            sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'active'")),
            schema=schema,
        )
        # Backfill from is_deleted if it exists
        if "is_deleted" in columns:
            op.execute(
                text("UPDATE candidates SET status = 'deleted' WHERE is_deleted = true")
            )

    # --- Resume columns ---
    if "resume_s3_key" not in columns:
        op.add_column(
            "candidates",
            sa.Column("resume_s3_key", sa.String(length=1024), nullable=True),
            schema=schema,
        )
        if "resume_url" in columns:
            op.execute(
                text("UPDATE candidates SET resume_s3_key = resume_url WHERE resume_url IS NOT NULL")
            )

    if "resume_file_name" not in columns:
        op.add_column(
            "candidates",
            sa.Column("resume_file_name", sa.String(length=512), nullable=True),
            schema=schema,
        )

    if "resume_uploaded_at" not in columns:
        op.add_column(
            "candidates",
            sa.Column("resume_uploaded_at", sa.DateTime(timezone=True), nullable=True),
            schema=schema,
        )

    if "ai_parse_version" not in columns:
        op.add_column(
            "candidates",
            sa.Column("ai_parse_version", sa.String(length=64), nullable=True),
            schema=schema,
        )

    if "parse_confidence" not in columns:
        op.add_column(
            "candidates",
            sa.Column("parse_confidence", sa.Numeric(4, 3), nullable=True),
            schema=schema,
        )

    if "parsed_resume_data" not in columns:
        op.add_column(
            "candidates",
            sa.Column("parsed_resume_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            schema=schema,
        )

    # --- Merge tracking ---
    if "merged_into_candidate_id" not in columns:
        op.add_column(
            "candidates",
            sa.Column("merged_into_candidate_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema=schema,
        )

    if "merged_at" not in columns:
        op.add_column(
            "candidates",
            sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
            schema=schema,
        )

    # --- Actor tracking ---
    if "recruiter_id" not in columns:
        op.add_column(
            "candidates",
            sa.Column("recruiter_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema=schema,
        )

    if "updated_by" not in columns:
        op.add_column(
            "candidates",
            sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
            schema=schema,
        )

    if "deleted_by" not in columns:
        op.add_column(
            "candidates",
            sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
            schema=schema,
        )

    if "deleted_at" not in columns:
        op.add_column(
            "candidates",
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            schema=schema,
        )

    # --- Indexes ---
    # Reload after adds
    idx_names = _index_names("candidates", schema)
    columns = _column_names("candidates", schema)

    if "org_id" in columns and "ix_candidates_org_id" not in idx_names:
        op.create_index("ix_candidates_org_id", "candidates", ["org_id"], unique=False, schema=schema)

    if "workspace_id" in columns and "ix_candidates_workspace_id" not in idx_names:
        op.create_index("ix_candidates_workspace_id", "candidates", ["workspace_id"], unique=False, schema=schema)

    if "job_id" in columns and "ix_candidates_job_id" not in idx_names:
        op.create_index("ix_candidates_job_id", "candidates", ["job_id"], unique=False, schema=schema)

    if "recruiter_id" in columns and "ix_candidates_recruiter_id" not in idx_names:
        op.create_index("ix_candidates_recruiter_id", "candidates", ["recruiter_id"], unique=False, schema=schema)

    if "stage" in columns and "ix_candidates_stage" not in idx_names:
        op.create_index("ix_candidates_stage", "candidates", ["stage"], unique=False, schema=schema)

    if "deleted_at" in columns and "ix_candidates_deleted_at" not in idx_names:
        op.create_index("ix_candidates_deleted_at", "candidates", ["deleted_at"], unique=False, schema=schema)

    if "created_by" in columns and "ix_candidates_created_by" not in idx_names:
        op.create_index("ix_candidates_created_by", "candidates", ["created_by"], unique=False, schema=schema)

    # -----------------------------------------------
    # Create candidate_skills table if missing
    # -----------------------------------------------
    inspector = inspect(op.get_bind())
    existing_tables = inspector.get_table_names(schema=schema)

    if "candidate_skills" not in existing_tables:
        op.create_table(
            "candidate_skills",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        op.create_index("ix_candidate_skills_candidate_id", "candidate_skills", ["candidate_id"], schema=schema)
        op.create_index("ix_candidate_skills_org_workspace_name", "candidate_skills", ["org_id", "workspace_id", "normalized_name"], schema=schema)

    # -----------------------------------------------
    # Create candidate_interactions table if missing
    # -----------------------------------------------
    if "candidate_interactions" not in existing_tables:
        op.create_table(
            "candidate_interactions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        op.create_index("ix_candidate_interactions_candidate_id", "candidate_interactions", ["candidate_id"], schema=schema)

    # -----------------------------------------------
    # Create candidate_audit_logs table if missing
    # -----------------------------------------------
    if "candidate_audit_logs" not in existing_tables:
        op.create_table(
            "candidate_audit_logs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        op.create_index("ix_candidate_audit_logs_candidate_id", "candidate_audit_logs", ["candidate_id"], schema=schema)

    # -----------------------------------------------
    # Create bulk_upload_jobs table if missing
    # -----------------------------------------------
    if "bulk_upload_jobs" not in existing_tables:
        op.create_table(
            "bulk_upload_jobs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
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

    # -----------------------------------------------
    # Create bulk_upload_items table if missing
    # -----------------------------------------------
    if "bulk_upload_items" not in existing_tables:
        op.create_table(
            "bulk_upload_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        op.create_index("ix_bulk_upload_items_job_id", "bulk_upload_items", ["job_id"], schema=schema)


def downgrade() -> None:
    schema = get_settings().db_schema
    # Drop only the columns added in this migration
    for col in [
        "org_id", "workspace_id", "full_name", "headline", "summary", "years_experience",
        "stage", "job_id", "source", "status", "resume_s3_key", "resume_file_name",
        "resume_uploaded_at", "ai_parse_version", "parse_confidence", "parsed_resume_data",
        "merged_into_candidate_id", "merged_at", "recruiter_id", "updated_by", "deleted_by", "deleted_at",
    ]:
        columns = _column_names("candidates", schema)
        if col in columns:
            op.drop_column("candidates", col, schema=schema)
