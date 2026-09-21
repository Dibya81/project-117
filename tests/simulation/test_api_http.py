import pytest
from backend.api.src.main import create_app
from backend.config import Settings
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    settings = Settings()
    app = create_app(settings)
    with TestClient(app) as client:
        yield client


def test_health(client: TestClient):
    resp = client.get("/api/simulation/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["mode"] == "live"
    assert "agents" in data


def test_list_plants(client: TestClient):
    resp = client.get("/api/simulation/plants")
    assert resp.status_code == 200
    data = resp.json()
    assert "plants" in data


def test_start_plant(client: TestClient):
    resp = client.post("/api/simulation/plants/refinery/start")
    assert resp.status_code == 200
    data = resp.json()
    assert data["plant"] == "refinery"
    assert data["running"] is True


def test_snapshot_plant(client: TestClient):
    resp = client.get("/api/simulation/plants/refinery/snapshot")
    assert resp.status_code == 200
    data = resp.json()
    assert "plant" in data


def test_inject_failure(client: TestClient):
    resp = client.post(
        "/api/simulation/plants/refinery/equipment/e-P-1001/failure", json={"mode_id": "seal_leak"}
    )
    assert resp.status_code == 200


def test_incidents(client: TestClient):
    resp = client.get("/api/simulation/plants/refinery/incidents")
    assert resp.status_code == 200
    data = resp.json()
    assert "incidents" in data
    incidents = data["incidents"]
    assert len(incidents) > 0

    # Take the first incident to test tasks and decisions
    inc_id = incidents[-1]["id"]

    # Tasks
    resp_tasks = client.get(f"/api/simulation/plants/refinery/incidents/{inc_id}/tasks")
    assert resp_tasks.status_code == 200
    data_tasks = resp_tasks.json()
    assert "tasks" in data_tasks
    assert "plan" in data_tasks

    # Decision
    resp_dec = client.post(
        f"/api/simulation/plants/refinery/incidents/{inc_id}/decision", json={"approved": True}
    )
    assert resp_dec.status_code == 200

    # Record
    resp_rec = client.get(f"/api/simulation/incidents/{inc_id}/record")
    assert resp_rec.status_code == 200


def test_audit(client: TestClient):
    resp = client.get("/api/simulation/audit?plant_id=refinery")
    assert resp.status_code == 200
    assert "events" in resp.json()


def test_history(client: TestClient):
    resp = client.get("/api/simulation/plants/refinery/history")
    assert resp.status_code == 200
    assert "incidents" in resp.json()


def test_plant_definition(client: TestClient):
    resp = client.get("/api/simulation/plants/refinery/definition")
    assert resp.status_code == 200
    assert "plant" in resp.json()


def test_plant_scenarios(client: TestClient):
    resp = client.get("/api/simulation/plants/refinery/scenarios")
    assert resp.status_code == 200
    scenarios = resp.json()["scenarios"]
    assert len(scenarios) == 14
    assert {"id", "name", "description", "steps"} <= set(scenarios[0])


def test_plant_scenarios_unknown_plant(client: TestClient):
    resp = client.get("/api/simulation/plants/no-such-plant/scenarios")
    assert resp.status_code == 404


def test_incident_pdf_download(client: TestClient):
    resp_inc = client.get("/api/simulation/plants/refinery/incidents")
    assert resp_inc.status_code == 200
    incidents = resp_inc.json()["incidents"]
    assert len(incidents) > 0
    inc_id = incidents[-1]["id"]

    # Test plant-scoped endpoint
    resp_pdf = client.get(f"/api/simulation/plants/refinery/incidents/{inc_id}/report.pdf")
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["content-type"] == "application/pdf"
    assert resp_pdf.content.startswith(b"%PDF-")
    assert b"%%EOF" in resp_pdf.content[-2048:]

    # Test global incident-scoped endpoint
    resp_pdf2 = client.get(f"/api/simulation/incidents/{inc_id}/report.pdf")
    assert resp_pdf2.status_code == 200
    assert resp_pdf2.headers["content-type"] == "application/pdf"
    assert resp_pdf2.content.startswith(b"%PDF-")
