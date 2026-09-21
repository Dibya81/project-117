"""Unit tests for /api/knowledge-hub endpoints."""

from __future__ import annotations

from starlette.testclient import TestClient


def test_knowledge_hub_entities_empty(client: TestClient) -> None:
    res = client.get("/api/knowledge-hub/entities")
    assert res.status_code == 200
    data = res.json()
    assert "entities" in data
    assert data["total"] == 0


def test_knowledge_hub_graph_empty(client: TestClient) -> None:
    res = client.get("/api/knowledge-hub/graph")
    assert res.status_code == 200
    data = res.json()
    assert "nodes" in data
    assert "edges" in data
    assert data["nodes"] == []
    assert data["edges"] == []
