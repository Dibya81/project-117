"""In-process job event bus (Phase 6).

Streaming exists so a 40-second job does not look like a hang. Every state
change and progress note written by :class:`backend.jobs.service.JobService`
is published here, and ``GET /api/jobs/{id}/stream`` (and the chat stream)
turn those events into server-sent events.

Three design decisions, each with a reason:

**Events are persisted first, published second.** The database is the source
of truth; the bus is a notification. A subscriber that connects late replays
from ``job_events`` by sequence number and then follows the bus, so no event
is invented and none is silently missed.

**Publishing is thread-safe.** ``JobService`` runs synchronously inside
``asyncio.to_thread`` (SQLAlchemy's sync session), so ``publish`` is called
from a worker thread while subscribers live on the event loop. The loop is
captured once and hops are made with ``call_soon_threadsafe`` rather than
touching ``asyncio.Queue`` from the wrong thread - which appears to work in
testing and then corrupts under load.

**A slow subscriber is dropped, not backpressured.** Queues are bounded. If a
browser tab stops reading, the job must not stall; the subscriber gets an
overflow marker and is expected to re-read the job. Job execution never waits
on a consumer.

This is in-process on purpose. A Redis fan-out would be the right answer for
multiple API replicas, and it is the wrong answer for a single on-premise box
where it would add a service to operate for no capability we need today
(ADR 0001: minimise infrastructure).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)

#: Per-subscriber buffer. Deep enough for a bursty plan, shallow enough that a
#: dead reader is noticed quickly.
QUEUE_MAXSIZE = 256

#: Sentinel pushed when a job reaches a terminal state, so a stream can close
#: instead of waiting for a timeout.
END = {"kind": "end"}


class JobEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Remember the loop that owns the subscriber queues.

        Called at application startup. Publishing from a worker thread needs a
        loop reference and ``asyncio.get_running_loop()`` is unavailable there.
        """
        self._loop = loop or asyncio.get_event_loop()

    # --- subscribe --------------------------------------------------------

    def subscribe(self, job_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        self._subscribers.setdefault(job_id, set()).add(queue)
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:  # pragma: no cover - only outside a loop
                self._loop = None
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        holders = self._subscribers.get(job_id)
        if not holders:
            return
        holders.discard(queue)
        if not holders:
            self._subscribers.pop(job_id, None)

    async def stream(
        self, job_id: str, *, timeout: float | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield events for a job until it ends (or ``timeout`` elapses).

        The caller is responsible for replaying persisted events first; this
        only yields what arrives from now on.
        """
        queue = self.subscribe(job_id)
        try:
            while True:
                if timeout is None:
                    event = await queue.get()
                else:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=timeout)
                    except asyncio.TimeoutError:
                        yield {"kind": "timeout", "job_id": job_id}
                        return
                if event.get("kind") == "end":
                    return
                yield event
        finally:
            self.unsubscribe(job_id, queue)

    # --- publish ----------------------------------------------------------

    def publish(self, job_id: str, event: dict[str, Any]) -> None:
        """Fan an event out to subscribers. Safe from any thread.

        Never raises: a publishing failure must not fail the job whose
        progress it was describing.
        """
        holders = self._subscribers.get(job_id)
        if not holders:
            return
        loop = self._loop
        if loop is None or loop.is_closed():
            self._deliver(job_id, event)
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            self._deliver(job_id, event)
        else:
            try:
                loop.call_soon_threadsafe(self._deliver, job_id, event)
            except RuntimeError:  # pragma: no cover - loop shutting down
                logger.debug("event loop closed while publishing job %s", job_id)

    def close(self, job_id: str) -> None:
        """Signal end-of-stream for a job that reached a terminal state."""
        self.publish(job_id, dict(END, job_id=job_id))

    def _deliver(self, job_id: str, event: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(job_id, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop the subscriber's place in line rather than the job.
                logger.warning("dropping event for slow subscriber on job %s", job_id)
                _drain_one(queue)
                try:
                    queue.put_nowait({"kind": "overflow", "job_id": job_id})
                except asyncio.QueueFull:  # pragma: no cover
                    pass


def _drain_one(queue: asyncio.Queue[dict[str, Any]]) -> None:
    try:
        queue.get_nowait()
    except asyncio.QueueEmpty:  # pragma: no cover
        pass
