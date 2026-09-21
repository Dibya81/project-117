"""Audit service.

Every sensitive operation records an audit event: user, timestamp, action,
resource, agent, tool, model, approval, outcome, error. `detail` carries
structured, non-sensitive metadata (ids, sizes, durations) — never raw
document contents.

The agent/tool/model/approval fields exist from Phase 0.5 so that the Phase 7
approval gates and Phase 9 sandbox executions are auditable the day they are
written, rather than retrofitted afterwards.

Shaping, validation and redaction live in `audit_log`, which is importable
without a database driver. This module is only the persistence half: it turns a
canonical event into an `AuditEvent` row. Keeping the split means the rule
"an API key never reaches a permanent row" is testable without SQLAlchemy, and
that the in-memory store in `event_store` enforces exactly the same rule.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from backend.database.models import AuditEvent
from backend.security.audit.audit_chain import (
    GENESIS_HASH,
    ChainVerification,
    append_link,
    chain_transaction,
    ensure_chain,
    verify_chain,
)
from backend.security.audit.audit_log import (
    APPROVAL_STATES,
    MAX_DETAIL_CHARS,
    OUTCOME_ALIASES,
    OUTCOMES,
    AuditFieldError,
    canonical_event,
    log_event,
    redact_detail,
    serialise_detail,
    validate_approval,
    validate_outcome,
)
from backend.security.audit.event_store import (
    DEFAULT_CAPACITY,
    EventStore,
    InMemoryEventStore,
    StoredEvent,
)

logger = logging.getLogger(__name__)

__all__ = [
    "APPROVAL_STATES",
    "DEFAULT_CAPACITY",
    "MAX_DETAIL_CHARS",
    "OUTCOMES",
    "OUTCOME_ALIASES",
    "AuditFieldError",
    "AuditService",
    "ChainVerification",
    "EventStore",
    "InMemoryEventStore",
    "StoredEvent",
    "canonical_event",
    "log_event",
    "redact_detail",
    "serialise_detail",
    "validate_approval",
    "validate_outcome",
]


def _new_event_id() -> str:
    """Same shape as ``AuditEvent.id``'s default, applied before hashing."""
    return str(uuid.uuid4())


def sqlite_path_for(database_url: str) -> Path | None:
    """The file behind a SQLite ``database_url``, or None for other backends.

    The hash chain is implemented against SQLite because that is what Phase 1
    persists to and what :mod:`backend.storage.operations` establishes as the
    convention. A non-SQLite URL returns None and the chain degrades to
    "not linked here" rather than pretending to be verified.
    """
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    raw = database_url[len(prefix) :]
    if not raw or raw == ":memory:":
        return None
    return Path(raw).expanduser()


class AuditService:
    """Database-backed audit sink. Satisfies the `EventStore` intent, but
    returns ORM rows rather than `StoredEvent`, because callers filter on
    indexed columns.

    As of Phase 2 every row is also linked into a SHA-256 hash chain, so the
    log is tamper-*evident* and not merely durable. The chain is applied here,
    in the one place rows are written, rather than at each call site: an audit
    row that skipped the chain would be detected as a break, and a caller
    cannot be trusted to remember.
    """

    def __init__(self, session_factory, database_url: str | None = None) -> None:
        self._session_factory = session_factory
        self._db_path = sqlite_path_for(database_url) if database_url else None
        self._chain_ready = False
        self._chain_lock = threading.Lock()

    # --- chain plumbing ---------------------------------------------------

    @property
    def chain_path(self) -> Path | None:
        """The SQLite file the chain lives in, or None when not SQLite."""
        return self._db_path

    def _ensure_chain(self) -> None:
        """Create/backfill chain columns once per process.

        Lazy rather than done in ``__init__``: constructing the audit service
        must not touch the filesystem (tests build an app with a database URL
        that does not exist yet), and the migration has to happen before the
        first append, which is exactly here.
        """
        if self._chain_ready or self._db_path is None:
            return
        with self._chain_lock:
            if self._chain_ready:
                return
            ensure_chain(self._db_path)
            self._chain_ready = True

    def _next_link(self, payload: dict[str, Any]) -> tuple[int, str, str] | None:
        """Compute the next chain link, or None when the chain cannot be used.

        A failure here must not lose the audit row: losing the record of an
        action in order to protect the record of an action is the wrong
        trade. The row is written unchained, which the verifier then reports as
        a broken link — loudly, and without the event being lost.
        """
        if self._db_path is None:
            return None
        try:
            self._ensure_chain()
            conn = sqlite3.connect(str(self._db_path), timeout=30.0)
            try:
                link = append_link(conn, payload)
                conn.rollback()  # read-only: never hold a write lock for a read
                return link
            finally:
                conn.close()
        except Exception:  # noqa: BLE001 - see docstring
            logger.warning("audit chain link could not be computed", exc_info=True)
            return None

    def verify(self) -> ChainVerification:
        """Walk this service's chain and report VALID / the first broken link."""
        if self._db_path is None:
            return ChainVerification(
                valid=False,
                events=0,
                last_hash=GENESIS_HASH,
                last_seq=0,
                error=("the audit log is not on SQLite, so no hash chain is maintained for it"),
            )
        self._ensure_chain()
        return verify_chain(self._db_path)

    # --- writing ----------------------------------------------------------

    def record(
        self,
        *,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        user: str | None = None,
        outcome: str = "success",
        agent: str | None = None,
        tool: str | None = None,
        model: str | None = None,
        approval: str = "not_required",
        detail: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> AuditEvent:
        """Validate, redact and persist one audit event.

        `canonical_event` raises `AuditFieldError` for an unknown approval
        state or outcome, and passes `detail` through the secret redactor. That
        redaction is the reason this method does not serialise `detail` itself:
        doing so previously wrote the mapping verbatim, so anything a caller
        happened to include - a connector token in a request echo, an API key
        in an error payload - was persisted in clear text.
        """
        payload = canonical_event(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user=user,
            outcome=outcome,
            agent=agent,
            tool=tool,
            model=model,
            approval=approval,
            detail=detail,
            error=error,
        )
        event = AuditEvent(**payload)
        with chain_transaction():
            # The hash covers id and timestamp, and both are Python-side
            # defaults applied at flush. They are seeded here so the value
            # hashed is exactly the value stored; hashing a None id and then
            # writing a UUID would make every fresh row fail verification.
            event.id = event.id or _new_event_id()
            event.timestamp = event.timestamp or datetime.now(timezone.utc)
            link = self._next_link({**payload, "id": event.id, "timestamp": event.timestamp})
            if link is not None:
                seq, previous_hash, current_hash = link
                event.chain_seq = seq
                event.previous_hash = previous_hash
                event.current_hash = current_hash
            with self._session_factory() as session:
                session.add(event)
                session.commit()
                session.refresh(event)
        log_event(payload)
        return event

    def get(self, event_id: str) -> AuditEvent | None:
        with self._session_factory() as session:
            return session.get(AuditEvent, event_id)

    def list(
        self,
        *,
        resource_type: str | None = None,
        resource_id: str | None = None,
        action: str | None = None,
        agent: str | None = None,
        tool: str | None = None,
        approval: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        with self._session_factory() as session:
            stmt = select(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(limit)
            if resource_type:
                stmt = stmt.where(AuditEvent.resource_type == resource_type)
            if resource_id:
                stmt = stmt.where(AuditEvent.resource_id == resource_id)
            if action:
                stmt = stmt.where(AuditEvent.action == action)
            if agent:
                stmt = stmt.where(AuditEvent.agent == agent)
            if tool:
                stmt = stmt.where(AuditEvent.tool == tool)
            if approval:
                stmt = stmt.where(AuditEvent.approval == approval)
            return list(session.scalars(stmt))
