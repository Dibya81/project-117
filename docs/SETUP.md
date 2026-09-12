# Project 117 — Reproducible setup

This file is the single source of truth for getting a **clean checkout** running.
Every command below is literal. Where a step needs network access it says so.

---

## 0. What the archive contains and what it does not

| Component | Shipped in this repo? | How it is supplied |
|---|---|---|
| Backend (FastAPI, simulation engine, agents, sandbox client, RAG service) | yes | `backend/` |
| Frontend (Next.js 14 console) | yes | `apps/web/` |
| Plant datasets (refinery, steel) | yes | committed SQL seed `project-117-simulation/database/seed_plants.sql`, applied on first run |
| Knowledge corpus for retrieval | yes | `data/knowledge/`, `data/demo/` (seeded by script) |
| **localGPT** retrieval stack | **no** | vendored separately into `vendor/localGPT` (optional) |
| **LightRAG** graph-RAG | **no** | installed from PyPI as the `graphrag` extra (optional) |
| Ollama models | no | pulled at runtime (optional) |
| OpenSandbox | no | external service, configured by URL (optional) |

### Why the previous layout was broken

`pyproject.toml` used to declare:

```toml
[tool.uv.sources]
lightrag-hku = { path = "../LightRAG-main", editable = true }
```

and pyright used `extraPaths = ["../localGPT-main"]`. Both point **outside** the
repository, at directories that are not part of any checkout, so `uv sync` on a
clean machine failed before installing anything. That is fixed:

* `lightrag-hku` is now a normal versioned **optional extra** resolved from PyPI
  (`uv sync --extra graphrag`). No path source is active by default.
* pyright's `extraPaths` now points at the in-repo `vendor/localGPT`, which is
  allowed to be absent.
* Nothing was silently deleted. Both integrations remain wired in code; they are
  now *declared optional* and the runtime degrades **visibly**, not silently —
  see "Degradation policy" below.

---

## 1. Prerequisites

```bash
python3 --version      # >= 3.11
node --version         # >= 20
corepack enable        # pnpm 9.15.0 is pinned in package.json
```

---

## 2. Backend install (network required for the first install only)

```bash
# from the repository root
pip install uv                    # or: pipx install uv
uv sync                           # core dependencies, no vendor stack

# optional extras
uv sync --extra graphrag          # LightRAG (graph RAG)
uv sync --extra localgpt          # sentence-transformers for the vendored pipeline
uv sync --extra rerank            # cross-encoder reranking (~2 GB, torch)
uv sync --group dev               # pytest / ruff / pyright
```

Without network access, run the fully offline path in section 8.

### Supplying localGPT

localGPT is vendored *source*, not a PyPI package. Place it at `vendor/localGPT`:

```bash
mkdir -p vendor
git clone https://github.com/PromtEngineer/localGPT.git vendor/localGPT
# or, air-gapped: copy a localGPT-main directory to vendor/localGPT
```

`backend/rag/adapter.py` adds `vendor/localGPT` to `sys.path` when present.
If it is absent, `LocalGPTBackend.try_build()` returns `None` and retrieval
falls back to the in-repo lexical BM25 backend over `data/knowledge` +
`data/demo`. The active backend is reported by
`GET /api/simulation/health` (`retrieval.backend`), so the mode is never hidden.

### Supplying LightRAG

```bash
uv sync --extra graphrag          # normal case, from PyPI
```

To develop against a local clone instead, put it at `vendor/LightRAG` and
uncomment the `[tool.uv.sources]` block at the bottom of `pyproject.toml`.

---

## 3. Initialise the database and seed content

```bash
export P117_SIMULATION_DB="$PWD/data/simulation.db"   # default if unset
python3 scripts/seed_knowledge_corpus.py              # SOP/OPS corpus for RAG
python3 scripts/validate_plant_data.py                # exits 0; prints per-plant report
```

The simulation schema (17 tables) is created automatically on first use by
`backend/simulation/persistence.py::SimulationStore`. Plant, zone, equipment,
sensor, actuator and connection rows are written when a plant is registered,
which happens on the first API call that touches it.

---

## 4. Start the backend

```bash
# from the repository root
uv run uvicorn backend.api.src.main:create_app --factory --host 127.0.0.1 --port 8000
```

Verify:

```bash
curl -s http://127.0.0.1:8000/api/simulation/health | python3 -m json.tool
curl -s http://127.0.0.1:8000/api/simulation/plants | python3 -m json.tool
```

`health` reports the database path, the retrieval backend actually in use, the
agent roster runtime, and which plants are registered.

---

## 5. Start the frontend (live mode is the default)

```bash
cd apps/web
pnpm install
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000 pnpm dev   # http://localhost:3017
```

`NEXT_PUBLIC_DATA_MODE` defaults to `live`. Mock mode is opt-in only:

```bash
NEXT_PUBLIC_DATA_MODE=mock pnpm dev   # in-browser engine, development only
```

In mock mode the console logs a warning and every simulation screen shows a
`mock mode (development only — not backend data)` badge. In live mode, if the
backend cannot be reached the UI shows **Backend unavailable — plant not
loaded** and refuses to render simulated data. There is no fallback path from
live into mock.

---

## 6. Run the sensor-failure demo

1. `http://localhost:3017/console` → **Launch Simulation**
2. Choose **Oil Refinery**
3. Click any sensor-bearing asset on the canvas
4. Context menu → **Simulate fault** → pick a failure mode
5. The Agent Command Center shows the incident, phase, the six agent tasks,
   their tools, evidence and results as the SSE stream delivers them
6. Approve the recommendation → action → verification → artifact
7. Repeat with **Iron & Steel**

Equivalent headless run (no browser):

```bash
curl -s -XPOST http://127.0.0.1:8000/api/simulation/plants/refinery/start
curl -s -XPOST http://127.0.0.1:8000/api/simulation/plants/refinery/equipment/e-P-1001/failure \
     -H 'content-type: application/json' -d '{"mode_id":"seal_leak"}'
curl -s -XPOST http://127.0.0.1:8000/api/simulation/plants/refinery/incidents/INC-1001/decision \
     -H 'content-type: application/json' -d '{"approved":true}'
curl -s http://127.0.0.1:8000/api/simulation/incidents/INC-1001/record | python3 -m json.tool
curl -s 'http://127.0.0.1:8000/api/simulation/audit?plant_id=refinery' | python3 -m json.tool
```

### Prove persistence

```bash
# stop uvicorn (Ctrl-C), then:
sqlite3 data/simulation.db \
  "SELECT id,status,severity FROM incidents; SELECT count(*) FROM agent_tasks; SELECT count(*) FROM audit_events;"
# restart uvicorn and re-query the API — the record is still there
curl -s http://127.0.0.1:8000/api/simulation/plants/refinery/history | python3 -m json.tool
```

---

## 7. Test suites

```bash
./.venv/bin/python scripts/validate_plant_data.py    # plant data quality (exit 0)
python3 tests/simulation/test_verification_regression.py
python3 tests/simulation/redteam_harness.py        # determinism + negative tests
python3 tests/simulation/test_integration_pipeline.py
```

The last one is the integration gate: 10 refinery + 10 steel randomised assets,
restart survival in a separate OS process, retrieval diversity, graph context,
failure paths and the builder save/load round trip. It needs **no network** and
**no extra packages** — standard library only.

With the dev group installed you can also run `uv run pytest`.

---

## 8. Fully offline / air-gapped install

The simulation pipeline (engine, orchestration, six agent roles, retrieval,
graph context, persistence, policy gate, audit) runs on the Python standard
library plus pydantic. Only the HTTP surface needs third-party packages.

```bash
# on a networked machine
uv pip download -r <(uv export --no-hashes) -d wheelhouse/
# transfer wheelhouse/, then on the air-gapped machine
uv pip install --no-index --find-links wheelhouse -r <(uv export --no-hashes)

# frontend
pnpm fetch                 # networked machine, populates the pnpm store
pnpm install --offline     # air-gapped machine
```

---

## 9. Degradation policy (what happens when an optional piece is missing)

| Missing | Behaviour | Where it is visible |
|---|---|---|
| `vendor/localGPT` | lexical BM25 retrieval over `data/knowledge` + `data/demo` | `health.retrieval.backend = lexical-bm25` |
| Knowledge corpus | documentation task status `blocked`, no citation invented | task status + audit row |
| `backend.agents` deps (pydantic-settings etc.) | deterministic evidence runtime | `health.agents.runtime`, every task's `agent_runtime` field |
| OpenSandbox | command actions return `ACTION BLOCKED / SANDBOX UNAVAILABLE` | action row, audit row, UI |
| Policy denial | action `blocked`, incident escalated, never verified | action row, audit row, UI |
| Backend down (frontend live mode) | "Backend unavailable" state | simulation pages |

No path in this table produces a fake success.

---

## 10. Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `P117_SIMULATION_DB` | `data/simulation.db` | simulation SQLite store |
| `P117_SIM_RETRIEVAL` | `auto` | `lexical` forces the BM25 backend |
| `P117_SIM_RETRIEVAL_DISABLE` | unset | `1` simulates a dead knowledge base (failure-path testing) |
| `P117_DATABASE_URL` | `sqlite:////data/project117.db` | main application database |
| `P117_LLM_BASE_URL` | `http://ollama:11434/v1` | local model endpoint |
| `NEXT_PUBLIC_DATA_MODE` | `live` | `mock` = in-browser engine, development only |
| `NEXT_PUBLIC_API_BASE` | `http://127.0.0.1:8000` | backend origin used by the console |
