"""Check whether fast-search DB index is present."""
from sqlalchemy import create_engine, text

from app.core.config import get_settings

engine = create_engine(get_settings().database_url)
with engine.connect() as conn:
    rows = conn.execute(
        text(
            "SELECT indexname FROM pg_indexes "
            "WHERE indexname = 'ix_candidates_search_document_trgm'"
        )
    ).fetchall()
    print("trgm_index_present:", bool(rows))
    try:
        rev = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        print("alembic_version:", rev)
    except Exception as exc:
        print("alembic_version:", exc)
