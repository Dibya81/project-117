from __future__ import annotations

import pytest
from backend.api.src.main import create_app
from backend.chat.service import ChatService
from backend.config import Settings
from backend.models import ModelRoles
from backend.models.gateway import ModelGateway
from backend.models.router import ModelRouter
from fastapi.testclient import TestClient

# Single source of truth: FakeProvider is defined in tests/conftest.py so that
# test modules importing it as ``from tests.conftest import FakeProvider`` and
# fixtures here both resolve the same class.
from tests.conftest import FakeProvider

__all__ = ["FakeProvider"]


@pytest.fixture
def settings(tmp_path):
    return Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        uploads_dir=tmp_path / "uploads",
        llm_base_url="http://127.0.0.1:1/v1",  # connection refused instantly
        log_level="WARNING",
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def fake_gateway() -> ModelGateway:
    return ModelGateway(providers={"fake": FakeProvider()}, default_provider="fake")


@pytest.fixture
def chat_client(fake_gateway, tmp_path):
    """App whose model layer is backed by the fake provider, with a
    configured reasoning model so /api/chat is fully functional."""
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'chat.db'}",
        uploads_dir=tmp_path / "uploads",
        reasoning_model="llama3:latest",
        log_level="WARNING",
    )
    app = create_app(settings)
    app.state.gateway = fake_gateway
    roles = ModelRoles(settings)
    app.state.router = ModelRouter(fake_gateway, roles, availability_ttl=0)
    # Retrieval stays None: the fake app has no vendor index, and grounding
    # degrades to ungrounded chat (evidence_for_chat is never consulted).
    app.state.chat = ChatService(
        app.state.router, app.state.sessions, app.state.audit, retrieval=None
    )
    with TestClient(app) as test_client:
        yield test_client