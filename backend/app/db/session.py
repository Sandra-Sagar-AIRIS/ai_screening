from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# pool_pre_ping helps keep long-lived API processes healthy.
# hide_parameters prevents SQLAlchemy from echoing sensitive bind/URL values.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
    hide_parameters=True,
)

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

