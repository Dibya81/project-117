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
    apply_additive_migrations(engine)


#: Columns added to existing tables after those tables shipped. ``create_all``
#: creates missing *tables* but never ALTERs one that already exists, so a
#: running install (``data/project117.db`` is written, not thrown away) needs
#: these applied explicitly.
#:
#: Each entry is additive and nullable, which is the only kind of change SQLite
#: performs without a table rewrite — so this is safe to run on every startup
#: against a live file, and safe to run twice.
_ADDITIVE_COLUMNS: dict[str, dict[str, str]] = {
    # Tamper-evident audit chain (Phase 2, gap 1). The chain module backfills
    # the values; this only makes room for them.
    "audit_events": {
        "chain_seq": "INTEGER",
        "previous_hash": "TEXT",
        "current_hash": "TEXT",
    },
    # Ed25519 artifact signatures (Phase 2, gap 2). Existing rows default to
    # 'unsigned', which is the honest value: they were never signed.
    "artifacts": {
        "signature_status": "VARCHAR(32) DEFAULT 'unsigned'",
        "signature_path": "VARCHAR(1024)",
        "signature_key_id": "VARCHAR(64)",
        "signed_at": "DATETIME",
    },
}


def apply_additive_migrations(engine: Engine) -> list[str]:
    """Add any missing columns to existing SQLite tables. Returns what it added.

    A no-op on a fresh database (``create_all`` already made the columns) and on
    every non-SQLite backend, where Alembic will own schema evolution. Logged
    loudly when it does something, because a schema change at startup is worth
    seeing in the log.
    """
    if engine.dialect.name != "sqlite":
        return []

    from sqlalchemy import inspect, text

    added: list[str] = []
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table, columns in _ADDITIVE_COLUMNS.items():
            if table not in existing_tables:
                continue
            present = {column["name"] for column in inspector.get_columns(table)}
            for name, declaration in columns.items():
                if name in present:
                    continue
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}"))
                added.append(f"{table}.{name}")
        if "audit_events" in existing_tables:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_audit_events_chain_seq "
                    "ON audit_events (chain_seq)"
                )
            )
    if added:
        import logging

        logging.getLogger(__name__).info(
            "schema: applied additive column migration(s): %s", ", ".join(added)
        )
    return added


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
