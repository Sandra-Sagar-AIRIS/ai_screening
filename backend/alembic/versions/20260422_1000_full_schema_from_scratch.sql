-- Full schema bootstrap SQL (mirrors 20260422_1000_full_schema_from_scratch.py)
-- Default schema is `public`. Replace `public.` with your target schema if needed.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE public.organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_profiles_organization_id_organizations
        FOREIGN KEY (organization_id) REFERENCES public.organizations (id)
);

CREATE INDEX ix_profiles_organization_id ON public.profiles (organization_id);
CREATE UNIQUE INDEX ix_profiles_email ON public.profiles (email);

CREATE TABLE public.candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    location VARCHAR(255),
    experience_summary TEXT,
    education TEXT,
    notes TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_candidates_organization_id ON public.candidates (organization_id);
CREATE INDEX ix_candidates_email ON public.candidates (email);

CREATE TABLE public.clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    name VARCHAR(200) NOT NULL,
    legal_name VARCHAR(255),
    industry VARCHAR(120),
    website VARCHAR(500),
    email VARCHAR(255),
    phone VARCHAR(50),
    location VARCHAR(255),
    notes TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_clients_organization_id ON public.clients (organization_id);

CREATE TABLE public.jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    client_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_jobs_client_id_clients
        FOREIGN KEY (client_id) REFERENCES public.clients (id)
);

CREATE INDEX ix_jobs_organization_id ON public.jobs (organization_id);
CREATE INDEX ix_jobs_client_id ON public.jobs (client_id);

CREATE TABLE public.pipelines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    candidate_id UUID NOT NULL,
    job_id UUID NOT NULL,
    stage VARCHAR(80) NOT NULL DEFAULT 'applied',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_pipeline_candidate_job UNIQUE (candidate_id, job_id),
    CONSTRAINT fk_pipelines_candidate_id_candidates
        FOREIGN KEY (candidate_id) REFERENCES public.candidates (id),
    CONSTRAINT fk_pipelines_job_id_jobs
        FOREIGN KEY (job_id) REFERENCES public.jobs (id)
);

CREATE INDEX ix_pipelines_organization_id ON public.pipelines (organization_id);
CREATE INDEX ix_pipelines_candidate_id ON public.pipelines (candidate_id);
CREATE INDEX ix_pipelines_job_id ON public.pipelines (job_id);

CREATE TABLE public.interviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    pipeline_id UUID NOT NULL,
    scheduled_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'scheduled',
    interviewer_name VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_interviews_pipeline_id_pipelines
        FOREIGN KEY (pipeline_id) REFERENCES public.pipelines (id)
);

CREATE INDEX ix_interviews_organization_id ON public.interviews (organization_id);
CREATE INDEX ix_interviews_pipeline_id ON public.interviews (pipeline_id);
CREATE INDEX ix_interviews_scheduled_at ON public.interviews (scheduled_at);

COMMIT;

-- ------------------------------------------------------------------------
-- Rollback (manual): run this block to drop all objects created above
-- ------------------------------------------------------------------------
-- BEGIN;
-- DROP INDEX IF EXISTS public.ix_interviews_scheduled_at;
-- DROP INDEX IF EXISTS public.ix_interviews_pipeline_id;
-- DROP INDEX IF EXISTS public.ix_interviews_organization_id;
-- ALTER TABLE IF EXISTS public.interviews DROP CONSTRAINT IF EXISTS fk_interviews_pipeline_id_pipelines;
-- DROP TABLE IF EXISTS public.interviews;
--
-- DROP INDEX IF EXISTS public.ix_pipelines_job_id;
-- DROP INDEX IF EXISTS public.ix_pipelines_candidate_id;
-- DROP INDEX IF EXISTS public.ix_pipelines_organization_id;
-- ALTER TABLE IF EXISTS public.pipelines DROP CONSTRAINT IF EXISTS fk_pipelines_job_id_jobs;
-- ALTER TABLE IF EXISTS public.pipelines DROP CONSTRAINT IF EXISTS fk_pipelines_candidate_id_candidates;
-- DROP TABLE IF EXISTS public.pipelines;
--
-- DROP INDEX IF EXISTS public.ix_jobs_client_id;
-- DROP INDEX IF EXISTS public.ix_jobs_organization_id;
-- ALTER TABLE IF EXISTS public.jobs DROP CONSTRAINT IF EXISTS fk_jobs_client_id_clients;
-- DROP TABLE IF EXISTS public.jobs;
--
-- DROP INDEX IF EXISTS public.ix_clients_organization_id;
-- DROP TABLE IF EXISTS public.clients;
--
-- DROP INDEX IF EXISTS public.ix_candidates_email;
-- DROP INDEX IF EXISTS public.ix_candidates_organization_id;
-- DROP TABLE IF EXISTS public.candidates;
--
-- DROP INDEX IF EXISTS public.ix_profiles_email;
-- DROP INDEX IF EXISTS public.ix_profiles_organization_id;
-- ALTER TABLE IF EXISTS public.profiles DROP CONSTRAINT IF EXISTS fk_profiles_organization_id_organizations;
-- DROP TABLE IF EXISTS public.profiles;
--
-- DROP TABLE IF EXISTS public.organizations;
-- COMMIT;
