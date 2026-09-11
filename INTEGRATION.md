# INTEGRATION.md

How the Project 117 simulation frontend (`frontend/`) talks to the data package
(`project-117-simulation/`) and to the existing Project 117 orchestrator
(`backend/`).

- [1. What runs where](#1-what-runs-where)
- [2. Data shape contracts](#2-data-shape-contracts)
- [3. Data source switching](#3-data-source-switching)
- [4. WebSocket event contract](#4-websocket-event-contract)
- [5. Where each event belongs in the existing backend](#5-where-each-event-belongs-in-the-existing-backend)
- [6. Pointing the frontend at the orchestrator](#6-pointing-the-frontend-at-the-orchestrator)
- [7. Run it](#7-run-it)
- [8. Known data observations](#8-known-data-observations)

---

## 1. What runs where

```
project-117-simulation/          data package (generated, deterministic, seed=117)
  database/schema.sql            SQLite schema — the authority on field names
  database/generate_seed.py      single source of truth; edit + re-run
  public/data/*.json             same rows as JSON
  public/plants.json             manifest added for the hub page

frontend/                        Vite + React + TS workbench
  src/data/service.ts            reads JSON or SQLite-backed API, one shape out
  src/sim/layout.ts              zone-grid layout (no hand-placed coordinates)
  src/sim/validate.ts            BFS/DFS circuit validation
  src/store/simStore.ts          canvas + plant state
  src/ws/orchestrator.ts         the WebSocket bridge

backend/                         existing Project 117 service (FastAPI)
  jobs/bus.py                    JobEventBus — already the event fan-out
  jobs/service.py                JobService — already the state machine
  verification/verifier.py       Verifier.verify()
  deliverables/service.py        ArtifactService
```

The frontend never writes plant data. It reads a plant, lets a user change
*canvas* state (drag, wire, drop, disable), and sends one message to the
orchestrator when a fault is injected. Everything the trace panel shows after
that came off the wire.

---

## 2. Data shape contracts

Source of truth: `project-117-simulation/database/schema.sql`. The JSON export
is the same rows with two differences, both normalised on load by
`src/data/service.ts`:

| SQL | JSON | Handling |
| --- | --- | --- |
| `connections.source_id` / `target_id` | `connections.source` / `target` | accepted either way |
| `failure_modes` TEXT (comma-separated) | `failure_modes` string[] | accepted either way |
| — | `equipment.age_years` | used if present, else recomputed from `install_date` |

```ts
Zone       { id, name, sequence }
Equipment  { id, tag, type, zone_id, install_date, expected_lifespan_years,
             age_years, last_inspection, status, failure_modes[] }
Sensor     { id, equipment_id, tag, type, label, unit,
             normal_min, normal_max, current_value }
Connection { id, source, target, kind: "pipe" | "wire" }
Plant      { plant_id, plant_name, zones[], equipment[], sensors[], connections[] }
```

`Equipment.type` is one of the 13 the schema comment lists. `Sensor.type` is
one of `PT | TT | FT | LT | VT`. `status` is
`normal | warning | critical | disabled`. The builder palette only offers these
values, so a dropped node is always a valid row.

`kind: "pipe"` is process flow; `kind: "wire"` is signal. In the seed, every
wire runs sensor → equipment (`wire count == sensor count`), which is the
invariant the canvas enforces and `validateCircuit` checks.

### Sensor thresholds

The dataset gives `normal_min`/`normal_max` but no separate warning and alarm
bands. `src/sim/thresholds.ts` derives them from the band width rather than
inventing absolutes: up to 10% of the band width outside normal is a warning,
beyond that is critical. A 0–1 bar transmitter and a 0–250 °C transmitter then
escalate on comparable terms. Change `WARN_FRACTION` there to retune.

---

## 3. Data source switching

```bash
VITE_DATA_SOURCE=json      # default — read public/data/*.json directly
VITE_DATA_SOURCE=backend   # GET {VITE_API_BASE}/plants/{id}
VITE_API_BASE=http://127.0.0.1:8000
```

`backend` mode expects `GET /plants/{id}` to return exactly the `Plant` JSON
above. To serve it from the schema:

```sql
SELECT * FROM zones      WHERE plant_id = :id ORDER BY sequence;
SELECT * FROM equipment  WHERE plant_id = :id;
SELECT * FROM sensors    WHERE equipment_id IN (SELECT id FROM equipment WHERE plant_id = :id);
SELECT * FROM connections WHERE plant_id = :id;
```

There is deliberately **no fallback** from `backend` to `json`. If the API is
down you get a visible error, not a demo that quietly reads stale JSON while
claiming to be live.

---

## 4. WebSocket event contract

One socket. No socket.io, no polling. Envelope is always
`{ "type": "<event>", "job_id": "...", ... }`.

### 4.1 Frontend → orchestrator

Emitted when a user picks a fault type from a node's context menu.

```json
{
  "type": "fault.injected",
  "plant_id": "refinery",
  "equipment_id": "refinery-CL-101",
  "fault_type": "sensor_drift",
  "sensor_snapshot": [
    { "id": "refinery-CL-101-SEN1", "equipment_id": "refinery-CL-101",
      "tag": "LT-CL-1011", "type": "LT", "label": "level", "unit": "%",
      "normal_min": 10, "normal_max": 95, "current_value": 96.4 }
  ]
}
```

- `fault_type` ∈ `disabled | removed | sensor_drift | leak` — the four values
  the schema allows for `fault_events.fault_type`. The UI does not invent
  names the column would reject.
- `sensor_snapshot` is the **post-fault** reading of every sensor attached to
  that unit. The store is mutated first and the snapshot is taken from the
  result, so the orchestrator reasons about the state the operator can see.

### 4.2 Orchestrator → frontend

| `type` | Required fields | Rendered as |
| --- | --- | --- |
| `job.created` | `job_id` (+ optional `equipment_id`) | Plan column, "Job created". Sets the active job. |
| `agent.started` | `job_id`, `agent` (+ optional `label`, `detail`) | Plan column, agent row |
| `tool.completed` | `job_id`, `tool` (+ optional `agent`, `related_equipment_id`) | Execution column, tool row |
| `verification.completed` | `job_id`, `passed` (bool) | Execution column, verification row |
| `artifact.created` | `job_id`, `filename`, `url` | Execution column **and** a download link |

Optional on any event: `label`, `detail`, `at` (ISO-8601; server time is used
if omitted).

```json
{ "type": "agent.started", "job_id": "job-91", "agent": "maintenance",
  "label": "Maintenance agent", "detail": "Reading C-3 service history" }

{ "type": "verification.completed", "job_id": "job-91", "passed": true,
  "related_equipment_id": "refinery-CL-101" }

{ "type": "artifact.created", "job_id": "job-91",
  "filename": "incident-report.pdf", "url": "/api/artifacts/art-7/download",
  "artifact_id": "art-7" }
```

**`related_equipment_id` is what drives the canvas.** When an event carries it,
that node starts the trace glow and every edge touching it animates. That is
the only wiring between the event stream and the canvas — no client-side
guessing about which node a job concerns.

### 4.3 What the frontend does *not* do

- It does not advance the trace on a timer. In live mode the list grows only
  when a frame arrives. A stage with no event shows `WAITING`, it is not faked.
- It does not synthesise an `artifact.created`. Artifact links come from the
  payload's `url`.

### 4.4 Mock mode

Attempts are capped at 3 with backoff (0.7s / 1.6s / 3.2s). If all three fail,
or `VITE_ORCHESTRATOR_WS_URL` is unset, the app enters **MOCK MODE**:

- the connection chip reads `MOCK MODE` in red,
- a striped banner sits at the top of the trace panel with the reason,
- every scripted row is individually tagged `mock`,
- the scripted sequence is deliberately generic placeholder text, not a
  plausible-looking investigation result.

The fallback exists so the UI can be developed offline. It is built to be
unmistakable on purpose.

---

## 5. Where each event belongs in the existing backend

The backend already has the fan-out and the state machine. What it does **not**
have is a WebSocket transport — today it streams over SSE at
`GET /api/jobs/{id}/stream`, fed by `JobEventBus`. So integration is two pieces
of work: forward the bus over WS, and publish the four events the frontend
listens for.

### 5.1 The transport

`backend/jobs/bus.py` — `JobEventBus.publish(job_id, event)` is already called
on every job state change, and `JobEventBus.subscribe(job_id)` already returns
an `asyncio.Queue`. Two supported routes:

**Option A — add a WS endpoint that forwards the bus (recommended).**
New module `backend/api/src/routes/simulation_ws.py`:

```python
@router.websocket("/ws/simulation")
async def simulation_ws(ws: WebSocket, bus: JobEventBus = Depends(get_job_bus)):
    await ws.accept()
    job_id: str | None = None
    try:
        while True:
            msg = await ws.receive_json()          # {type: "fault.injected", ...}
            if msg.get("type") != "fault.injected":
                continue
            job_id = await orchestrator.start_simulation_fault(msg)
            await ws.send_json({"type": "job.created", "job_id": job_id})
            queue = bus.subscribe(job_id)
            while True:
                event = await queue.get()
                await ws.send_json(event)          # already the right shape
    except WebSocketDisconnect:
        pass
    finally:
        if job_id:
            bus.unsubscribe(job_id, queue)
```

Register it in `backend/api/src/main.py` next to the other routers
(`app.include_router(simulation_api.router)` around line 395).

**Option B — point the frontend at an SSE→WS shim** if you would rather not
touch the backend. Not recommended: it puts a second service in the path for
no capability gain.

### 5.2 The events

| Frontend event | Emit from | How |
| --- | --- | --- |
| `job.created` | `backend/jobs/service.py` → `JobService.create()` | Already publishes a created event at line ~172 via `self._publish(...)`. Alias its `kind` to `job.created`. |
| `agent.started` | `backend/orchestrator/src/` at the point a specialist is dispatched | Call `JobService.progress(job_id, ...)` or `bus.publish` with `{type: "agent.started", agent, label}`. |
| `tool.completed` | `backend/tools/` at tool return, and `backend/agents/` after a tool call resolves | Publish `{type: "tool.completed", tool, related_equipment_id}`. Set `related_equipment_id` to the unit under investigation — that is what lights the canvas. |
| `verification.completed` | `backend/verification/verifier.py` → `Verifier.verify()` on return | Publish `{type: "verification.completed", passed: report.passed}`. |
| `artifact.created` | `backend/deliverables/service.py` → `ArtifactService` after a write | Publish `{type: "artifact.created", filename, url, artifact_id}` where `url` is the existing download route (`/api/artifacts/{id}/download`). |

`JobService.transition()` (line ~246) already publishes on every state change,
so reusing its `_publish` path keeps the SSE stream and the WebSocket in sync
rather than creating a second, divergent source of events.

### 5.3 Fault handling

The existing work-order / incident path already models exactly this shape:
an event creates a job, agents investigate, verification runs, an artifact is
produced, and a human approves. `fault.injected` should enter at the same
door — create a job, attach `equipment_id` to it, and let the existing
orchestrator decide which agents to dispatch. Nothing about the frontend
assumes a specific agent set.

---

## 6. Pointing the frontend at the orchestrator

```bash
cd frontend
cp .env.example .env
# then set:
# VITE_ORCHESTRATOR_WS_URL=ws://127.0.0.1:8000/ws/simulation
npm run dev
```

Vite reads `.env` from `frontend/`. The URL is used verbatim — there is no dev
proxy in `vite.config.ts`, so whatever you put here is the socket the browser
opens.

To confirm you are live rather than in mock mode: the chip in the top right
reads `orchestrator live` in green. If it reads `MOCK MODE`, the connection
failed and the trace panel will tell you why.

---

## 7. Run it

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
npm run build        # tsc -b && vite build
npm run typecheck
```

Regenerating the plant data (edit `PLANTS` in `generate_seed.py` first):

```bash
python3 project-117-simulation/database/generate_seed.py
```

The frontend serves `project-117-simulation/public` directly as its
`publicDir`, so regenerated JSON appears with no copy step.

---

## 8. Known data observations

These are properties of the provided dataset, reported rather than papered
over. The frontend renders them faithfully.

**1. Equipment `status` and sensor readings are independent axes.**
`generate_seed.py` derives `status` from age against expected life
(`ratio > 0.95` → warning, `> 1.05` → critical), while every sensor's
`current_value` is generated inside its own normal band
(`random.uniform(lo, hi)`). The result is that the refinery has 23 units marked
`critical` and 6 `warning`, but **0 of 137 sensors out of band**.

So "critical" in the Equipment Register means *past design life*, not *in
alarm*. The canvas shows this without ambiguity because the plant page prints
both counts side by side, and the info drawer labels a non-normal status with
its basis (`from age — 17.8y of 20y expected life`, or `from injected fault`
when you injected one). If you want the two axes to agree, publish out-of-band
readings on the critical units in `make_sensor`.

**2. Wire count equals sensor count in both plants** (137 wires / 137 refinery
sensors), so every instrument is already attached to its unit. `validateCircuit`
reports zero orphans on both prebuilt plants.

**3. `plants.json` is the one file added to the data package.** The hub page
needs a manifest; it did not exist. Nothing else in
`project-117-simulation/` was modified, and re-running `generate_seed.py`
reproduces the JSON byte-for-byte apart from `plants.json`, which the generator
does not write.
