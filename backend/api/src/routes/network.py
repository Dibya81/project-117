"""Network Sentinel SSE stream — ``GET /api/network/stream``.

Mirrors the simulation's stream endpoint (``backend/simulation/api.py``): a
``StreamingResponse`` over ``text/event-stream``, fed by the subscriber queues
the service exposes. There is no second event bus — this endpoint subscribes to
the one :mod:`backend.security.network.sentinel_stream` already publishes to.

The stream is **not** started anywhere else. It is subscribed only while a page
that needs it is mounted, which is why ``subscribe()``/``unsubscribe()`` are
paired here in a ``finally``: an SSE connection that outlives its page is a
leaked queue and a background task per visit.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.api.src.deps import get_principal
from backend.security.network.sentinel_stream import STREAM, sse_frame
from backend.security.rbac import Principal

router = APIRouter(prefix="/api/network", tags=["security"])

#: Comment frame every 15s. Proxies close an idle SSE connection, and a
#: keep-alive comment keeps the channel open without inventing an event: a
#: heartbeat is not a connection attempt and must never be rendered as one.
KEEPALIVE_SECONDS = 15.0


@router.get("/stream")
async def network_stream(
    principal: Principal = Depends(get_principal),
) -> StreamingResponse:
    """Live allow/block decisions from the egress guard.

    Emits ``network.connection_attempt`` events carrying the real decision:
    ``timestamp, source, destination, port, process, agent, task_id, action,
    reason``. Fields that were not observed are ``null``.
    """

    async def gen() -> AsyncIterator[str]:
        queue, subscription = STREAM.subscribe()
        try:
            # Open the stream immediately: a client that renders nothing until
            # the first decision cannot tell "no traffic" from "no connection".
            yield "retry: 3000\n: network sentinel attached\n\n"
            while True:
                try:
                    frame = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield sse_frame(frame)
        finally:
            subscription.close()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Without this a proxy may buffer the stream and the console would
            # show decisions in batches rather than as they happen.
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["router"]
