"""Sensor out-of-service operations and plant reset.

These drive the real engine and the real service — no mocks — because the
console depends on the removal response shape and on the agent pipeline
actually running for a lost measurement.
"""

from __future__ import annotations

import pytest
from backend.api.src.main import create_app
from backend.config import Settings
from backend.simulation.datasets import load_plant
from backend.simulation.engine import SimulationEngine
from backend.simulation.models import AlarmSeverity, IncidentStatus, TelemetryQuality
from backend.simulation.service import SimulationService
from fastapi.testclient import TestClient

SENSOR = "s-PT-1042A"
EQUIPMENT = "e-P-1042"


@pytest.fixture()
def engine() -> SimulationEngine:
    return SimulationEngine(load_plant("refinery"), seed=117)


@pytest.fixture()
def svc() -> SimulationService:
    service = SimulationService()
    service.register(load_plant("refinery"), seed=117)
    return service


# --------------------------------------------------------------------- engine


class TestEngineSensorOps:
    def test_disable_reports_bad_quality(self, engine):
        engine.disable_sensor(SENSOR)
        assert engine.sensor_out_of_service(SENSOR) == "disabled"
        assert engine.sensors[SENSOR].failed is True
        assert engine.sensors[SENSOR].quality == TelemetryQuality.BAD
        reading = next(r for r in engine.tick()["readings"] if r["sensor_id"] == SENSOR)
        assert reading["quality"] == "bad"

    def test_remove_absent_from_snapshot_and_plant_definition(self, engine):
        engine.remove_sensor(SENSOR)
        assert SENSOR not in engine.sensors
        assert SENSOR not in engine.snapshot()["sensors"]
        assert engine.sensor_out_of_service(SENSOR) == "removed"
        eq = next(e for e in engine.plant.equipment if e.id == EQUIPMENT)
        assert all(s.id != SENSOR for s in eq.sensors)
        # the heartbeat must not trip over the missing runtime
        assert SENSOR not in {r["sensor_id"] for r in engine.tick()["readings"]}

    def test_restore_removed_sensor_raises(self, engine):
        engine.remove_sensor(SENSOR)
        with pytest.raises(KeyError, match="reset"):
            engine.restore_sensor(SENSOR)

    def test_restore_disabled_sensor_resets_nominal(self, engine):
        engine.disable_sensor(SENSOR)
        engine.restore_sensor(SENSOR)
        assert engine.sensor_out_of_service(SENSOR) is None
        assert engine.sensors[SENSOR].failed is False
        assert engine.sensors[SENSOR].quality == TelemetryQuality.GOOD
        assert engine.sensors[SENSOR].value == engine.sensor_model[SENSOR].nominal

    def test_unknown_sensor_raises_keyerror(self, engine):
        for op in (engine.disable_sensor, engine.remove_sensor, engine.restore_sensor):
            with pytest.raises(KeyError):
                op("s-NOPE")

    def test_session_change_counts_are_accurate(self, engine):
        engine.disable_sensor(SENSOR)
        engine.remove_sensor("s-FT-1042")
        engine.disable_equipment("e-P-1042")
        assert engine.session_change_counts() == {
            "disabled_sensors": 1,
            "removed_sensors": 1,
            "disabled_equipment": 1,
        }
        # a disabled sensor that is then removed is counted once, as removed
        engine.disable_sensor("s-TT-1042")
        engine.remove_sensor("s-TT-1042")
        assert engine.session_change_counts()["disabled_sensors"] == 1
        assert engine.session_change_counts()["removed_sensors"] == 2

    def test_removed_detector_does_not_break_injection_or_repair(self, engine):
        detector = next(sid for sid, m in engine.sensor_model.items() if m.is_detector)
        engine.remove_sensor(detector)
        engine.tick()
        engine.inject_failure(EQUIPMENT, "seal_leak")
        engine.restore_equipment(EQUIPMENT)
        engine.tick()


# -------------------------------------------------------------------- service


class TestServiceSensorOps:
    def test_disable_raises_incident_for_the_lost_point(self, svc):
        out = svc.disable_sensor("refinery", SENSOR)
        assert set(out) == {
            "sensor_id",
            "equipment_id",
            "measurement",
            "alternates",
            "affected",
            "incident_id",
        }
        assert out["incident_id"]
        inc = svc.runtime("refinery").engine.incidents[out["incident_id"]]
        assert inc.origin_sensor == SENSOR
        assert inc.origin_equipment == EQUIPMENT
        assert inc.severity == AlarmSeverity.WARNING
        assert "Loss of measurement" in inc.title

    def test_second_disable_reuses_open_incident(self, svc):
        first = svc.disable_sensor("refinery", SENSOR)
        second = svc.disable_sensor("refinery", SENSOR)
        assert second["incident_id"] == first["incident_id"]
        rt = svc.runtime("refinery")
        open_for_sensor = [
            i
            for i in rt.engine.incidents.values()
            if i.origin_sensor == SENSOR and i.status != IncidentStatus.RESOLVED
        ]
        assert len(open_for_sensor) == 1
        assert len(rt.incident_tasks[first["incident_id"]]) > 0

    def test_remove_returns_redundancy_and_critical_incident(self, svc):
        out = svc.remove_sensor("refinery", SENSOR)
        assert out["equipment_id"] == EQUIPMENT
        assert out["measurement"] == "pressure"
        assert "s-PT-1042B" in out["alternates"]
        assert "e-E-1004" in out["affected"]
        assert SENSOR not in svc.runtime("refinery").engine.sensors
        inc = svc.runtime("refinery").engine.incidents[out["incident_id"]]
        assert inc.severity == AlarmSeverity.CRITICAL
        assert "Instrument deleted" in inc.title

    def test_reset_restores_pristine_plant(self, svc):
        removed = svc.remove_sensor("refinery", SENSOR)
        svc.disable_sensor("refinery", "s-FT-1042")
        assert svc.runtime("refinery").engine.sensor_out_of_service(SENSOR) == "removed"
        rt = svc.reset("refinery", load_plant("refinery"))
        assert rt is svc.runtime("refinery")
        assert SENSOR in rt.engine.sensors
        assert rt.engine.sensors[SENSOR].quality == TelemetryQuality.GOOD
        assert rt.engine.sensor_out_of_service(SENSOR) is None
        assert rt.engine.session_change_counts() == {
            "disabled_sensors": 0,
            "removed_sensors": 0,
            "disabled_equipment": 0,
        }
        # the stale runtime (and its open measurement-loss incidents) is gone,
        # and the persisted rows are closed rather than left awaiting approval
        assert rt.engine.incidents == {}
        history = {row["id"]: row["status"] for row in svc.store.incident_history("refinery")}
        assert history[removed["incident_id"]] == "resolved"


# ----------------------------------------------------------------------- HTTP


@pytest.fixture(scope="module")
def client():
    app = create_app(Settings())
    with TestClient(app) as test_client:
        yield test_client


def _tasks(client: TestClient, incident_id: str) -> dict:
    resp = client.get(f"/api/simulation/plants/refinery/incidents/{incident_id}/tasks")
    assert resp.status_code == 200
    return resp.json()


def test_http_disable_returns_context_and_incident(client: TestClient):
    resp = client.post(f"/api/simulation/plants/refinery/sensors/{SENSOR}/disable")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sensor_id"] == SENSOR
    assert data["equipment_id"] == EQUIPMENT
    assert data["incident_id"]
    # the console renders the pipeline through the existing tasks route
    pipeline = _tasks(client, data["incident_id"])
    assert pipeline["tasks"]
    assert pipeline["plan"]
    # a second disable must not stack a second open incident
    again = client.post(f"/api/simulation/plants/refinery/sensors/{SENSOR}/disable")
    assert again.status_code == 200
    assert again.json()["incident_id"] == data["incident_id"]
    restore = client.post(f"/api/simulation/plants/refinery/sensors/{SENSOR}/restore")
    assert restore.status_code == 200


def test_http_remove_returns_verbatim_redundancy(client: TestClient):
    resp = client.post("/api/simulation/plants/refinery/sensors/s-FT-1042/remove")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data) == {
        "sensor_id",
        "equipment_id",
        "measurement",
        "alternates",
        "affected",
        "incident_id",
    }
    assert data["sensor_id"] == "s-FT-1042"
    snapshot = client.get("/api/simulation/plants/refinery/snapshot").json()
    assert "s-FT-1042" not in snapshot["sensors"]


def test_http_reset_restores_sensor(client: TestClient):
    resp = client.post("/api/simulation/plants/refinery/reset")
    assert resp.status_code == 200
    equipment = len(load_plant("refinery").equipment)
    assert resp.json() == {"plant": "refinery", "reset": True, "equipment": equipment}
    snapshot = client.get("/api/simulation/plants/refinery/snapshot").json()
    assert snapshot["sensors"]["s-FT-1042"]["quality"] == "good"


def test_http_unknown_sensor_is_404(client: TestClient):
    for action in ("disable", "remove", "restore"):
        resp = client.post(f"/api/simulation/plants/refinery/sensors/s-NOPE/{action}")
        assert resp.status_code == 404, action


def test_http_reset_unknown_plant_is_404(client: TestClient):
    assert client.post("/api/simulation/plants/nope/reset").status_code == 404
