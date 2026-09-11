from __future__ import annotations

import json

from backend.api.src.main import create_app
from backend.chat.service import ChatService
from backend.config import Settings
from backend.models import ModelRoles
from backend.models.gateway import ModelGateway
from backend.models.router import ModelRouter
from fastapi.testclient import TestClient

from tests.conftest import FakeProvider


def test_chat_turn_returns_answer(chat_client):
    response = chat_client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 200
    body = response.json()
    assert body["response"].startswith("n=")
    assert body["model"] == "llama3:latest"
    assert body["provider"] == "fake"
    assert body["latency_ms"] >= 0
    assert body["evidence"] == []


def test_chat_session_history_is_used(chat_client):
    first = chat_client.post("/api/chat", json={"message": "turn one", "session_id": "s1"})
    assert first.status_code == 200
    assert first.json()["response"] == "n=2:turn one"  # system + user

    second = chat_client.post("/api/chat", json={"message": "turn two", "session_id": "s1"})
    assert second.status_code == 200
    # system + user + assistant + user — history propagated into the prompt.
    assert second.json()["response"] == "n=4:turn two"

    # Audit records both turns (metadata only).
    events = chat_client.get("/api/audit", params={"action": "chat.completed"}).json()
    assert events["total"] == 2
    assert events["events"][0]["detail"]["model"] == "llama3:latest"


def test_chat_without_session_is_stateless(chat_client):
    first = chat_client.post("/api/chat", json={"message": "only"})
    second = chat_client.post("/api/chat", json={"message": "only"})
    assert first.json()["response"] == second.json()["response"] == "n=2:only"


def test_chat_stream_emits_sse_events(chat_client):
    with chat_client.stream(
        "POST", "/api/chat/stream", json={"message": "stream me"}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = [
            json.loads(line[5:])
            for line in response.iter_lines()
            if line.startswith("data:") and line != "data: [DONE]"
        ]
    types = [event["type"] for event in events]
    assert types == ["start", "delta", "delta", "complete"]
    assert [event["text"] for event in events if event["type"] == "delta"] == ["hello ", "world"]
    assert events[-1]["model"] == "llama3:latest"


def test_chat_stream_persists_history(chat_client):
    with chat_client.stream("POST", "/api/chat/stream", json={"message": "hi", "session_id": "s2"}):
        pass
    turn = chat_client.post("/api/chat", json={"message": "again", "session_id": "s2"})
    # system + user + assistant + user = 4
    assert turn.json()["response"] == "n=4:again"


def test_model_not_served_returns_503(chat_client):
    response = chat_client.post("/api/chat", json={"message": "hi", "model": "ghost:latest"})
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "model_unavailable"
    assert "llama3:latest" in body["error"]["detail"]["available_models"]


def test_unconfigured_role_returns_503(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 't.db'}",
        uploads_dir=tmp_path / "up",
        reasoning_model="",  # nothing configured
        log_level="WARNING",
    )
    app = create_app(settings)
    gateway = ModelGateway(providers={"fake": FakeProvider()}, default_provider="fake")
    app.state.gateway = gateway
    app.state.router = ModelRouter(gateway, ModelRoles(settings), availability_ttl=0)
    app.state.chat = ChatService(
        app.state.router, app.state.sessions, app.state.audit, retrieval=None
    )
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "hi"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_unavailable"


def test_provider_unreachable_returns_503(chat_client, fake_gateway):
    fake_gateway._providers["fake"] = FakeProvider(fail_unreachable=True)
    response = chat_client.post("/api/chat", json={"message": "hi"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_unreachable"


def test_invalid_role_returns_400(chat_client):
    response = chat_client.post("/api/chat", json={"message": "hi", "role": "banana"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"


def test_explicit_model_override(chat_client):
    response = chat_client.post(
        "/api/chat", json={"message": "hi", "model": "nomic-embed-text:latest"}
    )
    assert response.status_code == 200
    assert response.json()["model"] == "nomic-embed-text:latest"