"""Regression tests for the two verification defects found in the red-team audit.

Runnable two ways:
  * pytest tests/simulation/test_verification_regression.py
  * python3 tests/simulation/test_verification_regression.py   (stdlib fallback)

Defect 1 (BLOCKER): verify_plan() applied the two-sided critical envelope test
to latched 0/1 gas/leak detectors. A healthy detector reads 0.0, which is
<= critical_min (0.5), so EVERY untripped detector inside the blast radius
produced a permanent "beyond critical envelope" finding. 10 of 20 randomized
fault cases could never reach RESOLVED.

Defect 2 (BLOCKER): restore_equipment() cleared the leaking flag on pipes but
never reset the latched detector the leak had tripped, so every `leak`
failure mode failed verification forever.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.simulation import datasets  # noqa: E402
from backend.simulation.service import SimulationService  # noqa: E402


def _run(plant_id: str, equipment_id: str, mode_id: str) -> dict:
    svc = SimulationService()
    plant = datasets.load_plant(plant_id)
    rt = svc.register(plant)
    svc.start(plant_id)
    for _ in range(5):
        svc.step(plant_id)
    res = svc.inject_failure(plant_id, equipment_id, mode_id)
    decision = svc.decide(plant_id, res["incident"]["id"], True)
    decision["artifacts"] = len(rt.artifacts)
    decision["events"] = [e.type for e in rt.events]
    return decision


def test_untripped_detectors_do_not_block_verification() -> None:
    """Defect 1: a sensor failure whose blast radius contains gas detectors
    must still verify."""
    d = _run("steel", "e-P-2033", "sensor_failure")
    assert d["verified"] is True, d["findings"]
    assert d["status"] == "resolved"
    assert not any("GD-" in f and "beyond critical envelope" in f for f in d["findings"])


def test_leak_repair_resets_latched_detector() -> None:
    """Defect 2: after restore_equipment the tripped detector must clear."""
    d = _run("steel", "e-P-2033", "seal_leak")
    assert d["verified"] is True, d["findings"]
    assert d["status"] == "resolved"


def test_tripped_detector_still_fails_verification() -> None:
    """Guard against over-correcting: a genuinely tripped detector must still
    fail verification (no fake success)."""
    svc = SimulationService()
    plant = datasets.load_plant("steel")
    rt = svc.register(plant)
    svc.start("steel")
    svc.step("steel")
    res = svc.inject_failure("steel", "e-P-2033", "seal_leak")
    inc = rt.engine.incidents[res["incident"]["id"]]
    # force a detector inside the scope to stay tripped by re-tripping it
    from backend.simulation.agents import verify_plan

    det = next(sid for sid, m in rt.engine.sensor_model.items() if m.is_detector)
    rt.engine.sensors[det].value = 1.0
    inc.affected = list({*inc.affected, rt.engine.sensor_model[det].equipment_id})
    ok, findings = verify_plan(rt.engine, inc)
    assert ok is False
    assert any("detector tripped" in f for f in findings)


def test_full_incident_lifecycle_emits_the_documented_event_sequence() -> None:
    d = _run("refinery", "e-P-1171", "sensor_failure")
    required = {
        "fault.injected",
        "incident.created",
        "agent.task_started",
        "agent.tool_completed",
        "agent.evidence_found",
        "agent.task_completed",
        "approval.required",
        "approval.granted",
        "action.completed",
        "verification.started",
        "verification.completed",
        "artifact.created",
        "incident.resolved",
        "audit.recorded",
    }
    missing = required - set(d["events"])
    assert not missing, f"missing events: {sorted(missing)}"
    assert d["artifacts"] == 1


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{failures} failure(s)")
    sys.exit(1 if failures else 0)
