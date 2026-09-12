"""Plant datasets are DB-first: seeding, DB-backed loading, and idempotence.

The JSON datasets were deleted, so these tests pin the new contract: a fresh
store seeds itself from the committed SQL, ``datasets`` reads the database, and
a second open never duplicates or clobbers what is already stored.
"""

from __future__ import annotations

import pytest
from backend.simulation import datasets
from backend.simulation.datasets import DatasetError
from backend.simulation.models import Plant
from backend.simulation.persistence import SimulationStore


@pytest.fixture()
def store(tmp_path):
    st = SimulationStore(tmp_path / "simulation.db")
    yield st
    st.close()


def test_empty_db_is_seeded(store: SimulationStore):
    ids = {p["id"] for p in store.list_saved_plants(origin="dataset")}
    assert ids == {"refinery", "steel"}
    assert len(store.load_scenarios("refinery")) == 14
    assert len(store.load_scenarios("steel")) == 14


def test_load_plant_from_db(store: SimulationStore):
    plant = datasets.load_plant("refinery", store=store)
    assert plant.id == "refinery"
    assert len(plant.equipment) == 58
    assert sum(len(e.sensors) for e in plant.equipment) == 224
    assert len(datasets.load_scenarios("steel", store=store)) == 14


def test_list_plants_counts_match_dataset(store: SimulationStore):
    by_id = {p["id"]: p for p in datasets.list_plants(store=store)}
    assert by_id["refinery"]["assets"] == 58
    assert by_id["refinery"]["sensors"] == 224
    assert by_id["refinery"]["scenarios"] == 14
    assert by_id["steel"]["assets"] == 55
    assert by_id["steel"]["sensors"] == 194
    assert by_id["steel"]["scenarios"] == 14


def test_unknown_plant_raises_dataset_error(store: SimulationStore):
    with pytest.raises(DatasetError, match="unknown plant dataset"):
        datasets.load_plant("no-such-plant", store=store)


def test_second_init_does_not_duplicate_or_clobber(tmp_path):
    path = tmp_path / "simulation.db"
    first = SimulationStore(path)
    # A builder plant must survive a re-open...
    builder = Plant(
        id="builder-x", name="Builder X", industry="custom",
        areas=[], equipment=[], connections=[], failure_modes=[],
    )
    first.save_plant(builder, origin="builder")
    # ...and re-registering a runtime-mutated dataset plant must not rewrite the
    # canonical seed definition (the engine mutates the in-memory Plant).
    mutated = first.load_plant_definition("refinery")
    mutated.name = "Should Not Persist"
    first.save_plant(mutated, origin="dataset")
    first.close()

    # Re-open: the non-empty plants table must skip re-seeding entirely.
    second = SimulationStore(path)
    try:
        assert second.load_plant_definition("refinery").name == "Meridian Synthetic Refinery"
        assert second.load_plant_dict("builder-x") is not None
        assert len(second.list_saved_plants()) == 3  # no duplicate seed rows
        assert len(second.load_scenarios("refinery")) == 14
    finally:
        second.close()
