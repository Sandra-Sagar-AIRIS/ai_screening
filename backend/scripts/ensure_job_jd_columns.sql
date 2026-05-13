-- Run against your AIRIS Postgres if Job detail returns 500 after pulling JD-document changes
-- but Alembic cannot upgrade (e.g. stale or missing revision in alembic_version).

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS jd_document_key VARCHAR(1024);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS jd_file_name VARCHAR(512);
