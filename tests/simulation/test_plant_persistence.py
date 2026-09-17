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


# ---------------------------------------------------------------------------
# Builder connection records
#
# A connection is not just "A feeds B": the Builder records which PORTS the
# wire was made on and what the link MEANS. Both were dropped on save (the
# model had no such fields), so a plant reloaded from the database lost the
# distinction between a REDUNDANCY wire and a MATERIAL_FLOW pipe — the exact
# distinction the failover reasoning reads.
# ---------------------------------------------------------------------------


def test_builder_connection_keeps_ports_and_relation(tmp_path):
    from backend.simulation.models import (
        Connection,
        ConnectionKind,
        Equipment,
        PlantArea,
    )

    path = tmp_path / "simulation.db"
    st = SimulationStore(path)
    try:
        plant = Plant(
            id="builder-ports", name="Ports", industry="custom",
            areas=[PlantArea(id="a", name="A", x=0, y=0, w=400, h=300)],
            equipment=[
                Equipment(id="e-A", tag="A-1", name="A", kind="pump", area_id="a", x=0, y=0),
                Equipment(id="e-B", tag="B-1", name="B", kind="tank", area_id="a", x=100, y=0),
            ],
            connections=[
                Connection(
                    id="pl-c1", kind=ConnectionKind.PIPE, relation="REDUNDANCY",
                    source="e-A", target="e-B",
                    source_port="out", target_port="in", medium="process",
                ),
            ],
            failure_modes=[],
        )
        st.save_plant(plant, origin="builder")
    finally:
        st.close()

    reloaded = SimulationStore(path)
    try:
        back = reloaded.load_plant_definition("builder-ports")
        assert back is not None
        c = back.connections[0]
        assert (c.source, c.target) == ("e-A", "e-B")
        assert (c.source_port, c.target_port) == ("out", "in")
        assert c.relation == "REDUNDANCY"
        assert c.medium == "process"
    finally:
        reloaded.close()


def test_dataset_connections_default_to_out_and_in(store: SimulationStore):
    """Legacy rows carry no ports; the defaults are the direction they mean."""
    plant = datasets.load_plant("refinery", store=store)
    assert plant.connections
    for c in plant.connections:
        assert (c.source_port, c.target_port) == ("out", "in")


# ---------------------------------------------------------------------------
# Telemetry retention
#
# Nothing reads the telemetry table yet, but the engine writes to it every
# persisted tick. Retention existed as a method with no caller, so the table
# grew without bound — 742k rows and ~95 MB in the working database before this
# was wired up. These tests pin the bound.
# ---------------------------------------------------------------------------


def _readings(n: int) -> list[dict]:
    return [{"sensor_id": f"S{i}", "value": 1.0, "quality": "good"} for i in range(n)]


def test_telemetry_is_pruned_to_the_retained_window(store: SimulationStore):
    """The table must stay bounded, not shrink to nothing.

    Retention runs every _TELEMETRY_PRUNE_EVERY batches rather than on every
    insert, so the table legitimately overshoots the window by up to one
    interval of writes. The bound asserted here is that overshoot, not the
    window itself — asserting exactly TELEMETRY_RETAINED_ROWS would demand
    per-insert pruning and fail a correct implementation.
    """
    from backend.simulation.persistence import (
        _TELEMETRY_PRUNE_EVERY,
        TELEMETRY_RETAINED_ROWS,
    )

    batch = 100
    # Write well past the window the way the engine does, in batches.
    batches = (TELEMETRY_RETAINED_ROWS // batch) + _TELEMETRY_PRUNE_EVERY * 2
    for i in range(batches):
        store.record_telemetry("refinery", _readings(batch), float(i))

    rows = store._db.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0]
    bound = TELEMETRY_RETAINED_ROWS + (_TELEMETRY_PRUNE_EVERY - 1) * batch
    assert rows <= bound, f"telemetry holds {rows} rows, above the {bound} bound"
    # A live sink must still be receiving writes after pruning.
    assert rows >= TELEMETRY_RETAINED_ROWS - batch, (
        f"retention trimmed too far: {rows} rows against a {TELEMETRY_RETAINED_ROWS} window"
    )


def test_prune_telemetry_keeps_the_newest_readings(store: SimulationStore):
    for i in range(4):
        store.record_telemetry("refinery", _readings(100), float(i))
    store.prune_telemetry("refinery", keep=150)

    rows = store._db.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0]
    assert rows == 150
    newest = store._db.execute("SELECT MAX(sim_t) FROM telemetry").fetchone()[0]
    assert newest == 3.0, "pruning dropped the most recent readings"


def test_prune_is_per_plant(store: SimulationStore):
    """One plant's retention must not delete another's readings."""
    for _ in range(3):
        store.record_telemetry("refinery", _readings(200), 1.0)
        store.record_telemetry("steel", _readings(200), 1.0)
    store.prune_telemetry("refinery", keep=100)

    by_plant = dict(
        store._db.execute("SELECT plant_id, COUNT(*) FROM telemetry GROUP BY plant_id").fetchall()
    )
    assert by_plant["refinery"] == 100
    assert by_plant["steel"] == 600
