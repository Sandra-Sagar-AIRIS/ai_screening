from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


def _declarative_metadata() -> MetaData:
    """
    When Alembic creates tables in a non-public schema (db_schema), ORM queries must use
    the same schema or SELECTs hit public.* and return no rows (empty permissions, etc.).
    """
    schema = get_settings().db_schema
    return MetaData(schema=schema) if schema else MetaData()


class Base(DeclarativeBase):
    """Base class for all declarative SQLAlchemy models."""

    metadata = _declarative_metadata()


# Ensure Invite model is imported so metadata registration is explicit.
from app.models.invite import Invite  # noqa: E402,F401

