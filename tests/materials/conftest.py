"""Shared fixtures for the materials domain tests.

The store is built over a temporary SQLite file and seeded with the real
generator, so every test exercises the same code path a deployment does — no
hand-built rows that could drift from what the seed actually produces.

Seeding is ~2 seconds, so it happens once per session and each test works against
a copy of the resulting file. That keeps the suite fast without letting one test's
writes leak into another's assertions.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest
from backend.materials.seed import seed_materials
from backend.storage.materials import MaterialsStore

#: A fixed anchor so "days of cover" and forecast dates are reproducible.
ANCHOR = date(2026, 9, 14)


@pytest.fixture(scope="session")
def seeded_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One seeded database, shared read-only as the template for every test."""
    path = tmp_path_factory.mktemp("materials-seed") / "template.db"
    store = MaterialsStore(path)
    store.clear()
    seed_materials(store, today=ANCHOR, price_days=365, production_days=180)
    store.close()
    return path


@pytest.fixture()
def store(seeded_template: Path, tmp_path: Path) -> MaterialsStore:
    """A private copy of the seeded database, with the writes disconnected."""
    copy = tmp_path / "materials.db"
    shutil.copyfile(seeded_template, copy)
    st = MaterialsStore(copy)
    yield st
    st.close()


@pytest.fixture()
def empty_store(tmp_path: Path) -> MaterialsStore:
    """An empty store, for the refusal and insufficient-data paths."""
    st = MaterialsStore(tmp_path / "empty.db")
    yield st
    st.close()


@pytest.fixture()
def anchor() -> date:
    return ANCHOR
