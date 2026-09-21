"""Per-caller request rate limiting.

A local deployment still needs a ceiling: one runaway client loop can starve
the single local model backend and make the whole workbench look dead. This is
a plain in-process token bucket — no Redis, no external service, consistent
with the sovereignty posture.

Configuration (env, read once at construction):

===============================  ==========================================
``P117_RATE_LIMIT_PER_MINUTE``   Sustained requests/minute per caller.
                                 ``0`` (default) disables the limiter.
``P117_RATE_LIMIT_BURST``        Bucket size. Defaults to the per-minute
                                 value, i.e. one minute of burst.
===============================  ==========================================

Honest scope: the bucket is per process. Two uvicorn workers each get their
own bucket, so the effective limit is ``workers x limit``. That is documented
rather than hidden, because pretending otherwise would be a false guarantee.
"""

from __future__ import annotations

import logging
import os
import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.api.src.middleware.auth import is_public

logger = logging.getLogger(__name__)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("%s=%r is not an integer; using %d", name, raw, default)
        return default
    return max(0, value)


class TokenBucket:
    """Refills continuously; ``take`` reports whether a request may proceed."""

    __slots__ = ("capacity", "rate_per_second", "_tokens", "_updated")

    def __init__(self, capacity: int, rate_per_second: float) -> None:
        self.capacity = float(capacity)
        self.rate_per_second = rate_per_second
        self._tokens = float(capacity)
        self._updated = time.monotonic()

    def take(self, now: float | None = None) -> tuple[bool, float]:
        now = now if now is not None else time.monotonic()
        elapsed = max(0.0, now - self._updated)
        self._updated = now
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate_per_second)
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True, 0.0
        deficit = 1.0 - self._tokens
        retry_after = deficit / self.rate_per_second if self.rate_per_second > 0 else 60.0
        return False, retry_after


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket limiter keyed by authenticated user, else client address."""

    def __init__(
        self,
        app,
        *,
        per_minute: int | None = None,
        burst: int | None = None,
        workers: int | None = None,
    ) -> None:
        super().__init__(app)
        self.per_minute = (
            per_minute if per_minute is not None else _int_env("P117_RATE_LIMIT_PER_MINUTE", 0)
        )
        self.burst = burst if burst is not None else _int_env("P117_RATE_LIMIT_BURST", self.per_minute)
        self.workers = workers if workers is not None else _int_env("P117_WORKERS", 1)
        if self.enabled and self.workers > 1:
            raise RuntimeError(
                f"Multi-worker configuration (workers={self.workers}) with in-process rate "
                f"limiting (per_minute={self.per_minute}) is unsupported. In-process token "
                "buckets do not share state across workers. Either set P117_RATE_LIMIT_PER_MINUTE=0 "
                "or deploy with a single worker."
            )
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()
        if self.enabled:
            logger.info(
                "rate limiting enabled: %d req/min per caller (burst %d, per process, %d worker(s))",
                self.per_minute,
                self.burst or self.per_minute,
                self.workers,
            )

    @property
    def enabled(self) -> bool:
        return self.per_minute > 0

    def _key(self, request: Request) -> str:
        principal = getattr(request.state, "principal", None)
        if principal is not None and getattr(principal, "authenticated", False):
            return f"user:{principal.user}"
        client = request.client.host if request.client else "unknown"
        return f"addr:{client}"

    def _bucket(self, key: str) -> TokenBucket:
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = TokenBucket(
                    capacity=max(1, self.burst or self.per_minute),
                    rate_per_second=self.per_minute / 60.0,
                )
                self._buckets[key] = bucket
            return bucket

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self.enabled or is_public(request.url.path):
            return await call_next(request)
        key = self._key(request)
        with self._lock:
            allowed, retry_after = self._bucket(key).take()
        if not allowed:
            logger.info("rate limited %s on %s", key, request.url.path)
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": (
                            f"more than {self.per_minute} requests/minute from this caller; "
                            f"retry in {retry_after:.1f}s"
                        ),
                    }
                },
                headers={"Retry-After": str(max(1, int(retry_after + 0.999)))},
            )
        return await call_next(request)


__all__ = ["RateLimitMiddleware", "TokenBucket"]
