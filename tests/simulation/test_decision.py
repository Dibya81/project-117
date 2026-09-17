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
        assert "RECOVERY DECISION INVALID" in (ev.payload["error"] or "")
        rt = svc.runtime("refinery")
        assert not any(e.type == "action.completed" for e in rt.events)
        assert not any(e.type == "incident.resolved" for e in rt.events)


class TestUnparseableModelIsNotSilent:
    def test_non_json_replies_never_become_an_empty_recovery(self, svc, monkeypatch):
        """Three unparseable turns must not slip through as "available".

        The retry loop feeds a parse failure back for another attempt. If every
        attempt is unparseable there is no route at all, and the honest result is
        LOCAL MODEL UNAVAILABLE — never an available decision with empty lists.
        """

        def ask(role: str, system: str, user: str) -> tuple[str, str]:
            if role == "diagnostic":
                return (
                    '{"affected_equipment": [], "diagnosis": "sensor loss", '
                    '"failure_mode": null}',
                    "test-model",
                )
            return "I am afraid I cannot answer that as JSON.", "test-model"

        monkeypatch.setattr(decision, "_ask_override", ask)
        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        res = svc.decide("refinery", out["incident"]["id"], True)

        assert res["available"] is False
        assert res["verified"] is False
        assert "LOCAL MODEL UNAVAILABLE" in " ".join(res["findings"])
        ev = _decision_event(svc)
        assert ev.payload["available"] is False
        rt = svc.runtime("refinery")
        assert not any(e.type == "action.completed" for e in rt.events)
        assert not any(e.type == "incident.resolved" for e in rt.events)


class TestSafetyFactsAreNarrow:
    def test_the_incidents_own_out_of_service_point_is_not_a_hazard(self, svc):
        """The Safety agent must judge the route, not the fault that caused it.

        Handing it the whole evidence pack made a small local model refuse
        routes because the incident's own lost transmitter appeared in the
        evidence. The narrowed facts separate "readable and beyond critical"
        (a real hazard) from "already out of service" (the incident itself).
        """
        from backend.simulation.decision import build_decision_evidence, safety_facts

        rt = svc.runtime("refinery")
        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        incident = rt.engine.incidents[out["incident"]["id"]]

        facts = safety_facts(build_decision_evidence(rt.engine, incident))

        assert set(facts) == {
            "critical_alarms",
            "readable_sensors_beyond_critical",
            "out_of_service_points",
        }
        assert incident.origin_sensor in facts["out_of_service_points"]
        assert all(
            s["id"] != incident.origin_sensor
            for s in facts["readable_sensors_beyond_critical"]
        )


class TestLiveAlarmDoesNotBreakTheEvidencePack:
    def test_a_live_alarm_carries_its_owner_equipment(self, svc):
        """An Alarm has a sensor_id, not an equipment_id.

        Reading ``a.equipment_id`` raised AttributeError as soon as any alarm was
        live, which 500'd the decision request. The visible symptom was a SECOND
        incident stranded in ``awaiting_approval`` while the console kept showing
        the first incident's route — the alarm from the first recovery made the
        second decision impossible. This pins the evidence pack and a full
        decision against a live alarm.
        """
        from backend.simulation.decision import build_decision_evidence
        from backend.simulation.models import Alarm, AlarmSeverity

        rt = svc.runtime("refinery")
        rt.engine.alarms["A-TEST"] = Alarm(
            id="A-TEST", sensor_id="s-VIB-1001", tag="VIB-1001",
            severity=AlarmSeverity.WARNING, message="vibration high", at=0.0,
        )
        out = svc.inject_failure("refinery", "e-P-1001", "sensor_failure")
        incident = rt.engine.incidents[out["incident"]["id"]]

        evidence = build_decision_evidence(rt.engine, incident)
        assert evidence["alarms"], "the live alarm must appear in the evidence"
        assert evidence["alarms"][0]["equipment_id"] == "e-P-1001"

        res = svc.decide("refinery", incident.id, True)
        assert res["verified"] is True
