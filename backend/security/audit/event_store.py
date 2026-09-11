"""Audit event storage interface and an in-memory implementation.

The production store is the database: `AuditService` writes `AuditEvent` rows
(see `backend.security.audit`). That path requires SQLAlchemy and a configured
engine, which is correct for a deployment but wrong for two other situations:

  * unit tests, which must assert on what was recorded without standing up a
    database, and
  * a DB-less local demo, where an operator still wants the audit trail to be
    inspectable rather than silently discarded.

So this module defines the *interface* both paths satisfy and ships a bounded
in-memory implementation of it. It is deliberately stdlib-only.

Two properties are load-bearing:

  * Events are normalised through `audit_log.canonical_event`, so an in-memory
    event and a database row carry the same validated, redacted fields. A test
    that passes against this store is testing the real contract.
  * The buffer is bounded (`DEFAULT_CAPACITY`). An audit buffer that grows
    without limit is a memory leak in a long-running process, and the failure
    mode of dropping the *oldest* event is visible: `dropped` is reported by
    `stats()` so a reader can tell the trail is incomplete instead of assuming
    it is whole.

This store is explicitly not durable. It does not survive a restart and it is
not shared between processes. Anything that needs a retained, tamper-evident
trail must use the database-backed service.
"""

from __future__ import annotations

import itertools
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Protocol, runtime_checkable

from backend.security.audit.audit_log import (
    canonical_event,
    log_event,
)

# Chosen to keep a meaningful recent window without unbounded growth. An
# operator who needs more should be using the database store.
DEFAULT_CAPACITY = 1000

__all__ = [
    "DEFAULT_CAPACITY",
    "EventStore",
    "InMemoryEventStore",
    "StoredEvent",
]


@dataclass(frozen=True)
class StoredEvent:
    """A recorded audit event.

    `event_id` is assigned by the store, not the caller, so a caller cannot
    overwrite or forge an existing entry. `fields` is the canonical, redacted
    payload produced by `audit_log.canonical_event`.
    """

    event_id: str
    sequence: int
    recorded_at: str
    fields: dict[str, Any] = field(default_factory=dict)

    @property
    def action(self) -> str:
        return str(self.fields.get("action", ""))

    @property
    def outcome(self) -> str:
        return str(self.fields.get("outcome", ""))

    @property
    def approval(self) -> str:
        return str(self.fields.get("approval", ""))

    @property
    def timestamp(self) -> str:
        """When the store accepted the event.

        `canonical_event` deliberately does not stamp a time - the database
        column owns that in the durable path. This store therefore assigns its
        own, rather than exposing a field that would always read empty.
        """
        return self.recorded_at

    def get(self, key: str, default: Any = None) -> Any:
        return self.fields.get(key, default)


@runtime_checkable
class EventStore(Protocol):
    """What an audit sink must provide.

    Kept small on purpose: append, read back one, read back a filtered list.
    Anything richer (aggregation, retention policy, export) belongs above this
    interface, not inside every implementation of it.
    """

    def record(self, **fields: Any) -> StoredEvent:
        """Validate, redact and append an event. Raises `AuditFieldError`."""
        ...

    def get(self, event_id: str) -> StoredEvent | None:
        """Return one event, or None if it is unknown or has been evicted."""
        ...

    def list(self, **filters: Any) -> list[StoredEvent]:
        """Return matching events, newest first."""
        ...


class InMemoryEventStore:
    """A bounded, thread-safe, non-durable `EventStore`.

    Thread-safe because tool execution and request middleware both record
    audit events, and in a threaded server those can overlap.
    """

    def __init__(
        self,
        *,
        capacity: int = DEFAULT_CAPACITY,
        emit_log: bool = False,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self._capacity = int(capacity)
        self._emit_log = bool(emit_log)
        self._events: deque[StoredEvent] = deque(maxlen=self._capacity)
        self._counter = itertools.count(1)
        self._dropped = 0
        self._lock = threading.Lock()

    # -- writing ---------------------------------------------------------

    def record(self, **fields: Any) -> StoredEvent:
        """Append an event.

        Validation happens *before* the lock is taken so a bad field raises
        without touching stored state. `canonical_event` performs the redaction,
        so a caller cannot smuggle a secret into the buffer by passing it in
        `detail`.
        """
        payload = canonical_event(**fields)
        with self._lock:
            sequence = next(self._counter)
            event = StoredEvent(
                event_id=f"evt-{sequence:08d}",
                sequence=sequence,
                recorded_at=datetime.now(timezone.utc).isoformat(),
                fields=payload,
            )
            if len(self._events) == self._capacity:
                # deque silently discards the oldest entry; count it so the
                # gap is reportable rather than invisible.
                self._dropped += 1
            self._events.append(event)
        if self._emit_log:
            log_event(payload)
        return event

    # -- reading ---------------------------------------------------------

    def get(self, event_id: str) -> StoredEvent | None:
        with self._lock:
            for event in reversed(self._events):
                if event.event_id == event_id:
                    return event
        return None

    def list(
        self,
        *,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        user: str | None = None,
        agent: str | None = None,
        tool: str | None = None,
        approval: str | None = None,
        outcome: str | None = None,
        limit: int = 100,
    ) -> list[StoredEvent]:
        """Return matching events, newest first.

        A filter left as None is not applied. `limit` is clamped to at least 1
        so a caller passing 0 gets an obvious single result rather than a
        silently empty trail.
        """
        wanted = {
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "user": user,
            "agent": agent,
            "tool": tool,
            "approval": approval,
            "outcome": outcome,
        }
        active = {key: value for key, value in wanted.items() if value is not None}
        capped = max(1, int(limit))
        with self._lock:
            candidates = list(self._events)
        matched: list[StoredEvent] = []
        for event in reversed(candidates):
            if all(event.fields.get(key) == value for key, value in active.items()):
                matched.append(event)
                if len(matched) >= capped:
                    break
        return matched

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)

    def __iter__(self) -> Iterable[StoredEvent]:
        with self._lock:
            return iter(list(self._events))

    # -- introspection ---------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """Describe the buffer. `dropped` > 0 means the trail is incomplete."""
        with self._lock:
            return {
                "stored": len(self._events),
                "capacity": self._capacity,
                "dropped": self._dropped,
                "durable": False,
                "scope": "this process only",
            }

    def clear(self) -> None:
        """Drop every event. For test isolation; resets the dropped counter too."""
        with self._lock:
            self._events.clear()
            self._dropped = 0
