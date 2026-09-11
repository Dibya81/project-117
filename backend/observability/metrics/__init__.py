"""In-memory metrics + request timing middleware.

Phase 1 keeps metrics in-process (no external collector). Counters and
durations are exposed via ``GET /api/metrics``. Phase 16 can swap the backend
for Prometheus/OpenTelemetry without changing the registry interface.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: defaultdict[str, int] = defaultdict(int)
        self._durations: defaultdict[str, list[float]] = defaultdict(list)

    def incr(self, name: str, by: int = 1) -> None:
        with self._lock:
            self._counters[name] += by

    def observe(self, name: str, seconds: float) -> None:
        with self._lock:
            self._durations[name].append(seconds)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "durations": {
                    name: {
                        "count": len(values),
                        "mean_ms": round(sum(values) / len(values) * 1000, 2) if values else 0.0,
                    }
                    for name, values in self._durations.items()
                },
            }


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """Assigns a request id, times every request, and logs an access line.

    The route template (not the concrete path) is used as the metric name so
    cardinality stays bounded.
    """

    def __init__(self, app, metrics: MetricsRegistry) -> None:
        super().__init__(app)
        self._metrics = metrics

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or _new_request_id()
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        duration = time.perf_counter() - started
        route = request.scope.get("route")
        label = getattr(route, "path", request.url.path)
        self._metrics.incr("http.requests_total")
        self._metrics.incr(f"http.status.{response.status_code}")
        self._metrics.observe(f"http.route.{label}", duration)
        logger.info(
            "request method=%s path=%s status=%d duration_ms=%.1f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration * 1000,
            request_id,
        )
        return response


def _new_request_id() -> str:
    import uuid

    return uuid.uuid4().hex[:12]