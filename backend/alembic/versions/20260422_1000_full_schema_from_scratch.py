"""Full schema bootstrap migration for clean database setup.

Revision ID: 20260422_1000
Revises:
Create Date: 2026-04-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

# revision identifiers, used by Alembic.
revision: str = "20260422_1000"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("bootstrap",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    op.create_table(
        "organizations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=schema,
    )

    op.create_table(
        "profiles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=schema,
    )
    op.create_foreign_key(
        "fk_profiles_organization_id_organizations",
        "profiles",
        "organizations",
        ["organization_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_index("ix_profiles_organization_id", "profiles", ["organization_id"], unique=False, schema=schema)
    op.create_index("ix_profiles_email", "profiles", ["email"], unique=True, schema=schema)

    op.create_table(
        "candidates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("experience_summary", sa.Text(), nullable=True),
        sa.Column("education", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=schema,
    )
    op.create_index("ix_candidates_organization_id", "candidates", ["organization_id"], unique=False, schema=schema)
    op.create_index("ix_candidates_email", "candidates", ["email"], unique=False, schema=schema)

    op.create_table(
        "clients",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("industry", sa.String(length=120), nullable=True),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=schema,
    )
    op.create_index("ix_clients_organization_id", "clients", ["organization_id"], unique=False, schema=schema)

    op.create_table(
        "jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'draft'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=schema,
    )
    op.create_foreign_key(
        "fk_jobs_client_id_clients",
        "jobs",
        "clients",
        ["client_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_index("ix_jobs_organization_id", "jobs", ["organization_id"], unique=False, schema=schema)
    op.create_index("ix_jobs_client_id", "jobs", ["client_id"], unique=False, schema=schema)

    op.create_table(
        "pipelines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage", sa.String(length=80), nullable=False, server_default=sa.text("'applied'")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'active'")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_pipeline_candidate_job"),
        schema=schema,
    )
    op.create_foreign_key(
        "fk_pipelines_candidate_id_candidates",
        "pipelines",
        "candidates",
        ["candidate_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_foreign_key(
        "fk_pipelines_job_id_jobs",
        "pipelines",
        "jobs",
        ["job_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_index("ix_pipelines_organization_id", "pipelines", ["organization_id"], unique=False, schema=schema)
    op.create_index("ix_pipelines_candidate_id", "pipelines", ["candidate_id"], unique=False, schema=schema)
    op.create_index("ix_pipelines_job_id", "pipelines", ["job_id"], unique=False, schema=schema)

    op.create_table(
        "interviews",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'scheduled'")),
        sa.Column("interviewer_name", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=schema,
    )
    op.create_foreign_key(
        "fk_interviews_pipeline_id_pipelines",
        "interviews",
        "pipelines",
        ["pipeline_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_index("ix_interviews_organization_id", "interviews", ["organization_id"], unique=False, schema=schema)
    op.create_index("ix_interviews_pipeline_id", "interviews", ["pipeline_id"], unique=False, schema=schema)
    op.create_index("ix_interviews_scheduled_at", "interviews", ["scheduled_at"], unique=False, schema=schema)


def downgrade() -> None:
    settings = get_settings()
    schema = settings.db_schema

    op.drop_index("ix_interviews_scheduled_at", table_name="interviews", schema=schema)
    op.drop_index("ix_interviews_pipeline_id", table_name="interviews", schema=schema)
    op.drop_index("ix_interviews_organization_id", table_name="interviews", schema=schema)
    op.drop_constraint("fk_interviews_pipeline_id_pipelines", "interviews", schema=schema, type_="foreignkey")
    op.drop_table("interviews", schema=schema)

    op.drop_index("ix_pipelines_job_id", table_name="pipelines", schema=schema)
    op.drop_index("ix_pipelines_candidate_id", table_name="pipelines", schema=schema)
    op.drop_index("ix_pipelines_organization_id", table_name="pipelines", schema=schema)
    op.drop_constraint("fk_pipelines_job_id_jobs", "pipelines", schema=schema, type_="foreignkey")
    op.drop_constraint("fk_pipelines_candidate_id_candidates", "pipelines", schema=schema, type_="foreignkey")
    op.drop_table("pipelines", schema=schema)

    op.drop_index("ix_jobs_client_id", table_name="jobs", schema=schema)
    op.drop_index("ix_jobs_organization_id", table_name="jobs", schema=schema)
    op.drop_constraint("fk_jobs_client_id_clients", "jobs", schema=schema, type_="foreignkey")
    op.drop_table("jobs", schema=schema)

    op.drop_index("ix_clients_organization_id", table_name="clients", schema=schema)
    op.drop_table("clients", schema=schema)

    op.drop_index("ix_candidates_email", table_name="candidates", schema=schema)
    op.drop_index("ix_candidates_organization_id", table_name="candidates", schema=schema)
    op.drop_table("candidates", schema=schema)

    op.drop_index("ix_profiles_email", table_name="profiles", schema=schema)
    op.drop_index("ix_profiles_organization_id", table_name="profiles", schema=schema)
    op.drop_constraint(
        "fk_profiles_organization_id_organizations",
        "profiles",
        schema=schema,
        type_="foreignkey",
    )
    op.drop_table("profiles", schema=schema)

    op.drop_table("organizations", schema=schema)
