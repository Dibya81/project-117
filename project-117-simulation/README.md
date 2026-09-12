# Project 117 — simulation data package

This is the data layer for the simulation demo: the committed SQL seed for
both prebuilt plants, plus JSON copies for the optional Vite workbench.

- `database/seed_plants.sql` — **source of truth** for the refinery and steel
  plant definitions and their scenarios. It is generated from the JSON dataset
  by `scripts/export_plant_sql.py` and applied automatically by
  `SimulationStore` (`backend/simulation/persistence.py`) on first run, so a
  fresh clone needs no JSON.
- `public/data/*.json` — a frozen JSON copy the Vite workbench loads directly
  without a DB round-trip. The backend does not read it.

The React app (canvas, node components, agent trace panel, WebSocket bridge)
is not in this package — build it with Claude Code using the prompt provided
in chat, which references this exact shape.
