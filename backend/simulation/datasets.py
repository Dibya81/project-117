"""Dataset loading + validation for synthetic plants.

Datasets are canonical JSON under ``data/simulation/<plant>/``. They are the
source of truth — the engine never invents topology. Loading validates every
reference (sensors → equipment, connections → equipment, scenarios → modes),
so a broken dataset fails loudly at boot instead of corrupting a demo.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.simulation.models import Connection, Equipment, FailureMode, Plant, PlantArea, Scenario

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "simulation"


class DatasetError(ValueError):
    """Raised when a dataset is missing or fails validation."""


def list_plants(root: Path = DATA_ROOT) -> list[dict]:
    if not root.exists():
        return []
    out = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        pj = d / "plant.json"
        if pj.exists():
            meta = json.loads(pj.read_text())
            eq = json.loads((d / "equipment.json").read_text()) if (d / "equipment.json").exists() else []
            sc = json.loads((d / "scenarios.json").read_text()) if (d / "scenarios.json").exists() else []
            out.append({
                "id": meta["id"],
                "name": meta["name"],
                "industry": meta.get("industry", "process"),
                "assets": len(eq),
                "sensors": sum(len(e.get("sensors", [])) for e in eq),
                "scenarios": len(sc),
                "areas": len(json.loads((d / "areas.json").read_text())) if (d / "areas.json").exists() else 0,
            })
    return out


def _read(root: Path, name: str) -> list[dict]:
    p = root / name
    if not p.exists():
        raise DatasetError(f"missing {p}")
    return json.loads(p.read_text())


def load_plant(plant_id: str, root: Path = DATA_ROOT) -> Plant:
    d = root / plant_id
    if not d.exists():
        raise DatasetError(f"unknown plant dataset: {plant_id}")
    meta = json.loads((d / "plant.json").read_text())

    areas = [PlantArea(**a) for a in _read(d, "areas.json")]
    equipment = [Equipment(**e) for e in _read(d, "equipment.json")]
    connections = [Connection(**c) for c in _read(d, "connections.json")]
    failure_modes = [FailureMode(**f) for f in _read(d, "failure_modes.json")]

    # --- validation: unique ids, resolvable references, sane topology ---
    eq_ids = [e.id for e in equipment]
    if len(eq_ids) != len(set(eq_ids)):
        raise DatasetError("duplicate equipment ids")
    eq_set = set(eq_ids)
    sensor_ids = [s.id for e in equipment for s in e.sensors]
    if len(sensor_ids) != len(set(sensor_ids)):
        raise DatasetError("duplicate sensor ids")
    tags = [e.tag for e in equipment] + [s.tag for s in (s for e in equipment for s in e.sensors)]
    if len(tags) != len(set(tags)):
        raise DatasetError("duplicate tags")
    area_set = {a.id for a in areas}
    for e in equipment:
        if e.area_id not in area_set:
            raise DatasetError(f"equipment {e.id} in unknown area {e.area_id}")
    for c in connections:
        if c.source not in eq_set or c.target not in eq_set:
            raise DatasetError(f"connection {c.id} references unknown equipment")
    fm_set = {f.id for f in failure_modes}
    for e in equipment:
        for fm in e.failure_modes:
            if fm not in fm_set:
                raise DatasetError(f"equipment {e.id} references unknown failure mode {fm}")

    return Plant(
        id=meta["id"],
        name=meta["name"],
        industry=meta.get("industry", "process"),
        areas=areas,
        equipment=equipment,
        connections=connections,
        failure_modes=failure_modes,
    )


def load_scenarios(plant_id: str, root: Path = DATA_ROOT) -> list[Scenario]:
    d = root / plant_id
    p = d / "scenarios.json"
    if not p.exists():
        return []
    return [Scenario(**s) for s in json.loads(p.read_text())]
