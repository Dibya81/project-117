from __future__ import annotations


def test_health_reports_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["uploads_writable"] is True
    # The local model backend is not running in tests; the check must degrade
    # gracefully instead of failing the health probe.
    assert "llm" in body
    assert body["llm"]["running"] is False
    assert "services" in body
    # Posture figures must be measured, not invented.
    storage = body["storage"]
    assert storage["available"] is True
    assert storage["total_gb"] > 0
    assert 0 <= storage["used_gb"] <= storage["total_gb"]
    assert body["egress"] in {"denied", "allowlist"}


def test_root_identifies_service(client):
    body = client.get("/").json()
    assert body["service"] == "project-117-backend"
    assert body["health"] == "/health"
