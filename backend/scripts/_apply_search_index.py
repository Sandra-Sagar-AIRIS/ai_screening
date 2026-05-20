"""Idempotently apply pg_trgm search index (safe if migration chain is out of sync)."""
from sqlalchemy import create_engine, text

from app.core.config import get_settings

INDEX_NAME = "ix_candidates_search_document_trgm"

engine = create_engine(get_settings().database_url)
with engine.begin() as conn:
    exists = conn.execute(
        text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
        {"name": INDEX_NAME},
    ).fetchone()
    if exists:
        print(f"{INDEX_NAME} already exists — nothing to do.")
    else:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.execute(
            text(
                f"""
                CREATE INDEX {INDEX_NAME}
                ON candidates
                USING gin (
                  lower(
                    coalesce(full_name, '') || ' ' ||
                    coalesce(first_name, '') || ' ' ||
                    coalesce(last_name, '') || ' ' ||
                    coalesce(email, '') || ' ' ||
                    coalesce(phone, '') || ' ' ||
                    coalesce(location, '') || ' ' ||
                    coalesce(headline, '')
                  ) gin_trgm_ops
                )
                WHERE deleted_at IS NULL
                """
            )
        )
        print(f"Created {INDEX_NAME}.")
