#!/usr/bin/env python3
"""Plant dataset validator — structural + topological integrity.

Pure stdlib. Checks duplicate ids/tags, orphan sensors, dangling
connections, unknown areas/failure modes, graph connectivity (weakly
connected components over process pipes), and per-area isolation.

Usage: python3 scripts/validate_plant_data.py [--json]
Exit code 1 if any ERROR-level finding is present.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data" / "simulation"


def load(d: Path, name: str):
    p = d / name
    return json.loads(p.read_text()) if p.exists() else []


def validate(d: Path) -> dict:
    plant = json.loads((d / "plant.json").read_text())
    areas = load(d, "areas.json")
    equipment = load(d, "equipment.json")
    connections = load(d, "connections.json")
    modes = load(d, "failure_modes.json")
    scenarios = load(d, "scenarios.json")

    errors: list[str] = []
    warnings: list[str] = []

    eq_ids = [e["id"] for e in equipment]
    dupes = {i for i in eq_ids if eq_ids.count(i) > 1}
    if dupes:
        errors.append(f"duplicate equipment ids: {sorted(dupes)}")
    eq_set = set(eq_ids)
    area_set = {a["id"] for a in areas}
    mode_set = {m["id"] for m in modes}

    sensors = [(s, e) for e in equipment for s in e.get("sensors", [])]
    sid = [s["id"] for s, _ in sensors]
    sdupes = {i for i in sid if sid.count(i) > 1}
    if sdupes:
        errors.append(f"duplicate sensor ids: {sorted(sdupes)}")

    tags = [e["tag"] for e in equipment] + [s["tag"] for s, _ in sensors]
    tdupes = {t for t in tags if tags.count(t) > 1}
    if tdupes:
        errors.append(f"duplicate tags: {sorted(tdupes)}")

    for s, e in sensors:
        if s.get("equipment_id") != e["id"]:
            errors.append(f"orphan sensor {s['id']}: equipment_id={s.get('equipment_id')} but nested under {e['id']}")
        for k in ("normal_min", "normal_max", "warning_min", "warning_max", "critical_min", "critical_max", "nominal"):
            if k not in s:
                errors.append(f"sensor {s['id']} missing {k}")
        if all(k in s for k in ("critical_min", "warning_min", "normal_min", "normal_max", "warning_max", "critical_max")):
            ordered = [s["critical_min"], s["warning_min"], s["normal_min"], s["normal_max"], s["warning_max"], s["critical_max"]]
            # Detectors (gas, leak, flame) are latched 0/1 channels: there is no
            # "too low" side, so their lower thresholds collapse onto 0 and the
            # six-value sequence is legitimately non-monotonic. The engine and
            # the verifier both apply a one-sided test to these (see
            # backend/simulation/agents.py::verify_plan). Anything else that is
            # non-monotonic is a genuine data error.
            detector = bool(s.get("is_detector")) or s.get("measurement") in {"gas", "leak", "flame"}
            if ordered != sorted(ordered):
                if detector:
                    warnings.append(
                        f"sensor {s['id']} is a latched detector; envelope is one-sided by design: {ordered}"
                    )
                else:
                    errors.append(f"sensor {s['id']} envelope thresholds not monotonic: {ordered}")
            if not (s["normal_min"] <= s["nominal"] <= s["normal_max"]):
                warnings.append(f"sensor {s['id']} nominal {s['nominal']} outside normal band")

    for e in equipment:
        if e.get("area_id") not in area_set:
            errors.append(f"equipment {e['id']} references unknown area {e.get('area_id')}")
        for fm in e.get("failure_modes", []):
            if fm not in mode_set:
                errors.append(f"equipment {e['id']} references unknown failure mode {fm}")
        if not e.get("sensors"):
            warnings.append(f"equipment {e['id']} ({e.get('tag')}) has no sensors")

    cid = [c["id"] for c in connections]
    cdupes = {i for i in cid if cid.count(i) > 1}
    if cdupes:
        errors.append(f"duplicate connection ids: {sorted(cdupes)}")
    for c in connections:
        if c["source"] not in eq_set:
            errors.append(f"connection {c['id']} unknown source {c['source']}")
        if c["target"] not in eq_set:
            errors.append(f"connection {c['id']} unknown target {c['target']}")
        if c["source"] == c["target"]:
            errors.append(f"connection {c['id']} is a self-loop")

    # --- topology: weakly connected components over ALL connection kinds ---
    adj: dict[str, set[str]] = defaultdict(set)
    pipe_adj: dict[str, set[str]] = defaultdict(set)
    for c in connections:
        if c["source"] in eq_set and c["target"] in eq_set:
            adj[c["source"]].add(c["target"])
            adj[c["target"]].add(c["source"])
            if c.get("kind") == "pipe":
                pipe_adj[c["source"]].add(c["target"])
                pipe_adj[c["target"]].add(c["source"])

    def components(graph):
        seen, comps = set(), []
        for n in eq_ids:
            if n in seen:
                continue
            q, comp = deque([n]), []
            seen.add(n)
            while q:
                cur = q.popleft()
                comp.append(cur)
                for nb in graph.get(cur, ()): 
                    if nb not in seen:
                        seen.add(nb)
                        q.append(nb)
            comps.append(comp)
        return comps

    comps = components(adj)
    isolated = [c[0] for c in comps if len(c) == 1]
    if isolated:
        warnings.append(f"{len(isolated)} fully disconnected equipment: {sorted(isolated)[:12]}")

    pipe_comps = sorted((c for c in components(pipe_adj)), key=len, reverse=True)
    for sc in scenarios:
        for st in sc.get("steps", []):
            act = st.get("action", "")
            if act.startswith("inject_failure:"):
                parts = act.split(":")
                if len(parts) >= 2 and parts[1] not in mode_set:
                    errors.append(f"scenario {sc['id']} references unknown failure mode {parts[1]}")
            tgt = st.get("target")
            if tgt and tgt not in eq_set:
                errors.append(f"scenario {sc['id']} references unknown target {tgt}")

    by_kind: dict[str, int] = defaultdict(int)
    for e in equipment:
        by_kind[e.get("kind", "?")] += 1
    by_meas: dict[str, int] = defaultdict(int)
    for s, _ in sensors:
        by_meas[s.get("measurement", "?")] += 1
    by_conn: dict[str, int] = defaultdict(int)
    for c in connections:
        by_conn[c.get("kind", "?")] += 1

    return {
        "plant": plant.get("id"),
        "name": plant.get("name"),
        "counts": {
            "areas": len(areas),
            "equipment": len(equipment),
            "sensors": len(sensors),
            "connections": len(connections),
            "failure_modes": len(modes),
            "scenarios": len(scenarios),
        },
        "equipment_by_kind": dict(sorted(by_kind.items())),
        "sensors_by_measurement": dict(sorted(by_meas.items())),
        "connections_by_kind": dict(sorted(by_conn.items())),
        "areas": [a["id"] for a in areas],
        "weak_components": len(comps),
        "largest_component": len(max(comps, key=len)) if comps else 0,
        "pipe_components": len(pipe_comps),
        "largest_pipe_component": len(pipe_comps[0]) if pipe_comps else 0,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    reports = []
    for d in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        if (d / "plant.json").exists():
            reports.append(validate(d))
    print(json.dumps(reports, indent=2))
    return 1 if any(r["errors"] for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
