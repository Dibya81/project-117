# Project 117 — simulation data package

This is the data layer for the simulation demo: the committed SQL seed for
both prebuilt plants, plus JSON copies for the optional Vite workbench.

- `database/seed_plants.sql` — **source of truth** for the refinery and steel
  plant definitions and their scenarios. It is generated from the JSON dataset
  by `scripts/export_plant_sql.py` and applied automatically by
  `SimulationStore` (`backend/simulation/persistence.py`) on first run, so a
  fresh clone needs no JSON. The source JSON under `data/simulation/` was
  deleted after the export, so re-running the generator requires restoring it
  first (the script names the `git show` command).
- `public/data/*.json` — a frozen JSON copy the Vite workbench loads directly
  without a DB round-trip. The backend does not read it.

The React workbench (canvas, node components, agent trace panel, WebSocket
bridge) is not in this package — it ships at `frontend/` and serves
`public/` as its Vite `publicDir`. See `INTEGRATION.md` for the data contract.
