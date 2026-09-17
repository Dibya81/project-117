"""Network Sentinel stream tests.

The point of gap 5 is that ``record_decision()`` **streams** what it records,
with values that come from the actual policy decision. These tests drive real
egress decisions through the real monitor and assert on what a subscriber
receives — including the fields that must be ``null`` because nothing observed
them, which is the difference between an honest record and a plausible one.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from backend.api.src.main import create_app
from backend.config import Settings
from backend.security.egress import EgressBlocked, EgressPolicy
from backend.security.network import sentinel_stream
from backend.security.network.egress_policy import check_and_record
from backend.security.network.network_monitor import record_decision
from backend.security.network.sentinel_stream import (
    EVENT_NAME,
    SentinelStream,
    network_identity,
    sse_frame,
)
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def clean_stream():
    sentinel_stream.STREAM.clear()
    yield
    sentinel_stream.STREAM.clear()


# ------------------------------------------------------- the recorded event ---


def test_block_decision_is_streamed_with_real_values():
    stream = SentinelStream()
    queue, sub = stream.subscribe()
    try:
        stream.emit(
            sentinel_stream.SentinelEvent(
                timestamp="2026-01-01T00:00:00.000+00:00",
                source="127.0.0.1",
                destination="api.openai.com",
                port=443,
                process="python",
                agent=None,
                task_id=None,
                action="BLOCK",
                reason="denied by egress policy",
            )
        )
        frame = queue.get_nowait()
        data = frame
        assert data["action"] == "BLOCK"
        assert data["destination"] == "api.openai.com"
        assert data["port"] == 443
        assert data["reason"] == "denied by egress policy"
        # Nothing observed an agent or a task, so they are null rather than
        # a plausible-looking name.
        assert data["agent"] is None
        assert data["task_id"] is None
    finally:
        sub.close()


def test_stream_is_empty_before_anything_is_attempted():
    """The honest empty state: no decisions means no events, not a fake one."""
    assert sentinel_stream.STREAM.recent() == []
    assert sentinel_stream.STREAM.subscriber_count == 0


# --------------------------------------------------- through the real policy ---


def test_policy_block_produces_a_streamed_block_event():
    policy = EgressPolicy(default_deny=True, allowed_hosts=frozenset())
    stream = sentinel_stream.STREAM
    queue, sub = stream.subscribe()
    try:
        with pytest.raises(EgressBlocked):
            check_and_record(policy, "https://evil.example.com/collect?data=1")
        frame = queue.get_nowait()
        data = frame
        assert data["action"] == "BLOCK"
        assert data["destination"] == "evil.example.com"
        assert data["port"] is None or data["port"] == 443
        # The query string is never carried into the record: it can hold
        # document content.
        assert "data=1" not in json.dumps(data)
        assert data["reason"] == "denied by egress policy"
    finally:
        sub.close()


def test_policy_allow_produces_a_streamed_allow_event():
    policy = EgressPolicy(default_deny=True, allowed_hosts=frozenset({"good.example.com"}))
    queue, sub = sentinel_stream.STREAM.subscribe()
    try:
        check_and_record(policy, "https://good.example.com/thing")
        data = queue.get_nowait()
        assert data["action"] == "ALLOW"
        assert data["destination"] == "good.example.com"
        assert data["reason"] is None
    finally:
        sub.close()


def test_recent_history_survives_without_a_subscriber():
    record_decision(host="api.openai.com", scheme="https", decision="blocked")
    recent = sentinel_stream.STREAM.recent()
    assert len(recent) == 1
    assert recent[0]["action"] == "BLOCK"


# ------------------------------------------------------------- task context ---


def test_agent_and_task_come_from_the_task_context():
    queue, sub = sentinel_stream.STREAM.subscribe()
    try:
        with network_identity(agent="recovery-planner", task_id="task-117"):
            record_decision(
                host="127.0.0.1", scheme="http", decision="allowed", local=True
            )
        data = queue.get_nowait()
        assert data["agent"] == "recovery-planner"
        assert data["task_id"] == "task-117"
        assert data["action"] == "ALLOW"
    finally:
        sub.close()


def test_context_is_cleared_after_the_block():
    with network_identity(agent="a", task_id="t"):
        pass
    assert sentinel_stream.current_identity() == (None, None)
    queue, sub = sentinel_stream.STREAM.subscribe()
    try:
        record_decision(host="127.0.0.1", scheme="http", decision="allowed", local=True)
        data = queue.get_nowait()
        assert data["agent"] is None
        assert data["task_id"] is None
    finally:
        sub.close()


# ---------------------------------------------------------------- lifecycle ---


def test_slow_subscriber_is_dropped_not_awaited(monkeypatch):
    """A stalled reader must not be able to slow the egress path."""
    monkeypatch.setattr(sentinel_stream, "QUEUE_MAXSIZE", 4)
    stream = SentinelStream(history=4)
    queue, sub = stream.subscribe()
    assert stream.subscriber_count == 1
    for index in range(9):
        stream.emit(
            sentinel_stream.SentinelEvent(
                timestamp="t",
                source="s",
                destination=f"host{index}",
                port=None,
                process="p",
                agent=None,
                task_id=None,
                action="BLOCK",
                reason=None,
            )
        )
    assert stream.subscriber_count == 0  # dropped rather than blocking
    assert len(stream.recent(1000)) <= 4  # bounded history


def test_unsubscribe_is_idempotent():
    stream = SentinelStream()
    _, sub = stream.subscribe()
    assert stream.subscriber_count == 1
    sub.close()
    sub.close()
    assert stream.subscriber_count == 0


def test_emitting_with_no_subscribers_does_not_raise():
    stream = SentinelStream()
    stream.emit(
        sentinel_stream.SentinelEvent(
            timestamp="t",
            source="s",
            destination="d",
            port=None,
            process="p",
            agent=None,
            task_id=None,
            action="ALLOW",
            reason=None,
        )
    )
    assert len(stream.recent()) == 1


def test_emit_from_a_worker_thread_reaches_the_loop():
    """The httpx transport runs off-loop; the hop must be thread-safe."""

    async def scenario() -> dict:
        stream = SentinelStream()
        queue, sub = stream.subscribe()
        try:
            await asyncio.to_thread(
                stream.emit,
                sentinel_stream.SentinelEvent(
                    timestamp="t",
                    source="127.0.0.1",
                    destination="blocked.example",
                    port=443,
                    process="python",
                    agent=None,
                    task_id=None,
                    action="BLOCK",
                    reason="denied by egress policy",
                ),
            )
            return await asyncio.wait_for(queue.get(), timeout=2.0)
        finally:
            sub.close()

    frame = asyncio.run(scenario())
    assert frame["destination"] == "blocked.example"


# ---------------------------------------------------------------- http api ---


def _settings(tmp_path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'net.db'}",
        uploads_dir=tmp_path / "uploads",
        log_level="WARNING",
    )


def test_sse_frame_carries_the_documented_field_set():
    """The wire contract the console parses, asserted on the encoder itself."""
    frame = sse_frame(
        {
            "timestamp": "2026-01-01T00:00:00.000+00:00",
            "source": "127.0.0.1",
            "destination": "exfiltrate.example.net",
            "port": 443,
            "process": "python",
            "agent": None,
            "task_id": None,
            "action": "BLOCK",
            "reason": "denied by egress policy",
        }
    )
    assert frame.startswith(f"event: {EVENT_NAME}\n")
    assert frame.endswith("\n\n")
    body = frame.split("data: ", 1)[1].strip()
    payload = json.loads(body)
    assert set(payload) >= {
        "timestamp",
        "source",
        "destination",
        "port",
        "process",
        "agent",
        "task_id",
        "action",
        "reason",
    }
    assert payload["action"] in {"ALLOW", "BLOCK"}
    # Unknown stays null on the wire rather than being dropped or invented.
    assert payload["agent"] is None and payload["task_id"] is None


def test_queue_payload_is_flat_and_sse_frame_does_not_nest_it():
    """Regression: the stream once emitted `data: {"event":...,"data":{...}}`.

    The event *name* belongs in the SSE `event:` line. Nesting the payload
    under a `data` key put every documented field one level below where the
    contract says it is, so a client reading `event.action` saw undefined.
    """
    queue, sub = sentinel_stream.STREAM.subscribe()
    try:
        try:
            check_and_record(EgressPolicy(default_deny=True), "https://evil.example.com/x")
        except EgressBlocked:
            pass
        payload = queue.get_nowait() if queue.qsize() else {}
    finally:
        sub.close()

    # Flat at the queue...
    assert "data" not in payload, payload
    assert payload["action"] == "BLOCK"

    # ...and still flat after the SSE encoder.
    encoded = sse_frame(payload)
    body = json.loads(encoded.split("data: ", 1)[1].strip())
    assert "data" not in body
    assert body["action"] == "BLOCK"
    assert body["destination"] == "evil.example.com"


def test_stream_route_is_registered_with_the_expected_path(tmp_path):
    """Both new endpoints are mounted on the real app.

    Read from the OpenAPI schema rather than ``app.routes``: this app includes
    its routers through a wrapper object that does not expose ``path``, so
    walking the route list silently finds nothing and would look like a pass
    for the wrong reason.
    """
    with TestClient(create_app(_settings(tmp_path))) as client:
        schema = client.get("/openapi.json").json()
    paths = set(schema.get("paths", {}))
    assert "/api/network/stream" in paths
    assert "/api/audit/integrity" in paths


def test_stream_endpoint_requires_a_principal(tmp_path):
    """The route is behind the same auth as every other console read."""
    settings = _settings(tmp_path)
    settings.auth_required = True
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/network/stream")
    assert response.status_code in (401, 403)
