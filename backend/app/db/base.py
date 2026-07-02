from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all declarative SQLAlchemy models.

    AIRIS is schema-per-service (see alembic/versions/0001_initial.py): every
    table lives in its owning service's Postgres schema (identity, candidate,
    jobs, pipeline, interview, screening, communication, ...), not a single
    shared schema. There is no one global schema to bind here — each model
    declares its own schema via `__table_args__ = {"schema": "..."}` (or as
    the last element of a __table_args__ tuple).
    """


# Ensure Invite model is imported so metadata registration is explicit.
from app.models.invite import Invite  # noqa: E402,F401
from app.models.auth_session import AuthSession  # noqa: E402,F401

