"""Agent Response Console event contract.

The console's three lanes may only advance on real backend events, so these
tests pin the contract those events carry: the job id that buckets them, the
department resolved from real ownership data, the alternate the engine actually
chose, a root-cause mode the equipment really declares, and prediction
candidates that are real plant assets.

They drive the real service against the committed refinery dataset — no mocks.
"""

from __future__ import annotations

import pytest
from backend.simulation.assessment import predict_next_failure
from backend.simulation.datasets import load_plant
from backend.simulation.response import choose_failover, resolve_department
from backend.simulation.service import SimulationService


@pytest.fixture()
def svc():
    service = SimulationService()
    service.register(load_plant("refinery"), seed=117)
    service.start("refinery")
    return service


def _events(svc, prefix: str | None = None) -> list:
    evs = svc.runtime("refinery").events
    return [e for e in evs if prefix is None or e.type.startswith(prefix)]


def _decide(svc, incident_id: str) -> None:
    """Drive the incident through the real three-agent decision.

    The lane FINDINGS are emitted only once the models have answered, so a test
    that asserts them must run the decision first. Asserting them straight after
    ``inject_failure`` is what encoded the old defect: the console was told the
    root cause, the prediction and the chosen alternate within milliseconds of
    the fault, before any model had been asked anything.
    """
    svc.decide("refinery", incident_id, True)


class TestFindingsWaitForTheAgents:
    """The lane conclusions must not exist before the agents have run."""

    @pytest.mark.parametrize(
        "event",
        [
            "response.failover_completed",
            "response.history_reviewed",
            "response.root_cause_identified",
            "response.prediction",
            "response.user_notified",
        ],
    )
    def test_not_emitted_at_handoff(self, svc, event):
        svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        assert _events(svc, event) == [], (
            f"{event} was emitted before the agents answered — the console would "
            "render a conclusion the models had not reached"
        )

    def test_start_beats_are_emitted_at_handoff(self, svc):
        """Work actually begins at handoff, so these are true immediately."""
        svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        assert len(_events(svc, "response.lane_started")) == 2
        assert _events(svc, "response.operations_notified")
        assert _events(svc, "response.failover_evaluating")

    def test_findings_appear_once_the_decision_exists(self, svc):
        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        _decide(svc, out["incident"]["id"])
        for event in (
            "response.failover_completed",
            "response.root_cause_identified",
            "response.prediction",
            "response.user_notified",
        ):
            assert _events(svc, event), f"{event} never emitted after the decision"

    def test_every_finding_follows_the_decision_event(self, svc):
        """Ordering is the whole point: conclusions come after the model output."""
        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        _decide(svc, out["incident"]["id"])
        evs = svc.runtime("refinery").events
        decision_seq = next(e.seq for e in evs if e.type == "response.decision")
        for event in (
            "response.failover_completed",
            "response.root_cause_identified",
            "response.prediction",
        ):
            seq = next(e.seq for e in evs if e.type == event)
            assert seq > decision_seq, f"{event} (#{seq}) preceded the decision (#{decision_seq})"


class TestPerception:
    def test_perception_carries_job_and_asset_context(self, svc):
        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        inc = out["incident"]
        [perception] = [e for e in _events(svc, "response.perception")]
        p = perception.payload
        assert p["job_id"] == inc["id"]
        assert p["incident_id"] == inc["id"]
        assert p["equipment_id"] == "e-P-1042"
        assert p["equipment_tag"] == "P-1042"
        assert p["fault_type"] == "sensor_failure"
        assert p["fault_name"] == "Sensor failure"
        assert p["severity"] == inc["severity"]
        # department resolves through the equipment's own process area
        assert p["department"] == "Crude Distillation"
        assert p["department_source"] == "plant_area.name"

    def test_agent_started_carries_explicit_handoff(self, svc):
        svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        [started] = [e for e in _events(svc, "agent.started")]
        payload = started.payload
        assert payload["job_id"]
        assert payload["equipment_tag"] == "P-1042"
        assert payload["severity"] in ("warning", "critical")
        assert payload["handoff"]["to"] == ["operations", "diagnostics"]


class TestOperationsLane:
    def test_sensor_failure_emits_chosen_failover(self, svc):
        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        [notified] = _events(svc, "response.operations_notified")
        assert notified.payload["role"] == "shift supervisor"
        assert notified.payload["department"] == "Crude Distillation"

        [evaluating] = _events(svc, "response.failover_evaluating")
        assert evaluating.payload["origin_sensor_id"] == "s-PT-1042A"
        assert evaluating.payload["candidates"], "must report the alternates it considered"
        assert _events(svc, "response.failover_completed") == [], "the choice is a finding"

        _decide(svc, out["incident"]["id"])
        [completed] = _events(svc, "response.failover_completed")
        related = completed.payload["related_equipment_id"]
        plant_ids = {e.id for e in svc.runtime("refinery").engine.plant.equipment}
        assert related in plant_ids, "failover must point at a real equipment id"
        assert related != "e-P-1042", "a cross-asset alternate is preferred when one exists"
        assert completed.payload["related_sensor_id"]
        assert completed.payload["same_asset"] is False

    def test_no_alternate_emits_no_failover_completion(self, svc):
        """A trip on a pump has no redundant measurement, so the ops lane never
        resolves its failover beat — the console must surface a no-response
        rather than a fabricated switch."""
        svc.inject_failure("refinery", "e-P-1042", "trip")
        assert _events(svc, "response.failover_evaluating")
        assert not _events(svc, "response.failover_completed")

    def test_choose_failover_helper_agrees_with_engine(self, svc):
        engine = svc.runtime("refinery").engine
        chosen = choose_failover(engine, "s-PT-1042A")
        alternates = {s.id for s in engine.alternate_sensors("s-PT-1042A")}
        assert chosen is not None
        assert chosen.id in alternates
        assert chosen.equipment_id == "e-V-1103"


class TestDiagnosticsLane:
    def test_history_counts_only_real_records(self, svc):
        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        _decide(svc, out["incident"]["id"])
        [history] = _events(svc, "response.history_reviewed")
        counts = history.payload["counts"]
        assert counts["maintenance_records"] >= 1
        assert counts["failure_modes_known"] == 7
        assert counts["last_inspection"]

    def test_root_cause_is_a_declared_failure_mode(self, svc):
        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        _decide(svc, out["incident"]["id"])
        [root] = _events(svc, "response.root_cause_identified")
        payload = root.payload
        eq = next(e for e in svc.runtime("refinery").engine.plant.equipment if e.id == "e-P-1042")
        assert payload["failure_mode"] in eq.failure_modes
        assert payload["failure_mode_declared"] is True
        assert payload["explanation"]

    def test_sensor_loss_reports_no_invented_mode(self, svc):
        out = svc.disable_sensor("refinery", "s-PT-1042A")
        _decide(svc, out["incident_id"])
        [root] = _events(svc, "response.root_cause_identified")
        assert root.payload["failure_mode"] is None
        assert root.payload["failure_mode_declared"] is False
        assert "PT-1042A" in root.payload["explanation"]

    def test_prediction_candidates_are_real_equipment(self, svc):
        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        _decide(svc, out["incident"]["id"])
        [prediction] = _events(svc, "response.prediction")
        plant_ids = {e.id for e in svc.runtime("refinery").engine.plant.equipment}
        assert prediction.payload["available"] is True
        assert 1 <= len(prediction.payload["candidates"]) <= 3
        for c in prediction.payload["candidates"]:
            assert c["equipment_id"] in plant_ids
            assert 0 < c["risk"] <= 1
            assert c["reasons"]

    def test_helper_matches_frontend_formula_shape(self, svc):
        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        engine = svc.runtime("refinery").engine
        incident = engine.incidents[out["incident"]["id"]]
        result = predict_next_failure(engine, incident)
        assert set(result) >= {"available", "candidates", "caveat"}

    def test_user_notification_summarises_real_fields(self, svc):
        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        _decide(svc, out["incident"]["id"])
        [notice] = _events(svc, "response.user_notified")
        summary = notice.payload["summary"]
        assert "P-1042" in summary
        assert "PT-1103" in summary  # the alternate actually chosen


class TestDepartmentResolution:
    def test_department_is_the_owning_area(self, svc):
        engine = svc.runtime("refinery").engine
        resolved = resolve_department(engine, "e-P-1042")
        assert resolved == {
            "department": "Crude Distillation",
            "department_source": "plant_area.name",
        }

    def test_unknown_equipment_falls_back_honestly(self, svc):
        resolved = resolve_department(svc.runtime("refinery").engine, "e-nope")
        assert resolved["department_source"] == "fallback"


class TestVerificationStillGated:
    def test_verified_event_only_after_decision(self, svc):
        out = svc.inject_failure("refinery", "e-P-1042", "sensor_failure")
        assert not _events(svc, "verification.completed")
        svc.decide("refinery", out["incident"]["id"], True)
        [verified] = _events(svc, "verification.completed")
        assert verified.payload["incident_id"] == out["incident"]["id"]
        assert verified.payload["ok"] is True
