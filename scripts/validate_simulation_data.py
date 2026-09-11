#!/usr/bin/env python3
"""Validate simulation datasets (§55).

Checks, per plant: unique ids/tags · sensor→equipment refs · connection
refs · area refs · failure-mode refs · threshold sanity
(min < nominal < max ladders) · scenario targets resolve · topology has no
orphan process equipment. Exit 1 with a report on any failure.

Usage: python3 scripts/validate_simulation_data.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data" / "simulation"


def fail(errors: list[str], msg: str) -> None:
    errors.append(msg)


def validate_plant(d: Path) -> list[str]:
    errors: list[str] = []
    plant = json.loads((d / "plant.json").read_text())
    areas = json.loads((d / "areas.json").read_text())
    equipment = json.loads((d / "equipment.json").read_text())
    connections = json.loads((d / "connections.json").read_text())
    modes = json.loads((d / "failure_modes.json").read_text())
    scenarios = json.loads((d / "scenarios.json").read_text())

    eq_ids = [e["id"] for e in equipment]
    if len(eq_ids) != len(set(eq_ids)):
        fail(errors, "duplicate equipment ids")
    eq_set = set(eq_ids)

    tags = [e["tag"] for e in equipment]
    sensor_tags = [s["tag"] for e in equipment for s in e["sensors"]]
    if len(tags) != len(set(tags)):
        fail(errors, "duplicate equipment tags")
    if len(sensor_tags) != len(set(sensor_tags)):
        fail(errors, "duplicate sensor tags")

    sensor_ids = [s["id"] for e in equipment for s in e["sensors"]]
    if len(sensor_ids) != len(set(sensor_ids)):
        fail(errors, "duplicate sensor ids")

    area_set = {a["id"] for a in areas}
    for e in equipment:
        if e["area_id"] not in area_set:
            fail(errors, f"{e['id']}: unknown area {e['area_id']}")
        for s in e["sensors"]:
            if s["equipment_id"] != e["id"]:
                fail(errors, f"sensor {s['id']} parent mismatch")
            if s.get("is_detector"):
                continue  # latched 0/1 detectors: envelope ladder does not apply
            if not (s["normal_min"] <= s["nominal"] <= s["normal_max"]):
                fail(errors, f"sensor {s['id']}: nominal outside normal envelope")
            if not (s["warning_min"] <= s["normal_min"] and s["normal_max"] <= s["warning_max"]):
                fail(errors, f"sensor {s['id']}: warning envelope inside normal")
            if not (s["critical_min"] <= s["warning_min"] and s["warning_max"] <= s["critical_max"]):
                fail(errors, f"sensor {s['id']}: critical envelope inside warning")

    mode_set = {m["id"] for m in modes}
    for e in equipment:
        for fm in e["failure_modes"]:
            if fm not in mode_set:
                fail(errors, f"{e['id']}: unknown failure mode {fm}")

    for c in connections:
        if c["source"] not in eq_set or c["target"] not in eq_set:
            fail(errors, f"connection {c['id']}: dangling endpoint")

    # topology: every process equipment should sit on at least one pipe or wire
    linked = {c["source"] for c in connections} | {c["target"] for c in connections}
    for e in equipment:
        if e["id"] not in linked:
            fail(errors, f"{e['id']} ({e['tag']}): orphan — no connections")

    for sc in scenarios:
        for st in sc["steps"]:
            if st["action"] == "inject_failure":
                if st["target"] not in eq_set:
                    fail(errors, f"scenario {sc['id']}: unknown target {st['target']}")
                if st["mode"] not in mode_set:
                    fail(errors, f"scenario {sc['id']}: unknown mode {st['mode']}")
                else:
                    tgt = next(e for e in equipment if e["id"] == st["target"])
                    if st["mode"] not in tgt["failure_modes"]:
                        fail(errors, f"scenario {sc['id']}: mode {st['mode']} not applicable to {tgt['tag']}")

    total = len(equipment) + len(sensor_ids)
    if total < 150:
        fail(errors, f"{plant['id']}: only {total} total assets (<150)")

    print(
        f"{plant['id']}: {len(equipment)} equipment · {len(sensor_ids)} sensors · "
        f"{len(connections)} connections · {len(areas)} areas · {len(scenarios)} scenarios · "
        f"{'OK' if not errors else f'{len(errors)} ERRORS'}"
    )
    return errors


def main() -> int:
    all_errors: list[str] = []
    for d in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        all_errors.extend(f"[{d.name}] {e}" for e in validate_plant(d))
    if all_errors:
        print("\nVALIDATION FAILED")
        for e in all_errors:
            print(" -", e)
        return 1
    print("\nALL DATASETS VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
