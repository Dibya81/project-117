"""Redis-backed distributed rate limiter.

Provides atomic token bucket / fixed-window tracking across multiple uvicorn workers or multi-instance deployments.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class RedisRateLimiter:
    """Distributed rate limiter backed by Redis key expiration/counters."""

    def __init__(
        self,
        redis_url: str,
        per_minute: int,
        burst: int | None = None,
    ) -> None:
        self.redis_url = redis_url
        self.per_minute = per_minute
        self.burst = burst or per_minute
        self._client: Any = None
        self._initialized = False

    def _get_client(self) -> Any:
        if not self._initialized:
            try:
                import redis

                self._client = redis.from_url(self.redis_url, decode_responses=True)
                self._client.ping()
                self._initialized = True
            except Exception as e:
                logger.warning("Redis rate limiter unavailable at %s: %s (falling back to open)", self.redis_url, e)
                self._client = None
                self._initialized = True
        return self._client

    def take(self, key: str) -> tuple[bool, float]:
        """Atomically increment and check caller rate limit."""
        client = self._get_client()
        if client is None:
            # Degrade gracefully if redis is unreachable
            return True, 0.0

        try:
            current_minute = int(time.time() // 60)
            redis_key = f"p117:ratelimit:{key}:{current_minute}"

            # Pipeline INCR and EXPIRE in a single round-trip
            pipe = client.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, 70)
            results = pipe.execute()
            count = results[0]

            if count > self.per_minute:
                seconds_remaining = 60 - int(time.time() % 60)
                return False, float(seconds_remaining)

            return True, 0.0
        except Exception as e:
            logger.debug("Redis rate check error: %s", e)
            return True, 0.0
