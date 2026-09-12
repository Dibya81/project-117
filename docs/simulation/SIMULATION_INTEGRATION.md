# Project 117 — Simulation Integration Guide

> Written so any engineer (or coding agent) can open the repo and understand
> exactly how the digital-twin simulation integrates with Project 117.

## 1. What this is

A **real, stateful industrial simulation environment** wired into the existing
multi-agent system. It is the primary demonstration environment for Project 117:

```
SIMULATED PLANT → TELEMETRY → EVENT → ORCHESTRATOR → AGENT PIPELINE
     → PLAN → APPROVAL → ACTION → PLANT STATE → VERIFY → ARTIFACT + AUDIT
```

Every stage is backed by code and state. Nothing is pre-recorded; the engine
is deterministic (seed 117): same seed + same faults = same plant behavior.

## 2. Where things live

```
backend/simulation/
├── models.py        # Pydantic domain contracts (mirrored in frontend TS)
├── engine.py        # tick loop · telemetry · propagation · alarms · incidents
├── agents.py        # deterministic multi-agent pipeline (task DAG + plan)
├── service.py       # lifecycle · event log (replayable) · agent orchestration
├── datasets.py      # DB-backed plant/scenario loader + validator
└── api.py           # /api/simulation/* + SSE stream

scripts/
└── validate_plant_data.py        # refs/envelopes/topology/scenarios from the DB

project-117-simulation/database/
└── seed_plants.sql   # committed seed: refinery 58/224/14 · steel 55/194/14
                        (equipment/sensors/scenarios), applied on first run

apps/web/src/
├── lib/sim/
│   ├── types.ts      # 1:1 TS mirror of backend/simulation/models.py
│   ├── engine.ts     # EMBEDDED DEMO ENGINE — same semantics, client-side
│   ├── adapter.ts    # live (SSE/REST) vs embedded transport selection
│   ├── store.ts      # React bridge: event ring buffer → 4 Hz projection
│   ├── custom.ts     # build-your-own factories (same sensors/failure modes)
│   └── symbols.tsx   # ORIGINAL industrial SVG symbol library (ISA-5.1-style)
├── components/sim/
│   ├── SchematicCanvas.tsx      # P&ID renderer: pan/zoom/minimap/states
│   └── AgentCommandCenter.tsx   # incident panel: agents/tools/evidence/DAG
└── app/console/simulation/
    ├── page.tsx                 # hub
    ├── plant/[id]/page.tsx      # twin screen (top/left/center/right/bottom)
    └── builder/page.tsx         # build-your-own canvas

tests/simulation/test_engine.py   # unit + integration (the §66 acceptance set)
docs/simulation/ASSET_SOURCES.md  # asset provenance (all ORIGINAL)
```

## 3. Running

```bash
# datasets come from the committed SQL seed (applied on first run); validate:
./.venv/bin/python scripts/validate_plant_data.py

# backend (serves /api/simulation/* with live engines at 1s ticks)
# run from the repository root: pyproject.toml/tests live there and
# backend.config resolves .env from the current working directory.
uv sync && uv run uvicorn backend.api.src.main:create_app --factory --port 8000

# frontend
cd apps/web && pnpm install && pnpm dev
#   console:  http://localhost:3017/console/simulation
#   live mode is the default (backend above); explicit in-browser engine:
#   NEXT_PUBLIC_DATA_MODE=mock pnpm dev
```

## 4. Engine semantics (backend/simulation/engine.py)

- **Tick**: `tick()` → propagate flow through pipe topology → read all sensors
  (noise + process factors + drift + mean reversion) → evaluate envelope alarms
  → emit one batched frame. One central tick; never per-sensor timers.
- **Process factors**: flow sensors read their machine's output × upstream
  delivery; pressures sag downstream of stopped/degraded sources; exchanger
  temperatures rise when flow is lost; vibration rises with wear faults.
- **Failure mechanisms**: `sensor` (quality=BAD, value frozen) · `drift`
  (reading walks ~2% of span/tick) · `degrade` (capacity factor) · `stop`
  (capacity=0) · `leak` (pipes leak, area detector trips) · `surge`.
- **§23 invariant**: a sensor failure never stops its equipment. The AI path
  exists precisely because the plant can't see itself anymore.
- **Alarms are projections** of live values against the envelope — cleared
  automatically when the envelope recovers.

## 5. Agent pipeline (backend/simulation/agents.py)

`build_pipeline(engine, incident, t0)` constructs the task DAG **from the
incident's actual topology** — no tag-specific logic:

```
orchestrator (classify)
 ├─ data_analysis (telemetry.query · graph.query · anomaly.detect)   ─┐
 ├─ maintenance   (maintenance_history.query · failure_mode.match)    │
 ├─ operations    (topology.impact)                depends: data      │
 ├─ safety        (policy_check)                   depends: data+mt   │
 ├─ documentation (retrieve_documents)                               │
 └─ orchestrator (synthesize plan)                 depends: all  ◄────┘
```

Records per task: tools used, evidence (with confidence), result, timing,
dependencies. `execute_plan` mutates the real engine; `verify_plan` fails
closed — any critical alarm or out-of-envelope sensor in the blast radius
keeps the incident open (status returns to `investigating`).

## 6. Events (§33)

All emitted on the per-plant log (durable, replayable, then live via SSE
`GET /api/simulation/plants/{id}/stream?after=<seq>`):

`simulation.started/paused` · `telemetry.batch` · `fault.injected` ·
`equipment.state_changed/disabled/removed` · `alarm.created/cleared` ·
`incident.created/updated/resolved` · `agent.task_started/task_completed` ·
`agent.tool_completed` · `agent.evidence_found` · `approval.required/granted/rejected` ·
`action.completed` · `verification.started/completed` · `artifact.created` · `audit.recorded`

## 7. API surface

| Endpoint | Purpose |
|---|---|
| `GET /api/simulation/plants` | dataset catalog (assets/sensors/scenarios counts) |
| `POST /plants/{id}/start` · `/pause` | lifecycle (cold-loads + registers on first start) |
| `GET /plants/{id}/snapshot` | full state for late joiners (includes plant def) |
| `GET /plants/{id}/stream` | SSE event stream (replay from `after`) |
| `POST /plants/{id}/equipment/{eq}/failure` | `{mode_id}` — inject |
| `POST /plants/{id}/equipment/{eq}/disable` · `/remove` | state/graph surgery |
| `GET /plants/{id}/incidents` · `/incidents/{iid}/tasks` | incident + task DAG + plan |
| `POST /plants/{id}/incidents/{iid}/decision` | `{approved}` — the human gate |
| `GET /plants/{id}/alarms` · `/artifacts` | projections + generated reports |

## 8. Frontend transport (`lib/sim/adapter.ts`)

`NEXT_PUBLIC_DATA_MODE=mock` (default) constructs the **embedded demo engine**
— a line-for-line TS port of the backend engine with the same seed math, run
in-browser so the demo works with zero infrastructure. `live` swaps to REST +
SSE against the real backend. The UI never branches on transport; it renders
events from a single adapter surface.

## 9. Extending

- **New equipment kind**: add to `EquipmentKind` (models.py + types.ts),
  a symbol in `lib/sim/symbols.tsx` (+ `KIND_SYMBOL`), a sensor template in
  the generator + `custom.ts`, failure modes in both FAILURE_MODES lists.
- **New failure mode**: add to `FAILURE_MODES` (generator + custom.ts) and a
  `mechanism` branch in both engines. The pipeline is generic — nothing else
  to touch.
- **New plant**: add it to `project-117-simulation/database/seed_plants.sql`
  (or save one from the builder canvas), then re-open a fresh store — seeding
  picks it up. Validate with `scripts/validate_plant_data.py`.
- **New scenario**: a row in the `scenarios` table for the plant — steps are
  `inject_failure` events at sim-time offsets.

## 10. Honest limits

- Physics is *engineering-plausible*, not CFD: capacity factors, sag/rise
  factors and envelopes are documented heuristics (engine.py docstrings).
- The health indicator (plant page, `plantHealth()`) is a SIMULATION HEALTH
  INDICATOR — deterministic demo heuristic, not a validated predictive model.
- Embedded mode exists for demos; live mode is the production path.
