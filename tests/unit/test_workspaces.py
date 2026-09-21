"""Unit tests for workspace management and knowledge health."""

from __future__ import annotations

from starlette.testclient import TestClient


def test_get_default_workspace(client: TestClient) -> None:
    res = client.get("/api/workspaces/default")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "default"
    assert "id" in data
    assert data["knowledge_version"].startswith("v")


def test_create_and_list_workspaces(client: TestClient) -> None:
    res = client.post(
        "/api/workspaces",
        json={"name": "acme_refinery", "description": "Acme Refinery Plant Documents"},
    )
    assert res.status_code == 201
    created = res.json()
    assert created["name"] == "acme_refinery"
    assert created["description"] == "Acme Refinery Plant Documents"

    list_res = client.get("/api/workspaces")
    assert list_res.status_code == 200
    workspaces = list_res.json()["workspaces"]
    names = [w["name"] for w in workspaces]
    assert "acme_refinery" in names


def test_workspace_health_empty(client: TestClient) -> None:
    res = client.post("/api/workspaces", json={"name": "empty_ws"})
    assert res.status_code == 201
    ws_id = res.json()["id"]

    health_res = client.get(f"/api/workspaces/{ws_id}/health")
    assert health_res.status_code == 200
    health = health_res.json()
    assert health["workspace_id"] == ws_id
    assert health["documents"] == 0
    assert health["status"] == "EMPTY"
