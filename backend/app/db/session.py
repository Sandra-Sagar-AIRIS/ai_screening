from collections.abc import Generator
from urllib.parse import urlparse

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# ── pgBouncer / Supabase compatibility ────────────────────────────────────────
#
# Supabase transaction-mode pooler (port 6543) multiplexes many app connections
# over a small set of real Postgres connections.  Two SQLAlchemy settings are
# required to avoid hard-to-debug 500s:
#
# 1. NullPool — SQLAlchemy must NOT maintain its own connection pool on top of
#    pgBouncer.  Without this, the pool holds connections open between requests,
#    exhausting the pooler's 15-client session-mode cap instantly.  With NullPool,
#    each request gets a fresh socket to pgBouncer and releases it immediately.
#
# 2. prepare_threshold=None — psycopg v3 auto-prepares frequently-used SQL
#    statements on the Postgres connection.  In transaction mode, pgBouncer
#    reuses the same underlying Postgres connection across different app sessions.
#    If psycopg tries to prepare "_pg3_0" on a connection that already has it
#    (from a previous app session), Postgres raises DuplicatePreparedStatement
#    → 500.  Setting prepare_threshold=None disables server-side prepared
#    statements entirely; psycopg sends all queries as simple protocol instead.
#
# Both settings are applied only when the URL targets the Supabase pooler.
# For local Postgres the defaults work fine.

_db_url = settings.database_url or ""
_parsed_db = urlparse(_db_url)
# Transaction-mode pooler (:6543) requires NullPool + no prepared statements.
# Session-mode pooler (:5432) can use a small app-side pool (much faster per request).
_use_transaction_pooler = (
    "pooler.supabase.com" in _db_url and _parsed_db.port == 6543
)

_engine_kwargs: dict = {
    "future": True,
    "hide_parameters": True,
}

if _use_transaction_pooler:
    _engine_kwargs["poolclass"] = NullPool
    _engine_kwargs["connect_args"] = {"prepare_threshold": None}
else:
    _engine_kwargs["pool_pre_ping"] = True
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10

engine = create_engine(_db_url, **_engine_kwargs)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except BaseException:
        # Prevent poisoned sessions from leaking pending rollback state to the pool.
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        db.close()
