#!/usr/bin/env python3
"""Export the JSON datasets to the committed SQL seed.

This is a one-time (but repeatable) migration tool. It reads the pre-DB
dataset layout under ``data/simulation/<plant>/`` and writes a single
``project-117-simulation/database/seed_plants.sql`` containing the plant
definition and each scenario as an ``INSERT`` against the ``plants`` and
``scenarios`` tables defined in ``backend/simulation/persistence.py``.

Why: the SQLite store is the single source of truth. ``SimulationStore``
applies this file once on a fresh database, so a clone no longer needs the
JSON files at all. The generated file is committed; the JSON was deleted after
the export, so re-running this script requires restoring it first (e.g.
``git show HEAD:data/simulation/refinery/equipment.json``).

Usage: ./.venv/bin/python scripts/export_plant_sql.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "simulation"
OUTPUT = ROOT / "project-117-simulation" / "database" / "seed_plants.sql"

sys.path.insert(0, str(ROOT))
from backend.simulation.models import (  # noqa: E402  (path set up above)
    Connection,
    Equipment,
    FailureMode,
    Plant,
    PlantArea,
)


def _read(directory: Path, name: str) -> list[dict]:
    path = directory / name
    return json.loads(path.read_text()) if path.exists() else []


def load_plant(plant_id: str) -> Plant:
    """Build and validate a ``Plant`` straight from the JSON dataset.

    Deliberately independent of ``backend.simulation.datasets``: that module
    will read the database after this migration, so the exporter must keep its
    own JSON reader to stay runnable before the files are deleted.
    """
    directory = DATA_ROOT / plant_id
    meta = json.loads((directory / "plant.json").read_text())
    areas = [PlantArea(**a) for a in _read(directory, "areas.json")]
    equipment = [Equipment(**e) for e in _read(directory, "equipment.json")]
    connections = [Connection(**c) for c in _read(directory, "connections.json")]
    failure_modes = [FailureMode(**f) for f in _read(directory, "failure_modes.json")]

    # Repository-grade integrity check, same intent as the old loader: a seed
    # that cannot simulate is worse than no seed.
    eq_ids = {e.id for e in equipment}
    area_ids = {a.id for a in areas}
    mode_ids = {f.id for f in failure_modes}
    for e in equipment:
        if e.area_id not in area_ids:
            raise SystemExit(f"{plant_id}: equipment {e.id} in unknown area {e.area_id}")
        missing = [fm for fm in e.failure_modes if fm not in mode_ids]
        if missing:
            raise SystemExit(f"{plant_id}: equipment {e.id} references unknown modes {missing}")
    for c in connections:
        if c.source not in eq_ids or c.target not in eq_ids:
            raise SystemExit(f"{plant_id}: connection {c.id} has a dangling endpoint")

    return Plant(
        id=meta["id"],
        name=meta["name"],
        industry=meta.get("industry", "process"),
        areas=areas,
        equipment=equipment,
        connections=connections,
        failure_modes=failure_modes,
    )


def _literal(value: object) -> str:
    """Render a value as a SQLite literal, escaping single quotes."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def _insert(table: str, columns: list[str], values: list[object]) -> str:
    cols = ",".join(columns)
    rendered = ",".join(_literal(v) for v in values)
    return f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({rendered});"


def build_sql(plant_ids: list[str]) -> str:
    lines = [
        "-- Project 117 simulation plant seed — GENERATED, do not edit by hand.",
        "-- Regenerate with: ./.venv/bin/python scripts/export_plant_sql.py",
        "--",
        "-- Source of truth for the refinery/steel datasets. backend/simulation/",
        "-- persistence.py applies this on first run (empty `plants` table), so a",
        "-- fresh clone needs no JSON. INSERT OR IGNORE keeps re-runs idempotent and",
        "-- never overwrites a builder plant or a plant the operator saved.",
        "",
        "BEGIN;",
    ]
    for plant_id in plant_ids:
        plant = load_plant(plant_id)
        definition = json.dumps(plant.model_dump(), separators=(",", ":"))
        lines.append("")
        lines.append(f"-- {plant.id}: {plant.name}")
        lines.append(
            _insert(
                "plants",
                ["id", "name", "industry", "origin", "definition", "created_at", "updated_at"],
                [plant.id, plant.name, plant.industry, "dataset", definition, 0.0, 0.0],
            )
        )
        scenarios = _read(DATA_ROOT / plant_id, "scenarios.json")
        for scenario in scenarios:
            body = json.dumps(scenario, separators=(",", ":"))
            lines.append(
                _insert(
                    "scenarios",
                    ["plant_id", "id", "definition", "updated_at"],
                    [plant.id, scenario["id"], body, 0.0],
                )
            )
    lines.append("")
    lines.append("COMMIT;")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    if not DATA_ROOT.exists():
        print(f"no JSON datasets found under {DATA_ROOT} (restore them first)", file=sys.stderr)
        return 1
    plant_ids = sorted(
        d.name for d in DATA_ROOT.iterdir() if d.is_dir() and (d / "plant.json").exists()
    )
    if not plant_ids:
        print(f"no JSON datasets found under {DATA_ROOT}", file=sys.stderr)
        return 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build_sql(plant_ids))
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes) for {', '.join(plant_ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
