"""Tests for Phase 5: Rate limiter behavior and worker constraint enforcement."""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from backend.api.src.middleware.rate_limit import RateLimitMiddleware, TokenBucket
from backend.config import Settings


def test_token_bucket_consume_and_refill():
    bucket = TokenBucket(capacity=2, rate_per_second=10.0)
    bucket._updated = 100.0
    # Take 2 tokens
    ok1, _ = bucket.take(now=100.0)
    ok2, _ = bucket.take(now=100.0)
    assert ok1 is True
    assert ok2 is True

    # 3rd token immediately should fail
    ok3, retry_after = bucket.take(now=100.0)
    assert ok3 is False
    assert retry_after > 0.0

    # Advance time by 0.15s (> 1 token refilled)
    ok4, _ = bucket.take(now=100.15)
    assert ok4 is True


def test_multi_worker_rate_limit_fails_in_middleware():
    app = FastAPI()
    with pytest.raises(RuntimeError, match="Multi-worker configuration"):
        RateLimitMiddleware(app, per_minute=60, workers=2)


def test_multi_worker_rate_limit_fails_in_settings():
    with pytest.raises(ValueError, match="Multi-worker configuration"):
        Settings(
            workers=4,
            rate_limit_per_minute=100,
        )


def test_rate_limit_middleware_initialization_and_bucket_creation():
    app = FastAPI()
    mw = RateLimitMiddleware(app, per_minute=60, burst=5, workers=1)
    assert mw.enabled is True
    assert mw.per_minute == 60
    assert mw.burst == 5
    assert mw.workers == 1

    bucket = mw._bucket("user:alice")
    assert bucket.capacity == 5.0
    assert bucket.rate_per_second == 1.0

    # Test disabled state
    mw_disabled = RateLimitMiddleware(app, per_minute=0, workers=1)
    assert mw_disabled.enabled is False
