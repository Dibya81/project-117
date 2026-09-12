# Project 117 — Sovereign, On-Premise Industrial AI Workbench

> **From information to action. On-prem. In your hands.**

Project 117 is a fully local AI workbench for industrial operations. A plant
event becomes an investigated, approved, verified action — and every model,
document, database row and log line stays on the machine.

It was built for **SIH 2026 problem statement 26117**.

**Verified in this tree:** 153 tests passing · `ruff` clean · `tsc` clean for
both TypeScript projects · `next build` exits 0 across 20 routes · the landing
page's 121-frame sequence still scrubs · 14 console routes render with zero
console or page errors. `pyright` is **not** clean — the remaining typing debt
is listed under [Testing & quality](#testing--quality) rather than hidden.

Jump to: [Architecture](#architecture) · [Quickstart](#quickstart) ·
[Environment variables](#environment-variables) · [Testing & quality](#testing--quality)

## What it does

In one closed loop, running entirely on-premise:

**industrial event → detection → multi-agent investigation → plan → safe action
→ verification → prediction → human notification.**

A simulated plant (or a real historian feed) emits telemetry. The engine detects
an event — a failed transmitter, an instrument drifting out of its envelope, a
tripped detector — and raises an incident. A multi-agent pipeline then
decomposes it against the plant's actual topology, maintenance history and
retrieved SOPs: data analysis, maintenance, operations, safety and documentation
tasks run with real tools and real evidence, and synthesis produces a ranked
root-cause assessment, an action plan, and a prediction of the next asset at
risk. A human approves the plan. The action executes under policy in an isolated
sandbox. An independent verification stage checks the plant actually recovered
and **fails closed** if it did not. The whole run is persisted to SQLite and the
audit trail, and a report is generated for the operator.

Nothing about that path requires the internet. Local models (Ollama or any
OpenAI-compatible server), local retrieval (LanceDB), local sandbox, local data.

## Architecture

```
project117/
│
├── apps/web/                  NEXT.JS 14 CONSOLE + CINEMATIC LANDING      :3017
│   ├── src/app/               App Router: landing (/), console (/console/*)
│   ├── src/components/        console shell, sim canvas, landing (3D/shader)
│   └── src/lib/sim/           live (REST+SSE) ⇄ embedded (browser engine)
│
├── backend/                   FASTAPI ENGINE                              :8000
│   ├── api/src/               app factory, routes, middleware
│   ├── orchestrator/          incident → task DAG → plan
│   ├── agents/                data-analysis · maintenance · operations ·
│   │                          safety · documentation
│   ├── simulation/            tick engine, telemetry, incidents, SSE stream
│   ├── rag/                   retrieval adapter (LanceDB + citations)
│   ├── sandbox/               isolated execution client + policy
│   ├── verification/          fail-closed checkers (artifact/calculation/citation)
│   ├── security/              egress guard, RBAC, approvals, secrets, audit
│   ├── storage/  database/    documents, SQLite persistence, audit rows
│   └── workflows/             YAML workflow runtime
│
├── frontend/                  VITE + REACT SIMULATION WORKBENCH           :5173
│   └── src/                   React Flow canvas, agent trace, WS bridge
│
├── project-117-simulation/    PLANT DATA PACKAGE (deliverable)
│   ├── database/seed_plants.sql   committed seed — source of truth for
│   │                              the refinery/steel plant definitions
│   └── public/                the same rows exported as JSON (workbench copy)
│
├── data/                      runtime + demo data (see data/README.md)
│   ├── knowledge/  demo/      retrieval corpus (tracked)
│   ├── simulation.db          simulation SQLite store (git-ignored, seeded)
│   ├── uploads/  lancedb/     runtime stores (git-ignored)
│   └── *.db                   SQLite stores (git-ignored)
│
├── scripts/                   generators, validators, smoke tests
├── tests/                     unit/ + simulation/ suites
├── workflows/definitions/     YAML workflow definitions
├── docs/                      setup, architecture, decisions, simulation, knowledge
├── packages/                  shared package placeholders (not implemented)
├── infrastructure/docker/     Dockerfiles for backend + sandbox image
└── Makefile  pyproject.toml  package.json  docker-compose.yml
```

### The four surfaces

| Surface | What it is |
|---|---|
| **`apps/web/`** | The product console: a Next.js 14 App Router app with a cinematic landing page (`/`) and the operator console (`/console/*`) — plant twin, agent command center, approvals, work orders, documents, knowledge graphs, admin. |
| **`backend/`** | The engine. FastAPI service exposing the orchestrator, the specialized agents, ingestion + hybrid RAG with citations, the sandbox client, verification checkers, approvals/RBAC, persistence and the audit trail. It also runs the digital-twin simulation and streams it over SSE. |
| **`frontend/`** | A standalone Vite + React **simulation workbench**: a React Flow canvas over the `project-117-simulation/` data package, with a WebSocket bridge to an orchestrator. It is a separate, smaller demo surface — not part of the Next.js app or the pnpm workspace. |
| **`project-117-simulation/`** | The plant **data package**: the committed SQL seed (`database/seed_plants.sql`) that is the source of truth for the prebuilt refinery and steelworks, plus frozen JSON exports for the Vite workbench. |

### Which engine runs

There is exactly one engine implementation per surface, and the transport is
chosen explicitly — never inferred:

* **Live mode (the default).** The browser talks to the FastAPI backend over
  REST + SSE. The backend's simulation engine is the source of truth; the UI
  renders events and never invents them.
* **Embedded mode — offline, opt-in.** With `NEXT_PUBLIC_DATA_MODE=mock` the
  console runs a deterministic in-browser engine (a TS port of the backend
  engine) so the demo works with zero infrastructure. It must be selected on
  purpose and is labelled in the UI. **There is no automatic fallback into it:**
  if the backend is down in live mode, the console shows a hard
  "backend unavailable" state instead of faking data.

The Vite workbench has the same discipline: `VITE_DATA_SOURCE=json` reads the
committed JSON offline; `VITE_DATA_SOURCE=backend` expects a JSON API (see the
caveat in [Testing & quality](#testing--quality)).

## Sovereignty posture

Project 117's claim is that confidential industrial data never leaves the
machine. That is enforced, not just declared:

* **Local models only.** One OpenAI-compatible endpoint (`P117_LLM_BASE_URL`,
  default `http://localhost:11434/v1` — Ollama's `/v1`) serves chat and
  embeddings. vLLM speaks the same protocol; switching is configuration, not a
  code change.
* **Fail-closed model roles.** Every model role (`P117_REASONING_MODEL`,
  `P117_EMBEDDING_MODEL`, …) is unconfigured by default. A role that is not set
  returns `503 model_unavailable` naming the variable to set — it never silently
  picks a model. A Hugging Face repo id (`org/name`) would download weights and
  is **rejected at startup** unless `P117_ALLOW_REMOTE_MODEL_REPOS=true`.
* **Enforced zero egress.** `P117_EGRESS_DEFAULT_DENY=true`; every outbound
  `httpx` request is checked by `backend/security/egress.py` before it leaves,
  including redirects and streams. `localhost` / `127.0.0.1` / `::1` are always
  reachable so local model servers and the sandbox work. Any host added to
  `P117_EGRESS_ALLOWED_HOSTS` is a deliberate hole in the guarantee.
* **Isolated execution.** Generated code and document tooling run through the
  sandbox client (`backend/sandbox/`), with CPU/memory/time/output limits and
  `P117_SANDBOX_ALLOW_NETWORK=false` by default. Enabling network without an API
  key refuses to start.
* **On-prem data.** Documents, uploads, vectors (LanceDB), SQLite databases and
  audit rows all live under `data/` on this machine.
* **Honest scope.** The egress guard covers HTTP made by this process through
  `httpx`; vendored code that opens its own sockets and container-level egress
  control are not covered yet (see the module docstring).

## Prerequisites

| Requirement | Version | Where it is pinned |
|---|---|---|
| Python | **>= 3.11** | `pyproject.toml` → `requires-python = ">=3.11"` |
| [uv](https://docs.astral.sh/uv/) | current | Python env + dependency manager |
| Node.js | **18+** (Next.js 14 needs 18.17+) | not pinned in-repo; `docs/SETUP.md` suggests 20 |
| pnpm | **9.15.0** | `package.json` → `"packageManager": "pnpm@9.15.0"` |
| Ollama | optional, recommended | local inference; not required to boot the backend |
| Docker | optional | `docker-compose.yml` and the sandbox images |

Enable the pinned pnpm with `corepack enable`.

Ollama is optional in the sense that the backend starts and the simulation runs
without it — but any call that needs a model role will return
`503 model_unavailable` until a model is pulled and the role variable is set.

## Quickstart

### (a) Backend + console (the main path)

```bash
# 1. Python environment (from the repository root)
uv sync                 # preferred: uses pyproject.toml + uv.lock

#    No uv, or installing with plain pip? A pinned requirements.txt is
#    committed and generated from the same lock file:
#      python3 -m venv .venv && . .venv/bin/activate
#      pip install -r requirements.txt

# 2. local models — a set that fits a 16 GB machine (see the table below)
ollama pull nomic-embed-text:latest     # 274 MB  embedding
ollama pull llama3:latest               # 4.7 GB  reasoning
ollama pull deepseek-coder:6.7b         # 3.8 GB  coding
ollama pull mistral:latest              # 4.4 GB  domain

# 3. configuration
cp .env.example .env
#    The example carries the reference set above, commented out — uncomment it
#    or set the roles yourself. Every role is unconfigured by default and fails
#    loudly (503 model_unavailable) rather than silently guessing a model.

# 4. start the backend on :8000
uv run uvicorn backend.api.src.main:create_app --factory --host 127.0.0.1 --port 8000

# verify (second shell)
curl http://127.0.0.1:8000/health

# 5. start the console on :3017
pnpm install
pnpm dev            # = pnpm --filter web dev = next dev -p 3017
# open http://127.0.0.1:3017/console/simulation
```

### Choosing models for a 16 GB machine

The reference set targets an Apple M4 with 16 GB of unified memory, where the
OS, the KV cache and the resident embedding server all share one pool:

| Role | Model | Weights | Why |
|---|---|---|---|
| `reasoning` | `llama3:latest` (8B) | 4.7 GB | The workhorse; fast enough for an operator console. |
| `coding` | `deepseek-coder:6.7b` | 3.8 GB | Writes the sandbox scripts the analysis agent designs. |
| `domain` | `mistral:latest` (7B) | 4.4 GB | Maintenance and operations wording. |
| `embedding` | `nomic-embed-text:latest` | 274 MB | Feeds LanceDB; small and always resident. |
| `vision` | *unset* | — | No vision model pulled. Set one only for on-device image understanding. |
| `reranker` | *unset* | — | Needs `uv sync --extra rerank` (torch alone ~2 GB) **and** local weights. |

A 14B instruct model at Q4 (~9 GB) was considered and rejected: it leaves too
little headroom once everything else is resident, and it swaps under sustained
load. Parameter count is not the goal — a machine that stays responsive matters
more than a slightly larger model. These are configuration, never hard-coded:
point the roles at what you have actually pulled and confirm with `ollama list`
or `GET /api/models`.

**Ports and CORS.** These are the real ports read from the code:
* Next.js console — **3017**: `apps/web/package.json:6` → `"dev": "next dev -p 3017"`.
* Backend — **8000**: `backend/config.py:43` → `api_port: int = 8000`.
* Vite workbench — **5173**: `frontend/vite.config.ts:20` → `server: { port: 5173 }`.

The backend's CORS allow-list is `cors_origins` in `backend/config.py:56-61`:

```python
cors_origins: set[str] = {
    "http://127.0.0.1:3017",
    "http://localhost:3017",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
}
```

The console **must be served on a port in that list.** Serve it elsewhere and
the browser blocks every API call, the adapter raises
`BackendUnavailableError`, and the simulation falls back to its
"backend unavailable" state. Add your origin to `P117_CORS_ORIGINS`
(comma-separated) if you cannot use one of the four above.

### (b) The Vite simulation workbench

```bash
cd frontend
npm install
npm run dev        # http://127.0.0.1:5173
```

By default this reads the committed JSON in
`project-117-simulation/public/` and runs offline. The orchestrator bridge is
optional and opt-in:

```bash
VITE_ORCHESTRATOR_WS_URL=ws://<orchestrator-host>:<port>/<path> npm run dev
```

Left unset (the default), the workbench runs in its clearly-labelled mock mode.
Note that the current FastAPI backend does **not** expose a WebSocket endpoint;
it streams simulation events over SSE at
`/api/simulation/plants/{id}/stream`. See [Testing & quality](#testing--quality).

## Environment variables

Copy the relevant example first:
`cp .env.example .env` (backend), `cp apps/web/.env.example
apps/web/.env.local` (console), `cp frontend/.env.example frontend/.env` (Vite).

There is exactly **one** backend example, at the repository root, because that
is the only directory whose `.env` is ever read: `backend/config.py` resolves
`.env` from the **current working directory**, and the backend is run from the
repository root. An example copied into `backend/` would have no effect.

`backend/config.py` loads that file with `load_dotenv(".env", override=False)`,
so *every* documented variable reaches the process — including the ones read
straight from `os.environ` rather than through the settings object (the HTTP
audit toggle, rate limits, the simulation database, tool policy and the
workflow directory). A variable exported in the shell always wins over the file.

### Console (`apps/web`) — read at build time, inlined into the browser bundle

| Variable | Read in | Default | Purpose |
|---|---|---|---|
| `NEXT_PUBLIC_API_BASE` | `src/lib/api.ts`, `src/lib/sim/adapter.ts`, `src/lib/uploads.ts`, `next.config.mjs` | `http://127.0.0.1:8000` | Backend origin for every `/api/...` call. |
| `NEXT_PUBLIC_DATA_MODE` | `src/lib/sim/adapter.ts`, `src/lib/websocket.ts`, `next.config.mjs` | `live` | `live` = backend; `mock` = explicit in-browser engine. |
| `NEXT_PUBLIC_WS_URL` | `src/lib/websocket.ts`, `next.config.mjs` | `ws://127.0.0.1:8000/api/jobs/ws` | Job/agent event socket. The socket module exists but is not mounted by any page today, and the backend serves no WS endpoint. |

### Vite workbench (`frontend`)

| Variable | Read in | Default | Purpose |
|---|---|---|---|
| `VITE_ORCHESTRATOR_WS_URL` | `src/ws/orchestrator.ts` | empty | Orchestrator WebSocket. Unset ⇒ labelled mock mode. |
| `VITE_DATA_SOURCE` | `src/data/service.ts` | `json` | `json` = committed JSON; `backend` = `GET {VITE_API_BASE}/plants/{id}`. |
| `VITE_API_BASE` | `src/data/service.ts` | `http://127.0.0.1:8000` | Base URL used only when `VITE_DATA_SOURCE=backend`. |

### Backend (`backend/config.py`) — all prefixed `P117_`

**Service, persistence, logging**

| Variable | Default | Purpose |
|---|---|---|
| `P117_ENVIRONMENT` | `development` | Environment label. |
| `P117_API_HOST` | `127.0.0.1` | Bind address. |
| `P117_API_PORT` | `8000` | Bind port. |
| `P117_LOG_LEVEL` | `INFO` | Log level. |
| `P117_DATABASE_URL` | `sqlite:///./data/project117.db` | Application database. |
| `P117_JSON_LOGS` | `false` | `true` = JSON logs, `false` = console. |
| `P117_CORS_ORIGINS` | the four `3017`/`3000` origins | Comma-separated browser origins allowed to call the API. |

**Documents, workflows, artifacts**

| Variable | Default | Purpose |
|---|---|---|
| `P117_UPLOADS_DIR` | `./data/uploads` | Uploaded document storage. |
| `P117_MAX_UPLOAD_BYTES` | `209715200` (200 MB) | Upload size ceiling. |
| `P117_ALLOWED_EXTENSIONS` | `.pdf,.docx,.doc,.txt,.md,.html,.htm,.png,.jpg,.jpeg` | Extensions accepted on upload. |
| `P117_WORKFLOWS_DIR` | `../workflows/definitions` | YAML workflow directory loaded at startup. |
| `P117_LANCEDB_DIR` | `./data/lancedb` | Vector + full-text index directory. |
| `P117_LANCEDB_TABLE` | `p117_chunks` | LanceDB table name. |
| `P117_CHUNK_SIZE_TOKENS` | `1500` | Tokens per ingested chunk. |
| `P117_CHUNK_OVERLAP_SENTENCES` | `1` | Sentence overlap between chunks. |
| `P117_INGESTIBLE_EXTENSIONS` | `.pdf,.docx,.txt,.md,.html,.htm` | Extensions eligible for indexing. |
| `P117_ARTIFACTS_DIR` | `./data/artifacts` | Generated PDF/DOCX/PPTX/XLSX output. |

**Retrieval**

| Variable | Default | Purpose |
|---|---|---|
| `P117_RETRIEVAL_RERANK_ENABLED` | `false` | Enable reranking (needs `uv sync --extra rerank` + local weights). |
| `P117_RETRIEVAL_RERANK_CANDIDATES` | `30` | Fused candidates shown to the reranker. |
| `P117_CHAT_EVIDENCE_TOP_K` | `5` | Evidence chunks attached to a grounded chat turn. |
| `P117_CHAT_DEFAULT_USE_RAG` | `false` | Ground chat turns by default. |

**Models (local inference)**

| Variable | Default | Purpose |
|---|---|---|
| `P117_LLM_BACKEND` | `openai_compatible` | Gateway protocol. |
| `P117_LLM_BASE_URL` | `http://localhost:11434/v1` | Local model endpoint (Ollama `/v1` or vLLM). |
| `P117_LLM_API_KEY` | empty | Key for the local endpoint, if any. |
| `P117_LLM_TIMEOUT_SECONDS` | `120` | Inference timeout. |
| `P117_LLM_AVAILABILITY_TTL` | `60` | Provider model-list cache TTL. |
| `P117_OPEN_SANDBOX_BASE_URL` | `http://localhost:8080` | Sandbox control plane (see sandbox vars). |
| `P117_REASONING_MODEL` | empty | Main reasoning model role. |
| `P117_VISION_MODEL` | empty | Vision role. |
| `P117_EMBEDDING_MODEL` | empty | Embedding role (root `.env.example` suggests `nomic-embed-text:latest`). |
| `P117_RERANKER_MODEL` | empty | Reranker role. |
| `P117_CODING_MODEL` | empty | Coding role. |
| `P117_DOMAIN_MODEL` | empty | Domain role. |
| `P117_ALLOW_REMOTE_MODEL_REPOS` | `false` | Allow `org/name` model ids that download weights. Leave false. |

**Simulation (digital twin)**

| Variable | Default | Purpose |
|---|---|---|
| `P117_SIMULATION_ENABLED` | `true` | Start a tick loop per loaded dataset. |
| `P117_SIMULATION_TICK_S` | `1.0` | Tick period in seconds. |
| `P117_SIMULATION_DB` | `data/simulation.db` | Simulation SQLite store (read directly in `backend/simulation/persistence.py`). |
| `P117_SIM_RETRIEVAL` | `auto` | `lexical` forces the in-repo BM25 retrieval backend. |
| `P117_SIM_RETRIEVAL_DISABLE` | unset | `1` simulates a dead knowledge base (failure-path testing). |

**Security: egress, auth, approvals, tool policy**

| Variable | Default | Purpose |
|---|---|---|
| `P117_EGRESS_DEFAULT_DENY` | `true` | Deny all outbound hosts except localhost. |
| `P117_EGRESS_ALLOWED_HOSTS` | empty | Exact hostnames to permit (no wildcards). |
| `P117_AUTH_REQUIRED` | `false` | Require authentication. |
| `P117_AUTH_API_KEY` | empty | API key when auth is required. |
| `P117_APPROVAL_ALWAYS_REQUIRE` | empty | Tool names that always need human approval. |
| `P117_APPROVAL_AUTO_EXECUTE` | `false` | Remove the human gate before code execution. |
| `P117_APPROVAL_AUTO_EXTERNAL` | `false` | Remove the human gate before external-risk actions. |
| `P117_TOOL_MAX_RISK` | `execute` | Highest risk this deployment runs: `read\|compute\|write\|execute\|external`. |
| `P117_TOOL_ALLOWLIST` | empty | Exclusive tool allowlist (comma-separated). |
| `P117_TOOL_DENYLIST` | empty | Tool denylist (comma-separated). |
| `P117_TOOL_MAX_CALLS_PER_PLAN` | `32` | Tool-invocation ceiling per job. |
| `P117_MAX_CHUNKS_PER_STEP` | `24` | Evidence chunks any one step may pull into context. |

**Sandbox**

| Variable | Default | Purpose |
|---|---|---|
| `P117_SANDBOX_IMAGE` | empty (built-in `python:3.11-slim`) | Sandbox image override. |
| `P117_SANDBOX_DOCUMENTS_IMAGE` | empty (built-in `project117/sandbox-documents:1.0`) | Document-tooling image override. |
| `P117_SANDBOX_IMAGE_DIGEST` | empty | Pin the sandbox image by digest. |
| `P117_SANDBOX_DOCUMENTS_IMAGE_DIGEST` | empty | Pin the document image by digest. |
| `P117_SANDBOX_API_KEY` | empty | Shared secret for the sandbox daemon. |
| `P117_SANDBOX_REQUIRE_API_KEY` | `true` | Refuse to run without an API key. |
| `P117_SANDBOX_CPU_MILLICORES` | `500` | CPU limit. |
| `P117_SANDBOX_MEMORY_MIB` | `512` | Memory limit. |
| `P117_SANDBOX_TIMEOUT_SECONDS` | `120` | Per-command timeout. |
| `P117_SANDBOX_LIFETIME_SECONDS` | `600` | Sandbox lifetime. |
| `P117_SANDBOX_MAX_OUTPUT_BYTES` | `256000` | Captured output ceiling. |
| `P117_SANDBOX_MAX_ARTIFACT_BYTES` | `26214400` | Produced-artifact ceiling. |
| `P117_SANDBOX_ALLOW_NETWORK` | `false` | Allow sandbox network access. Leave false. |

**Read directly from `os.environ` (not `backend/config.py`)**

| Variable | Read in | Default | Purpose |
|---|---|---|---|
| `P117_AUDIT_HTTP` | `api/src/middleware/audit.py` | `true` | Record mutating HTTP requests. |
| `P117_RATE_LIMIT_PER_MINUTE` | `api/src/middleware/rate_limit.py` | `0` (off) | Sustained requests/minute per caller. |
| `P117_RATE_LIMIT_BURST` | `api/src/middleware/rate_limit.py` | per-minute value | Token-bucket size. |
| `P117_FILE_ROOTS` | `tools/files/reader.py` | empty | Roots the file reader may read. |
| `P117_WORKSPACE_DIR` | `tools/files/writer.py` | empty | Workspace the file writer may write to. |
| `P117_DEMO_DIR` | `storage/demo.py` | empty | Demo-data directory override. |
| `P117_DEMO_WRITEBACK` | `storage/demo.py` | off | Allow demo-data writeback. |

**Secrets** (declared in `backend/security/secrets/__init__.py`; redacted from
logs and audit detail by name): `P117_DATABASE_PASSWORD`, `P117_MODEL_API_KEY`,
`P117_CONNECTOR_SAP_PASSWORD`, `P117_CONNECTOR_CMMS_TOKEN`,
`P117_CONNECTOR_DMS_TOKEN`, `P117_CONNECTOR_HISTORIAN_TOKEN`.

## The demo

A five-minute golden path. Both the console and the backend must be running
(Quickstart (a)).

1. **Open the refinery.** Go to <http://127.0.0.1:3017/console/simulation> and
   choose the **Oil Refinery** card (dataset id `refinery`; 58 equipment,
   224 sensors, 14 scenarios). The plant twin opens at
   `/console/simulation/plant/refinery`.
2. **Inject a sensor fault.** Click the crude charge pump **P-1042**
   (`e-P-1042`) on the schematic, then inject the **sensor failure** mode
   (`sensor_failure`). This is exactly the committed scenario
   `sc-sensor-failure` ("PT-1042A sensor failure"): the primary pressure
   transmitter goes bad while the process keeps running.
3. **Watch the agents.** The incident panel opens and the task DAG fills in as
   the SSE stream delivers it: orchestrator classification, then data analysis,
   maintenance, operations, safety and documentation, then a synthesis step —
   each with the tools it used, the evidence it found (with confidence), and its
   result.
4. **Read the assessment.** Once the tasks have produced evidence, the
   assessment panel shows the outcome checklist, the **ranked root-cause
   assessment** with the evidence that moved it, and the **prediction** — the
   next asset at elevated risk with the reasons it scored.
5. **Approve the plan.** Use the decision control in the agent command center to
   approve. The action executes, verification gates run, and the event stream
   reports `action.completed` → `verification.started/completed` →
   `artifact.created` → `audit.recorded`.
6. **Create a work order.** In the assessment panel, **Create work order** files
   a maintenance work order for the failed asset and takes you to
   `/console/work-orders/{id}`.

### Taking an instrument out of service

Each row under **Live sensors** in the unit panel carries two controls:

* **⏸ out of service** — the transmitter is marked failed (value frozen, quality
  bad), an incident is raised against that exact sensor, and the agent pipeline
  runs on it. The **recovery panel** slides in on the right showing the affected
  circuit, the agents working through it in pipeline order, and the
  instruments that can still read the point. That fallback list is not
  decorative: it is the same redundancy rule the engine uses to decide whether
  the process is still readable, ordered declared-redundancy first, then
  same-measurement, then adjacent-unit, then process correlates. If nothing can
  read it, the panel says so rather than pointing at a second dead transmitter.
* **✕ delete** — the sensor is genuinely removed: it leaves the list, the
  schematic stops drawing it, and it is absent from telemetry and snapshots.

**Every operator change is temporary.** Nothing is written to the plant
definition or the database. A chip in the top bar counts the session's changes
and offers **Reset plant**; reloading the page does the same thing. In live mode
the engine lives in the backend's memory for the life of the process, so the
console explicitly resets the plant on load — otherwise a reload would still
show the previous session's disabled transmitter. Client-side navigation
between console pages keeps your work; only a reload discards it.

The builder has the same session semantics, plus a **★ Saved** library: keep one
instrumented unit or one relation (a redundancy pair, say) and drop copies back
onto the canvas later. A saved connection is stored by end tags and relation, so
it can still be re-applied after the units have been rebuilt.

Headless equivalent (no browser), against a running backend:

```bash
curl -s -XPOST http://127.0.0.1:8000/api/simulation/plants/refinery/start
curl -s -XPOST http://127.0.0.1:8000/api/simulation/plants/refinery/equipment/e-P-1042/failure \
     -H 'content-type: application/json' -d '{"mode_id":"sensor_failure"}'
curl -s http://127.0.0.1:8000/api/simulation/plants/refinery/snapshot | python3 -m json.tool
```

The plant datasets live in the simulation SQLite store. A fresh clone seeds
itself on first run from the committed
`project-117-simulation/database/seed_plants.sql`; validate it with:

```bash
./.venv/bin/python scripts/validate_plant_data.py
```

## Testing & quality

These commands work from the **repository root**. The Makefile targets wrap the
same commands (`make help` lists them), and both entry points are exercised.

| Command | What it runs |
|---|---|
| `uv run pytest -q` | Python unit + simulation suite (`tests/`). |
| `uv run ruff check backend tests` | Lint (ruff). |
| `uv run pyright backend` | Static types (pyright). |
| `pnpm typecheck` | `tsc --noEmit` for the Next.js console. |
| `pnpm lint` | `next lint` for the Next.js console. |
| `cd frontend && npm run typecheck` | `tsc --noEmit` for the Vite workbench. |
| `pnpm build` / `pnpm start` | Build and serve the Next.js console. |
| `./.venv/bin/python scripts/validate_plant_data.py` | Plant-data quality report from the DB (exit 0 on success). |
| `python3 tests/simulation/test_verification_regression.py` | Verification regression (stdlib only). |
| `python3 tests/simulation/redteam_harness.py` | Determinism + negative tests (stdlib only). |
| `python3 tests/simulation/test_integration_pipeline.py` | End-to-end simulation gate (stdlib only). |
| `python3 scripts/smoke_pure_logic.py` | Runtime smoke for pure logic (pydantic only). |
| `python3 scripts/smoke_agents.py` | Agent/decomposer smoke (pydantic only). |
| `python3 scripts/smoke_phase3.py` | Upload → ingest → LanceDB citations (needs a running backend + Ollama). |
| `python3 scripts/smoke_phase4.py` | Upload → hybrid search → grounded chat (needs a running backend + Ollama). |

### Known gaps in the tooling — stated plainly

* **The Vite workbench's `backend` data source has no endpoint yet.**
  `VITE_DATA_SOURCE=backend` fetches `{VITE_API_BASE}/plants/{id}`, but the
  FastAPI service serves plants under `/api/simulation/plants/...`
  (`GET /plants/refinery` returns 404). Use `VITE_DATA_SOURCE=json`.
* **No WebSocket in the backend.** The test/client workbenches have optional
  WebSocket bridges, but the backend streams simulation events over SSE
  (`/api/simulation/plants/{id}/stream`). Any `VITE_ORCHESTRATOR_WS_URL` or
  `NEXT_PUBLIC_WS_URL` therefore has nothing to connect to today.
* **Sensors are modelled as data attached to an asset, not as canvas nodes.**
  The builder's connect dialog can therefore express equipment↔equipment
  relations (including `REDUNDANCY`), but not sensor↔equipment wiring.
* **Graph RAG is opt-in and not installed.** LightRAG arrives with
  `uv sync --extra graphrag`; without it the retrieval backend falls back to
  the vendored lexical/vector stack.
* **Reranking is off by default and needs both an extra and local weights.**
  `uv sync --extra rerank` pulls torch (~2 GB) and every reranker backend
  resolves to a Hugging Face download, so an air-gapped install must skip it.
* **`pyright` is not clean.** It reports 17 real type errors across 8 modules
  (`deliverables/generators/pdf_generator.py` 10, `simulation/actions.py` 6,
  `orchestrator/src/execution_manager.py`, `workflows/engine/step_runner.py`,
  `tools/vision/drawing_analysis.py` and two more), plus 19 unresolvable-import
  errors for the vendored `rag_system` package that only exists once
  `vendor/localGPT` is populated. `ruff` and both TypeScript projects are clean,
  and the 134-test suite passes, so these are typing debt rather than runtime
  faults — but `make typecheck` exits non-zero until they are paid down. Fixing
  them properly means changing signatures in working code, which was out of
  scope for this pass; hiding them behind a looser pyright mode would have been
  worse than reporting them.

### Fixed in this pass

Recorded because each was a real defect that had been documented as a
limitation rather than repaired:

* **Every Makefile target was broken.** `make lint`, `make typecheck` and
  `make test` ran `cd backend` and then used root-relative paths that do not
  exist under `backend/`; `make run` invoked `backend.main:create_app`, a
  module that never existed. All targets now run from the repository root
  against `backend.api.src.main:create_app`, and `make help` documents them.
* **`uv run pytest` failed collection in two modules.**
  `tests/unit/test_chat.py` and `tests/unit/test_search.py` imported
  `from tests.conftest import FakeProvider`, but `FakeProvider` lived in
  `tests/unit/conftest.py` and there was no `tests/conftest.py`. The shared
  double now lives in `tests/conftest.py`; the suite also strips `P117_*` and
  ignores `.env` so a developer's local configuration cannot change results.
* **The smoke scripts had a hard-coded absolute root.**
  `scripts/smoke_pure_logic.py` and `smoke_agents.py` set
  `ROOT = "/data/sih_extract/SIH/backend"`, which exists only on the machine
  they were written on, and referenced three modules whose paths had moved
  (`backend/agents/base.py`, `orchestrator/task_decomposer.py`,
  `orchestrator/verification_manager.py`). Both now derive the root from the
  script location and run clean (52/52 each).
* **`POST /api/agents/run` returned HTTP 500 on every call.** The handler was
  synchronous, so FastAPI ran it in a worker thread where
  `Orchestrator.spawn`'s `asyncio.create_task` had no running loop. The same
  bug made `POST /api/jobs/{id}/approve` fail, so an approved job never
  resumed. Both handlers are now `async` and offload blocking SQLite work.
* **Tool faults surfaced as HTTP 500.** `ToolError` derives from
  `RuntimeError`, so bad arguments, an unknown tool and a tool needing human
  approval all looked like server crashes. They now map to 400/404/403/409.
* **`chunk_count` reported 0 for a successfully indexed document.** LanceDB
  0.38 returns a `ListTablesResponse` from `list_tables()`, not a list of
  names, so the membership test `name not in db.list_tables()` was always
  false. The same bug made retrieval's `has_table()` report "nothing indexed"
  after a clean ingest, and made deletes report zero rows purged.
* **`docker-compose.yml` was not runnable**: its backend `command` referenced
  the removed `backend.main` module.
* **Documented settings were silently inert.** Nothing called `load_dotenv`,
  and `BaseSettings(env_file=...)` only populates declared fields — so
  `P117_AUDIT_HTTP`, `P117_RATE_LIMIT_*`, `P117_SIMULATION_DB`,
  `P117_FILE_ROOTS` and friends had no effect when set in `.env`.
* **`P117_WORKFLOWS_DIR` defaulted to `../workflows/definitions`**, which
  resolves outside the checkout from the documented repo-root CWD, so a fresh
  clone started with an empty workflow registry.
* **The simulation canvas had a dead zone.** The floating zoom cluster is
  translucent and sits over the process map, and its panel swallowed every
  pointer event aimed at a symbol underneath it — a unit positioned there could
  not be selected at all. The cluster is now transparent to clicks except for
  its own buttons.
* **A reload did not always restore the plant.** In development React 18
  StrictMode invokes effects twice; the "already prepared" guard was a boolean
  set *before* the asynchronous reset finished, so the second invocation skipped
  the reset and read the plant definition while the first reset was still in
  flight. A deleted sensor therefore survived the reload that was supposed to
  remove it. The guard is now the shared reset *promise*, so a second caller
  awaits the same reset instead of racing past it.
* **Two side repos are optional and not installed here**: the vendored localGPT
  retrieval stack (`vendor/localGPT`) and LightRAG (`uv sync --extra graphrag`).
  When they are absent, retrieval degrades **visibly** to the in-repo lexical
  BM25 backend and the active backend is reported by
  `GET /api/simulation/health` (`retrieval.backend`). See `docs/SETUP.md`.
  When they are absent, retrieval degrades **visibly** to the in-repo lexical
  BM25 backend and the active backend is reported by
  `GET /api/simulation/health` (`retrieval.backend`). See `docs/SETUP.md`.

## Project structure

| Path | What it is |
|---|---|
| `apps/web/` | Next.js 14 console + cinematic landing page. |
| `backend/` | FastAPI engine: orchestrator, agents, simulation, RAG, sandbox, verification, audit. |
| `frontend/` | Vite + React simulation workbench. |
| `project-117-simulation/` | Plant data package: committed SQL seed + frozen JSON exports. |
| `data/` | Tracked demo/knowledge data plus git-ignored runtime stores (incl. the seeded simulation DB). |
| `docs/` | Setup, architecture, decisions, frontend design, simulation and knowledge docs. |
| `scripts/` | Dataset generators/validators and smoke tests. |
| `tests/` | `unit/` and `simulation/` test suites. |
| `workflows/definitions/` | YAML workflow definitions loaded at startup. |
| `packages/` | Shared package placeholders — not implemented. |
| `infrastructure/docker/` | Backend and sandbox Dockerfiles. |
| `pyproject.toml` | Python project, dependencies, ruff/pytest/pyright config. |
| `requirements.txt` | Pinned backend deps generated from `uv.lock`, for plain `pip install`. |
| `package.json`, `pnpm-workspace.yaml` | pnpm workspace (`apps/*`, `packages/*`). |
| `docker-compose.yml` | Phase-1 compose stack (backend + optional Ollama). |
| `Makefile` | Convenience targets wrapping the commands above (`make help`). |

## Knowledge base & Obsidian

The repository doubles as a browsable knowledge universe. `docs/knowledge-universe.md`
documents the two live graphs behind `/console/knowledge` (the plant graph built
from the simulation datasets, and the system/code graph), and
`docs/graphify-obsidian.md` documents mirroring the source tree into a local
Obsidian vault as a queryable, community-clustered graph. Both are built and
rendered entirely on this machine.

## License

**Apache License 2.0** — see [`LICENSE`](LICENSE).
