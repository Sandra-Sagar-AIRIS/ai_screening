"""Verify AIR-502 candidate_placement_history migration (run after alembic upgrade)."""
from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    schema = settings.db_schema or "public"

    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        print("alembic_version:", version)

    inspector = inspect(engine)
    table = "candidate_placement_history"
    assert inspector.has_table(table, schema=schema), f"{table} missing"

    cols = {c["name"]: c for c in inspector.get_columns(table, schema=schema)}
    for name in ("id", "candidate_id", "job_id", "outcome", "placement_date", "created_at"):
        assert name in cols, f"missing column: {name}"
        print(f"  column {name}: nullable={cols[name]['nullable']}")

    indexes = inspector.get_indexes(table, schema=schema)
    print("indexes:", [i["name"] for i in indexes])
    expected_idx = {
        "ix_candidate_placement_history_candidate_id",
        "ix_candidate_placement_history_job_id",
        "ix_candidate_placement_history_candidate_placement_date",
    }
    assert expected_idx.issubset({i["name"] for i in indexes}), "missing expected indexes"

    fks = inspector.get_foreign_keys(table, schema=schema)
    fk_targets = {(tuple(fk["constrained_columns"]), fk["referred_table"]) for fk in fks}
    assert (("candidate_id",), "candidates") in fk_targets
    assert (("job_id",), "jobs") in fk_targets
    print("foreign keys:", fk_targets)

    for existing in ("pipelines", "job_submissions", "pipeline_stage_history"):
        assert inspector.has_table(existing, schema=schema), f"{existing} missing"
        print(f"  ok: {existing} unchanged")

    print("VERIFICATION_OK")


if __name__ == "__main__":
    main()
