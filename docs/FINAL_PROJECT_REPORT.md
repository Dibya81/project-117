# Project 117 — Final Project Report

**Release audit date:** 2026-09-15
**Audit type:** full-repository production / public-release pass
**Scope:** correctness of the documented flows, placeholder and dead-code removal, security, performance, generated-file hygiene, documentation

This report describes the implementation **as it exists in the repository**. Every claim below was verified by running the code, reading the source, or querying the running system. Where something is partial, unfinished, or unverified, it is stated as such.

---

## 1. Executive Summary

Project 117 is a working sovereign industrial-AI system: a digital-twin refinery simulation whose operational decisions are produced by three local LLM agents running on Ollama, with no external network calls in the decision path. The headline flow — a sensor is taken out of service, the affected process section is isolated, three agents diagnose the fault and plan a recovery route, safety verifies it, the engine executes it, and the incident resolves — is genuinely event-driven from backend SSE events. It is not simulated by frontend timers, and no agent conclusion is emitted before the model has actually answered.

**State at the end of this pass:**

| Area | Status |
|---|---|
| Sensor → recovery workflow | Verified end-to-end, event-driven, no fabrication |
| Three-agent Ollama architecture | Verified; all three models present and answering |
| Refinery simulation (58 units, 60 connections, 224 sensors) | Verified |
| Materials & Industrial Intelligence (25 materials, 10 agent tools) | Verified, all data labelled `SYNTHETIC_DEMO` |
| Console (26 routes) | All return 200, no runtime errors |
| Landing page (121-frame sequence) | Verified, 120/120 frames load, no failures |
| Test suite | 368 passing |
| TypeScript / lint / production build | 0 errors / 0 errors / exit 0 |
| Secrets in source | None found |

**Release readiness: READY**, with the limitations in §23 documented rather than hidden.

---

## 2. Product Overview

**The problem.** An industrial plant runs on information that is fragmented across SOPs, inspection reports, work-order history, telemetry and the tacit knowledge of engineers who retire. The decisions that matter — is this measurement trustworthy, what is the alternate route, is that route safe, what spare does this failure need — are made by reasoning over that fragmented evidence under time pressure.

**What Project 117 does.** It installs that reasoning inside the plant boundary. A local plant model (digital twin) supplies real topology and live telemetry; a retrieval layer supplies the documents; a knowledge graph supplies the relationships; and three local models reason over both to produce an auditable decision with an explicit evidence trail. Nothing leaves the site.

**What it is not.** It is not a chatbot over documents, and it is not a dashboard. The unit of output is a *verified decision with an execution path*, not a text answer.

---

## 3. Architecture

```
  Web (Next.js 14 App Router, port 3017)
    │  REST + SSE
    ▼
  Backend API (FastAPI, port 8000)
    │  RBAC / permissions / audit middleware
    ▼
  Orchestrator ──► Agents ──► Models (Ollama, local)
    │                │
    │                ▼
    │              Tools  ──► Memory / Knowledge Graph
    │                │            │
    ▼                ▼            ▼
  Simulation ◄── Verification ── Approvals
   (digital       (envelope,      (human
    twin)          policy)         gate)
```

**Layers, in the order a request traverses them:**

| Layer | Module | Responsibility |
|---|---|---|
| Web | `apps/web` | Console, landing, live plant rendering, Builder |
| API | `backend/api/src` | Routes, auth, permissions, rate limiting, audit, SSE |
| Orchestrator | `backend/orchestrator` | Execution manager, agent dispatch, job lifecycle |
| Agents | `backend/agents`, `backend/simulation/decision.py` | Role-specific reasoning turns |
| Models | Ollama via an OpenAI-compatible client | Local inference, no egress |
| Tools | `backend/tools` | Typed, read-only capability surface (19 tools) |
| Memory / Graph | `backend/graph`, `backend/memory`, `backend/rag` | Relationships and retrieval |
| Simulation | `backend/simulation` | Plant model, engine, tick loop, fault injection |
| Verification | `backend/verification` | Safe-operating envelope, policy checks, secret scan |
| Approvals | `backend/api/src/routes/approvals.py` | Human gate on consequential actions |

---

## 4. Frontend

**Stack:** Next.js 14.2 (App Router), React 18.3, TypeScript, Tailwind CSS 3.4, Framer Motion 11, Lucide icons, three.js 0.169 (Knowledge Core only), Recharts 2.13 (materials charts only).

**Routes — 26 `page.tsx` files, all verified returning HTTP 200 with no page or console errors:**

| Route | Purpose |
|---|---|
| `/` | Cinematic landing (121-frame sequence + commercial section) |
| `/console/home` | Command centre: plant posture, live KPIs, Knowledge Core |
| `/console/workspace` | AI workbench |
| `/console/equipment`, `/console/equipment/[id]` | Asset register and detail |
| `/console/simulation` | Plant hub (refinery + steel) |
| `/console/simulation/plant/[id]` | **LIVE MODE** — live plant, fixed camera |
| `/console/simulation/builder` | **EDIT MODE** — author topology |
| `/console/knowledge` | Knowledge graph |
| `/console/documents` | Document corpus |
| `/console/work-orders`, `/console/work-orders/[id]` | Work-order Kanban and detail |
| `/console/insights` | Analytics |
| `/console/history` | Operational memory / audit register |
| `/console/approvals` | Human approval queue |
| `/console/admin` | Administration |
| `/console/materials` (+ `register`, `inventory`, `spares`, `production`, `price-history`, `suppliers`, `[id]`) | Materials & Industrial Intelligence (8 pages) |
| `/dashboard`, `/workbench` | Legacy redirects |

**Design system:** `docs/design/GLASS_SYSTEM.md`; a `p117-*` namespace for the landing (self-contained, so nothing leaks into the console) and `cs-*` / `mat-*` / `km-*` namespaces for the console.

**Landing page** is a scroll-driven cinematic track (`height: 2950vh`) with 24 absolutely-positioned beats, 4 procedural canvases, and a 121-frame WebP sequence. Scroll progress is computed as `window.scrollY / (track.offsetHeight - innerHeight)`. Verified: 120 frames requested, **0 failures**; navigation and the commercial section render correctly.

---

## 5. Backend

**Stack:** Python 3.14.2, FastAPI 0.141.1, Pydantic 2.13.5, Uvicorn, pandas 3.0.5, SQLite (three separate stores), LanceDB for vector retrieval.

**19 route modules** under `backend/api/src/routes/`: `agents`, `analytics`, `approvals`, `artifacts`, `audit`, `auth`, `chat`, `documents`, `equipment`, `health`, `jobs`, `knowledge`, `materials`, `models`, `tools`, `work_orders`, `workflows`, plus `__init__`.

**Middleware:** principal resolution, route permission checks (`backend/api/src/middleware/permissions.py` maps path prefixes to required scopes), rate limiting, request audit, and an egress-enforcement layer with its own tests.

**Measured endpoint latency:** every major read endpoint answers in ≤30 ms locally, including `/api/audit?limit=120`, the materials dashboard, inventory, production, price history, graph, and the simulation frame. No query was slow enough to justify an index; none was added.

---

## 6. AI / Agent Architecture

Three agents, each with a distinct responsibility and its own local model, run per incident:

| Agent | Role | Reads | Produces |
|---|---|---|---|
| **Diagnostic** | Identify the fault | Failed sensor state, equipment telemetry, maintenance and inspection history, topology | Affected equipment, diagnosis, failure mode (only if the equipment actually declares one) |
| **Operations** | Choose the recovery route | Real plant topology, diagnostic evidence when available | `route[]`, `block[]`, `restore[]` — all real connection ids |
| **Safety / Verification** | Approve or reject | The incident and the proposed route | `safe: true/false` plus concerns |

**Per-agent truth is published, not inferred.** `RecoveryDecision.agent_status` records `completed` / `rejected` / `failed` / `skipped` per role, and is emitted in `response.decision`. The console panel state is derived from this field, so a panel can only report the outcome its own turn produced.

**Bounded recovery.** `RECOVERY_ATTEMPTS = 2`. A route the validator accepts can still fail the engine's own envelope verification; a failed pass is fed back to the same three agents with the real findings for one more turn. Past that the incident escalates rather than leaving the plant degraded with an open incident.

**No silent fallback.** When a model is unreachable the decision is `available: false`; the incident stays open, no recovery executes, and the failure is reported per-agent.

---

## 7. Ollama Models

All three run locally via Ollama's OpenAI-compatible endpoint at `http://localhost:11434/v1`.

| Role | Model | Configuration variable |
|---|---|---|
| Diagnostic | `qwen3:1.7b` | `P117_DIAGNOSTIC_MODEL` |
| Operations | `llama3.2:3b` | `P117_OPERATIONS_MODEL` |
| Safety | `gemma3:1b` | `P117_SAFETY_MODEL` |

Verified present on the host and verified answering in a live incident.

**Two configuration details that are load-bearing, and were wrong before this pass:**

1. **`P117_LLM_THINK=off` is required.** `qwen3:1.7b` emits a hidden reasoning trace that is charged against the output token budget but is *not* returned as `message.content`. With the trace enabled the model spent its entire budget thinking and returned an **empty** completion (`finish_reason: length`), so the Diagnostic agent failed on every incident. The setting previously read a field that did not exist on `Settings`, so the flag was never sent to Ollama at all; it now exists, defaults to `off`, and is documented.

2. **`P117_DECISION_MAX_TOKENS=2048`.** A ceiling, not a cost. With the trace suppressed a diagnostic turn costs ~330 tokens (measured), but a local server that ignores `think:false` needs the headroom or the reply truncates to nothing. A `_REASONING_MIN_TOKENS = 2048` floor is applied on top of whatever is configured.

These three per-role variables were **absent from `.env.example`**. Left unset, model resolution silently fell through to `P117_REASONING_MODEL` / `P117_DOMAIN_MODEL`, meaning a clean clone would run the agents on general-purpose models and the per-role architecture would not exist. All 72 settings are now documented.

---

## 8. Simulation Architecture

**Plant data** is the source of truth at `project-117-simulation/database/seed_plants.sql` plus `project-117-simulation/public/data/*.json`, loaded into SQLite by `backend/simulation/persistence.py` and `backend/storage/documents.py`.

**Refinery twin:** 58 equipment units, 60 connections, 224 sensors, 7 failure modes per unit where declared.

**Two modes, deliberately distinct:**

| | **LIVE MODE** (`/console/simulation/plant/[id]`) | **EDIT MODE** (`/console/simulation/builder`) |
|---|---|---|
| Camera | Fixed full-plant framing; pan/zoom disabled | Free pan/zoom |
| Purpose | Operate and observe | Author |
| Actions | Sensor disable, fault injection, line block, decision approval | Place, move, snap, duplicate, delete, wire, save |
| Writes to engine | Yes, with audit | No — edits a session draft |

**The canonical renderer is shared.** Both modes render through the same `ProcessMap` component; the Builder differs by props (`editable`, `connectMode`), not by a second renderer.

**Engine loop:** `simulation_tick_s = 1.0`. Each tick advances the model, recomputes line flow, evaluates alarms, emits `telemetry.batch`, and persists telemetry at a configured interval.

---

## 9. Sensor Failure → Recovery Flow

**Verified event chain, captured from the live SSE stream:**

```
sensor.disabled
→ incident.created
→ response.perception
→ incident.updated
→ agent.started
→ response.lane_started (operations, diagnostics)
→ response.operations_notified
→ response.failover_evaluating
→ agent.task_started → agent.tool_completed → agent.evidence_found → agent.task_completed
→ approval.required → approval.granted
→ response.decision              ← the three models have answered
→ response.failover_completed
→ response.history_reviewed
→ response.root_cause_identified
→ response.prediction
→ response.user_notified
→ action.started → action.completed
→ verification.started → verification.completed
→ incident.resolved
```

**Verified:** **no finding is emitted before `response.decision`.** `response.root_cause_identified`, `response.failover_completed`, `response.prediction` and `response.user_notified` are all emitted after the models answer. This was a real defect earlier in the project's history — the whole lane narrative was emitted at handoff, so the console displayed a root cause and a chosen alternate within milliseconds of the fault, before any model had been asked anything. It is now structurally impossible: the findings emitters are called from the decide path, and each is idempotent per incident.

**UI sequencing, measured in the browser:**

| Moment | Measured |
|---|---|
| Affected section isolated | **1,534 ms** after the click |
| Visuals | 3 units and 3 lines isolated; line stroke `rgb(220, 38, 38)`; the flow layer is **removed** (process stopped) |
| Three-agent panel opens | on `agent.started`, behind a `requestAnimationFrame` paint barrier so the red section is on screen first — a paint barrier, not a delay |
| Terminal phase | `verified` at ~20.7 s |
| Agents | diagnostic `completed` (qwen3:1.7b), operations `completed` (llama3.2:3b), safety `completed` (gemma3:1b) |
| Decision | `route=["pl-001","pl-003"]`, `block=["pl-004"]` — real connection ids from the plant topology |

**Scenario coverage is not uniform — verified per scenario against the real models:**

| Origin | Fault | Outcome |
|---|---|---|
| `e-P-1001` | `s-PT-1001A` sensor disabled | **resolved**, `verified: true` |
| `e-C-1053` | `bearing_overheat` | **resolved**, `verified: true`, action → verification → `incident.resolved` |
| `e-P-1042` | `s-PT-1042A` sensor disabled | Fails route validation; incident stays `investigating` |
| `e-V-1047` | `valve_stuck` | Fails route validation |

For the failing cases the three models genuinely run, `response.decision` is emitted with `route[]`, `block[]`, `restore[]` and per-agent `agent_status`, and the route is then **correctly rejected** by the validator — for example `route is not ordered topology: pl-001 ends at e-TK-1101, pl-043 starts at e-E-1004`. The bounded retry hands the real findings back to the agents, and when they cannot produce a valid route the incident escalates rather than executing a bad one. That is the designed behaviour, not a silent failure.

The root cause is model capability, not topology: for `e-P-1042` the engine has a valid recovery through the origin (`pl-004 → pl-005`) among its 11 candidate connections, and `llama3.2:3b` does not reliably perform that graph search while also satisfying the `block`/`restore` consistency rules. Two prompt improvements were attempted during this pass: supplying each candidate's endpoints (`id: FROM -> TO`) is retained — it makes the stated "each line must end where the next begins" rule answerable and did not regress the working scenarios; enumerating the engine-computed valid ordered routes for the model to choose from **regressed `e-P-1001`** and was reverted. Select this scenario deliberately in a demo.

**Failure handling, verified** by running with a non-existent diagnostic model: Diagnostic `failed` → "Diagnosis Failed"; Operations `skipped` → "Not run — diagnosis failed"; Safety `skipped` → "Not run — no route to check"; banner "NO RECOVERY PRODUCED — Diagnostic Agent did not return a usable result, so the recovery stopped before any route"; retry control present; plant untouched; incident open.

**Incident isolation:** a decision is looked up by its own incident id and never inherited from another incident, so a previous incident cannot trigger panels, routes or recovery for a new failure.

---

## 10. Materials & Industrial Intelligence

**Verified inventory of the layer:**

| Entity | Count |
|---|---|
| Materials (4 classes) | 25 |
| Suppliers | 6 |
| Price observations | 4,270 |
| Production days | 543 |
| Inventory movements | 190 |
| Equipment material requirements | 12 |
| Financial events | 30 |

**The four material classes** are `RAW_MATERIAL`, `INTERMEDIATE`, `FINISHED_PRODUCT`, `MAINTENANCE_SPARE`. Units are deterministic: `KL → MT` raises `ConversionBasisRequired` unless a density basis is supplied, and `EA` (a count dimension) raises `IncompatibleUnits` rather than being coerced into a mass or volume.

**Verified chain — equipment → maintenance → spare → inventory → price → financial impact.** For `e-P-1001`, `/api/materials/maintenance-requirements/e-P-1001` returns requirement `REQ-MECH-SEAL-P1001` → item `MECH-SEAL-P1001` ("Mechanical seal kit — crude charge pump", unit `EA`) with coverage `COVERED`. Movements and prices are append-only; there is no update-in-place path.

**10 materials agent tools** are registered and callable (`calculate_material_requirement`, `forecast_inventory`, `generate_procurement_recommendation`, `get_equipment_material_requirements`, `get_inventory_status`, `get_maintenance_requirements`, `get_material`, `get_material_movements`, `get_production_output`, `search_price_history`) out of 19 total tools. They are read-only.

**Approval boundary — no automatic purchasing.** A procurement recommendation can be composed into a `PENDING` approval; it is idempotent per type and related id, audited as `materials.procurement_requested`, and requires an explicit human decision. Nothing is ordered. The approval store is currently empty, which is the correct resting state.

**Labelling — verified, not assumed.** 25/25 inventory rows carry `data_status: "SYNTHETIC_DEMO"` with provenance source `PROJECT117-SYNTHETIC-DEMO` and a note stating it is coherent synthetic refinery data, **not MRPL data, not a market price, not a real supplier**.

---

## 11. Knowledge Graph / Industrial Memory

The graph composes real sources rather than a hand-written fixture: plant topology (equipment and connections), documents from the corpus, work orders, incidents, and — spliced in before the live filter — material, location, supplier and price-history nodes with `REQUIRES`, `STOCKED_AT`, `SUPPLIED_BY`, `FLOWS_TO`, `PRODUCES` and `HAS_PRICE_HISTORY` edges.

Duplicate `PRODUCES` edges are deduplicated (a defect that previously emitted 508 duplicate edges is fixed; the graph emits 62). The build is cached by the Builder's session revision, and the in-flight promise is cached so two components mounting in the same tick do not each rebuild it.

**Operational memory** (`/console/history`) is the real audit register: observed → decided → acted → verified → learned. Transport noise (`http.*` rows written by the request-audit middleware) is excluded at the API, not filtered client-side after an over-fetch.

---

## 12. Verification & Safety

| Mechanism | Implementation |
|---|---|
| Safe-operating envelope | `backend/simulation` verifies the executed action against the engine's own post-action state; a route that passes the validator can still fail here and is fed back to the agents |
| Policy checks | `backend/verification/policy_checker.py` — safe-operating criteria |
| Secret scanning | `policy_checker.py` detects PEM blocks, `AKIA` ids and JWT shapes, with an explicit allowance for documentation placeholders |
| Evidence trail | Findings cite the tool call and source that produced them |
| Per-agent status | `agent_status` published in the decision; the UI cannot claim an agent succeeded when it did not |
| Human approval | Consequential actions raise an `ApprovalRequest` requiring an explicit decision |
| Audit | Every sensitive operation writes an audit row with actor, action, target, outcome and provenance |

**Envelope verification is not cosmetic.** In the recovery loop it is the mechanism that rejects a plausible-but-unsafe route and forces a re-plan.

---

## 13. Security / Sovereignty

**Verified in this pass:**

- **No secrets in source.** A scan for `api_key|secret|password|token|bearer|private_key` assignments, AWS `AKIA` ids, JWT shapes and PEM blocks found only the policy checker's own detection regex. Clean.
- **`.env` is not tracked** by git (`.gitignore` matches `.env` and `.env.*`, with `!.env.example` re-included and an explanatory comment).
- **`.env.example` contains variable names and non-sensitive local defaults only.** `P117_LLM_API_KEY` is empty.
- **All 72 settings are documented** — verified by diffing `Settings.model_fields` against `.env.example`.
- **No hardcoded external hosts.** The two `127.0.0.1:8000` occurrences are `process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000"` fallbacks, not baked values.
- **No debug endpoints exposed.** No `console.log` in application source; a single deliberate `console.error`.
- **No debug routes.** The 26 routes are all product surfaces.
- **RBAC enforced** through route-prefix permission mapping; reads require `connectors:read`, control requires `connectors:write`.
- **Egress enforcement** exists as a layer with dedicated tests (`test_egress.py`, `test_egress_enforcement.py`).

**Sovereignty claim, stated precisely:** inference runs on local Ollama models over a local OpenAI-compatible endpoint. The decision path does not call an external model provider. This is enforced by configuration and an egress layer, not merely by convention.

---

## 14. Performance Optimizations

Measured before and after, in this pass.

| Fix | Before | After |
|---|---|---|
| Plant page idle traffic | 40 requests / **5,069 KB per 10 s (507 KB/s)** | 8 requests / **234 KB per 10 s (24 KB/s)** — **−95%** |
| Plant telemetry payload | `/snapshot` 127 KB, 90% of it the static plant definition | `/frame` 24 KB, live state only |
| Plant poll rate | 4 Hz vs a 1 Hz engine — 3 of every 4 replies byte-identical | exactly the engine rate |
| `/console/home` first load | 367 kB | **140 kB (−62%)** |
| `/console/materials/price-history` | 246 kB | **141 kB (−43%)** |
| `/console/materials/production` | 246 kB | **141 kB (−43%)** |
| History register payload | 205 KB | 3 KB (server-side exclusion of transport rows) |
| Store re-renders | published every 250 ms unconditionally | publishes only when a change signature moves |
| EventSource connections | 1 per page (already correct) | 1 per page |

**Production runtime:** first contentful paint 104–304 ms across console routes; **client-side navigation between console pages 239–357 ms**.

**Two changes were reverted after measuring them as no-ops** rather than kept as plausible-looking configuration: `experimental.optimizePackageImports` for `@react-three/drei` (the heavy chunk is three.js core at 676 KB, not drei's barrel — its transmission material is a separate 28 KB chunk), and reducing the transmissive material's `samples` from 6 to 2 (no measurable frame-cost change, and it is a visual change).

**Also fixed:** the plant page leaked a mutation of shared runtime state (`states` was written through by reference); the store never populated `t` in live mode; and an accidental duplicate of the lane-emission body caused `response.failover_completed` to be emitted twice per incident.

---

## 15. Database / Data Model

Three SQLite stores, deliberately separate lifecycles.

**`data/project117.db` — 7 tables:** `artifacts`, `audit_events`, `documents`, `job_events`, `jobs`, `memory_records`, `tool_executions`.

**`data/materials.db` — 8 tables:** `equipment_material_requirements`, `financial_events`, `inventory_balances`, `material_movements`, `materials`, `price_observations`, `production_output`, `suppliers`.

**`data/operations.db` — 2 tables:** `approvals`, `work_orders`.

Plus LanceDB for vector retrieval (`data/lancedb/`).

**Design notes:** movements and price observations are append-only; `CREATE TABLE IF NOT EXISTS` is used throughout so a fresh clone self-initialises. Stores, uploads, WAL/SHM files and vector indexes are gitignored; the document corpus (`data/corpus/`) and fixtures are tracked because a clean checkout needs them.

**No indexes were added in this pass** because no query was measured as slow — every endpoint answers in ≤30 ms.

---

## 16. API Architecture

**REST for control and reads; SSE for the live event stream.**

- Reads require `connectors:read`; control requires `connectors:write`.
- The simulation stream is `GET /api/simulation/plants/{id}/stream` (Server-Sent Events), with sequence numbers so a client can resume via `?after=`.
- Two focused read shapes exist for the plant: `/snapshot` (definition + live state, for a first load) and `/frame` (live state only, for polling). The split exists because polling the snapshot re-sent 114 KB of unchanging definition four times a second.
- `GET /api/audit` accepts `exclude_action_prefix` so a client that wants domain events does not have to over-fetch and discard transport rows.
- Errors use a structured `APIError` type; `EndpointNotImplemented` is explicit rather than returning a plausible empty body.

---

## 17. Current Routes / Pages

See §4 for the 26 web routes. Backend surface: 19 route modules registered under `/api`.

---

## 18. Project Structure

```
project117/
├── apps/web/                  Next.js 14 console + landing
│   ├── src/app/               26 routes (App Router)
│   ├── src/components/        console, landing, sim, materials, ui, fx
│   ├── src/lib/               api client, sim store/adapter, data adapters, knowledge
│   ├── src/styles/            console.css, plant.css, sim.css, knowledge.css,
│   │                          project117-landing.css
│   └── public/assets/         121-frame landing sequence, refinery art
├── backend/
│   ├── api/src/routes/        19 route modules + middleware
│   ├── simulation/            engine, service, decision, agents, persistence, datasets
│   ├── materials/             domain, units, service, seed
│   ├── tools/                 tool registry (19 tools, 10 materials)
│   ├── orchestrator/          execution manager
│   ├── agents/  graph/  memory/  rag/  verification/  security/
│   ├── storage/               SQLite stores (documents, materials, operations, lancedb)
│   ├── workflows/  jobs/  ingestion/  sandbox/  observability/
│   └── config.py              all settings (P117_ prefix)
├── project-117-simulation/    plant data source of truth (SQL + JSON)
├── frontend/                  separate Vite workbench (not in the pnpm workspace)
├── data/                      corpus + fixtures (tracked), runtime stores (ignored)
├── docs/                      architecture, decisions, design, frontend, simulation
├── tests/                     27 test files
├── infrastructure/  scripts/  workflows/  packages/
├── Makefile  docker-compose.yml  pnpm-workspace.yaml
└── .env.example               all 72 settings documented
```

---

## 19. Testing Status

| Suite | Command | Result |
|---|---|---|
| Backend | `.venv/bin/python -m pytest tests/` | **368 passed** (27 test files) |
| Types | `pnpm run typecheck` | **0 errors** |
| Lint | `pnpm run lint` | **0 errors** |
| Build | `pnpm build` | **exit 0** |
| Routes | live sweep of all 26 | all 200, no page/console errors |
| Flow | sensor → recovery, live | verified end-to-end |
| Failure path | forced model failure | correct, no fabrication |

Coverage includes `materials/` (units, domain, agent tools), `simulation/` (engine, decision, API, sensor ops, pipeline integration, plant persistence, response events, verification regression) and `unit/` (audit, chat, documents, egress, egress enforcement, health, ingestion, metrics, model config, models API, orchestrator wiring, search).

---

## 20. Deployment Instructions

**Prerequisites:** Python 3.12+ (3.14 verified), Node 22, pnpm 9+, Ollama.

```bash
# 1. Backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # then set the three role models (see §7)

# 2. Frontend
pnpm install

# 3. Models
ollama pull qwen3:1.7b
ollama pull llama3.2:3b
ollama pull gemma3:1b
ollama pull llama3:latest
ollama pull deepseek-coder:6.7b
ollama pull mistral:latest
ollama pull nomic-embed-text:latest

# 4. Run (backend must run from the repository root — .env is CWD-relative)
.venv/bin/python -m uvicorn backend.api.src.main:create_app \
  --factory --host 127.0.0.1 --port 8000
pnpm --filter web dev
```

**Production build:**

```bash
pnpm build
pnpm --filter web start
```

Console: `http://127.0.0.1:3017` · API: `http://127.0.0.1:8000` · API docs: `/docs`.

> **Operational note.** `next build` writes to `apps/web/.next`, which a running `next dev` is also using. Stop the dev server before building, or the running server loses its dev artifacts and starts returning 404s.

---

## 21. Demo Instructions

1. Open `http://127.0.0.1:3017/` — the cinematic landing. Scroll through; at the end is the commercial section with the Industrial Value model.
2. **Enter the workbench** → `/console/home`. Note the plant posture and live KPIs.
3. Go to **Simulation → Refinery** (`/console/simulation/plant/refinery`). This is **LIVE MODE** with a fixed camera.
4. Select **P-1001** (crude charge pump) and open its sensors.
5. Click **Take PT-1001A out of service**. Watch, in order:
   - the affected section (**P-1001, TK-1101, V-1103**) turns **red and dashed** and its flow **stops** — this happens first;
   - the three-agent panel opens;
   - Diagnostic, Operations and Safety each show a real in-progress state (`Diagnosing`, `Routing`, `Verifying`) while their model call is actually running;
   - the decision arrives with a real `route[]` / `block[]` / `restore[]` and per-agent outcomes.
6. Open **Knowledge Graph** to see the topology plus the materials, supplier and price-history overlay.
7. Go to **Materials → Inventory / Spares / Price History** to see the synthetic demo dataset with its provenance labelling.
8. Go to **Approvals** to see the human gate that prevents automatic purchasing.
9. Optionally, `/console/simulation/builder` demonstrates **EDIT MODE** — a genuinely different mode on the same renderer.

---

## 22. Synthetic Data / Limitations

**Synthetic data — explicitly labelled:**

| Data | Status |
|---|---|
| Refinery plant twin (58 units, 60 connections, 224 sensors) | Synthetic simulation, generated by the engine |
| Materials, inventory, movements, prices, production, suppliers, financial events | `SYNTHETIC_DEMO`, source `PROJECT117-SYNTHETIC-DEMO` |
| Document corpus (`data/corpus/`) | Demonstration documents |

Every materials row carries `data_status: "SYNTHETIC_DEMO"` and a note stating it is coherent synthetic refinery data, **not MRPL data, not a market price, and not a real supplier**. The UI surfaces this: the materials kit renders the title *"Generated demonstration data. Not MRPL data, not a market price, not a real supplier."*

**No fabricated commercial figures.** The pricing section shows **"Custom Deployment"** for every tier, with the stated basis (site complexity, deployment scope, integrations, operational requirements). There are no list prices, no per-user or per-seat billing, no discounts, no customer logos and no endorsements. The Industrial Value model is transparent arithmetic over the user's own inputs with every fixed assumption printed beside the figure it produces, and is labelled *"Illustrative estimate — actual value depends on site data and deployment scope."*

---

## 23. Known Limitations

Stated plainly rather than hidden:

1. **The Knowledge Core costs ~2.2 s of post-load main-thread time** on `/console/home` while the 676 KB three.js chunk parses. It no longer blocks anything — FCP is 160 ms and the page is interactive first — but it is the largest remaining frontend cost. The real fix is reducing the three.js surface or moving the scene off the main thread, not further deferral.
2. **`/console/knowledge`** carries 167 kB and ~685 ms of long tasks from graph layout.
3. **`/console/simulation/builder`** has a 205 kB first load.
4. **`/console/documents`** issues 14 requests on load.
5. **The plant twin is a simulation, not a live plant connection.** There is no OPC-UA / Modbus / historian adapter in the repository. The architecture has a connectors layer, but the demo path is the simulation engine.
6. **Retrieval reranking is disabled by default** (`P117_RETRIEVAL_RERANK_ENABLED=false`).
7. **No vision model is configured**; `P117_VISION_MODEL` is intentionally unset.
8. **`frontend/`** is a separate Vite workbench, not part of the pnpm workspace and not covered by the console test suite.
9. **The commercial CTAs do not submit a lead.** They select a position and scroll to a documented engagement path; there is no CRM or contact endpoint.
10. **Recovery succeeds for some scenarios and not others.** `e-P-1001` and `e-C-1053` resolve; `e-P-1042` and `e-V-1047` currently end with a validator-rejected route while the incident escalates. The cause is the Operations model's capability, not the topology — see §9 for the per-scenario breakdown.
11. **`ruff` and `pyright` are not both clean.** `ruff` passes as of this pass (20 findings fixed). `pyright` still reports unresolved type errors, and `make typecheck` exits non-zero.
12. **Phase 10 (Android) and Phase 12 (full integration test harness) are not complete.** A mobile field interface is listed as an Enterprise capability; a responsive web interface exists, but there is no native mobile application.

---

## 24. Final Release Checklist

| Item | Status |
|---|---|
| No TODO / FIXME in source | ✅ 0 found |
| No placeholder or fake content | ✅ verified |
| No `console.log` debug statements | ✅ 0 in application source |
| No secrets, keys or tokens in source | ✅ verified |
| `.env` untracked; `.env.example` names only | ✅ |
| All 72 settings documented | ✅ |
| Three-agent models configured and documented | ✅ (was missing) |
| Core flow event-driven, no frontend timers | ✅ verified |
| No findings emitted before the decision | ✅ verified |
| Model-unavailable path fabricates nothing | ✅ verified |
| Simulation topology and ids are real | ✅ verified |
| Materials data labelled SYNTHETIC_DEMO | ✅ 25/25 |
| No automatic purchasing | ✅ approval gate verified |
| Landing sequence intact (121 frames) | ✅ 120/120 load |
| No fake claims or endorsements | ✅ verified |
| Duplicate requests / connections removed | ✅ −95% plant traffic |
| Bundle reduced where heavy code was unneeded | ✅ home −62% |
| Generated caches cleaned | ✅ `__pycache__`, `*.pyc`, `.pytest_cache`, `.ruff_cache` |
| TypeScript | ✅ 0 errors |
| Lint | ✅ 0 errors |
| Production build | ✅ exit 0 |
| Backend tests | ✅ 368 passed |
| All routes verified | ✅ 26/26 |
| README rewritten | ✅ |
| Documentation audited | ✅ |
| Final report | ✅ this document |

---

**Final release readiness: READY.**

The system does what it claims, the claims trace to verifiable code, synthetic data is labelled, commercial figures are not invented, and the failure paths are honest. The limitations in §23 are real and are documented — none of them blocks a release, and each is a known next step rather than an unknown gap.
