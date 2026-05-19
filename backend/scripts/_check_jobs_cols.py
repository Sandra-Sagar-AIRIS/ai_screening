"""Quick check: jobs table columns vs ORM expectations."""
from __future__ import annotations

from sqlalchemy import inspect

from app.db.session import SessionLocal

NEEDED = (
    "enrichment_status",
    "jd_document_key",
    "jd_file_name",
    "key_responsibilities",
    "parsing_status",
    "parsing_source",
    "raw_jd_text",
)


def main() -> None:
    db = SessionLocal()
    try:
        bind = db.get_bind()
        insp = inspect(bind)
        cols = {c["name"] for c in insp.get_columns("jobs")}
        missing = [c for c in NEEDED if c not in cols]
        print("missing:", missing or "none")
        print("total columns:", len(cols))
    finally:
        db.close()


if __name__ == "__main__":
    main()
