from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.ext.automap import automap_base

from app.core.config import get_settings
from app.db.session import engine

settings = get_settings()

metadata = MetaData(schema=settings.db_schema)
ReflectedBase = automap_base(metadata=metadata)
_is_reflected = False


def reflect_database_schema() -> None:
    """
    Reflect current Supabase/PostgreSQL schema into SQLAlchemy ORM classes.

    This is read-only reflection and does NOT modify database structure.
    Lazy — not run at app startup (full introspection over a remote DB is slow).
    Call from scripts via ``get_reflected_models()`` when needed.
    """
    global _is_reflected
    if _is_reflected:
        return

    ReflectedBase.prepare(autoload_with=engine)
    _is_reflected = True


def get_reflected_models() -> dict[str, type]:
    reflect_database_schema()
    return {mapper.class_.__name__: mapper.class_ for mapper in ReflectedBase.registry.mappers}

