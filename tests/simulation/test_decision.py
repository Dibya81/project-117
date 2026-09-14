"""The model-driven recovery decision contract.

The three agents decide the route; the engine executes exactly that route.
When the local model is unavailable there is no silent fallback to a scripted
recovery — the incident stays open and the caller sees LOCAL MODEL UNAVAILABLE.
"""

from __future__ import annotations

import pytest
from backend.simulation import decision
from backend.simulation.datasets import load_plant
from backend.simulation.service import SimulationService


@pytest.fixture()
def svc():
    service = SimulationService()
    service.register(load_plant("refinery"), seed=117)
    service.start("refinery")
    return service


def _decision_event(svc):
    rt = svc.runtime("refinery")
    return next((e for e in rt.events if e.type == "response.decision"), None)


class TestDecisionDrivesRecovery:
    def test_agents_choose_the_route_the_engine_executes(self, svc):
        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        res = svc.decide("refinery", out["incident"]["id"], True)

        assert res["verified"] is True
        decision = svc.runtime("refinery").incident_decisions[out["incident"]["id"]]
        assert decision.available is True
        # The route is real connection ids from the plant graph.
        plant_ids = {c.id for c in svc.runtime("refinery").engine.plant.connections}
        assert decision.restore
        assert set(decision.restore) <= plant_ids
        # The action the engine executed is the decision, not a hardcoded plan.
        ev = _decision_event(svc)
        assert ev.payload["available"] is True
        assert ev.payload["restore"] == decision.restore

    def test_each_sensor_produces_its_own_evidence(self):
        svc_a = SimulationService()
        svc_a.register(load_plant("refinery"), seed=117)
        svc_a.start("refinery")
        a = svc_a.inject_failure("refinery", "e-P-1042", "sensor_failure")
        svc_a.decide("refinery", a["incident"]["id"], True)

        svc_b = SimulationService()
        svc_b.register(load_plant("refinery"), seed=117)
        svc_b.start("refinery")
        b = svc_b.inject_failure("refinery", "e-P-1001", "sensor_failure")
        svc_b.decide("refinery", b["incident"]["id"], True)

        assert a["incident"]["origin_sensor"] != b["incident"]["origin_sensor"]
        da = svc_a.runtime("refinery").incident_decisions[a["incident"]["id"]]
        db = svc_b.runtime("refinery").incident_decisions[b["incident"]["id"]]
        # Two origins -> two evidence packs -> the routes the agents were handed
        # differ, so the chosen route ids differ.
        assert set(da.restore) != set(db.restore)


class TestUnavailableModelIsNotSilent:
    def test_unavailable_model_blocks_recovery(self, svc, monkeypatch):
        monkeypatch.setattr(decision, "_ask_override", None)
        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        res = svc.decide("refinery", out["incident"]["id"], True)

        assert res["verified"] is False
        assert res["available"] is False
        assert "LOCAL MODEL UNAVAILABLE" in " ".join(res["findings"])
        ev = _decision_event(svc)
        assert ev.payload["available"] is False
        assert "LOCAL MODEL UNAVAILABLE" in (ev.payload["error"] or "")
        # No recovery event was fabricated.
        rt = svc.runtime("refinery")
        assert not any(e.type == "action.completed" for e in rt.events)
        assert not any(e.type == "incident.resolved" for e in rt.events)


class TestInvalidDecisionIsRejected:
    def test_block_restore_overlap_cannot_execute(self, svc, monkeypatch):
        def ask(role: str, system: str, user: str) -> tuple[str, str]:
            if role == "diagnostic":
                return (
                    '{"affected_equipment": [], "diagnosis": "sensor failure", '
                    '"failure_mode": "sensor_failure"}',
                    "test-model",
                )
            if role == "operations":
                return (
                    '{"route": ["pl-004"], "block": ["pl-004"], '
                    '"restore": ["pl-004"], "rationale": "no-op"}',
                    "test-model",
                )
            return '{"safe": true, "concerns": []}', "test-model"

        monkeypatch.setattr(decision, "_ask_override", ask)
        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        res = svc.decide("refinery", out["incident"]["id"], True)

        assert res["verified"] is False
        assert res["available"] is False
        assert "block and restore overlap" in " ".join(res["findings"])
        ev = _decision_event(svc)
        assert ev.payload["available"] is False
        assert "INVALID RECOVERY DECISION" in (ev.payload["error"] or "")
        rt = svc.runtime("refinery")
        assert not any(e.type == "action.completed" for e in rt.events)
        assert not any(e.type == "incident.resolved" for e in rt.events)
