"""Extend jobs and add job-management tables.

Revision ID: 20260429_0001
Revises: 78abbe09286e
Create Date: 2026-04-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "20260429_0001"
down_revision: str | None = "78abbe09286e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names(schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return set(inspector.get_table_names(schema=schema))


def _column_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {col["name"] for col in inspector.get_columns(table, schema=schema)}


def _index_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {idx["name"] for idx in inspector.get_indexes(table, schema=schema)}


def _check_constraint_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {c["name"] for c in inspector.get_check_constraints(table, schema=schema)}


def _foreign_key_constraint_names(table: str, schema: str | None) -> set[str]:
    inspector = inspect(op.get_bind())
    return {fk.get("name") for fk in inspector.get_foreign_keys(table, schema=schema) if fk.get("name")}


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    tables = _table_names(schema)

    # ---------------------------
    # Extend `jobs` table
    # ---------------------------
    if "jobs" in tables:
        existing_cols = _column_names("jobs", schema)

        if "location" not in existing_cols:
            op.add_column("jobs", sa.Column("location", sa.String(length=255), nullable=True), schema=schema)
        if "salary_min" not in existing_cols:
            op.add_column(
                "jobs",
                sa.Column("salary_min", sa.Numeric(10, 2), nullable=True),
                schema=schema,
            )
        if "salary_max" not in existing_cols:
            op.add_column(
                "jobs",
                sa.Column("salary_max", sa.Numeric(10, 2), nullable=True),
                schema=schema,
            )
        if "salary_currency" not in existing_cols:
            op.add_column(
                "jobs",
                sa.Column("salary_currency", sa.String(length=3), nullable=True, server_default=sa.text("'USD'")),
                schema=schema,
            )
        if "experience_min_years" not in existing_cols:
            op.add_column("jobs", sa.Column("experience_min_years", sa.Integer(), nullable=True), schema=schema)
        if "experience_max_years" not in existing_cols:
            op.add_column("jobs", sa.Column("experience_max_years", sa.Integer(), nullable=True), schema=schema)
        if "employment_type" not in existing_cols:
            op.add_column(
                "jobs",
                sa.Column("employment_type", sa.String(length=30), nullable=True),
                schema=schema,
            )
        if "urgency" not in existing_cols:
            op.add_column(
                "jobs",
                sa.Column("urgency", sa.String(length=20), nullable=True, server_default=sa.text("'standard'")),
                schema=schema,
            )
        if "filled_at" not in existing_cols:
            op.add_column("jobs", sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True), schema=schema)
        if "created_by" not in existing_cols:
            op.add_column(
                "jobs",
                sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
                schema=schema,
            )

        # Foreign key for `created_by` -> `profiles.id`
        fk_names = _foreign_key_constraint_names("jobs", schema)
        if "fk_jobs_created_by_profiles" not in fk_names:
            if "created_by" in existing_cols:
                op.create_foreign_key(
                    "fk_jobs_created_by_profiles",
                    "jobs",
                    "profiles",
                    ["created_by"],
                    ["id"],
                    source_schema=schema,
                    referent_schema=schema,
                )

        # Checks
        check_names = _check_constraint_names("jobs", schema)
        if "jobs_salary_range_valid" not in check_names:
            op.create_check_constraint(
                "jobs_salary_range_valid",
                "jobs",
                "salary_max IS NULL OR salary_min IS NULL OR salary_min <= salary_max",
                schema=schema,
            )
        if "jobs_experience_range_valid" not in check_names:
            op.create_check_constraint(
                "jobs_experience_range_valid",
                "jobs",
                "experience_max_years IS NULL OR experience_min_years IS NULL OR experience_min_years <= experience_max_years",
                schema=schema,
            )

        # Indexes
        idx_names = _index_names("jobs", schema)
        if "ix_jobs_status" not in idx_names:
            op.create_index("ix_jobs_status", "jobs", ["status"], unique=False, schema=schema)
        if "ix_jobs_urgency" not in idx_names and "urgency" in existing_cols:
            op.create_index("ix_jobs_urgency", "jobs", ["urgency"], unique=False, schema=schema)
        if "ix_jobs_created_at" not in idx_names:
            op.create_index("ix_jobs_created_at", "jobs", ["created_at"], unique=False, schema=schema)
        if "ix_jobs_location" not in idx_names and "location" in existing_cols:
            op.create_index("ix_jobs_location", "jobs", ["location"], unique=False, schema=schema)

    # ---------------------------
    # job_skills
    # ---------------------------
    if "job_skills" not in tables:
        op.create_table(
            "job_skills",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "job_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("jobs.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("skill", sa.String(length=100), nullable=False),
            sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("job_id", "skill", name="uq_job_skills_job_id_skill"),
            schema=schema,
        )
        op.create_index("ix_job_skills_job_id", "job_skills", ["job_id"], unique=False, schema=schema)
        op.create_index("ix_job_skills_skill", "job_skills", ["skill"], unique=False, schema=schema)

    # ---------------------------
    # job_submissions
    # ---------------------------
    if "job_submissions" not in tables:
        op.create_table(
            "job_submissions",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "job_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("jobs.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "candidate_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("candidates.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "submitted_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "submitted_by",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("profiles.id"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "submission_status",
                sa.String(length=30),
                nullable=False,
                server_default=sa.text("'pending'"),
            ),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.UniqueConstraint("job_id", "candidate_id", name="uq_job_submissions_job_id_candidate_id"),
            schema=schema,
        )
        op.create_index("ix_job_submissions_job_id", "job_submissions", ["job_id"], unique=False, schema=schema)
        op.create_index(
            "ix_job_submissions_candidate_id",
            "job_submissions",
            ["candidate_id"],
            unique=False,
            schema=schema,
        )
        op.create_index(
            "ix_job_submissions_submission_status",
            "job_submissions",
            ["submission_status"],
            unique=False,
            schema=schema,
        )
        op.create_index(
            "ix_job_submissions_created_at",
            "job_submissions",
            ["created_at"],
            unique=False,
            schema=schema,
        )

    # ---------------------------
    # job_match_cache
    # ---------------------------
    if "job_match_cache" not in tables:
        op.create_table(
            "job_match_cache",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "job_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("jobs.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "ranked_candidate_ids",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("job_id", name="uq_job_match_cache_job_id"),
            schema=schema,
        )
        op.create_index("ix_job_match_cache_job_id", "job_match_cache", ["job_id"], unique=False, schema=schema)
        op.create_index(
            "ix_job_match_cache_generated_at",
            "job_match_cache",
            ["generated_at"],
            unique=False,
            schema=schema,
        )


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema
    tables = _table_names(schema)

    # Drop match cache first (depends on jobs)
    if "job_match_cache" in tables:
        op.drop_index("ix_job_match_cache_generated_at", table_name="job_match_cache", schema=schema)
        op.drop_index("ix_job_match_cache_job_id", table_name="job_match_cache", schema=schema)
        op.drop_table("job_match_cache", schema=schema)

    if "job_submissions" in tables:
        op.drop_index("ix_job_submissions_created_at", table_name="job_submissions", schema=schema)
        op.drop_index(
            "ix_job_submissions_submission_status",
            table_name="job_submissions",
            schema=schema,
        )
        op.drop_index(
            "ix_job_submissions_candidate_id",
            table_name="job_submissions",
            schema=schema,
        )
        op.drop_index("ix_job_submissions_job_id", table_name="job_submissions", schema=schema)
        op.drop_table("job_submissions", schema=schema)

    if "job_skills" in tables:
        op.drop_index("ix_job_skills_skill", table_name="job_skills", schema=schema)
        op.drop_index("ix_job_skills_job_id", table_name="job_skills", schema=schema)
        op.drop_table("job_skills", schema=schema)

    # Drop extensions on jobs
    if "jobs" in tables:
        existing_cols = _column_names("jobs", schema)
        idx_names = _index_names("jobs", schema)
        for idx in ("ix_jobs_location", "ix_jobs_created_at", "ix_jobs_urgency", "ix_jobs_status"):
            if idx in idx_names:
                op.drop_index(idx, table_name="jobs", schema=schema)

        check_names = _check_constraint_names("jobs", schema)
        if "jobs_experience_range_valid" in check_names:
            op.drop_constraint("jobs_experience_range_valid", "jobs", type_="check", schema=schema)
        if "jobs_salary_range_valid" in check_names:
            op.drop_constraint("jobs_salary_range_valid", "jobs", type_="check", schema=schema)

        # Foreign key (may not exist on downgrade ordering)
        fk_names = _foreign_key_constraint_names("jobs", schema)
        if "fk_jobs_created_by_profiles" in fk_names:
            op.drop_constraint(
                "fk_jobs_created_by_profiles",
                "jobs",
                type_="foreignkey",
                schema=schema,
            )

        # Columns
        for col in (
            "created_by",
            "filled_at",
            "urgency",
            "employment_type",
            "experience_max_years",
            "experience_min_years",
            "salary_currency",
            "salary_max",
            "salary_min",
            "location",
        ):
            if col in existing_cols:
                op.drop_column("jobs", col, schema=schema)

