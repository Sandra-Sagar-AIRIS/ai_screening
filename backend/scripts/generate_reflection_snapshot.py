from __future__ import annotations

from pathlib import Path

from app.models.reflected import get_reflected_models


def main() -> None:
    models = get_reflected_models()
    output_path = Path("app/models/reflection_snapshot.md")

    lines = [
        "# Reflected Model Snapshot",
        "",
        "This file is generated from the live database reflection.",
        "It is documentation only and does not modify database structure.",
        "",
        "## Reflected ORM Classes",
        "",
    ]

    if not models:
        lines.append("_No models reflected. Check DATABASE_URL / DB_SCHEMA._")
    else:
        for model_name, model_cls in sorted(models.items()):
            table = getattr(model_cls, "__table__", None)
            table_name = table.name if table is not None else "unknown"
            schema = table.schema if table is not None else None
            fq_name = f"{schema}.{table_name}" if schema else table_name
            lines.append(f"- `{model_name}` -> `{fq_name}`")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote reflection snapshot: {output_path}")


if __name__ == "__main__":
    main()

