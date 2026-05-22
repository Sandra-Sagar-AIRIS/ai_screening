"""Apply CAND-006 candidate merge columns when alembic_version is ahead of actual schema."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, inspect

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    schema = settings.db_schema
    engine = create_engine(settings.database_url)

    with engine.begin() as conn:
        insp = inspect(conn)
        cols = {c["name"] for c in insp.get_columns("candidates", schema=schema)}
        if "is_merged" in cols and "merged_into_id" in cols:
            print("CAND-006 columns already present.")
            return

        if "is_merged" not in cols:
            conn.exec_driver_sql(
                f'ALTER TABLE {"candidates" if not schema else f"{schema}.candidates"} '
                "ADD COLUMN IF NOT EXISTS is_merged BOOLEAN NOT NULL DEFAULT false"
            )
            print("Added is_merged")

        if "merged_into_id" not in cols:
            conn.exec_driver_sql(
                f'ALTER TABLE {"candidates" if not schema else f"{schema}.candidates"} '
                "ADD COLUMN IF NOT EXISTS merged_into_id UUID"
            )
            print("Added merged_into_id")

        # Re-inspect for FK/index creation
        fks = {fk["name"] for fk in insp.get_foreign_keys("candidates", schema=schema)}
        indexes = {idx["name"] for idx in insp.get_indexes("candidates", schema=schema)}
        table_ref = "candidates" if not schema else f'"{schema}"."candidates"'

        if "fk_candidates_merged_into_id" not in fks:
            conn.exec_driver_sql(
                f"ALTER TABLE {table_ref} "
                "ADD CONSTRAINT fk_candidates_merged_into_id "
                f"FOREIGN KEY (merged_into_id) REFERENCES {table_ref}(id) ON DELETE SET NULL"
            )
            print("Added fk_candidates_merged_into_id")

        if "ix_candidates_is_merged" not in indexes:
            conn.exec_driver_sql(
                f'CREATE INDEX IF NOT EXISTS ix_candidates_is_merged ON {table_ref} (is_merged)'
            )
            print("Added ix_candidates_is_merged")

        if "ix_candidates_merged_into_id" not in indexes:
            conn.exec_driver_sql(
                f'CREATE INDEX IF NOT EXISTS ix_candidates_merged_into_id ON {table_ref} (merged_into_id)'
            )
            print("Added ix_candidates_merged_into_id")

    print("Done.")


if __name__ == "__main__":
    main()
