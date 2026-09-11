from __future__ import annotations


def test_list_models_shows_available_and_role_mapping(chat_client):
    body = chat_client.get("/api/models").json()
    assert body["backend"]["name"] == "fake"
    assert body["models"]["fake"] == ["llama3:latest", "nomic-embed-text:latest"]
    assert body["roles"]["reasoning"] == "llama3:latest"
    # Other roles default to empty until configured.
    assert body["roles"]["vision"] is None


def test_roles_are_config_driven(fake_gateway, tmp_path):
    from backend.api.src.main import create_app
    from backend.chat.service import ChatService
    from backend.config import Settings
    from backend.models import ModelRoles
    from backend.models.router import ModelRouter
    from fastapi.testclient import TestClient

    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path / 't.db'}",
        uploads_dir=tmp_path / "up",
        reasoning_model="llama3:latest",
        embedding_model="nomic-embed-text:latest",
        log_level="WARNING",
    )
    app = create_app(settings)
    app.state.gateway = fake_gateway
    app.state.router = ModelRouter(fake_gateway, ModelRoles(settings), availability_ttl=0)
    app.state.chat = ChatService(app.state.router, app.state.sessions, app.state.audit)
    with TestClient(app) as client:
        body = client.get("/api/models").json()
    assert body["roles"]["reasoning"] == "llama3:latest"
    assert body["roles"]["embedding"] == "nomic-embed-text:latest"