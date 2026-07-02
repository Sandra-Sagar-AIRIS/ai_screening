"""AIRIS consolidated initial schema — microservices edition.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-30

Single, from-scratch migration that builds the COMPLETE AIRIS database for a
brand-new PostgreSQL instance. It supersedes the entire historical Alembic
chain (143 revisions). The schema is organised into one PostgreSQL schema per
microservice. Intra-service foreign keys are enforced; cross-service edges are
kept as indexed reference-ID columns (see the generated comments) so each
schema can later be lifted into its own physical database.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMAS = [
    "identity",
    "candidate",
    "jobs",
    "pipeline",
    "screening",
    "interview",
    "proctoring",
    "communication",
    "ai",
    "analytics",
]


def upgrade() -> None:
    # ───────────────────────────────────────────────────────────────────────
    # 0. Extensions (pgcrypto -> gen_random_uuid(); pg_trgm -> fuzzy search)
    # ───────────────────────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ───────────────────────────────────────────────────────────────────────
    # 1. Service schemas (one per microservice / bounded context)
    # ───────────────────────────────────────────────────────────────────────
    for schema in SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    # ───────────────────────────────────────────────────────────────────────
    # 2. Enum types (created inside their owning service schema)
    # ───────────────────────────────────────────────────────────────────────
    op.execute("CREATE TYPE ai.ai_pricing_status AS ENUM ('configured', 'unknown', 'estimated')")
    op.execute("CREATE TYPE ai.ai_request_status AS ENUM ('success', 'failed', 'timeout', 'cancelled', 'rate_limited', 'partial')")
    op.execute("CREATE TYPE identity.auth_security_event_type AS ENUM ('invalid_signature', 'expired', 'version_mismatch', 'revoked_session', 'rate_limit', 'invalid_invite', 'expired_invite', 'reused_invite', 'unknown')")
    op.execute("CREATE TYPE candidate.candidate_source_type AS ENUM ('internal', 'vendor')")
    op.execute("CREATE TYPE identity.permission_effect AS ENUM ('grant', 'deny')")
    op.execute("CREATE TYPE candidate.sourcing_result_action AS ENUM ('pending', 'shortlisted', 'rejected', 'imported')")
    op.execute("CREATE TYPE candidate.sourcing_session_status AS ENUM ('pending', 'running', 'complete', 'failed')")

    # ═══════════════════════════════════════════════════════════════════════
    # SERVICE: identity
    # ═══════════════════════════════════════════════════════════════════════
    op.execute(
        """
        CREATE TABLE identity.organizations (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	name VARCHAR(255) NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	max_concurrent_sessions INTEGER, 
        	ai_monthly_cost_threshold NUMERIC(14, 2), 
        	ai_threshold_enabled BOOLEAN DEFAULT true NOT NULL, 
        	ai_alert_recipient_emails JSON, 
        	ai_threshold_updated_at TIMESTAMP WITH TIME ZONE, 
        	ai_threshold_updated_by UUID, 
        	billing_timezone VARCHAR(64) DEFAULT 'UTC'::character varying NOT NULL, 
        	screening_reminders_enabled BOOLEAN DEFAULT true NOT NULL, 
        	plan_name VARCHAR(64) NOT NULL, 
        	max_users INTEGER NOT NULL, 
        	dpdpa_enabled BOOLEAN DEFAULT false NOT NULL, 
        	dpdpa_grievance_officer_name VARCHAR(255), 
        	dpdpa_grievance_officer_email VARCHAR(255), 
        	data_localization_region VARCHAR(64), 
        	CONSTRAINT organizations_pkey PRIMARY KEY (id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE identity.permissions (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	code VARCHAR(128) NOT NULL, 
        	module VARCHAR(128) NOT NULL, 
        	display_name VARCHAR(255) NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT permissions_pkey PRIMARY KEY (id)
        )
        """
    )
    op.execute("""CREATE UNIQUE INDEX ix_permissions_code ON identity.permissions USING btree (code)""")
    op.execute("""CREATE INDEX ix_permissions_module ON identity.permissions USING btree (module)""")

    op.execute(
        """
        CREATE TABLE identity.super_admin_audit_logs (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	actor_id UUID NOT NULL, 
        	action VARCHAR(128) NOT NULL, 
        	entity_type VARCHAR(64), 
        	entity_id VARCHAR(255), 
        	details JSONB, 
        	ip_address VARCHAR(64), 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT super_admin_audit_logs_pkey PRIMARY KEY (id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE identity.organization_roles (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	name VARCHAR(128) NOT NULL, 
        	key VARCHAR(64) NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	is_system BOOLEAN DEFAULT false NOT NULL, 
        	description VARCHAR(500), 
        	CONSTRAINT organization_roles_pkey PRIMARY KEY (id), 
        	CONSTRAINT fk_organization_roles_organization_id FOREIGN KEY(organization_id) REFERENCES identity.organizations (id), 
        	CONSTRAINT uq_organization_roles_org_key UNIQUE (organization_id, key)
        )
        """
    )
    op.execute("""CREATE INDEX ix_organization_roles_key ON identity.organization_roles USING btree (key)""")
    op.execute("""CREATE INDEX ix_organization_roles_organization_id ON identity.organization_roles USING btree (organization_id)""")

    op.execute(
        """
        CREATE TABLE identity.workspaces (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	name VARCHAR(255) NOT NULL, 
        	slug VARCHAR(255) NOT NULL, 
        	is_active BOOLEAN DEFAULT true NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT workspaces_pkey PRIMARY KEY (id), 
        	CONSTRAINT workspaces_organization_id_fkey FOREIGN KEY(organization_id) REFERENCES identity.organizations (id) ON DELETE CASCADE, 
        	CONSTRAINT workspaces_organization_id_key UNIQUE (organization_id), 
        	CONSTRAINT workspaces_slug_key UNIQUE (slug)
        )
        """
    )
    op.execute("""CREATE UNIQUE INDEX ix_workspaces_organization_id ON identity.workspaces USING btree (organization_id)""")
    op.execute("""CREATE UNIQUE INDEX ix_workspaces_slug ON identity.workspaces USING btree (slug)""")

    op.execute(
        """
        CREATE TABLE identity.profiles (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	email VARCHAR(255) NOT NULL, 
        	password_hash VARCHAR(255) NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	role VARCHAR(64) DEFAULT 'recruiter'::character varying NOT NULL, 
        	type VARCHAR(32) DEFAULT 'internal'::character varying NOT NULL, 
        	role_id UUID NOT NULL, 
        	first_name VARCHAR(120), 
        	last_name VARCHAR(120), 
        	phone VARCHAR(40), 
        	avatar_url VARCHAR(1024), 
        	email_verified BOOLEAN DEFAULT true NOT NULL, 
        	mfa_enabled BOOLEAN DEFAULT false NOT NULL, 
        	mfa_secret TEXT, 
        	mfa_enrolled_at TIMESTAMP WITH TIME ZONE, 
        	backup_codes JSONB, 
        	token_version INTEGER DEFAULT 1 NOT NULL, 
        	deleted_at TIMESTAMP WITH TIME ZONE, 
        	deleted_by UUID, 
        	CONSTRAINT profiles_pkey PRIMARY KEY (id), 
        	CONSTRAINT fk_profiles_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES identity.organizations (id), 
        	CONSTRAINT fk_profiles_role_id FOREIGN KEY(role_id) REFERENCES identity.organization_roles (id), 
        	CONSTRAINT profiles_organization_id_fkey FOREIGN KEY(organization_id) REFERENCES identity.organizations (id), 
        	CONSTRAINT ck_profiles_role_allowed CHECK (role::text = ANY (ARRAY['admin'::character varying, 'recruiter'::character varying, 'client_viewer'::character varying, 'vendor'::character varying]::text[])), 
        	CONSTRAINT ck_profiles_type_allowed CHECK (type::text = ANY (ARRAY['internal'::character varying, 'client'::character varying]::text[]))
        )
        """
    )
    op.execute("""CREATE INDEX ix_profiles_deleted_at ON identity.profiles USING btree (deleted_at) WHERE (deleted_at IS NOT NULL)""")
    op.execute("""CREATE UNIQUE INDEX ix_profiles_email ON identity.profiles USING btree (email)""")
    op.execute("""CREATE INDEX ix_profiles_organization_id ON identity.profiles USING btree (organization_id)""")
    op.execute("""CREATE INDEX ix_profiles_role_id ON identity.profiles USING btree (role_id)""")

    op.execute(
        """
        CREATE TABLE identity.role_permissions (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	role VARCHAR(64) NOT NULL, 
        	permission VARCHAR(128) NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	role_id UUID NOT NULL, 
        	CONSTRAINT role_permissions_pkey PRIMARY KEY (id), 
        	CONSTRAINT fk_role_permissions_organization_id FOREIGN KEY(organization_id) REFERENCES identity.organizations (id), 
        	CONSTRAINT fk_role_permissions_role_id FOREIGN KEY(role_id) REFERENCES identity.organization_roles (id), 
        	CONSTRAINT uq_role_permissions_org_role_id_permission UNIQUE (organization_id, role_id, permission)
        )
        """
    )
    op.execute("""CREATE INDEX ix_role_permissions_organization_id ON identity.role_permissions USING btree (organization_id)""")
    op.execute("""CREATE INDEX ix_role_permissions_permission ON identity.role_permissions USING btree (permission)""")
    op.execute("""CREATE INDEX ix_role_permissions_role_id ON identity.role_permissions USING btree (role_id)""")

    op.execute(
        """
        CREATE TABLE identity.workspace_settings (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	workspace_id UUID NOT NULL, 
        	timezone VARCHAR(64) DEFAULT 'UTC'::character varying NOT NULL, 
        	date_format VARCHAR(32) DEFAULT 'MM/DD/YYYY'::character varying NOT NULL, 
        	currency VARCHAR(3) DEFAULT 'USD'::character varying NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT workspace_settings_pkey PRIMARY KEY (id), 
        	CONSTRAINT workspace_settings_workspace_id_fkey FOREIGN KEY(workspace_id) REFERENCES identity.workspaces (id) ON DELETE CASCADE, 
        	CONSTRAINT workspace_settings_workspace_id_key UNIQUE (workspace_id)
        )
        """
    )
    op.execute("""CREATE UNIQUE INDEX ix_workspace_settings_workspace_id ON identity.workspace_settings USING btree (workspace_id)""")

    op.execute(
        """
        CREATE TABLE identity.auth_security_logs (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	user_id UUID, 
        	organization_id UUID, 
        	ip_address VARCHAR(64), 
        	event_type identity.auth_security_event_type NOT NULL, 
        	reason VARCHAR(500), 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT auth_security_logs_pkey PRIMARY KEY (id), 
        	CONSTRAINT auth_security_logs_organization_id_fkey FOREIGN KEY(organization_id) REFERENCES identity.organizations (id) ON DELETE SET NULL, 
        	CONSTRAINT auth_security_logs_user_id_fkey FOREIGN KEY(user_id) REFERENCES identity.profiles (id) ON DELETE SET NULL
        )
        """
    )
    op.execute("""CREATE INDEX ix_auth_security_logs_created_at ON identity.auth_security_logs USING btree (created_at)""")
    op.execute("""CREATE INDEX ix_auth_security_logs_event_type ON identity.auth_security_logs USING btree (event_type)""")
    op.execute("""CREATE INDEX ix_auth_security_logs_organization_id ON identity.auth_security_logs USING btree (organization_id)""")
    op.execute("""CREATE INDEX ix_auth_security_logs_user_id ON identity.auth_security_logs USING btree (user_id)""")

    op.execute(
        """
        CREATE TABLE identity.auth_sessions (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	user_id UUID NOT NULL, 
        	refresh_token_hash VARCHAR(128) NOT NULL, 
        	refresh_expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	revoked_at TIMESTAMP WITH TIME ZONE, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	last_used_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT auth_sessions_pkey PRIMARY KEY (id), 
        	CONSTRAINT auth_sessions_organization_id_fkey FOREIGN KEY(organization_id) REFERENCES identity.organizations (id), 
        	CONSTRAINT auth_sessions_user_id_fkey FOREIGN KEY(user_id) REFERENCES identity.profiles (id)
        )
        """
    )
    op.execute("""CREATE INDEX ix_auth_sessions_organization_id ON identity.auth_sessions USING btree (organization_id)""")
    op.execute("""CREATE INDEX ix_auth_sessions_user_id ON identity.auth_sessions USING btree (user_id)""")

    op.execute(
        """
        CREATE TABLE identity.email_verification_tokens (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	user_id UUID NOT NULL, 
        	organization_id UUID NOT NULL, 
        	new_email VARCHAR(255) NOT NULL, 
        	token VARCHAR(255) NOT NULL, 
        	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	used_at TIMESTAMP WITH TIME ZONE, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT email_verification_tokens_pkey PRIMARY KEY (id), 
        	CONSTRAINT email_verification_tokens_organization_id_fkey FOREIGN KEY(organization_id) REFERENCES identity.organizations (id) ON DELETE CASCADE, 
        	CONSTRAINT email_verification_tokens_user_id_fkey FOREIGN KEY(user_id) REFERENCES identity.profiles (id) ON DELETE CASCADE, 
        	CONSTRAINT email_verification_tokens_token_key UNIQUE (token)
        )
        """
    )
    op.execute("""CREATE INDEX ix_email_verification_tokens_expires_at ON identity.email_verification_tokens USING btree (expires_at)""")
    op.execute("""CREATE UNIQUE INDEX ix_email_verification_tokens_token ON identity.email_verification_tokens USING btree (token)""")
    op.execute("""CREATE INDEX ix_email_verification_tokens_user_id ON identity.email_verification_tokens USING btree (user_id)""")

    op.execute(
        """
        CREATE TABLE identity.mfa_trusted_devices (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	user_id UUID NOT NULL, 
        	token_hash VARCHAR(128) NOT NULL, 
        	user_agent VARCHAR(512), 
        	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT mfa_trusted_devices_pkey PRIMARY KEY (id), 
        	CONSTRAINT mfa_trusted_devices_user_id_fkey FOREIGN KEY(user_id) REFERENCES identity.profiles (id) ON DELETE CASCADE, 
        	CONSTRAINT mfa_trusted_devices_token_hash_key UNIQUE (token_hash)
        )
        """
    )
    op.execute("""CREATE UNIQUE INDEX ix_mfa_trusted_devices_token_hash ON identity.mfa_trusted_devices USING btree (token_hash)""")
    op.execute("""CREATE INDEX ix_mfa_trusted_devices_user_id ON identity.mfa_trusted_devices USING btree (user_id)""")

    # ═══════════════════════════════════════════════════════════════════════
    # SERVICE: candidate
    # ═══════════════════════════════════════════════════════════════════════
    op.execute(
        """
        CREATE TABLE candidate.bulk_upload_jobs (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	org_id UUID NOT NULL, 
        	workspace_id UUID NOT NULL, 
        	status VARCHAR(40) DEFAULT 'pending'::character varying NOT NULL, 
        	total_items INTEGER DEFAULT 0 NOT NULL, 
        	processed_items INTEGER DEFAULT 0 NOT NULL, 
        	success_items INTEGER DEFAULT 0 NOT NULL, 
        	failed_items INTEGER DEFAULT 0 NOT NULL, 
        	skipped_items INTEGER DEFAULT 0 NOT NULL, 
        	requested_by UUID, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT bulk_upload_jobs_pkey PRIMARY KEY (id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE candidate.bulk_upload_items (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	org_id UUID NOT NULL, 
        	workspace_id UUID NOT NULL, 
        	job_id UUID NOT NULL, 
        	row_number INTEGER NOT NULL, 
        	resume_s3_key VARCHAR(1024), 
        	original_file_name VARCHAR(512), 
        	status VARCHAR(40) DEFAULT 'pending'::character varying NOT NULL, 
        	extracted_email VARCHAR(320), 
        	extracted_phone VARCHAR(40), 
        	ai_confidence NUMERIC(4, 3), 
        	error_message TEXT, 
        	candidate_id UUID, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT bulk_upload_items_pkey PRIMARY KEY (id), 
        	CONSTRAINT bulk_upload_items_job_id_fkey FOREIGN KEY(job_id) REFERENCES candidate.bulk_upload_jobs (id) ON DELETE CASCADE
        )
        """
    )

    # [candidates] cross-service reference IDs (no FK — integrity at service layer):
    #   - created_by -> identity.profiles.id
    op.execute(
        """
        CREATE TABLE candidate.candidates (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	first_name VARCHAR(100) NOT NULL, 
        	last_name VARCHAR(100) NOT NULL, 
        	email VARCHAR(255) NOT NULL, 
        	phone VARCHAR(50), 
        	location VARCHAR(255), 
        	experience_summary TEXT, 
        	education TEXT, 
        	notes TEXT, 
        	is_deleted BOOLEAN DEFAULT false NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	stage VARCHAR(40) DEFAULT 'applied'::character varying NOT NULL, 
        	job_id UUID, 
        	recruiter_id UUID, 
        	parse_status VARCHAR(20) DEFAULT 'pending'::character varying NOT NULL, 
        	parse_error TEXT, 
        	parsed_at TIMESTAMP WITH TIME ZONE, 
        	created_by UUID, 
        	source_type candidate.candidate_source_type DEFAULT 'internal'::candidate.candidate_source_type NOT NULL, 
        	org_id UUID, 
        	workspace_id UUID, 
        	full_name VARCHAR(260), 
        	headline VARCHAR(255), 
        	summary TEXT, 
        	years_experience DOUBLE PRECISION, 
        	source VARCHAR(40) DEFAULT 'manual'::character varying NOT NULL, 
        	status VARCHAR(40) DEFAULT 'active'::character varying NOT NULL, 
        	resume_s3_key VARCHAR(1024), 
        	resume_file_name VARCHAR(512), 
        	resume_uploaded_at TIMESTAMP WITH TIME ZONE, 
        	ai_parse_version VARCHAR(64), 
        	parse_confidence NUMERIC(4, 3), 
        	parsed_resume_data JSONB, 
        	merged_into_candidate_id UUID, 
        	merged_at TIMESTAMP WITH TIME ZONE, 
        	updated_by UUID, 
        	deleted_by UUID, 
        	deleted_at TIMESTAMP WITH TIME ZONE, 
        	is_merged BOOLEAN DEFAULT false NOT NULL, 
        	merged_into_id UUID, 
        	consent_given BOOLEAN, 
        	consent_given_at TIMESTAMP WITH TIME ZONE, 
        	consent_language VARCHAR(10), 
        	consent_ip_address VARCHAR(64), 
        	CONSTRAINT candidates_pkey PRIMARY KEY (id), 
        	CONSTRAINT fk_candidates_merged_into_id FOREIGN KEY(merged_into_id) REFERENCES candidate.candidates (id) ON DELETE SET NULL, 
        	CONSTRAINT uq_candidates_id_org_workspace UNIQUE (id, org_id, workspace_id)
        )
        """
    )
    op.execute("""CREATE INDEX ix_candidates_created_at ON candidate.candidates USING btree (created_at)""")
    op.execute("""CREATE INDEX ix_candidates_created_by ON candidate.candidates USING btree (created_by)""")
    op.execute("""CREATE INDEX ix_candidates_deleted_at ON candidate.candidates USING btree (deleted_at)""")
    op.execute("""CREATE INDEX ix_candidates_email ON candidate.candidates USING btree (email)""")
    op.execute("""CREATE INDEX ix_candidates_is_merged ON candidate.candidates USING btree (is_merged)""")
    op.execute("""CREATE INDEX ix_candidates_merged_into_id ON candidate.candidates USING btree (merged_into_id)""")
    op.execute("""CREATE INDEX ix_candidates_org_id ON candidate.candidates USING btree (org_id)""")
    op.execute("""CREATE INDEX ix_candidates_organization_id ON candidate.candidates USING btree (organization_id)""")

    # [sourcing_sessions] cross-service reference IDs (no FK — integrity at service layer):
    #   - organization_id -> identity.organizations.id
    #   - created_by -> identity.profiles.id
    op.execute(
        """
        CREATE TABLE candidate.sourcing_sessions (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	job_id UUID, 
        	created_by UUID, 
        	status candidate.sourcing_session_status DEFAULT 'pending'::candidate.sourcing_session_status NOT NULL, 
        	query_snapshot JSONB, 
        	providers_used VARCHAR[], 
        	total_results INTEGER DEFAULT 0 NOT NULL, 
        	error_detail TEXT, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT sourcing_sessions_pkey PRIMARY KEY (id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE candidate.candidate_audit_logs (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	org_id UUID NOT NULL, 
        	workspace_id UUID NOT NULL, 
        	candidate_id UUID NOT NULL, 
        	action VARCHAR(80) NOT NULL, 
        	field_name VARCHAR(80), 
        	old_value JSONB, 
        	new_value JSONB, 
        	actor_user_id UUID, 
        	actor_role VARCHAR(40), 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT candidate_audit_logs_pkey PRIMARY KEY (id), 
        	CONSTRAINT fk_candidate_audit_logs_candidate_tenant FOREIGN KEY(candidate_id, org_id, workspace_id) REFERENCES candidate.candidates (id, org_id, workspace_id) ON DELETE CASCADE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE candidate.candidate_interactions (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	org_id UUID NOT NULL, 
        	workspace_id UUID NOT NULL, 
        	candidate_id UUID NOT NULL, 
        	type VARCHAR(40) NOT NULL, 
        	title VARCHAR(255), 
        	body TEXT, 
        	metadata JSONB, 
        	actor_user_id UUID, 
        	actor_role VARCHAR(40), 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT candidate_interactions_pkey PRIMARY KEY (id), 
        	CONSTRAINT fk_candidate_interactions_candidate_tenant FOREIGN KEY(candidate_id, org_id, workspace_id) REFERENCES candidate.candidates (id, org_id, workspace_id) ON DELETE CASCADE
        )
        """
    )

    # [candidate_job_matches] cross-service reference IDs (no FK — integrity at service layer):
    #   - job_id -> jobs.jobs.id
    op.execute(
        """
        CREATE TABLE candidate.candidate_job_matches (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	candidate_id UUID NOT NULL, 
        	job_id UUID NOT NULL, 
        	match_score INTEGER NOT NULL, 
        	category_scores JSONB, 
        	matched_skills JSONB, 
        	missing_skills JSONB, 
        	matched_preferred_skills JSONB, 
        	recommendation VARCHAR(20) NOT NULL, 
        	confidence_score NUMERIC(4, 3), 
        	evaluated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	deterministic_match_score INTEGER DEFAULT 0 NOT NULL, 
        	semantic_match_score INTEGER, 
        	ai_enrichment_status VARCHAR(32), 
        	recruiter_summary TEXT, 
        	confidence_reasoning TEXT, 
        	semantic_skill_matches JSONB, 
        	transferable_skills JSONB, 
        	inferred_strengths JSONB, 
        	inferred_gaps JSONB, 
        	ats_pipeline_status VARCHAR(32) DEFAULT 'pending'::character varying NOT NULL, 
        	enrichment_started_at TIMESTAMP WITH TIME ZONE, 
        	deterministic_completed_at TIMESTAMP WITH TIME ZONE, 
        	semantic_completed_at TIMESTAMP WITH TIME ZONE, 
        	enrichment_error TEXT, 
        	CONSTRAINT candidate_job_matches_pkey PRIMARY KEY (id), 
        	CONSTRAINT uq_candidate_job_matches_candidate_job UNIQUE (candidate_id, job_id)
        )
        """
    )
    op.execute("""CREATE INDEX ix_candidate_job_matches_candidate_id ON candidate.candidate_job_matches USING btree (candidate_id)""")
    op.execute("""CREATE INDEX ix_candidate_job_matches_job_id ON candidate.candidate_job_matches USING btree (job_id)""")
    op.execute("""CREATE INDEX ix_candidate_job_matches_org_candidate_score ON candidate.candidate_job_matches USING btree (organization_id, candidate_id, match_score)""")
    op.execute("""CREATE INDEX ix_candidate_job_matches_org_job_score ON candidate.candidate_job_matches USING btree (organization_id, job_id, match_score)""")
    op.execute("""CREATE INDEX ix_candidate_job_matches_organization_id ON candidate.candidate_job_matches USING btree (organization_id)""")
    op.execute("""CREATE INDEX ix_cjm_org_candidate_job ON candidate.candidate_job_matches USING btree (organization_id, candidate_id, job_id)""")
    op.execute("""CREATE INDEX ix_cjm_org_status_updated ON candidate.candidate_job_matches USING btree (organization_id, ats_pipeline_status, updated_at)""")

    # [candidate_placement_history] cross-service reference IDs (no FK — integrity at service layer):
    #   - job_id -> jobs.jobs.id
    op.execute(
        """
        CREATE TABLE candidate.candidate_placement_history (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	candidate_id UUID NOT NULL, 
        	job_id UUID NOT NULL, 
        	outcome VARCHAR(20) NOT NULL, 
        	placement_date TIMESTAMP WITH TIME ZONE NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT candidate_placement_history_pkey PRIMARY KEY (id), 
        	CONSTRAINT candidate_placement_history_candidate_id_fkey FOREIGN KEY(candidate_id) REFERENCES candidate.candidates (id) ON DELETE CASCADE, 
        	CONSTRAINT ck_candidate_placement_history_outcome CHECK (outcome::text = ANY (ARRAY['pending'::character varying, 'placed'::character varying, 'rejected'::character varying, 'applied'::character varying, 'ai_interview'::character varying, 'interview'::character varying, 'offer'::character varying]::text[]))
        )
        """
    )

    op.execute(
        """
        CREATE TABLE candidate.candidate_skills (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	org_id UUID NOT NULL, 
        	workspace_id UUID NOT NULL, 
        	candidate_id UUID NOT NULL, 
        	name VARCHAR(120) NOT NULL, 
        	normalized_name VARCHAR(120) NOT NULL, 
        	proficiency VARCHAR(30), 
        	years_experience INTEGER, 
        	confidence NUMERIC(4, 3), 
        	source VARCHAR(40) DEFAULT 'manual'::character varying NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT candidate_skills_pkey PRIMARY KEY (id), 
        	CONSTRAINT fk_candidate_skills_candidate_tenant FOREIGN KEY(candidate_id, org_id, workspace_id) REFERENCES candidate.candidates (id, org_id, workspace_id) ON DELETE CASCADE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE candidate.sourcing_results (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	session_id UUID NOT NULL, 
        	organization_id UUID NOT NULL, 
        	external_id VARCHAR(255), 
        	source VARCHAR(64) NOT NULL, 
        	first_name VARCHAR(100), 
        	last_name VARCHAR(100), 
        	email VARCHAR(255), 
        	phone VARCHAR(50), 
        	location VARCHAR(255), 
        	title VARCHAR(255), 
        	skills VARCHAR[], 
        	ats_score DOUBLE PRECISION, 
        	ats_tier VARCHAR(32), 
        	semantic_score DOUBLE PRECISION, 
        	recruiter_summary TEXT, 
        	matched_skills VARCHAR[], 
        	action candidate.sourcing_result_action DEFAULT 'pending'::candidate.sourcing_result_action NOT NULL, 
        	reject_reason TEXT, 
        	candidate_id UUID, 
        	is_duplicate BOOLEAN DEFAULT false NOT NULL, 
        	raw_data JSONB, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT sourcing_results_pkey PRIMARY KEY (id), 
        	CONSTRAINT sourcing_results_candidate_id_fkey FOREIGN KEY(candidate_id) REFERENCES candidate.candidates (id) ON DELETE SET NULL, 
        	CONSTRAINT sourcing_results_session_id_fkey FOREIGN KEY(session_id) REFERENCES candidate.sourcing_sessions (id) ON DELETE CASCADE
        )
        """
    )

    # ═══════════════════════════════════════════════════════════════════════
    # SERVICE: jobs
    # ═══════════════════════════════════════════════════════════════════════
    op.execute(
        """
        CREATE TABLE jobs.clients (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	name VARCHAR(200) NOT NULL, 
        	legal_name VARCHAR(255), 
        	industry VARCHAR(120), 
        	website VARCHAR(500), 
        	email VARCHAR(255), 
        	phone VARCHAR(50), 
        	location VARCHAR(255), 
        	notes TEXT, 
        	is_deleted BOOLEAN DEFAULT false NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	deleted_at TIMESTAMP WITH TIME ZONE, 
        	deleted_by UUID, 
        	CONSTRAINT clients_pkey PRIMARY KEY (id), 
        	CONSTRAINT uq_clients_org_email UNIQUE (organization_id, email), 
        	CONSTRAINT uq_clients_org_name UNIQUE (organization_id, name)
        )
        """
    )
    op.execute("""CREATE INDEX ix_clients_deleted_at ON jobs.clients USING btree (deleted_at)""")
    op.execute("""CREATE INDEX ix_clients_organization_id ON jobs.clients USING btree (organization_id)""")

    # [client_recruiter_assignments] cross-service reference IDs (no FK — integrity at service layer):
    #   - recruiter_id -> identity.profiles.id
    op.execute(
        """
        CREATE TABLE jobs.client_recruiter_assignments (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	client_id UUID NOT NULL, 
        	recruiter_id UUID NOT NULL, 
        	assigned_by UUID, 
        	assigned_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT client_recruiter_assignments_pkey PRIMARY KEY (id), 
        	CONSTRAINT client_recruiter_assignments_client_id_fkey FOREIGN KEY(client_id) REFERENCES jobs.clients (id) ON DELETE CASCADE, 
        	CONSTRAINT uq_client_recruiter UNIQUE (client_id, recruiter_id)
        )
        """
    )
    op.execute("""CREATE INDEX ix_client_recruiter_assignments_client_id ON jobs.client_recruiter_assignments USING btree (client_id)""")
    op.execute("""CREATE INDEX ix_client_recruiter_assignments_recruiter_id ON jobs.client_recruiter_assignments USING btree (recruiter_id)""")

    # [jobs] cross-service reference IDs (no FK — integrity at service layer):
    #   - created_by -> identity.profiles.id
    op.execute(
        """
        CREATE TABLE jobs.jobs (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	client_id UUID NOT NULL, 
        	title VARCHAR(255) NOT NULL, 
        	description TEXT, 
        	status VARCHAR(32) DEFAULT 'draft'::character varying NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	location VARCHAR(255), 
        	salary_min NUMERIC(10, 2), 
        	salary_max NUMERIC(10, 2), 
        	salary_currency VARCHAR(3) DEFAULT 'USD'::character varying, 
        	experience_min_years INTEGER, 
        	experience_max_years INTEGER, 
        	employment_type VARCHAR(30), 
        	urgency VARCHAR(20) DEFAULT 'standard'::character varying, 
        	filled_at TIMESTAMP WITH TIME ZONE, 
        	created_by UUID, 
        	raw_jd_text TEXT, 
        	parsing_source VARCHAR(20), 
        	parsing_status VARCHAR(20), 
        	paused_reason TEXT, 
        	enrichment_status VARCHAR(32), 
        	jd_document_key VARCHAR(1024), 
        	jd_file_name VARCHAR(512), 
        	location_flexibility VARCHAR(20) DEFAULT 'preferred'::character varying, 
        	key_responsibilities VARCHAR[], 
        	CONSTRAINT jobs_pkey PRIMARY KEY (id), 
        	CONSTRAINT fk_jobs_client_id_clients FOREIGN KEY(client_id) REFERENCES jobs.clients (id), 
        	CONSTRAINT jobs_client_id_fkey FOREIGN KEY(client_id) REFERENCES jobs.clients (id), 
        	CONSTRAINT ck_jobs_status_lifecycle CHECK (status::text = ANY (ARRAY['draft'::character varying::text, 'open'::character varying::text, 'paused'::character varying::text, 'closed'::character varying::text, 'filled'::character varying::text])), 
        	CONSTRAINT jobs_experience_range_valid CHECK (experience_max_years IS NULL OR experience_min_years IS NULL OR experience_min_years <= experience_max_years), 
        	CONSTRAINT jobs_salary_range_valid CHECK (salary_max IS NULL OR salary_min IS NULL OR salary_min <= salary_max)
        )
        """
    )
    op.execute("""CREATE INDEX ix_jobs_client_id ON jobs.jobs USING btree (client_id)""")
    op.execute("""CREATE INDEX ix_jobs_created_at ON jobs.jobs USING btree (created_at)""")
    op.execute("""CREATE INDEX ix_jobs_created_by ON jobs.jobs USING btree (created_by)""")
    op.execute("""CREATE INDEX ix_jobs_location ON jobs.jobs USING btree (location)""")
    op.execute("""CREATE INDEX ix_jobs_organization_id ON jobs.jobs USING btree (organization_id)""")
    op.execute("""CREATE INDEX ix_jobs_status ON jobs.jobs USING btree (status)""")

    # [client_job_access] cross-service reference IDs (no FK — integrity at service layer):
    #   - user_id -> identity.profiles.id
    op.execute(
        """
        CREATE TABLE jobs.client_job_access (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	user_id UUID NOT NULL, 
        	job_id UUID NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT client_job_access_pkey PRIMARY KEY (id), 
        	CONSTRAINT fk_client_job_access_job_id FOREIGN KEY(job_id) REFERENCES jobs.jobs (id), 
        	CONSTRAINT uq_client_job_access_user_job UNIQUE (user_id, job_id)
        )
        """
    )
    op.execute("""CREATE INDEX ix_client_job_access_job_id ON jobs.client_job_access USING btree (job_id)""")
    op.execute("""CREATE INDEX ix_client_job_access_user_id ON jobs.client_job_access USING btree (user_id)""")

    op.execute(
        """
        CREATE TABLE jobs.job_match_cache (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	job_id UUID NOT NULL, 
        	ranked_candidate_ids JSONB DEFAULT '[]'::jsonb NOT NULL, 
        	generated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT job_match_cache_pkey PRIMARY KEY (id), 
        	CONSTRAINT job_match_cache_job_id_fkey FOREIGN KEY(job_id) REFERENCES jobs.jobs (id) ON DELETE CASCADE, 
        	CONSTRAINT uq_job_match_cache_job_id UNIQUE (job_id)
        )
        """
    )
    op.execute("""CREATE INDEX ix_job_match_cache_generated_at ON jobs.job_match_cache USING btree (generated_at)""")
    op.execute("""CREATE INDEX ix_job_match_cache_job_id ON jobs.job_match_cache USING btree (job_id)""")

    op.execute(
        """
        CREATE TABLE jobs.job_skills (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	job_id UUID NOT NULL, 
        	skill VARCHAR(100) NOT NULL, 
        	is_required BOOLEAN DEFAULT true NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT job_skills_pkey PRIMARY KEY (id), 
        	CONSTRAINT job_skills_job_id_fkey FOREIGN KEY(job_id) REFERENCES jobs.jobs (id) ON DELETE CASCADE, 
        	CONSTRAINT uq_job_skills_job_id_skill UNIQUE (job_id, skill)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE jobs.job_status_history (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	job_id UUID NOT NULL, 
        	previous_status VARCHAR(32) NOT NULL, 
        	new_status VARCHAR(32) NOT NULL, 
        	changed_by UUID, 
        	changed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	reason TEXT, 
        	CONSTRAINT job_status_history_pkey PRIMARY KEY (id), 
        	CONSTRAINT job_status_history_job_id_fkey FOREIGN KEY(job_id) REFERENCES jobs.jobs (id) ON DELETE CASCADE
        )
        """
    )
    op.execute("""CREATE INDEX ix_job_status_history_job_id ON jobs.job_status_history USING btree (job_id)""")

    # [job_submissions] cross-service reference IDs (no FK — integrity at service layer):
    #   - submitted_by -> identity.profiles.id
    #   - vendor_id -> identity.profiles.id
    #   - candidate_id -> candidate.candidates.id
    op.execute(
        """
        CREATE TABLE jobs.job_submissions (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	job_id UUID NOT NULL, 
        	candidate_id UUID NOT NULL, 
        	submitted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	submitted_by UUID NOT NULL, 
        	submission_status VARCHAR(30) DEFAULT 'pending'::character varying NOT NULL, 
        	notes TEXT, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	vendor_id UUID, 
        	outcome VARCHAR(20) DEFAULT 'pending'::character varying NOT NULL, 
        	client_feedback TEXT, 
        	CONSTRAINT job_submissions_pkey PRIMARY KEY (id), 
        	CONSTRAINT job_submissions_job_id_fkey FOREIGN KEY(job_id) REFERENCES jobs.jobs (id) ON DELETE CASCADE, 
        	CONSTRAINT uq_job_submissions_job_id_candidate_id UNIQUE (job_id, candidate_id)
        )
        """
    )
    op.execute("""CREATE INDEX ix_job_submissions_submitted_by ON jobs.job_submissions USING btree (submitted_by)""")

    # [job_vendors] cross-service reference IDs (no FK — integrity at service layer):
    #   - vendor_id -> identity.profiles.id
    op.execute(
        """
        CREATE TABLE jobs.job_vendors (
        	job_id UUID NOT NULL, 
        	vendor_id UUID NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT pk_job_vendors_job_vendor PRIMARY KEY (job_id, vendor_id), 
        	CONSTRAINT fk_job_vendors_job_id FOREIGN KEY(job_id) REFERENCES jobs.jobs (id) ON DELETE CASCADE
        )
        """
    )
    op.execute("""CREATE INDEX ix_job_vendors_job_id ON jobs.job_vendors USING btree (job_id)""")

    # ═══════════════════════════════════════════════════════════════════════
    # SERVICE: pipeline
    # ═══════════════════════════════════════════════════════════════════════
    # [applications] cross-service reference IDs (no FK — integrity at service layer):
    #   - candidate_id -> candidate.candidates.id
    #   - job_id -> jobs.jobs.id
    op.execute(
        """
        CREATE TABLE pipeline.applications (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	candidate_id UUID NOT NULL, 
        	job_id UUID NOT NULL, 
        	stage VARCHAR(80) DEFAULT 'applied'::character varying NOT NULL, 
        	status VARCHAR(32) DEFAULT 'active'::character varying NOT NULL, 
        	notes TEXT, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT applications_pkey PRIMARY KEY (id), 
        	CONSTRAINT uq_application_candidate_job UNIQUE (candidate_id, job_id)
        )
        """
    )

    # [pipelines] cross-service reference IDs (no FK — integrity at service layer):
    #   - candidate_id -> candidate.candidates.id
    #   - candidate_id -> candidate.candidates.id
    #   - job_id -> jobs.jobs.id
    #   - job_id -> jobs.jobs.id
    op.execute(
        """
        CREATE TABLE pipeline.pipelines (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	candidate_id UUID NOT NULL, 
        	job_id UUID NOT NULL, 
        	stage VARCHAR(80) DEFAULT 'applied'::character varying NOT NULL, 
        	status VARCHAR(32) DEFAULT 'active'::character varying NOT NULL, 
        	notes TEXT, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	stage_updated_at TIMESTAMP WITH TIME ZONE, 
        	status_changed_at TIMESTAMP WITH TIME ZONE, 
        	CONSTRAINT pipelines_pkey PRIMARY KEY (id), 
        	CONSTRAINT uq_pipeline_candidate_job UNIQUE (candidate_id, job_id)
        )
        """
    )
    op.execute("""CREATE INDEX ix_pipelines_candidate_id ON pipeline.pipelines USING btree (candidate_id)""")
    op.execute("""CREATE INDEX ix_pipelines_created_at ON pipeline.pipelines USING btree (created_at)""")
    op.execute("""CREATE INDEX ix_pipelines_job_id ON pipeline.pipelines USING btree (job_id)""")
    op.execute("""CREATE INDEX ix_pipelines_org_updated ON pipeline.pipelines USING btree (organization_id, updated_at)""")
    op.execute("""CREATE INDEX ix_pipelines_organization_id ON pipeline.pipelines USING btree (organization_id)""")

    op.execute(
        """
        CREATE TABLE pipeline.pipeline_offers (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	pipeline_id UUID NOT NULL, 
        	candidate_id UUID NOT NULL, 
        	job_id UUID NOT NULL, 
        	offered_salary NUMERIC(14, 2) NOT NULL, 
        	currency VARCHAR(3) DEFAULT 'USD'::character varying NOT NULL, 
        	offer_date DATE NOT NULL, 
        	expiry_date DATE NOT NULL, 
        	offer_response VARCHAR(20) DEFAULT 'pending'::character varying NOT NULL, 
        	decline_reason TEXT, 
        	previous_stage VARCHAR(80), 
        	expiry_alert_sent BOOLEAN DEFAULT false NOT NULL, 
        	notes TEXT, 
        	created_by UUID, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT pipeline_offers_pkey PRIMARY KEY (id), 
        	CONSTRAINT pipeline_offers_pipeline_id_fkey FOREIGN KEY(pipeline_id) REFERENCES pipeline.pipelines (id) ON DELETE CASCADE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE pipeline.pipeline_stage_history (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	pipeline_id UUID NOT NULL, 
        	organization_id UUID NOT NULL, 
        	previous_stage VARCHAR(80), 
        	new_stage VARCHAR(80) NOT NULL, 
        	actor_user_id UUID, 
        	reason TEXT, 
        	transitioned_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT pipeline_stage_history_pkey PRIMARY KEY (id), 
        	CONSTRAINT pipeline_stage_history_pipeline_id_fkey FOREIGN KEY(pipeline_id) REFERENCES pipeline.pipelines (id) ON DELETE CASCADE
        )
        """
    )
    op.execute("""CREATE INDEX ix_pipeline_stage_history_organization_id ON pipeline.pipeline_stage_history USING btree (organization_id)""")
    op.execute("""CREATE INDEX ix_pipeline_stage_history_pipeline_id ON pipeline.pipeline_stage_history USING btree (pipeline_id)""")

    op.execute(
        """
        CREATE TABLE pipeline.pipeline_status_history (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	pipeline_id UUID NOT NULL, 
        	organization_id UUID NOT NULL, 
        	previous_status VARCHAR(32), 
        	new_status VARCHAR(32) NOT NULL, 
        	actor_user_id UUID, 
        	reason TEXT, 
        	changed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT pipeline_status_history_pkey PRIMARY KEY (id), 
        	CONSTRAINT pipeline_status_history_pipeline_id_fkey FOREIGN KEY(pipeline_id) REFERENCES pipeline.pipelines (id) ON DELETE CASCADE
        )
        """
    )
    op.execute("""CREATE INDEX ix_pipeline_status_history_organization_id ON pipeline.pipeline_status_history USING btree (organization_id)""")
    op.execute("""CREATE INDEX ix_pipeline_status_history_pipeline_id ON pipeline.pipeline_status_history USING btree (pipeline_id)""")

    op.execute(
        """
        CREATE TABLE pipeline.pipeline_offer_events (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	pipeline_id UUID NOT NULL, 
        	offer_id UUID NOT NULL, 
        	event_type VARCHAR(40) NOT NULL, 
        	actor_user_id UUID, 
        	previous_response VARCHAR(20), 
        	new_response VARCHAR(20), 
        	notes TEXT, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT pipeline_offer_events_pkey PRIMARY KEY (id), 
        	CONSTRAINT pipeline_offer_events_offer_id_fkey FOREIGN KEY(offer_id) REFERENCES pipeline.pipeline_offers (id) ON DELETE CASCADE, 
        	CONSTRAINT pipeline_offer_events_pipeline_id_fkey FOREIGN KEY(pipeline_id) REFERENCES pipeline.pipelines (id) ON DELETE CASCADE
        )
        """
    )

    # ═══════════════════════════════════════════════════════════════════════
    # SERVICE: screening
    # ═══════════════════════════════════════════════════════════════════════
    # [ai_screenings] cross-service reference IDs (no FK — integrity at service layer):
    #   - candidate_id -> candidate.candidates.id
    #   - job_id -> jobs.jobs.id
    op.execute(
        """
        CREATE TABLE screening.ai_screenings (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	candidate_id UUID NOT NULL, 
        	job_id UUID, 
        	created_by UUID, 
        	status VARCHAR(32) DEFAULT 'pending'::character varying NOT NULL, 
        	screening_type VARCHAR(32) DEFAULT 'technical'::character varying NOT NULL, 
        	ai_model VARCHAR(64), 
        	overall_score NUMERIC(5, 2), 
        	communication_score NUMERIC(5, 2), 
        	technical_score NUMERIC(5, 2), 
        	confidence_score NUMERIC(5, 2), 
        	recommendation VARCHAR(32), 
        	ai_summary TEXT, 
        	recruiter_summary TEXT, 
        	recruiter_decision VARCHAR(32), 
        	recruiter_notes TEXT, 
        	generation_context JSONB, 
        	prompt_tokens_used INTEGER, 
        	completion_tokens_used INTEGER, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	completed_at TIMESTAMP WITH TIME ZONE, 
        	interview_mode VARCHAR(32) DEFAULT 'async'::character varying NOT NULL, 
        	session_token VARCHAR(255), 
        	livekit_room_name VARCHAR(255), 
        	candidate_name_snapshot VARCHAR(255), 
        	job_title_snapshot VARCHAR(255), 
        	started_at TIMESTAMP WITH TIME ZONE, 
        	ended_at TIMESTAMP WITH TIME ZONE, 
        	duration_seconds INTEGER, 
        	experience_score NUMERIC(5, 2), 
        	culture_fit_score NUMERIC(5, 2), 
        	salary_expectation VARCHAR(255), 
        	notice_period VARCHAR(128), 
        	career_goals TEXT, 
        	key_projects_mentioned JSONB, 
        	strengths JSONB, 
        	concerns JSONB, 
        	candidate_questions TEXT, 
        	expires_at TIMESTAMP WITH TIME ZONE, 
        	max_questions INTEGER DEFAULT 12, 
        	interview_duration_minutes INTEGER DEFAULT 20, 
        	custom_instructions TEXT, 
        	invitation_sent_at TIMESTAMP WITH TIME ZONE, 
        	invitation_email VARCHAR(255), 
        	video_url VARCHAR(500), 
        	audio_url VARCHAR(500), 
        	leadership_score NUMERIC(5, 2), 
        	reminders_enabled BOOLEAN DEFAULT true NOT NULL, 
        	pipeline_id UUID, 
        	incomplete_reason VARCHAR(500), 
        	recording_status VARCHAR(32), 
        	recording_size_bytes INTEGER, 
        	recording_uploaded_at TIMESTAMP WITH TIME ZONE, 
        	CONSTRAINT ai_screenings_pkey PRIMARY KEY (id), 
        	CONSTRAINT uq_ai_screenings_session_token UNIQUE (session_token)
        )
        """
    )
    op.execute("""CREATE INDEX ix_ai_screenings_candidate_id ON screening.ai_screenings USING btree (candidate_id)""")
    op.execute("""CREATE INDEX ix_ai_screenings_job_id ON screening.ai_screenings USING btree (job_id)""")
    op.execute("""CREATE INDEX ix_ai_screenings_organization_id ON screening.ai_screenings USING btree (organization_id)""")
    op.execute("""CREATE INDEX ix_ai_screenings_status ON screening.ai_screenings USING btree (status)""")

    op.execute(
        """
        CREATE TABLE screening.ai_screening_messages (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	screening_id UUID NOT NULL, 
        	role VARCHAR(32) NOT NULL, 
        	content TEXT NOT NULL, 
        	sequence_number INTEGER DEFAULT 0 NOT NULL, 
        	question_number INTEGER, 
        	is_followup BOOLEAN DEFAULT false NOT NULL, 
        	raw_transcript TEXT, 
        	transcript_confidence NUMERIC(4, 3), 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT ai_screening_messages_pkey PRIMARY KEY (id), 
        	CONSTRAINT ai_screening_messages_screening_id_fkey FOREIGN KEY(screening_id) REFERENCES screening.ai_screenings (id) ON DELETE CASCADE
        )
        """
    )
    op.execute("""CREATE INDEX ix_ai_screening_messages_screening_id ON screening.ai_screening_messages USING btree (screening_id)""")

    op.execute(
        """
        CREATE TABLE screening.ai_screening_questions (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	screening_id UUID NOT NULL, 
        	category VARCHAR(64) NOT NULL, 
        	difficulty VARCHAR(16) DEFAULT 'medium'::character varying NOT NULL, 
        	position INTEGER DEFAULT 0 NOT NULL, 
        	question_text TEXT NOT NULL, 
        	expected_signals JSONB, 
        	generated_by_ai BOOLEAN DEFAULT true NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT ai_screening_questions_pkey PRIMARY KEY (id), 
        	CONSTRAINT ai_screening_questions_screening_id_fkey FOREIGN KEY(screening_id) REFERENCES screening.ai_screenings (id) ON DELETE CASCADE
        )
        """
    )
    op.execute("""CREATE INDEX ix_ai_screening_questions_screening_id ON screening.ai_screening_questions USING btree (screening_id)""")

    op.execute(
        """
        CREATE TABLE screening.ai_screening_reminders (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	screening_id UUID NOT NULL, 
        	reminder_number SMALLINT NOT NULL, 
        	scheduled_for TIMESTAMP WITH TIME ZONE NOT NULL, 
        	sent_at TIMESTAMP WITH TIME ZONE, 
        	status VARCHAR(16) DEFAULT 'pending'::character varying NOT NULL, 
        	failure_reason VARCHAR(500), 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT ai_screening_reminders_pkey PRIMARY KEY (id), 
        	CONSTRAINT ai_screening_reminders_screening_id_fkey FOREIGN KEY(screening_id) REFERENCES screening.ai_screenings (id) ON DELETE CASCADE
        )
        """
    )
    op.execute("""CREATE INDEX ix_ai_screening_reminders_screening_id ON screening.ai_screening_reminders USING btree (screening_id)""")

    op.execute(
        """
        CREATE TABLE screening.ai_screening_segments (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	screening_id UUID NOT NULL, 
        	question_number INTEGER NOT NULL, 
        	question_text TEXT NOT NULL, 
        	transcript TEXT, 
        	question_start_seconds NUMERIC(10, 3), 
        	answer_start_seconds NUMERIC(10, 3), 
        	answer_end_seconds NUMERIC(10, 3), 
        	duration_seconds NUMERIC(10, 3), 
        	video_clip_url VARCHAR(1000), 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT ai_screening_segments_pkey PRIMARY KEY (id), 
        	CONSTRAINT ai_screening_segments_screening_id_fkey FOREIGN KEY(screening_id) REFERENCES screening.ai_screenings (id) ON DELETE CASCADE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE screening.ai_screening_answers (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	screening_id UUID NOT NULL, 
        	question_id UUID NOT NULL, 
        	answer_text TEXT NOT NULL, 
        	recruiter_entered BOOLEAN DEFAULT true NOT NULL, 
        	source_type VARCHAR(32) DEFAULT 'manual'::character varying NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT ai_screening_answers_pkey PRIMARY KEY (id), 
        	CONSTRAINT ai_screening_answers_question_id_fkey FOREIGN KEY(question_id) REFERENCES screening.ai_screening_questions (id) ON DELETE CASCADE, 
        	CONSTRAINT ai_screening_answers_screening_id_fkey FOREIGN KEY(screening_id) REFERENCES screening.ai_screenings (id) ON DELETE CASCADE
        )
        """
    )
    op.execute("""CREATE INDEX ix_ai_screening_answers_question_id ON screening.ai_screening_answers USING btree (question_id)""")
    op.execute("""CREATE INDEX ix_ai_screening_answers_screening_id ON screening.ai_screening_answers USING btree (screening_id)""")

    op.execute(
        """
        CREATE TABLE screening.ai_screening_evaluations (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	screening_id UUID NOT NULL, 
        	question_id UUID NOT NULL, 
        	ai_score INTEGER, 
        	communication_rating INTEGER, 
        	technical_rating INTEGER, 
        	strengths JSONB, 
        	concerns JSONB, 
        	reasoning TEXT, 
        	follow_up_suggestion TEXT, 
        	confidence INTEGER, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT ai_screening_evaluations_pkey PRIMARY KEY (id), 
        	CONSTRAINT ai_screening_evaluations_question_id_fkey FOREIGN KEY(question_id) REFERENCES screening.ai_screening_questions (id) ON DELETE CASCADE, 
        	CONSTRAINT ai_screening_evaluations_screening_id_fkey FOREIGN KEY(screening_id) REFERENCES screening.ai_screenings (id) ON DELETE CASCADE
        )
        """
    )
    op.execute("""CREATE INDEX ix_ai_screening_evaluations_question_id ON screening.ai_screening_evaluations USING btree (question_id)""")
    op.execute("""CREATE INDEX ix_ai_screening_evaluations_screening_id ON screening.ai_screening_evaluations USING btree (screening_id)""")

    # ═══════════════════════════════════════════════════════════════════════
    # SERVICE: interview
    # ═══════════════════════════════════════════════════════════════════════
    op.execute(
        """
        CREATE TABLE interview.interviewer_profiles (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	user_id UUID NOT NULL, 
        	title VARCHAR(255), 
        	department VARCHAR(255), 
        	is_active BOOLEAN DEFAULT true NOT NULL, 
        	max_interviews_per_day INTEGER, 
        	timezone VARCHAR(64), 
        	bio TEXT, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT interviewer_profiles_pkey PRIMARY KEY (id)
        )
        """
    )
    op.execute("""CREATE INDEX ix_interviewer_profiles_organization_id ON interview.interviewer_profiles USING btree (organization_id)""")
    op.execute("""CREATE INDEX ix_interviewer_profiles_user_id ON interview.interviewer_profiles USING btree (user_id)""")

    op.execute(
        """
        CREATE TABLE interview.interviewer_availability (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	interviewer_profile_id UUID NOT NULL, 
        	day_of_week INTEGER NOT NULL, 
        	start_time TIME WITHOUT TIME ZONE NOT NULL, 
        	end_time TIME WITHOUT TIME ZONE NOT NULL, 
        	timezone VARCHAR(64), 
        	CONSTRAINT interviewer_availability_pkey PRIMARY KEY (id), 
        	CONSTRAINT fk_interviewer_availability_profile_id FOREIGN KEY(interviewer_profile_id) REFERENCES interview.interviewer_profiles (id) ON DELETE CASCADE
        )
        """
    )
    op.execute("""CREATE INDEX ix_interviewer_availability_interviewer_profile_id ON interview.interviewer_availability USING btree (interviewer_profile_id)""")

    op.execute(
        """
        CREATE TABLE interview.interviewer_skills (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	interviewer_profile_id UUID NOT NULL, 
        	skill VARCHAR(128) NOT NULL, 
        	CONSTRAINT interviewer_skills_pkey PRIMARY KEY (id), 
        	CONSTRAINT fk_interviewer_skills_profile_id FOREIGN KEY(interviewer_profile_id) REFERENCES interview.interviewer_profiles (id) ON DELETE CASCADE
        )
        """
    )
    op.execute("""CREATE INDEX ix_interviewer_skills_interviewer_profile_id ON interview.interviewer_skills USING btree (interviewer_profile_id)""")

    # [invites] cross-service reference IDs (no FK — integrity at service layer):
    #   - organization_id -> identity.organizations.id
    op.execute(
        """
        CREATE TABLE interview.invites (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	email VARCHAR(255) NOT NULL, 
        	organization_id UUID NOT NULL, 
        	role VARCHAR(32) NOT NULL, 
        	token VARCHAR(255) NOT NULL, 
        	status VARCHAR(16) DEFAULT 'pending'::character varying NOT NULL, 
        	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	sent_at TIMESTAMP WITH TIME ZONE, 
        	opened_at TIMESTAMP WITH TIME ZONE, 
        	accepted_at TIMESTAMP WITH TIME ZONE, 
        	expired_at TIMESTAMP WITH TIME ZONE, 
        	delivery_status VARCHAR(16) DEFAULT 'pending'::character varying NOT NULL, 
        	delivery_provider VARCHAR(64), 
        	message_id VARCHAR(255), 
        	delivery_attempts INTEGER DEFAULT 0 NOT NULL, 
        	last_delivery_attempt_at TIMESTAMP WITH TIME ZONE, 
        	last_delivery_error VARCHAR(500), 
        	CONSTRAINT invites_pkey PRIMARY KEY (id), 
        	CONSTRAINT uq_invites_token UNIQUE (token), 
        	CONSTRAINT ck_invites_status_lifecycle CHECK (status::text = ANY (ARRAY['sent'::character varying, 'opened'::character varying, 'accepted'::character varying, 'expired'::character varying]::text[]))
        )
        """
    )
    op.execute("""CREATE INDEX ix_invites_email ON interview.invites USING btree (email)""")
    op.execute("""CREATE INDEX ix_invites_expires_at ON interview.invites USING btree (expires_at)""")
    op.execute("""CREATE INDEX ix_invites_organization_id ON interview.invites USING btree (organization_id)""")
    op.execute("""CREATE INDEX ix_invites_role ON interview.invites USING btree (role)""")
    op.execute("""CREATE UNIQUE INDEX ix_invites_token ON interview.invites USING btree (token)""")

    # [interview_booking_links] cross-service reference IDs (no FK — integrity at service layer):
    #   - job_id -> jobs.jobs.id
    #   - organization_id -> identity.organizations.id
    #   - pipeline_id -> pipeline.pipelines.id
    #   - candidate_id -> candidate.candidates.id
    #   - recruiter_id -> identity.profiles.id
    op.execute(
        """
        CREATE TABLE interview.interview_booking_links (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	recruiter_id UUID NOT NULL, 
        	candidate_id UUID, 
        	job_id UUID, 
        	pipeline_id UUID, 
        	token UUID DEFAULT gen_random_uuid() NOT NULL, 
        	title VARCHAR(255) NOT NULL, 
        	description TEXT, 
        	duration_minutes INTEGER DEFAULT 60 NOT NULL, 
        	timezone VARCHAR(64) DEFAULT 'UTC'::character varying NOT NULL, 
        	interview_type VARCHAR(32), 
        	meeting_type VARCHAR(32), 
        	location VARCHAR(255), 
        	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	status VARCHAR(16) DEFAULT 'active'::character varying NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT interview_booking_links_pkey PRIMARY KEY (id), 
        	CONSTRAINT interview_booking_links_token_key UNIQUE (token)
        )
        """
    )
    op.execute("""CREATE INDEX ix_booking_links_candidate_id ON interview.interview_booking_links USING btree (candidate_id)""")
    op.execute("""CREATE INDEX ix_booking_links_organization_id ON interview.interview_booking_links USING btree (organization_id)""")
    op.execute("""CREATE INDEX ix_booking_links_recruiter_id ON interview.interview_booking_links USING btree (recruiter_id)""")
    op.execute("""CREATE INDEX ix_booking_links_status ON interview.interview_booking_links USING btree (status)""")
    op.execute("""CREATE UNIQUE INDEX ix_booking_links_token ON interview.interview_booking_links USING btree (token)""")

    # [interview_voice_profiles] cross-service reference IDs (no FK — integrity at service layer):
    #   - screening_id -> screening.ai_screenings.id
    op.execute(
        """
        CREATE TABLE interview.interview_voice_profiles (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	screening_id UUID NOT NULL, 
        	embedding JSONB, 
        	mismatch_streak SMALLINT DEFAULT 0 NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT interview_voice_profiles_pkey PRIMARY KEY (id)
        )
        """
    )
    op.execute("""CREATE UNIQUE INDEX ix_interview_voice_profiles_screening_id ON interview.interview_voice_profiles USING btree (screening_id)""")

    # [interviews] cross-service reference IDs (no FK — integrity at service layer):
    #   - candidate_id -> candidate.candidates.id
    #   - pipeline_id -> pipeline.pipelines.id
    #   - pipeline_id -> pipeline.pipelines.id
    #   - job_id -> jobs.jobs.id
    op.execute(
        """
        CREATE TABLE interview.interviews (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	pipeline_id UUID NOT NULL, 
        	scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	status VARCHAR(32) DEFAULT 'scheduled'::character varying NOT NULL, 
        	interviewer_name VARCHAR(255), 
        	notes TEXT, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	interview_type VARCHAR(32), 
        	duration_minutes INTEGER, 
        	meeting_link VARCHAR(512), 
        	location VARCHAR(255), 
        	created_by UUID, 
        	candidate_id UUID, 
        	job_id UUID, 
        	meeting_type VARCHAR(32), 
        	meeting_provider VARCHAR(32), 
        	started_at TIMESTAMP WITH TIME ZONE, 
        	ended_at TIMESTAMP WITH TIME ZONE, 
        	ai_summary JSONB, 
        	ai_summary_generated_at TIMESTAMP WITH TIME ZONE, 
        	ai_summary_provider VARCHAR(64), 
        	ai_summary_edited BOOLEAN DEFAULT false NOT NULL, 
        	reschedule_count INTEGER DEFAULT 0 NOT NULL, 
        	last_rescheduled_at TIMESTAMP WITH TIME ZONE, 
        	reschedule_reason TEXT, 
        	CONSTRAINT interviews_pkey PRIMARY KEY (id)
        )
        """
    )
    op.execute("""CREATE INDEX ix_interviews_candidate_id ON interview.interviews USING btree (candidate_id)""")
    op.execute("""CREATE INDEX ix_interviews_job_id ON interview.interviews USING btree (job_id)""")
    op.execute("""CREATE INDEX ix_interviews_organization_id ON interview.interviews USING btree (organization_id)""")
    op.execute("""CREATE INDEX ix_interviews_pipeline_id ON interview.interviews USING btree (pipeline_id)""")
    op.execute("""CREATE INDEX ix_interviews_scheduled_at ON interview.interviews USING btree (scheduled_at)""")

    op.execute(
        """
        CREATE TABLE interview.interview_booking_slots (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	booking_link_id UUID NOT NULL, 
        	start_time TIMESTAMP WITH TIME ZONE NOT NULL, 
        	end_time TIMESTAMP WITH TIME ZONE NOT NULL, 
        	is_booked BOOLEAN DEFAULT false NOT NULL, 
        	booked_at TIMESTAMP WITH TIME ZONE, 
        	interview_id UUID, 
        	CONSTRAINT interview_booking_slots_pkey PRIMARY KEY (id), 
        	CONSTRAINT interview_booking_slots_booking_link_id_fkey FOREIGN KEY(booking_link_id) REFERENCES interview.interview_booking_links (id) ON DELETE CASCADE, 
        	CONSTRAINT interview_booking_slots_interview_id_fkey FOREIGN KEY(interview_id) REFERENCES interview.interviews (id)
        )
        """
    )
    op.execute("""CREATE INDEX ix_booking_slots_booking_link_id ON interview.interview_booking_slots USING btree (booking_link_id)""")

    op.execute(
        """
        CREATE TABLE interview.interview_copilot_sessions (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	interview_id UUID NOT NULL, 
        	status VARCHAR(32) DEFAULT 'active'::character varying NOT NULL, 
        	summary JSONB, 
        	skills_covered JSONB, 
        	prompt_tokens_used INTEGER DEFAULT 0 NOT NULL, 
        	completion_tokens_used INTEGER DEFAULT 0 NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	summarized_at TIMESTAMP WITH TIME ZONE, 
        	CONSTRAINT interview_copilot_sessions_pkey PRIMARY KEY (id), 
        	CONSTRAINT interview_copilot_sessions_interview_id_fkey FOREIGN KEY(interview_id) REFERENCES interview.interviews (id) ON DELETE CASCADE, 
        	CONSTRAINT interview_copilot_sessions_interview_id_key UNIQUE (interview_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE interview.interview_feedback (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	interview_id UUID NOT NULL, 
        	reviewer_id UUID NOT NULL, 
        	rating INTEGER, 
        	recommendation VARCHAR(32), 
        	strengths TEXT, 
        	weaknesses TEXT, 
        	notes TEXT, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	technical_score INTEGER, 
        	communication_score INTEGER, 
        	problem_solving_score INTEGER, 
        	culture_fit_score INTEGER, 
        	submitted_at TIMESTAMP WITH TIME ZONE, 
        	system_design_score INTEGER, 
        	leadership_score INTEGER, 
        	CONSTRAINT interview_feedback_pkey PRIMARY KEY (id), 
        	CONSTRAINT fk_interview_feedback_interview_id FOREIGN KEY(interview_id) REFERENCES interview.interviews (id) ON DELETE CASCADE
        )
        """
    )
    op.execute("""CREATE INDEX ix_interview_feedback_interview_id ON interview.interview_feedback USING btree (interview_id)""")

    op.execute(
        """
        CREATE TABLE interview.interview_notes (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	interview_id UUID NOT NULL, 
        	interviewer_id UUID NOT NULL, 
        	organization_id UUID NOT NULL, 
        	section VARCHAR(64), 
        	content TEXT DEFAULT ''::text NOT NULL, 
        	autosaved_at TIMESTAMP WITH TIME ZONE, 
        	finalized BOOLEAN DEFAULT false NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT interview_notes_pkey PRIMARY KEY (id), 
        	CONSTRAINT fk_interview_notes_interview_id FOREIGN KEY(interview_id) REFERENCES interview.interviews (id) ON DELETE CASCADE
        )
        """
    )
    op.execute("""CREATE INDEX ix_interview_notes_interview_id ON interview.interview_notes USING btree (interview_id)""")
    op.execute("""CREATE INDEX ix_interview_notes_interviewer_id ON interview.interview_notes USING btree (interviewer_id)""")
    op.execute("""CREATE INDEX ix_interview_notes_organization_id ON interview.interview_notes USING btree (organization_id)""")

    op.execute(
        """
        CREATE TABLE interview.interview_participants (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	interview_id UUID NOT NULL, 
        	user_id UUID NOT NULL, 
        	role VARCHAR(32) DEFAULT 'interviewer'::character varying NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	organization_id UUID, 
        	participant_role VARCHAR(32) DEFAULT 'panel'::character varying NOT NULL, 
        	status VARCHAR(32) DEFAULT 'accepted'::character varying NOT NULL, 
        	joined_at TIMESTAMP WITH TIME ZONE, 
        	CONSTRAINT interview_participants_pkey PRIMARY KEY (id), 
        	CONSTRAINT fk_interview_participants_interview_id FOREIGN KEY(interview_id) REFERENCES interview.interviews (id) ON DELETE CASCADE
        )
        """
    )
    op.execute("""CREATE INDEX ix_interview_participants_interview_id ON interview.interview_participants USING btree (interview_id)""")
    op.execute("""CREATE INDEX ix_interview_participants_organization_id ON interview.interview_participants USING btree (organization_id)""")
    op.execute("""CREATE INDEX ix_interview_participants_user_id ON interview.interview_participants USING btree (user_id)""")

    op.execute(
        """
        CREATE TABLE interview.interview_reminders (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	interview_id UUID NOT NULL, 
        	organization_id UUID NOT NULL, 
        	reminder_type VARCHAR(8) NOT NULL, 
        	recipient_type VARCHAR(16) NOT NULL, 
        	recipient_email VARCHAR(255) NOT NULL, 
        	scheduled_for TIMESTAMP WITH TIME ZONE NOT NULL, 
        	status VARCHAR(16) DEFAULT 'scheduled'::character varying NOT NULL, 
        	sent_at TIMESTAMP WITH TIME ZONE, 
        	failure_reason TEXT, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT interview_reminders_pkey PRIMARY KEY (id), 
        	CONSTRAINT interview_reminders_interview_id_fkey FOREIGN KEY(interview_id) REFERENCES interview.interviews (id) ON DELETE CASCADE
        )
        """
    )

    # [interview_reschedule_history] cross-service reference IDs (no FK — integrity at service layer):
    #   - changed_by -> identity.profiles.id
    op.execute(
        """
        CREATE TABLE interview.interview_reschedule_history (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	interview_id UUID NOT NULL, 
        	old_scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	new_scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	reason TEXT, 
        	changed_by UUID, 
        	changed_by_type VARCHAR(16) DEFAULT 'recruiter'::character varying NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT interview_reschedule_history_pkey PRIMARY KEY (id), 
        	CONSTRAINT interview_reschedule_history_interview_id_fkey FOREIGN KEY(interview_id) REFERENCES interview.interviews (id) ON DELETE CASCADE
        )
        """
    )
    op.execute("""CREATE INDEX ix_reschedule_history_interview_id ON interview.interview_reschedule_history USING btree (interview_id)""")

    op.execute(
        """
        CREATE TABLE interview.interview_ai_suggestions (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	session_id UUID NOT NULL, 
        	interview_id UUID NOT NULL, 
        	organization_id UUID NOT NULL, 
        	suggestion_type VARCHAR(32) DEFAULT 'follow_up'::character varying NOT NULL, 
        	question_text TEXT NOT NULL, 
        	rationale TEXT, 
        	target_skills JSONB, 
        	difficulty VARCHAR(16), 
        	used BOOLEAN DEFAULT false NOT NULL, 
        	used_at TIMESTAMP WITH TIME ZONE, 
        	dismissed BOOLEAN DEFAULT false NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT interview_ai_suggestions_pkey PRIMARY KEY (id), 
        	CONSTRAINT interview_ai_suggestions_interview_id_fkey FOREIGN KEY(interview_id) REFERENCES interview.interviews (id) ON DELETE CASCADE, 
        	CONSTRAINT interview_ai_suggestions_session_id_fkey FOREIGN KEY(session_id) REFERENCES interview.interview_copilot_sessions (id) ON DELETE CASCADE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE interview.interview_transcript_segments (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	session_id UUID NOT NULL, 
        	interview_id UUID NOT NULL, 
        	organization_id UUID NOT NULL, 
        	speaker VARCHAR(32) DEFAULT 'unknown'::character varying NOT NULL, 
        	content TEXT NOT NULL, 
        	offset_ms INTEGER, 
        	duration_ms INTEGER, 
        	source VARCHAR(32) DEFAULT 'manual'::character varying NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT interview_transcript_segments_pkey PRIMARY KEY (id), 
        	CONSTRAINT interview_transcript_segments_interview_id_fkey FOREIGN KEY(interview_id) REFERENCES interview.interviews (id) ON DELETE CASCADE, 
        	CONSTRAINT interview_transcript_segments_session_id_fkey FOREIGN KEY(session_id) REFERENCES interview.interview_copilot_sessions (id) ON DELETE CASCADE
        )
        """
    )

    # ═══════════════════════════════════════════════════════════════════════
    # SERVICE: proctoring
    # ═══════════════════════════════════════════════════════════════════════
    # [proctoring_sessions] cross-service reference IDs (no FK — integrity at service layer):
    #   - screening_id -> screening.ai_screenings.id
    op.execute(
        """
        CREATE TABLE proctoring.proctoring_sessions (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	screening_id UUID NOT NULL, 
        	is_hardware_verified BOOLEAN DEFAULT false NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	baseline_image_url VARCHAR, 
        	CONSTRAINT proctoring_sessions_pkey PRIMARY KEY (id)
        )
        """
    )
    op.execute("""CREATE UNIQUE INDEX ix_proctoring_sessions_screening_id ON proctoring.proctoring_sessions USING btree (screening_id)""")

    op.execute(
        """
        CREATE TABLE proctoring.proctoring_events (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	session_id UUID NOT NULL, 
        	event_type VARCHAR(64) NOT NULL, 
        	timestamp TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	details JSONB, 
        	confidence NUMERIC(5, 4), 
        	CONSTRAINT proctoring_events_pkey PRIMARY KEY (id), 
        	CONSTRAINT proctoring_events_session_id_fkey FOREIGN KEY(session_id) REFERENCES proctoring.proctoring_sessions (id) ON DELETE CASCADE
        )
        """
    )
    op.execute("""CREATE INDEX ix_proctoring_events_session_id ON proctoring.proctoring_events USING btree (session_id)""")

    op.execute(
        """
        CREATE TABLE proctoring.proctoring_risk_scores (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	session_id UUID NOT NULL, 
        	trust_score SMALLINT DEFAULT 100 NOT NULL, 
        	risk_score SMALLINT DEFAULT 0 NOT NULL, 
        	risk_level VARCHAR(8) DEFAULT 'low'::character varying NOT NULL, 
        	tab_switches SMALLINT DEFAULT 0 NOT NULL, 
        	fullscreen_exits SMALLINT DEFAULT 0 NOT NULL, 
        	window_blurs SMALLINT DEFAULT 0 NOT NULL, 
        	face_missing_count SMALLINT DEFAULT 0 NOT NULL, 
        	multiple_person_count SMALLINT DEFAULT 0 NOT NULL, 
        	mobile_detected_count SMALLINT DEFAULT 0 NOT NULL, 
        	copy_paste_count SMALLINT DEFAULT 0 NOT NULL, 
        	identity_mismatch_count SMALLINT DEFAULT 0 NOT NULL, 
        	voice_mismatch_count SMALLINT DEFAULT 0 NOT NULL, 
        	computed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT proctoring_risk_scores_pkey PRIMARY KEY (id), 
        	CONSTRAINT proctoring_risk_scores_session_id_fkey FOREIGN KEY(session_id) REFERENCES proctoring.proctoring_sessions (id) ON DELETE CASCADE
        )
        """
    )
    op.execute("""CREATE UNIQUE INDEX ix_proctoring_risk_scores_session_id ON proctoring.proctoring_risk_scores USING btree (session_id)""")

    op.execute(
        """
        CREATE TABLE proctoring.proctoring_evidence (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	event_id UUID NOT NULL, 
        	session_id UUID NOT NULL, 
        	storage_key VARCHAR(512), 
        	captured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
        	frame_index SMALLINT DEFAULT 0 NOT NULL, 
        	width_px INTEGER, 
        	height_px INTEGER, 
        	size_bytes INTEGER, 
        	upload_status VARCHAR(16) DEFAULT 'pending'::character varying NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT proctoring_evidence_pkey PRIMARY KEY (id), 
        	CONSTRAINT proctoring_evidence_event_id_fkey FOREIGN KEY(event_id) REFERENCES proctoring.proctoring_events (id) ON DELETE CASCADE, 
        	CONSTRAINT proctoring_evidence_session_id_fkey FOREIGN KEY(session_id) REFERENCES proctoring.proctoring_sessions (id) ON DELETE CASCADE
        )
        """
    )
    op.execute("""CREATE INDEX ix_proctoring_evidence_event_id ON proctoring.proctoring_evidence USING btree (event_id)""")
    op.execute("""CREATE INDEX ix_proctoring_evidence_session_id ON proctoring.proctoring_evidence USING btree (session_id)""")

    # ═══════════════════════════════════════════════════════════════════════
    # SERVICE: communication
    # ═══════════════════════════════════════════════════════════════════════
    op.execute(
        """
        CREATE TABLE communication.comm_connections (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	org_id UUID NOT NULL, 
        	workspace_id UUID NOT NULL, 
        	user_id UUID, 
        	provider VARCHAR(24) NOT NULL, 
        	channel VARCHAR(24) DEFAULT 'email'::character varying NOT NULL, 
        	external_account_id VARCHAR(255) NOT NULL, 
        	external_account_email VARCHAR(320), 
        	access_token_encrypted TEXT, 
        	refresh_token_encrypted TEXT, 
        	token_expires_at TIMESTAMP WITH TIME ZONE, 
        	scopes JSONB, 
        	status VARCHAR(32) DEFAULT 'connected'::character varying NOT NULL, 
        	last_error TEXT, 
        	last_sync_at TIMESTAMP WITH TIME ZONE, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT comm_connections_pkey PRIMARY KEY (id), 
        	CONSTRAINT uq_comm_connections_account_provider UNIQUE (org_id, workspace_id, provider, external_account_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE communication.comm_templates (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	org_id UUID NOT NULL, 
        	workspace_id UUID NOT NULL, 
        	channel VARCHAR(24) DEFAULT 'email'::character varying NOT NULL, 
        	provider VARCHAR(24), 
        	name VARCHAR(140) NOT NULL, 
        	subject_template VARCHAR(255), 
        	body_template TEXT NOT NULL, 
        	placeholders JSONB, 
        	is_deleted BOOLEAN DEFAULT false NOT NULL, 
        	created_by UUID, 
        	updated_by UUID, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	category VARCHAR(80), 
        	CONSTRAINT comm_templates_pkey PRIMARY KEY (id), 
        	CONSTRAINT uq_comm_templates_name_per_channel UNIQUE (org_id, workspace_id, channel, name)
        )
        """
    )

    # [comm_messages] cross-service reference IDs (no FK — integrity at service layer):
    #   - candidate_id -> candidate.candidates.id
    op.execute(
        """
        CREATE TABLE communication.comm_messages (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	org_id UUID NOT NULL, 
        	workspace_id UUID NOT NULL, 
        	candidate_id UUID NOT NULL, 
        	channel VARCHAR(24) DEFAULT 'email'::character varying NOT NULL, 
        	provider VARCHAR(24) NOT NULL, 
        	direction VARCHAR(24) DEFAULT 'outbound'::character varying NOT NULL, 
        	status VARCHAR(24) DEFAULT 'queued'::character varying NOT NULL, 
        	to_address VARCHAR(320), 
        	from_address VARCHAR(320), 
        	subject VARCHAR(255), 
        	body TEXT, 
        	template_id UUID, 
        	provider_message_id VARCHAR(255), 
        	idempotency_key VARCHAR(120), 
        	failure_reason TEXT, 
        	sent_by_user_id UUID, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	attachments JSONB, 
        	CONSTRAINT comm_messages_pkey PRIMARY KEY (id), 
        	CONSTRAINT comm_messages_template_id_fkey FOREIGN KEY(template_id) REFERENCES communication.comm_templates (id), 
        	CONSTRAINT uq_comm_messages_provider_message_id UNIQUE (org_id, workspace_id, provider, provider_message_id)
        )
        """
    )

    # [comm_reminders] cross-service reference IDs (no FK — integrity at service layer):
    #   - candidate_id -> candidate.candidates.id
    op.execute(
        """
        CREATE TABLE communication.comm_reminders (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	org_id UUID NOT NULL, 
        	workspace_id UUID NOT NULL, 
        	candidate_id UUID NOT NULL, 
        	channel VARCHAR(24) DEFAULT 'email'::character varying NOT NULL, 
        	provider VARCHAR(24) NOT NULL, 
        	template_id UUID, 
        	to_address VARCHAR(320), 
        	subject VARCHAR(255), 
        	body TEXT, 
        	template_values JSONB, 
        	scheduled_for TIMESTAMP WITH TIME ZONE NOT NULL, 
        	status VARCHAR(24) DEFAULT 'pending'::character varying NOT NULL, 
        	failure_reason TEXT, 
        	created_by_user_id UUID, 
        	processed_at TIMESTAMP WITH TIME ZONE, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT comm_reminders_pkey PRIMARY KEY (id), 
        	CONSTRAINT comm_reminders_template_id_fkey FOREIGN KEY(template_id) REFERENCES communication.comm_templates (id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE communication.comm_message_events (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	org_id UUID NOT NULL, 
        	workspace_id UUID NOT NULL, 
        	message_id UUID NOT NULL, 
        	event_type VARCHAR(64) NOT NULL, 
        	provider_payload JSONB, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT comm_message_events_pkey PRIMARY KEY (id), 
        	CONSTRAINT comm_message_events_message_id_fkey FOREIGN KEY(message_id) REFERENCES communication.comm_messages (id) ON DELETE CASCADE
        )
        """
    )

    # ═══════════════════════════════════════════════════════════════════════
    # SERVICE: ai
    # ═══════════════════════════════════════════════════════════════════════
    op.execute(
        """
        CREATE TABLE ai.ai_log_cleanup_audit (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	retention_days_used INTEGER NOT NULL, 
        	records_processed INTEGER NOT NULL, 
        	records_soft_deleted INTEGER NOT NULL, 
        	executed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	execution_duration_ms INTEGER NOT NULL, 
        	status VARCHAR(50) NOT NULL, 
        	error_message TEXT, 
        	CONSTRAINT ai_log_cleanup_audit_pkey PRIMARY KEY (id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE ai.ai_model_pricing_master (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	provider_name VARCHAR(50) NOT NULL, 
        	model_name VARCHAR(100) NOT NULL, 
        	input_rate_per_million_tokens NUMERIC(14, 8) NOT NULL, 
        	output_rate_per_million_tokens NUMERIC(14, 8) NOT NULL, 
        	effective_from TIMESTAMP WITH TIME ZONE NOT NULL, 
        	effective_to TIMESTAMP WITH TIME ZONE, 
        	is_active BOOLEAN NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT ai_model_pricing_master_pkey PRIMARY KEY (id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE ai.ai_rate_limit_log (
        	id BIGSERIAL NOT NULL, 
        	user_id UUID, 
        	organization_id UUID, 
        	ip_address VARCHAR(45), 
        	endpoint VARCHAR(255) NOT NULL, 
        	blocked_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT ai_rate_limit_log_pkey PRIMARY KEY (id)
        )
        """
    )
    op.execute("""CREATE INDEX ix_ai_rl_log_blocked_at ON ai.ai_rate_limit_log USING btree (blocked_at)""")
    op.execute("""CREATE INDEX ix_ai_rl_log_org ON ai.ai_rate_limit_log USING btree (organization_id)""")
    op.execute("""CREATE INDEX ix_ai_rl_log_user ON ai.ai_rate_limit_log USING btree (user_id)""")

    # [ai_cost_alerts] cross-service reference IDs (no FK — integrity at service layer):
    #   - organization_id -> identity.organizations.id
    op.execute(
        """
        CREATE TABLE ai.ai_cost_alerts (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	billing_month VARCHAR(7) NOT NULL, 
        	alert_type VARCHAR(20) NOT NULL, 
        	threshold_amount NUMERIC(14, 2) NOT NULL, 
        	current_amount NUMERIC(14, 2) NOT NULL, 
        	notification_status VARCHAR(20) DEFAULT 'pending'::character varying NOT NULL, 
        	notification_error TEXT, 
        	notified_at TIMESTAMP WITH TIME ZONE, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT ai_cost_alerts_pkey PRIMARY KEY (id), 
        	CONSTRAINT uq_ai_cost_alert_org_month_type UNIQUE (organization_id, billing_month, alert_type)
        )
        """
    )
    op.execute("""CREATE INDEX ix_ai_cost_alerts_organization_id ON ai.ai_cost_alerts USING btree (organization_id)""")

    # [ai_log_retention_config] cross-service reference IDs (no FK — integrity at service layer):
    #   - organization_id -> identity.organizations.id
    op.execute(
        """
        CREATE TABLE ai.ai_log_retention_config (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID, 
        	retention_days INTEGER DEFAULT 730 NOT NULL, 
        	is_enabled BOOLEAN DEFAULT true NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	CONSTRAINT ai_log_retention_config_pkey PRIMARY KEY (id)
        )
        """
    )
    op.execute("""CREATE UNIQUE INDEX ix_ai_log_retention_config_organization_id ON ai.ai_log_retention_config USING btree (organization_id)""")

    # [ai_request_log] cross-service reference IDs (no FK — integrity at service layer):
    #   - organization_id -> identity.organizations.id
    op.execute(
        """
        CREATE TABLE ai.ai_request_log (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	organization_id UUID NOT NULL, 
        	user_id UUID, 
        	function_name VARCHAR(100) NOT NULL, 
        	provider VARCHAR(50) NOT NULL, 
        	model_name VARCHAR(100) NOT NULL, 
        	input_tokens BIGINT, 
        	output_tokens BIGINT, 
        	total_tokens BIGINT, 
        	credits_used BIGINT, 
        	input_cost_rate NUMERIC(14, 8) DEFAULT '0'::numeric NOT NULL, 
        	output_cost_rate NUMERIC(14, 8) DEFAULT '0'::numeric NOT NULL, 
        	pricing_unit INTEGER DEFAULT 1000000 NOT NULL, 
        	pricing_version VARCHAR(50), 
        	pricing_status ai.ai_pricing_status DEFAULT 'configured'::ai.ai_pricing_status NOT NULL, 
        	currency VARCHAR(3) DEFAULT 'USD'::character varying NOT NULL, 
        	estimated_cost NUMERIC(14, 8) DEFAULT '0'::numeric NOT NULL, 
        	request_status ai.ai_request_status NOT NULL, 
        	provider_request_id VARCHAR(255), 
        	latency_ms INTEGER, 
        	error_code VARCHAR(50), 
        	error_message TEXT, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	is_deleted BOOLEAN DEFAULT false NOT NULL, 
        	deleted_at TIMESTAMP WITH TIME ZONE, 
        	CONSTRAINT ai_request_log_pkey PRIMARY KEY (id)
        )
        """
    )
    op.execute("""CREATE INDEX ix_ai_request_log_created_at ON ai.ai_request_log USING btree (created_at)""")
    op.execute("""CREATE INDEX ix_ai_request_log_function_created ON ai.ai_request_log USING btree (function_name, created_at)""")
    op.execute("""CREATE INDEX ix_ai_request_log_is_deleted ON ai.ai_request_log USING btree (is_deleted)""")
    op.execute("""CREATE INDEX ix_ai_request_log_model_created ON ai.ai_request_log USING btree (model_name, created_at)""")
    op.execute("""CREATE INDEX ix_ai_request_log_org_created ON ai.ai_request_log USING btree (organization_id, created_at)""")
    op.execute("""CREATE INDEX ix_ai_request_log_organization_id ON ai.ai_request_log USING btree (organization_id)""")
    op.execute("""CREATE INDEX ix_ai_request_log_provider_created ON ai.ai_request_log USING btree (provider, created_at)""")
    op.execute("""CREATE INDEX ix_ai_request_log_status_created ON ai.ai_request_log USING btree (request_status, created_at)""")
    op.execute("""CREATE INDEX ix_ai_request_log_user_id ON ai.ai_request_log USING btree (user_id)""")

    # ═══════════════════════════════════════════════════════════════════════
    # SERVICE: analytics
    # ═══════════════════════════════════════════════════════════════════════
    op.execute(
        """
        CREATE TABLE analytics.audit_logs (
        	id UUID DEFAULT gen_random_uuid() NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	request_id VARCHAR(36), 
        	user_id UUID, 
        	organization_id UUID, 
        	method VARCHAR(10) NOT NULL, 
        	path VARCHAR(500) NOT NULL, 
        	status_code INTEGER NOT NULL, 
        	ip_address VARCHAR(64), 
        	duration_ms INTEGER, 
        	request_body JSONB, 
        	response_body JSONB, 
        	CONSTRAINT audit_logs_pkey PRIMARY KEY (id)
        )
        """
    )
    op.execute("""CREATE INDEX ix_audit_logs_created_at ON analytics.audit_logs USING btree (created_at)""")
    op.execute("""CREATE INDEX ix_audit_logs_org_created ON analytics.audit_logs USING btree (organization_id, created_at)""")
    op.execute("""CREATE INDEX ix_audit_logs_org_path ON analytics.audit_logs USING btree (organization_id, path)""")
    op.execute("""CREATE INDEX ix_audit_logs_org_status ON analytics.audit_logs USING btree (organization_id, status_code)""")
    op.execute("""CREATE INDEX ix_audit_logs_org_user ON analytics.audit_logs USING btree (organization_id, user_id)""")
    op.execute("""CREATE INDEX ix_audit_logs_organization_id ON analytics.audit_logs USING btree (organization_id)""")
    op.execute("""CREATE INDEX ix_audit_logs_path ON analytics.audit_logs USING btree (path)""")
    op.execute("""CREATE INDEX ix_audit_logs_request_id ON analytics.audit_logs USING btree (request_id)""")
    op.execute("""CREATE INDEX ix_audit_logs_status_code ON analytics.audit_logs USING btree (status_code)""")
    op.execute("""CREATE INDEX ix_audit_logs_user_id ON analytics.audit_logs USING btree (user_id)""")


def downgrade() -> None:
    # Drop every service schema (CASCADE clears tables, types, indexes, FKs).
    for schema in reversed(SCHEMAS):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
