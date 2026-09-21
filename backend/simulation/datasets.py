"""Dataset access + validation for synthetic plants.

The SQLite store (``backend/simulation/persistence.py``) is the source of
truth: the JSON files that used to live under ``data/simulation/<plant>/`` are
gone, and the refinery/steel datasets now arrive via the committed SQL seed
(``project-117-simulation/database/seed_plants.sql``). This module keeps the
same public surface (``list_plants``, ``load_plant``, ``load_scenarios``,
``DatasetError``) so API and service callers do not change.

Loading still validates every reference (sensors → equipment, connections →
equipment, failure modes), so broken topology fails loudly instead of
corrupting a demo.
"""

from __future__ import annotations

from backend.simulation.models import (
    Plant,
    Scenario,
)
from backend.simulation.persistence import SimulationStore, get_store


class DatasetError(ValueError):
    """Raised when a dataset is missing or fails validation."""


def list_plants(store: SimulationStore | None = None) -> list[dict]:
    """Dataset plants with the counts the console shows.

    Reads the stored definitions (counts are derived, never cached) and the
    scenarios table; only ``origin='dataset'`` plants are listed here — the
    API appends builder-saved plants separately.
    """
    st = store or get_store()
    out = []
    for meta in st.list_saved_plants(origin="dataset"):
        definition = st.load_plant_dict(meta["id"]) or {}
        equipment = definition.get("equipment", [])
        out.append(
            {
                "id": meta["id"],
                "name": meta["name"],
                "industry": meta.get("industry", "process"),
                "assets": len(equipment),
                "sensors": sum(len(e.get("sensors", [])) for e in equipment),
                "scenarios": len(st.load_scenarios(meta["id"])),
                "areas": len(definition.get("areas", [])),
            }
        )
    # Stable, human-sensible order regardless of SQLite's default row order.
    out.sort(key=lambda p: p["id"])
    return out


def _validate(plant: Plant) -> None:
    """Referential integrity of a rehydrated plant. Raises ``DatasetError``."""
    eq_ids = [e.id for e in plant.equipment]
    if len(eq_ids) != len(set(eq_ids)):
        raise DatasetError("duplicate equipment ids")
    eq_set = set(eq_ids)
    sensor_ids = [s.id for e in plant.equipment for s in e.sensors]
    if len(sensor_ids) != len(set(sensor_ids)):
        raise DatasetError("duplicate sensor ids")
    tags = [e.tag for e in plant.equipment] + [
        s.tag for s in (s for e in plant.equipment for s in e.sensors)
    ]
    if len(tags) != len(set(tags)):
        raise DatasetError("duplicate tags")
    area_set = {a.id for a in plant.areas}
    for e in plant.equipment:
        if e.area_id not in area_set:
            raise DatasetError(f"equipment {e.id} in unknown area {e.area_id}")
    for c in plant.connections:
        if c.source not in eq_set or c.target not in eq_set:
            raise DatasetError(f"connection {c.id} references unknown equipment")
    fm_set = {f.id for f in plant.failure_modes}
    for e in plant.equipment:
        for fm in e.failure_modes:
            if fm not in fm_set:
                raise DatasetError(f"equipment {e.id} references unknown failure mode {fm}")


def load_plant(plant_id: str, store: SimulationStore | None = None) -> Plant:
    """Rehydrate a dataset plant from the database, validating its references."""
    st = store or get_store()
    plant = st.load_plant_definition(plant_id)
    if plant is None:
        raise DatasetError(f"unknown plant dataset: {plant_id}")
    _validate(plant)
    return plant


def load_scenarios(plant_id: str, store: SimulationStore | None = None) -> list[Scenario]:
    """Typed scenarios for a plant; empty when the plant has none."""
    st = store or get_store()
    return [Scenario.model_validate(s) for s in st.load_scenarios(plant_id)]
