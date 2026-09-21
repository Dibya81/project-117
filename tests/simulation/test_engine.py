"""Simulation engine unit + integration tests (§56).

Run: uv run pytest tests/simulation -q

These drive the real engine against the real generated datasets — no mocks
of the engine itself. The pipeline under test is the same one the API and
the Command Center consume.
"""

from __future__ import annotations

import json

import pytest
from backend.simulation.datasets import load_plant, load_scenarios
from backend.simulation.models import AlarmSeverity, AssetState, TelemetryQuality
from backend.simulation.service import SimulationService


@pytest.fixture(scope="module")
def refinery():
    return load_plant("refinery")


@pytest.fixture()
def svc(refinery):
    svc = SimulationService()
    svc.register(refinery, seed=117)
    svc.start("refinery")
    return svc


# --------------------------------------------------------------------- unit


class TestTelemetry:
    def test_baseline_inside_envelope(self, svc):
        frame = svc.step("refinery")
        for r in frame["readings"][:200]:
            assert r["quality"] == "good"

    def test_determinism(self, refinery):
        a = SimulationService()
        a.register(refinery, seed=117)
        b = SimulationService()
        b.register(refinery, seed=117)
        for _ in range(5):
            fa = a.step("refinery")
            fb = b.step("refinery")
        assert [r["value"] for r in fa["readings"]] == [r["value"] for r in fb["readings"]]

    def test_sensor_failure_sets_bad_quality(self, svc):
        rt = svc.runtime("refinery")
        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        sid = out["changed"]["sensor_id"]
        assert rt.engine.sensors[sid].quality == TelemetryQuality.BAD

    def test_sensor_failure_does_not_stop_the_plant(self, svc):
        """§23: measurement loss ≠ equipment loss."""
        svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        rt = svc.runtime("refinery")
        assert rt.engine.eq["e-P-1042"].capacity == 1.0
        assert rt.engine.eq["e-P-1042"].state == AssetState.NORMAL

    def test_drift_eventually_alarms(self, svc):
        svc.inject_failure("refinery", "e-P-1042", "instrument_drift")
        for _ in range(70):
            svc.step("refinery")
        assert any(
            a.tag.startswith(("PT-1042", "TT-1042", "FT-1042"))
            for a in rt_engine(svc).alarms.values()
        )


class TestTopology:
    def test_trip_propagates_downstream(self, svc):
        svc.inject_failure("refinery", "e-P-1042", "trip")
        for _ in range(4):
            frame = svc.step("refinery")
        flow = next(p for p in frame["readings"] if p["sensor_id"] == "s-FT-1042")
        assert flow["value"] < 70  # collapsed from ~96

    def test_neighbors_are_graph_derived(self, svc):
        rt = svc.runtime("refinery")
        hood = rt.engine.neighbors("e-P-1042", depth=2)["affected"]
        assert "e-E-1004" in hood and "e-V-1103" in hood

    def test_alternate_sensors_finds_redundant_pair(self, svc):
        rt = svc.runtime("refinery")
        alts = rt.engine.alternate_sensors("s-PT-1042A")
        assert any(a.tag == "PT-1042B" for a in alts)

    def test_remove_breaks_connections(self, svc):
        rt = svc.runtime("refinery")
        broken = svc.remove_equipment("refinery", "e-P-1042")
        assert "e-E-1004" in broken
        for c in rt.engine.plant.connections:
            if c.source == "e-P-1042" or c.target == "e-P-1042":
                assert not c.enabled


class TestIncidentPipeline:
    def test_full_pipeline_sensor_failure(self, svc):
        """§62 golden path: failure → incident → agents → plan → approve →
        action → verify → resolved → artifact → audit."""
        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        inc = out["incident"]
        rt = svc.runtime("refinery")

        tasks = rt.incident_tasks[inc["id"]]
        agents = {t.agent for t in tasks}
        assert {
            "orchestrator",
            "data_analysis",
            "maintenance",
            "operations",
            "safety",
            "documentation",
        } <= agents
        assert any(t.depends_on for t in tasks)  # a real DAG, not a flat list
        assert any(len(t.evidence) > 0 for t in tasks)

        plan = rt.incident_plans[inc["id"]]
        assert plan.requires_approval
        assert plan.action["kind"] == "repair_sensor"

        res = svc.decide("refinery", inc["id"], True)
        assert res["status"] == "resolved"
        assert res["verified"]
        assert rt.artifacts and rt.artifacts[-1]["kind"] == "incident_report"

        types = {e.type for e in rt.events}
        assert "incident.created" in types
        assert "approval.granted" in types
        assert "verification.completed" in types
        assert "artifact.created" in types
        assert "audit.recorded" in types

    def test_rejection_escalates(self, svc):
        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        res = svc.decide("refinery", out["incident"]["id"], False)
        assert res["status"] == "escalated"

    def test_failed_verification_replans_then_escalates(self, svc, monkeypatch):
        """A route that validates but never clears the envelope must not leave
        the incident open forever.

        The first attempt only knows the topology, so a failed pass is handed
        back to the same three agents together with the real findings. When that
        second route also fails, the incident reaches a terminal state —
        escalated — instead of sitting in `investigating` with the plant
        degraded and the console stuck on the recovery panel.
        """
        from backend.simulation import service as service_mod
        from backend.simulation.models import IncidentStatus

        # Force verification to fail every pass, deterministically.
        monkeypatch.setattr(
            service_mod,
            "verify_plan",
            lambda engine, incident: (False, ["LT-9001 still beyond critical envelope"]),
        )
        seen: list[dict] = []
        real = service_mod.run_incident_decision

        def spy(engine, incident, **kw):
            seen.append(kw)
            return real(engine, incident, **kw)

        monkeypatch.setattr(service_mod, "run_incident_decision", spy)

        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        inc_id = out["incident"]["id"]
        res = svc.decide("refinery", inc_id, True)

        assert res["status"] == "escalated"
        assert res["escalated"] is True
        assert service_mod.RECOVERY_ATTEMPTS == 2
        assert len(seen) == 2
        # The second turn is told what the first one already tried — otherwise
        # the agents are free to return the same failed route forever.
        assert seen[0].get("prior_attempt") is None
        prior = seen[1]["prior_attempt"]
        assert prior["findings"] == ["LT-9001 still beyond critical envelope"]
        assert prior["route"] or prior["block"] or prior["restore"]

        rt = svc.runtime("refinery")
        assert rt.engine.incidents[inc_id].status == IncidentStatus.ESCALATED
        types = [e.type for e in rt.events]
        assert "recovery.replanning" in types
        assert "recovery.escalated" in types
        # Two real verification records, one per attempt — not one overwritten row.
        ver_ids = [
            e.payload["verification_id"] for e in rt.events if e.type == "verification.completed"
        ]
        assert len(ver_ids) == 2 and len(set(ver_ids)) == 2
        # And the escalation is on the audit trail with the real findings.
        audit = svc.store.audit_events(incident_id=inc_id)
        row = next(r for r in audit if r["event_type"] == "recovery.escalated")
        assert row["result"] == "escalated"
        assert "critical envelope" in json.dumps(row.get("payload"))

    def test_successful_recovery_is_one_attempt(self, svc, monkeypatch):
        """The happy path must not pay for the retry loop."""
        from backend.simulation import service as service_mod

        real = service_mod.run_incident_decision
        calls = {"n": 0}

        def spy(engine, incident, **kw):
            calls["n"] += 1
            return real(engine, incident, **kw)

        monkeypatch.setattr(service_mod, "run_incident_decision", spy)
        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        res = svc.decide("refinery", out["incident"]["id"], True)
        assert res["status"] == "resolved"
        assert calls["n"] == 1
        assert res["attempt"] == 1

    def test_leak_trips_detector(self, svc):
        out = svc.inject_failure("refinery", "e-P-1042", "seal_leak")
        assert out["changed"].get("detector"), "leak must trip a nearby detector"
        inc = out["incident"]
        assert inc["severity"] == AlarmSeverity.CRITICAL.value

    def test_arbitrary_equipment_no_hardcoding(self, svc):
        """§66 TEST 5: a different equipment runs the same generic pipeline."""
        out = svc.inject_failure("refinery", "e-C-1053", "trip")
        inc = out["incident"]
        rt = svc.runtime("refinery")
        assert rt.incident_tasks[inc["id"]]  # pipeline built from topology
        assert rt.incident_plans[inc["id"]].action["target"] == "e-C-1053"


class TestSteelPlant:
    def test_dataset_loads_and_ticks(self):
        svc = SimulationService()
        svc.register(load_plant("steel"))
        svc.start("steel")
        frame = svc.step("steel")
        assert len(frame["readings"]) > 180

    def test_steel_scenario_targets_resolve(self):
        plant = load_plant("steel")
        eq_ids = {e.id for e in plant.equipment}
        for sc in load_scenarios("steel"):
            for st in sc.steps:
                assert st.target in eq_ids


def rt_engine(svc: SimulationService):
    return svc.runtime("refinery").engine
