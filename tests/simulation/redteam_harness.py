#!/usr/bin/env python3
"""RED-TEAM harness: drives the REAL SimulationService end-to-end.

No HTTP layer (fastapi unavailable offline), but every layer below the
router is the production code path: datasets -> engine -> fault injection
-> incident -> agent pipeline -> event bus -> approval -> action ->
verification -> artifact/audit.

Randomly selects assets (seeded) instead of the documented demo path.
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.simulation import datasets  # noqa: E402
from backend.simulation.service import SimulationService  # noqa: E402

OUT: dict = {"cases": [], "summary": {}}


def run_case(plant_id: str, eq_id: str, mode_id: str, approve: bool = True) -> dict:
    svc = SimulationService()
    plant = datasets.load_plant(plant_id)
    rt = svc.register(plant)
    svc.start(plant_id)
    for _ in range(5):
        svc.step(plant_id)
    pre = rt.engine.snapshot()
    seq_before = rt.seq

    res = svc.inject_failure(plant_id, eq_id, mode_id)
    inc_id = res["incident"]["id"]
    tasks = rt.incident_tasks[inc_id]
    plan = rt.incident_plans[inc_id]
    decision = svc.decide(plant_id, inc_id, approve)
    post = rt.engine.snapshot()

    ev_types = Counter(e.type for e in rt.events if e.seq > seq_before)
    # did real state change?
    changed_eq = [k for k in pre["equipment"] if pre["equipment"][k] != post["equipment"][k]]
    changed_sensors = [
        k
        for k in pre["sensors"]
        if pre["sensors"][k]["quality"] != post["sensors"][k]["quality"]
        or pre["sensors"][k]["failed"] != post["sensors"][k]["failed"]
    ]
    return {
        "plant": plant_id,
        "equipment": eq_id,
        "mode": mode_id,
        "incident": inc_id,
        "approved": approve,
        "agents": sorted({t.agent for t in tasks}),
        "tasks": len(tasks),
        "evidence": sum(len(t.evidence) for t in tasks),
        "tools": sum(len(t.tools) for t in tasks),
        "deps": sum(len(t.depends_on) for t in tasks),
        "affected": len(res["incident"]["affected"]),
        "action": plan.action,
        "verified": decision.get("verified"),
        "final_status": decision["status"],
        "findings": decision.get("findings", [])[:3],
        "artifacts": len(rt.artifacts),
        "events": dict(ev_types),
        "state_changed_equipment": changed_eq[:5],
        "state_changed_sensors": changed_sensors[:5],
    }


def pick(plant_id: str, n: int, seed: int):
    plant = datasets.load_plant(plant_id)
    rnd = random.Random(seed)
    sensor_cases, eq_cases = [], []
    eqs = [e for e in plant.equipment if e.failure_modes]
    modes = {m.id: m for m in plant.failure_modes}
    for e in rnd.sample(eqs, min(len(eqs), 40)):
        for fm in e.failure_modes:
            mech = modes[fm].mechanism
            if mech in ("sensor", "drift") and len(sensor_cases) < n:
                sensor_cases.append((e.id, fm))
            elif mech in ("stop", "degrade", "leak", "surge") and len(eq_cases) < n:
                eq_cases.append((e.id, fm))
    return sensor_cases, eq_cases


def main() -> int:
    for plant_id, seed in (("refinery", 11), ("steel", 22)):
        s_cases, e_cases = pick(plant_id, 5, seed)
        for eq, fm in s_cases + e_cases:
            try:
                OUT["cases"].append(run_case(plant_id, eq, fm))
            except Exception as exc:  # noqa: BLE001
                OUT["cases"].append(
                    {
                        "plant": plant_id,
                        "equipment": eq,
                        "mode": fm,
                        "ERROR": f"{type(exc).__name__}: {exc}",
                    }
                )

    # negative / failure-path tests
    neg = []
    svc = SimulationService()
    p = datasets.load_plant("refinery")
    svc.register(p)
    svc.start("refinery")
    for label, fn in (
        (
            "unknown_equipment",
            lambda: svc.inject_failure("refinery", "NOPE-999", p.failure_modes[0].id),
        ),
        ("unknown_mode", lambda: svc.inject_failure("refinery", p.equipment[0].id, "not-a-mode")),
        ("unknown_plant", lambda: svc.runtime("ghost")),
        ("unknown_incident_decision", lambda: svc.decide("refinery", "INC-0000", True)),
        ("duplicate_fault", None),
    ):
        if fn is None:
            continue
        try:
            fn()
            neg.append({"case": label, "raised": None, "result": "NO ERROR RAISED"})
        except Exception as exc:  # noqa: BLE001
            neg.append({"case": label, "raised": type(exc).__name__, "msg": str(exc)[:90]})

    # duplicate fault injection on the same asset
    eq0 = next(e for e in p.equipment if e.failure_modes)
    try:
        a = svc.inject_failure("refinery", eq0.id, eq0.failure_modes[0])
        b = svc.inject_failure("refinery", eq0.id, eq0.failure_modes[0])
        neg.append(
            {
                "case": "duplicate_fault",
                "first": a["incident"]["id"],
                "second": b["incident"]["id"],
                "distinct_incidents": a["incident"]["id"] != b["incident"]["id"],
            }
        )
    except Exception as exc:  # noqa: BLE001
        neg.append({"case": "duplicate_fault", "raised": type(exc).__name__, "msg": str(exc)[:90]})
    OUT["negative"] = neg

    # determinism check: same seed twice -> identical telemetry
    def run_ticks(seed: int):
        s = SimulationService()
        pl = datasets.load_plant("refinery")
        s.register(pl, seed=seed)
        s.start("refinery")
        return [s.step("refinery")["readings"] for _ in range(10)]

    OUT["determinism"] = {
        "same_seed_identical": run_ticks(117) == run_ticks(117),
        "diff_seed_differs": run_ticks(117) != run_ticks(999),
    }

    # SSE replay/subscribe check
    async def sse_check():
        s = SimulationService()
        pl = datasets.load_plant("refinery")
        s.register(pl)
        s.start("refinery")
        s.step("refinery")
        got = []
        agen = s.subscribe("refinery", after_seq=0)
        for _ in range(2):
            got.append((await agen.__anext__())["type"])
        return got

    OUT["sse_replay"] = asyncio.run(sse_check())

    ok = [c for c in OUT["cases"] if "ERROR" not in c]
    OUT["summary"] = {
        "cases_run": len(OUT["cases"]),
        "cases_errored": len(OUT["cases"]) - len(ok),
        "verified_true": sum(1 for c in ok if c.get("verified")),
        "verified_false": sum(1 for c in ok if c.get("verified") is False),
        "distinct_actions": sorted({json.dumps(c["action"]["kind"]) for c in ok}),
    }
    print(json.dumps(OUT, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
