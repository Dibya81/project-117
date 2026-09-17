"""Live stream of outbound network decisions (Network Sentinel, gap 5).

:mod:`backend.security.network.network_monitor` already *records* every allow
and block the egress policy makes. This module makes those decisions *observable
while they happen*, so the console can show a connection attempt at the moment
it is refused rather than as a counter that moved since the page loaded.

The pattern is deliberately the one the simulation already uses
(``backend/simulation/service.py``): a bounded in-process history plus a set of
``asyncio.Queue`` subscribers, with a slow subscriber dropped rather than
allowed to apply back-pressure. There is no second event bus here — this is the
same shape, sized for a low-volume security stream, and it exists in its own
module so the monitor stays dependency-free and synchronous.

Three properties matter:

**It works from any thread.** ``record_decision`` is called from the httpx
transport, which runs on a worker thread, while SSE subscribers live on the
event loop. :meth:`SentinelStream.emit` therefore hops with
``call_soon_threadsafe`` when the publishing thread is not the loop thread, and
drops the event if there is no loop — a security observation must never be able
to raise into the request path it is observing.

**Unknown is null, never invented.** ``agent`` and ``task_id`` are only known
inside a task context (:func:`network_identity`); everywhere else they are
``None`` and travel as JSON ``null``. ``process`` is the process that made the
attempt, which is this one, and ``port`` is the destination port that was
actually dialled. Neither is guessed.

**Nothing here holds a request open.** Subscribers are notified, not awaited.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import os
import sys
import threading
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator, Mapping

logger = logging.getLogger("backend.security.network.sentinel")

#: The SSE event name. One stream, one event type, so a subscriber cannot
#: accidentally treat a heartbeat as a decision.
EVENT_NAME = "network.connection_attempt"

#: Enough to explain an incident that just happened; not enough to matter.
DEFAULT_HISTORY = 200

#: Bounded subscriber queue size. A browser tab that stops reading is dropped
#: rather than being allowed to stall the emitter.
QUEUE_MAXSIZE = 256


#: Identity that a *task* establishes. Declared here rather than in the
#: monitor because it is context, not bookkeeping: the audit service and the
#: monitor both read it, and neither owns it.
_AGENT: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "p117_network_agent", default=None
)
_TASK_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "p117_network_task_id", default=None
)


@contextmanager
def network_identity(
    agent: str | None = None, task_id: str | None = None
) -> Iterator[None]:
    """Attribute outbound attempts made in this block to ``agent``/``task_id``.

    Used where a task is genuinely in scope. Outside such a block both values
    are ``None`` and appear as ``null`` on the stream — which is the honest
    answer, and the reason this is a context manager rather than a parameter
    threaded through every HTTP call site.
    """
    agent_token = _AGENT.set(agent)
    task_token = _TASK_ID.set(task_id)
    try:
        yield
    finally:
        _AGENT.reset(agent_token)
        _TASK_ID.reset(task_token)


def current_identity() -> tuple[str | None, str | None]:
    """``(agent, task_id)`` for the calling context. Both may be None."""
    return _AGENT.get(), _TASK_ID.get()


def process_name() -> str:
    """The process that made the attempt.

    The API runs out of ``.venv/bin/python`` (or a test runner); both are real
    and neither is a fabrication. This is the *name of the current process*,
    not a peer's — the monitor observes our own egress, so this is the right
    answer rather than a missing one.
    """
    try:
        return os.path.basename(os.path.realpath(sys.executable))
    except Exception:  # noqa: BLE001 - never fail for a label
        return "unknown"


@dataclass
class SentinelEvent:
    """One observed connection attempt, in the shape the console consumes."""

    timestamp: str
    source: str | None
    destination: str | None
    port: int | None
    process: str | None
    agent: str | None
    task_id: str | None
    action: str  # ALLOW | BLOCK
    reason: str | None
    local: bool = False
    scheme: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "source": self.source,
            "destination": self.destination,
            "port": self.port,
            "process": self.process,
            "agent": self.agent,
            "task_id": self.task_id,
            "action": self.action,
            "reason": self.reason,
            "local": self.local,
            "scheme": self.scheme,
        }


@dataclass
class SentinelStream:
    """Bounded history + subscriber set. Thread-safe; never blocks a publisher."""

    history: int = DEFAULT_HISTORY
    _history: deque[SentinelEvent] = field(default_factory=deque, init=False, repr=False)
    _subscribers: set[asyncio.Queue[dict[str, Any]]] = field(
        default_factory=set, init=False, repr=False
    )
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _loop: asyncio.AbstractEventLoop | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._history = deque(maxlen=self.history)

    # --- publishing -------------------------------------------------------

    def emit(self, event: SentinelEvent) -> None:
        """Publish ``event`` to history and to every live subscriber.

        Must not raise: the caller is the egress path.
        """
        with self._lock:
            self._history.append(event)
            subscribers = list(self._subscribers)
            loop = self._loop
        if not subscribers:
            return
        # The queue carries the event payload itself, not an envelope: the SSE
        # event *name* travels in the `event:` line, so an `{"event": ..., "data":
        # ...}` wrapper here would produce a `data` field that nests the real
        # payload one level down from what the field list promises.
        frame = event.as_dict()
        for queue in subscribers:
            self._deliver(queue, frame, loop)

    def _deliver(
        self, queue: asyncio.Queue[dict[str, Any]], frame: dict[str, Any], loop: Any
    ) -> None:
        current = _running_loop()
        try:
            if current is not None and (loop is None or current is loop):
                queue.put_nowait(frame)
            elif loop is not None and not loop.is_closed():
                # Publisher is on a worker thread (the httpx transport); hop to
                # the loop that owns the subscriber.
                loop.call_soon_threadsafe(self._put, queue, frame)
            else:
                # No running loop was observed. The queue is an ordinary
                # asyncio.Queue, which accepts items without a loop (a bound
                # loop is only required for the blocking `get`), so delivering
                # directly is both safe and correct here - and it is what makes
                # `record_decision()` observable from synchronous code.
                queue.put_nowait(frame)
        except asyncio.QueueFull:
            # Slow or dead subscriber: drop it, per the bus doctrine the
            # simulation already uses. A security stream must not be slowed to
            # the speed of its least attentive reader.
            with self._lock:
                self._subscribers.discard(queue)
        except RuntimeError:
            # The subscriber's loop is gone. Drop it; it is not coming back.
            with self._lock:
                self._subscribers.discard(queue)

    @staticmethod
    def _put(queue: asyncio.Queue[dict[str, Any]], frame: dict[str, Any]) -> None:
        try:
            queue.put_nowait(frame)
        except asyncio.QueueFull:
            pass

    # --- subscribing ------------------------------------------------------

    def subscribe(self) -> tuple[asyncio.Queue[dict[str, Any]], "SentinelSubscription"]:
        """Register a subscriber. The caller MUST close the subscription.

        Returned as a pair so the common mistake — subscribing and never
        unsubscribing, which leaks a queue per page visit — is visible at the
        call site rather than buried in a `finally` someone may forget. The
        subscription is also a context manager:

            queue, sub = stream.subscribe()
            try: ...
            finally: sub.close()
        """
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        subscription = SentinelSubscription(self, queue)
        with self._lock:
            self._subscribers.add(queue)
            self._loop = _running_loop() or self._loop
        return queue, subscription

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            self._subscribers.discard(queue)
            if not self._subscribers:
                self._loop = None

    @property
    def subscriber_count(self) -> int:
        """Live subscriber count. Read by tests and by the stream endpoint."""
        with self._lock:
            return len(self._subscribers)

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Most recent events, newest first."""
        with self._lock:
            items = list(self._history)
        return [event.as_dict() for event in reversed(items)][: max(0, limit)]

    def clear(self) -> None:
        """Drop history and subscribers. For tests; not exposed through the API."""
        with self._lock:
            self._history.clear()
            self._subscribers.clear()
            self._loop = None


class SentinelSubscription:
    """Handle for one subscriber. ``close()`` is idempotent."""

    def __init__(
        self, stream: SentinelStream, queue: asyncio.Queue[dict[str, Any]]
    ) -> None:
        self._stream = stream
        self._queue = queue

    @property
    def queue(self) -> asyncio.Queue[dict[str, Any]]:
        return self._queue

    def close(self) -> None:
        self._stream.unsubscribe(self._queue)

    def __enter__(self) -> "SentinelSubscription":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


def sse_frame(payload: Mapping[str, Any]) -> str:
    """Encode one event as an SSE frame, named so the client can filter.

    Accepts the event payload (what travels on the queue), not the dataclass:
    the subscriber receives the serialised dict, and re-wrapping it in the
    dataclass only to unwrap it again would be one round trip too many.
    """
    body = json.dumps(dict(payload), separators=(",", ":"), default=str)
    return f"event: {EVENT_NAME}\ndata: {body}\n\n"


#: Process-wide stream. One instance, like the monitor: a second one would
#: mean two places a security event could be published and neither complete.
STREAM = SentinelStream()


def emit_decision(
    *,
    host: str | None,
    scheme: str | None,
    port: int | None,
    action: str,
    reason: str | None,
    local: bool,
) -> None:
    """Build and publish one decision. Never raises.

    Called by :func:`backend.security.network.network_monitor.record_decision`,
    which is the single place every allow/block already passes through.
    """
    try:
        agent, task_id = current_identity()
        STREAM.emit(
            SentinelEvent(
                timestamp=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                source="127.0.0.1",
                destination=(host or None),
                port=port,
                process=process_name(),
                agent=agent,
                task_id=task_id,
                action=action,
                reason=reason,
                local=local,
                scheme=scheme,
            )
        )
    except Exception:  # noqa: BLE001 - observability must never break traffic
        logger.debug("sentinel event could not be published", exc_info=True)


__all__ = [
    "DEFAULT_HISTORY",
    "EVENT_NAME",
    "QUEUE_MAXSIZE",
    "STREAM",
    "SentinelEvent",
    "SentinelStream",
    "SentinelSubscription",
    "current_identity",
    "emit_decision",
    "network_identity",
    "process_name",
    "sse_frame",
]
