"""Engine/session wiring.

Phase 1 persists to SQLite (zero infrastructure). ``create_engine_for`` is the
single place that knows how to build an engine, so switching to PostgreSQL in
Phase 17 only touches this module (and the database URL).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# Importing these registers their tables on Base.metadata even though nothing
# in this module references the classes directly. A table lands with the
# phase that uses it (see models.py), but init_db must know about all of them
# by the time create_all runs, or Phase 6-14's tables simply never get created.
from backend.database import execution as _execution_models  # noqa: F401
from backend.database import memory as _memory_models  # noqa: F401
from backend.database.models import Base


def create_engine_for(database_url: str) -> Engine:
    """Build the engine for either backend the config allows.

    SQLite (the zero-infrastructure default) needs ``check_same_thread=False``
    because sessions are used across the async request lifecycle. Postgres
    (Phase 17) instead needs ``pool_pre_ping`` so a connection dropped by an
    idle timeout is detected and replaced before a request fails on it -
    without this, the first request after any DB restart or network blip
    would surface a raw connection error instead of transparently retrying.
    """
    kwargs: dict = {}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 5
    return create_engine(database_url, **kwargs)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Create tables. Alembic migrations replace this in Phase 17."""
    Base.metadata.create_all(engine)


def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Context-managed session: commit on success, rollback on error."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()