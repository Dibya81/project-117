# Project 117 — simulation data package

This is the data layer for the simulation demo: the SQL schema, seed data,
and JSON exports for both prebuilt plants. It's deterministic (seed=117) —
re-run `database/generate_seed.py` any time you want to regenerate or extend it.

- `database/schema.sql` — SQLite schema (zones, equipment, sensors, connections,
  plus runtime tables for fault events and the agent trace).
- `database/seed_oil_refinery.sql`, `database/seed_iron_steel_plant.sql` —
  generated INSERT statements. 101 and 104 equipment respectively.
- `public/data/oil_refinery.json`, `public/data/iron_steel_plant.json` —
  the same data as JSON, for the frontend to load directly without a DB round-trip.
- `database/generate_seed.py` — single source of truth. Edit the `PLANTS` list
  to add zones/equipment counts, then re-run.

The React app (canvas, node components, agent trace panel, WebSocket bridge)
is not in this package — build it with Claude Code using the prompt provided
in chat, which references this exact schema and JSON shape.
