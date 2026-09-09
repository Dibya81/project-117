# Sovereign On-Premise Agentic AI Workbench

![System Architecture](./docs/architecture/system-architecture.png)

**SIH Problem Statement 26117 — Secure execution for confidential industrial operations**

A sovereign, on-premise agentic AI workbench for confidential industrial environments where documents, engineering data, code, telemetry, and generated deliverables remain inside organization-controlled infrastructure.

## Vision

The platform moves industrial AI from assistance to autonomous execution:

**PERCEIVE → PLAN → ACT → VERIFY**

It combines local AI models, document intelligence, hybrid retrieval, graph memory, sandboxed execution, deterministic artifact generation, verification, real-time telemetry, and controlled operational learning.

## Core Pillars

- **Provably Sovereign** — local-first, on-premise, air-gapped capable, default-deny network execution.
- **Whole-Operation Context** — vector/full-text retrieval plus structured knowledge graphs, operational state, and telemetry.
- **Verified Labor Reduction** — agents execute tools, code, and artifact-generation workflows and independently verify their results.
- **Live Learning** — human corrections become controlled deterministic rules/knowledge updates without requiring on-the-fly model training.

## High-Level Architecture

```text
UI + Gateway
     ↓
Orchestrator
     ├── Planner / Task Decomposer
     ├── Task Router
     ├── Context Manager
     ├── Execution Manager
     ├── Recovery Manager
     └── Verification Manager
     ↓
Specialized Agents + Local Model Router
     ├── RAG / Knowledge Agent
     ├── Vision Agent
     ├── Coding Agent
     └── Predictive Agent
     ↓
Tool Registry
     ├── Documents
     ├── Data
     ├── Python / Shell
     ├── Artifacts
     ├── Graph
     └── Telemetry
     ↓
OpenSandbox
     ↓
Docker Runtime
     ↓
Verification
     ↓
Evidence + Artifact + Audit
```

## Repository Architecture

```text
sih/
├── backend/
│   ├── backend/
│   │   ├── api/
│   │   ├── chat/
│   │   ├── models/
│   │   ├── ingestion/
│   │   ├── rag/
│   │   ├── storage/
│   │   ├── database/
│   │   ├── security/
│   │   ├── observability/
│   │   ├── orchestrator/
│   │   ├── agents/
│   │   ├── workflows/
│   │   ├── tools/
│   │   └── graph/
│   ├── tests/
│   ├── pyproject.toml
│   └── uv.lock
├── data/
│   └── lancedb/
├── infrastructure/
│   └── docker/
│       └── backend.Dockerfile
├── localGPT-main/
├── LightRAG-main/
├── OpenSandbox-main/
├── ToolOrchestra-main/
└── graphify-8/
```

## Document Intelligence

The document pipeline is:

```text
PDF / DOCX / HTML / MD / TXT
          ↓
      Parsing / OCR
          ↓
    Structure Extraction
          ↓
        Chunking
          ↓
  Metadata + Embeddings
          ↓
 LanceDB Vector + Full Text
          ↓
 Hybrid Retrieval / RRF
          ↓
 Optional Reranking
          ↓
       Evidence Set
```

The architecture reuses localGPT for ingestion/RAG primitives and LanceDB for vector/full-text storage. Chunk metadata includes `document_id`, `chunk_id`, `chunk_index`, heading information, block type, and page when available.

*Do not run the vendored localGPT server; integrate it through an application adapter.*

## Knowledge Graph

The graph represents industrial entities and relationships such as:

```text
Inspection Report
   ├── mentions → Component
   ├── generated_at → Timestamp
   └── contains → Anomaly

Component
   ├── installed_in → Equipment
   └── has_anomaly → Anomaly

Equipment
   └── has_sensor → Sensor
```

The intended graph layer uses LightRAG selectively for graph functionality. It should not replace the existing parser, chunker, vector database, or reranker. A graph-only integration should be validated before becoming a core dependency.

## Dynamic Intelligence Routing

Different tasks use different local models.

Reference roles:

```yaml
models:
  - name: solar-pro-4
    role: orchestrator
  - name: qwen2.5-coder-32b
    role: coding
  - name: qwen2-vl-7b
    role: vision
```

The model gateway should remain local-first and compatible with Ollama/vLLM-style local serving. Cloud endpoints should not be silently selected.

## Verifiable Action Engine

Every meaningful agent action follows:

```text
PERCEIVE → PLAN → ACT → VERIFY
                       │
                 ┌─────┴─────┐
                 ↓           ↓
              COMPLETE    RECOVER
                              ↓
                           REPLAN
```

An LLM claiming that an action succeeded is not proof of success. Tool execution and side effects must be inspected independently.

## Tool Registry

Initial tool families:
- `search_documents`
- `read_document`
- `extract_table`
- `analyze_csv`
- `run_python`
- `run_shell`
- `create_pdf`
- `create_docx`
- `create_pptx`
- `create_xlsx`
- `graph_query`
- telemetry/alert tools

Each tool should have an explicit schema, input validation, permission/risk metadata, resource limits, timeout, audit logging, and verification requirements.

## Sandbox & Air Gap

The execution architecture is:

```text
Backend
  ↓
OpenSandbox Adapter
  ↓
OpenSandbox Control Plane
  ↓
Docker
  ↓
Isolated Sandbox
```

Docker remains the runtime substrate.

The execution boundary must enforce default-deny egress, not merely document it.

Sandbox requirements include:
- Default-deny networking
- CPU and memory limits
- Execution timeout
- Process limits
- Filesystem isolation
- Restricted writable directories
- Output-size limits
- Image allowlisting
- Pinned image digests
- No host environment secrets
- No SSH keys
- No unrestricted host filesystem mounts
- Explicit cleanup
- Execution audit records
- Human approval for risky operations
- Docker socket warning

If OpenSandbox requires `/var/run/docker.sock`, treat the control plane as privileged infrastructure because Docker daemon access can become effectively host-level control. Use a dedicated execution host where appropriate, restrict access, pin images, and never expose host credentials to sandboxed code.

## Agents

### Orchestrator Agent
Plans, decomposes, routes, executes, recovers, verifies, and produces the final response.

### RAG / Knowledge Agent
Retrieves evidence, answers knowledge questions, produces citations, and queries structured knowledge.

### Vision Agent
Processes scanned documents, drawings, images, and visual anomalies.

### Coding Agent
Generates, debugs, executes, and validates code inside the sandbox.

### Predictive Agent
Analyzes telemetry, detects patterns, performs localized prediction/regression, and creates verifiable alerts.

*Agents must use the tool registry and must not bypass sandbox/policy controls.*

## Predictive Analysis

```text
Telemetry
   ↓
Historical Baseline
   ↓
Prediction / Anomaly Analysis
   ↓
Threshold?
 ├─ NO → Continue
 └─ YES → Alert → Agent Intervention → Verify
```

## Instantaneous Learning

Human corrections can update deterministic operational rules:

```text
Human Correction
      ↓
Deterministic Rule Update
      ↓
Re-ingestion / Memory Update
      ↓
Future Task
      ↓
Updated Behavior
```

This is intended to provide rapid adaptation without on-the-fly fine-tuning of sensitive industrial data.

## Real-Time Command UI

A WebSocket event bus should expose:
- Agent actions
- Tool execution
- Verification
- Sensor updates
- Graph changes
- Alerts
- Job-state changes
- Artifact generation
- Sandbox execution

Example event families:
`agent.action`, `tool.started`, `tool.completed`, `verification.completed`, `sensor.updated`, `alert.created`, `artifact.created`

## Deterministic Factory Simulator

A standalone simulator should generate repeatable synthetic operations:

```text
Simulator
 ├── Synthetic Sensors
 ├── Maintenance Orders
 └── Generated Inspection PDFs
              ↓
          /incoming/
              ↓
        Agentic System
```

A scripted anomaly at a known point in time makes the full demo reproducible.

## Job State Machine

Long-running jobs should have explicit state:

```text
QUEUED
  ↓
PLANNING
  ↓
RETRIEVING
  ↓
EXECUTING
  ↓
VERIFYING
  ↓
COMPLETED
```

Failure states: `FAILED`, `CANCELLED`, `TIMEOUT`, `NEEDS_APPROVAL`

Track at minimum: `request_id`, `job_id`, `execution_id`, `agent_id`, `tool_call_id`, `sandbox_id`, `artifact_id`

## Artifact Lifecycle

Artifacts are first-class outputs.

Recommended metadata:
`artifact_id`, `job_id`, `type`, `filename`, `size`, `sha256`, `created_at`, `sandbox_execution_id`, `verification_status`, `storage_path`

Typical outputs: PDF, DOCX, PPTX, XLSX, CSV, Code files

*Use deterministic libraries for office-file generation where possible.*

## Verification

Verification is a dedicated subsystem.

It should independently check:
- Evidence grounding
- Citation correctness
- Calculations
- Tool execution
- Generated artifacts
- Policy compliance
- Hallucination/groundedness

**Core rule:**
> Never treat an LLM's statement that an action succeeded as proof that it succeeded.

## Storage

The intentionally small storage architecture is:

| Store | Purpose |
| --- | --- |
| SQLite | Application state, jobs, audit |
| LanceDB | Vector + full-text retrieval |
| LightRAG / NetworkX-backed graph | Knowledge graph |
| OpenSandbox storage | Sandbox/control-plane state |

Avoid adding Redis, MongoDB, PostgreSQL, or other infrastructure unless a real deployment requirement justifies it.

## Vendor Boundaries

Vendored upstream code should remain unmodified and be accessed through thin adapters.

- **localGPT**: Production reuse: document ingestion, chunking, retrieval, hybrid search, optional reranking, groundedness primitives.
- **LightRAG**: Selective reuse: knowledge graph and graph reasoning.
- **OpenSandbox**: Production reuse: sandbox lifecycle, command/filesystem execution, network policy and isolation.
- **ToolOrchestra**: Reference only: tool/model metadata concepts. Do not pull its large RL/training stack into the production runtime without a concrete need.
- **Graphify**: Development tooling only: source-code dependency/code knowledge graph. It is not the document knowledge graph.

## Security Model

Security is an architectural requirement.

Principles:
- Local-only model access.
- Explicitly block cloud paths where strict sovereignty is required.
- Do not silently download models/dependencies.
- Default-deny sandbox egress.
- Isolate secrets.
- Authenticate services before exposing them outside localhost/trusted infrastructure.
- Audit sensitive operations.
- Require approval for high-impact actions.

## Configuration

Example:

```env
APP_HOST=127.0.0.1
APP_PORT=8000

MODEL_BASE_URL=http://127.0.0.1:11434/v1

ORCHESTRATOR_MODEL=
CODING_MODEL=
VISION_MODEL=

LANCEDB_PATH=./data/lancedb
SQLITE_PATH=./data/project117.db

ALLOW_EXTERNAL_NETWORK=false

SANDBOX_CPU_LIMIT=
SANDBOX_MEMORY_LIMIT=
SANDBOX_TIMEOUT_SECONDS=
```

Empty model configuration should fail clearly rather than silently selecting a model that triggers an external download.

## Ports

| Service | Port | Notes |
| --- | --- | --- |
| Backend | 8000 | Primary application |
| Frontend | 3000 | Planned |
| Ollama | 11434 | Local model service |
| OpenSandbox | 8090 | Example/control-plane mapping |
| localGPT server | 8001 | Do not start |
| LightRAG server | 9621 | Do not start |

Pin the final ports explicitly in the project's Compose configuration.

## Docker Compose

The root stack should stay intentionally small:
- backend
- opensandbox
- ollama (profile-gated)

Do not merge vendor Compose files into the project stack. Kubernetes is not required for the demonstration deployment.

## Frontend Direction

The frontend is intentionally not a normal website/dashboard.

**Storytelling landing page**
The first page should communicate:

```text
THE INDUSTRIAL PROBLEM
        ↓
SENSITIVE DATA + SOVEREIGNTY BARRIER
        ↓
AI MUST MOVE FROM ANSWERING TO EXECUTING
        ↓
SOVEREIGN AGENTIC WORKBENCH
        ↓
PERCEIVE → PLAN → ACT → VERIFY
        ↓
LIVE INDUSTRIAL SYSTEM
```

**3D Industrial Environment**
The main experience should contain a large interactive 3D representation of the factory/industrial environment.

The 3D layer can visualize:
- Factory/equipment
- Sensors
- Components
- Agent activity
- Alerts
- Knowledge relationships
- Data movement

The 3D model should connect to actual backend state where possible rather than being purely decorative.

**Three intelligence roles**
The experience can visually represent:
- Orchestrator / reasoning
- Coding
- Vision

as specialized intelligence modules operating on the same industrial environment.

## Demo Narrative

A strong demo should be one continuous story:
1. Show the digital factory and live telemetry.
2. Inject a deterministic anomaly.
3. Receive sensor + inspection information.
4. Perceive the situation.
5. Retrieve supporting evidence.
6. Query graph context.
7. Decompose and plan the task.
8. Execute analysis in the sandbox.
9. Generate a concrete artifact.
10. Independently verify the result.
11. Display the action trace and final verified outcome.
12. Apply a human correction and demonstrate deterministic learning.

Target visible result:
`Action completed` | `Evidence verified` | `Artifact generated` | `Policy compliant`

## Implementation Roadmap

- **Phase 0.5 — Hardening**: Fix dependency declarations. Validate Python version. Correct model defaults. Enforce egress. Remove dead/misnamed modules. Establish real tests/lint/type checking.
- **Phase 1 — Orchestrator**: Planner, Task decomposition, Router, Context manager, Execution manager, Recovery manager, Verification manager, Job state machine.
- **Phase 2 — Tool Registry**: Implement typed tools for documents, data, Python, shell, artifacts, graph, and telemetry.
- **Phase 3 — Sandbox**: Integrate OpenSandbox through a thin adapter and implement lifecycle, filesystem, networking, limits, auditing, and cleanup.
- **Phase 4 — Deliverables**: Implement deterministic PDF/DOCX/PPTX/XLSX generation with artifact metadata.
- **Phase 5 — Verification**: Implement evidence, citation, calculation, artifact, execution, and policy verification.
- **Phase 6 — Specialized Agents**: Implement RAG, vision, coding, and predictive agents.
- **Phase 7 — Demo Vertical Slice**: Build one complete end-to-end inspection/anomaly workflow.
- **Phase 8 — Security Hardening**: Strengthen authentication, authorization, sandbox isolation, secret handling, auditing, rate/resource limits, and recovery.
- **Phase 9 — Graph Memory**: Validate graph-only LightRAG integration and add multi-hop operational reasoning.
- **Phase 10 — Memory & Workflows**: Add long-term operational memory, deterministic rule updates, human correction, and workflow templates.
- **Phase 11 — Observability & Connectors**: Add metrics, tracing, execution dashboards, and only approved internal connectors.

## Testing

**Unit tests** cover: Planner, Router, Tool schemas, Policies, Retrieval, Graph, Artifact metadata, Verification.
**Integration tests** cover: Backend ↔ local model gateway, Backend ↔ LanceDB, Backend ↔ graph, Backend ↔ sandbox, Tool ↔ sandbox, Artifact ↔ verifier.
**Security tests** cover: Egress denial, Unauthorized tools, Filesystem isolation, Resource limits, Timeouts, Secret isolation, Image allowlisting.

**End-to-end test:**
```text
Upload PDF → Index → Retrieve → Plan → Execute → Generate Artifact → Verify → Return Result
```

Before declaring a phase complete:
`uv sync`, `pytest`, `ruff check .`, `pyright`

## Air-Gapped Deployment

A strict deployment should work with the external network disabled.

Before entering the air-gapped environment:
- Provision required container images.
- Pin image versions/digests.
- Provision local models.
- Provision required Python dependencies.
- Cache required model artifacts.
- Test with networking disabled.
- Confirm no dependency attempts external downloads.
- Confirm sandbox egress denial.
- Confirm all required communication uses approved local endpoints.

Acceptance criterion:
`External Network = OFF → System still works`

## Risks

- **R1 — LightRAG graph-only integration**: Validate that unwanted vector/retrieval behavior can be bypassed.
- **R2 — Docker socket privilege**: Treat Docker daemon access as a privileged security boundary.
- **R3 — Model downloads**: Pre-cache required models and dependencies for air-gapped deployments.
- **R4 — Upstream drift**: Keep vendor integrations behind adapters.
- **R5 — Dependency weight**: Avoid unnecessary RL/training stacks.
- **R6 — Overengineering**: Do not add infrastructure before the end-to-end vertical slice proves the need.

## Architectural Rules

- One responsibility per subsystem.
- Vendors are accessed through adapters.
- Do not build a second RAG stack.
- Use one sandbox system: OpenSandbox + Docker.
- Verify side effects independently.
- Local by default.
- Default deny.
- Test continuously.
- Use human approval for risky operations.
- Keep demonstrations deterministic.

## Acceptance Criteria

- **Sovereignty**: No external AI API is required. Sensitive processing stays local. Sandbox egress is denied by policy.
- **Intelligence**: Tasks can route to appropriate local models. Documents can be retrieved using hybrid search. Structured relationships can be queried.
- **Agency**: The orchestrator decomposes tasks. Agents invoke tools. Code executes inside the sandbox. Artifacts are generated.
- **Verification**: Evidence is checked. Calculations can be reproduced. Artifacts are validated. Execution results are independently verified.
- **Operations**: The simulator produces repeatable events. The UI receives real-time events. Operators can inspect execution traces.
- **Learning**: Human corrections can update deterministic rules/knowledge. Future tasks use the updated knowledge.

## What This Project Is Not

This project should not become:
- A generic chatbot
- A second RAG implementation
- A second document parser
- A second reranker
- An unrestricted code interpreter
- A cloud-first agent platform
- An RL training platform
- A Kubernetes-heavy demo
- A collection of unnecessary databases
- A fake connector ecosystem
- A system that trusts unverified LLM-generated artifacts

## Final Product Definition

The Sovereign On-Premise Agentic AI Workbench is a local-first industrial AI execution platform combining:

```text
Local Models + Document Intelligence + Hybrid Retrieval + Knowledge Graph + Agent Orchestration + Sandboxed Execution + Deterministic Artifacts + Independent Verification + Real-Time Telemetry + Controlled Learning
```

The final objective is not simply an AI that can answer: *"What happened?"*
It is an AI system that can progress safely to: *"What should be done?"*
then: *"I performed the approved action inside an isolated environment."*
and finally: *"Here is the evidence proving what happened, what I did, and that the result was verified."*

## Status

| Area | Status |
| --- | --- |
| Architecture | Defined |
| Backend | Active implementation |
| Sandbox | OpenSandbox + Docker |
| Model serving | Local-first / Ollama-compatible |
| Retrieval | localGPT + LanceDB architecture |
| Graph | LightRAG selective integration |
| Frontend | Storytelling + 3D + real-time UI |
| Simulator | Deterministic factory simulation |
| Verification | Dedicated subsystem |
| Deployment | On-premise / air-gapped capable |

## License

This repository should use the license selected by the project team. Third-party components retain their respective upstream licenses.

**Core Principle**: Sovereign infrastructure. Whole-operation context. Verified execution. Live learning.

---

# Project 117 — Sovereign Industrial AI for Manufacturing Operations

> "From Information to Action. On-Prem. In Your Hands."

This README is the operating contract for the three engineers (and their coding agents) building this repo: **Frontend**, **Backend**, and **Mobile**. It exists to answer one question whenever anyone — human or agent — is unsure what to touch next: *"Is this mine to edit?"*

Read this fully before writing a single line of code. Agents working inside this repo should treat this document as a system prompt, not a suggestion.

---

## 1. The one rule everything else follows

**You own your folder. You do not edit anyone else's.** Integration happens through a shared, versioned contract layer (`packages/`) — not through one dev reaching into another dev's code to "just fix it quickly."

If a task seems to require touching a file outside your assigned folders, that is not a green light — it's a stop sign. See [Section 5: Contract-Change Protocol](#5-contract-change-protocol).

This constraint is deliberate. Three agents editing the same files in parallel is how repos rot. Three agents each owning a clean boundary, talking only through typed contracts, is how you get a system that integrates "spectacularly" instead of accidentally.

---

## 2. Team & folder ownership

### 2.1 Frontend Dev — Web Dashboard

**Owns exclusively:**
```text
apps/web/**
```
Everything under `apps/web` — pages, components, hooks, stores, styling, the chat UI, the approvals UI, the equipment/work-order/analytics dashboards shown in the architecture mockup.

**Reads (never writes):**
```text
packages/types/**        # contract types — source of truth for API shapes
packages/api-client/**   # generated/maintained client to call the backend
packages/ui/**           # shared design system components
packages/config/**
```

### 2.2 Backend Dev — AI Engine, API, Infra

**Owns exclusively:**
```text
backend/**                # api, orchestrator, agents, workflows, memory,
                           # models, tools, connectors, ingestion,
                           # deliverables, verification, security, observability
database/**
infrastructure/**
packages/types/**          # backend DEFINES the contract
packages/api-client/**     # backend maintains the client frontend/mobile consume
packages/validation/**
packages/events/**
workflows/mrpl/**
workflows/examples/**
data/**
scripts/**
```

The backend dev is the **contract owner**. Every type in `packages/types` and every method in `packages/api-client` exists because the backend implemented the corresponding route, agent, or workflow. Nothing gets added to the contract speculatively — contract changes are driven by real backend capability, and are the *one* place backend writes on behalf of the other two devs.

### 2.3 Mobile Dev — Field Technician App

**Owns exclusively:**
```text
apps/mobile/**
```
Home, Equipment, Scan, WorkOrders, SOP, ReportIssue, VoiceAssistant, Notifications screens, camera/scanner/voice services, and offline sync.

**Reads (never writes):**
```text
packages/types/**
packages/api-client/**
packages/config/**
```

### 2.4 Shared / not owned by any single dev

```text
README.md, LICENSE, .gitignore, .env.example, docker-compose.yml, Makefile,
package.json, pnpm-workspace.yaml
docs/**            (each dev writes docs/<their-area>/ only — see 2.5)
tests/**           (each dev owns tests for their own surface; tests/integration
                    is co-written and run at integration checkpoints — see Section 7)
```

### 2.5 Docs ownership breakdown

| Path | Owner |
|---|---|
| `docs/architecture/system.md`, `orchestrator.md`, `agents.md`, `memory.md`, `security.md`, `deployment.md` | Backend |
| `docs/api/**` | Backend (generated from routes) |
| `docs/workflows/**` | Backend |
| `docs/security/**` | Backend |
| `docs/demo/**` | Shared — each dev appends their demo-flow section under their own subheading |
| `docs/decisions/ADR-*.md` | Whoever proposes the decision; must be reviewed by the other two before merge |

---

## 3. The contract layer — how three isolated folders become one system

```text
packages/types/        ← the nouns everyone agrees on (Agent, Workflow, Equipment, WorkOrder, Document, Memory)
packages/api-client/   ← the verbs everyone agrees on (typed functions calling backend/api routes)
packages/validation/   ← shared zod/schema validators used by both backend routes and frontend/mobile forms
packages/events/       ← shared websocket/event payload shapes (alerts, work-order updates, chat streaming)
```

**Rule of engagement:**
- Backend implements a capability → backend adds/updates the type in `packages/types` and the client method in `packages/api-client` → backend bumps the package version → frontend and mobile pull the update and build against it.
- Frontend or mobile **never** invents a shape and hopes backend matches it later. If the contract doesn't have what you need, that's a contract-change request, not a local workaround.
- No dev mocks a fake shape "temporarily" in their own folder and forgets to reconcile it. Mocks are allowed only behind an interface that matches `packages/types` exactly, so swapping the mock for the real client is a one-line change.

---

## 4. Agent operating rules

If you are an AI coding agent assigned to one of these three areas, these rules apply to you literally, not as suggestions:

**Frontend agent:**
- ✅ Read/write anywhere under `apps/web/`
- ✅ Read (never write) `packages/types`, `packages/api-client`, `packages/ui`, `packages/config`
- ❌ Never write to `backend/`, `apps/mobile/`, `infrastructure/`, `database/`
- ❌ Never edit `packages/types` or `packages/api-client` even to "fix" a mismatch — file a contract-change request instead

**Backend agent:**
- ✅ Read/write anywhere under `backend/`, `database/`, `infrastructure/`, `packages/types`, `packages/api-client`, `packages/validation`, `packages/events`, `workflows/`, `data/`, `scripts/`
- ❌ Never write to `apps/web/` or `apps/mobile/` — if the UI needs to change to consume a new capability, that's a note to the frontend/mobile dev, not a backend edit
- ⚠️ Any change to `packages/types` or `packages/api-client` is a breaking-change candidate — must be flagged in the PR description and must bump a version marker

**Mobile agent:**
- ✅ Read/write anywhere under `apps/mobile/`
- ✅ Read (never write) `packages/types`, `packages/api-client`, `packages/config`
- ❌ Never write to `backend/`, `apps/web/`, `infrastructure/`, `database/`
- ❌ Never edit the contract packages — file a contract-change request instead

**All agents:**
- Every commit touches only your owned paths, plus (if applicable) an entry in your `STATUS.md` (see Section 6).
- If a task genuinely can't be completed without touching another folder, stop, write the request, and move to your next queued deliverable instead of blocking.

---

## 5. Contract-change protocol

When frontend or mobile needs something the contract doesn't yet expose:

1. Create a file: `packages/types/_requests/<your-name>-<short-description>.md`
2. Fill in:
   ```md
   ## Requested by: [frontend|mobile]
   ## Needed capability: <one sentence>
   ## Proposed shape:
   <sketch of the type or client method you think you need>
   ## Blocking which deliverable: <ID from Section 8>
   ```
3. Continue working on anything else in your queue that isn't blocked by this.
4. Backend agent picks up open requests in `packages/types/_requests/` as part of its own loop (Section 6), implements the real capability, updates `packages/types`/`packages/api-client`, deletes the request file, and notes it in `backend/STATUS.md`.

This is the *only* sanctioned cross-folder communication path. No Slack-message-style "hey can you just add a field" that bypasses the written trail — the request file **is** the audit trail for why the contract changed.

---

## 6. The fixed-deliverable loop

Every dev's agent works through an ordered queue of deliverables (Section 8). For **each** deliverable, run this loop until it terminates:

```text
LOOP for current deliverable D:
  1. Read D's Definition of Done (DoD) checklist in full before writing code.
  2. Implement/modify code strictly inside your owned folder(s).
  3. Run the test suite scoped to your surface (unit + your app's integration tests).
  4. Self-check: for each DoD item, mark it PASS or FAIL with evidence
     (test output, screenshot, log line — not just "looks done").
  5. IF any DoD item is FAIL:
       → identify the specific gap
       → return to step 2
  6. IF all DoD items are PASS:
       → update <your-folder>/STATUS.md:
           "D<id>: DONE — <one-line summary> — <date>"
       → commit with message "feat(D<id>): <deliverable title>"
       → open a PR referencing D<id>
       → IF this deliverable required a new contract capability that doesn't
         exist yet → file a contract-change request (Section 5) INSTEAD OF
         editing packages/ yourself, and mark D<id> as BLOCKED, not DONE
       → advance to next deliverable in queue
END LOOP

EXIT CONDITION for the whole project:
  All deliverables in Section 8 marked DONE in all three STATUS.md files
  AND the Section 7 integration checkpoints all pass.
```

Each app folder (`apps/web/`, `backend/`, `apps/mobile/`) gets its own `STATUS.md` at its root, created on day one, containing the deliverable queue for that owner with checkboxes. This is the one file each agent updates constantly — it's how the other two devs (and any human lead) see progress without reading someone else's code.

---

## 7. Integration checkpoints ("the spectacular part")

Individual perfection in isolated folders means nothing until the seams hold. Three fixed checkpoints, each gated on specific deliverables being DONE:

**Checkpoint 1 — Contract handshake** *(after B1, B7, F1, M1 are DONE)*
Frontend and mobile can both successfully call at least one real backend route through `packages/api-client` and render real (not mocked) data. Run: `pnpm test:integration -- --grep "handshake"`.

**Checkpoint 2 — The core demo flow, end to end** *(after B2–B6, F2–F3, M2 are DONE)*
A scanned inspection report, uploaded from either the mobile Scan screen or the web Approvals page, flows through: OCR/vision extraction → SOP cross-check → agent draft → generated Word approval note visible and downloadable from the web dashboard, with the mobile app receiving a real-time notification that the note is ready for review. This is the literal problem-statement demo requirement — treat it as non-negotiable.

**Checkpoint 3 — Full system rehearsal** *(after all deliverables in Section 8 are DONE)*
Run the entire judge-facing demo script back to back with `scripts/verify-zero-egress.ts` monitoring in parallel, proving no external network call fires at any point:
1. Model auto-selection shown live across two task types (coding + document task)
2. Inspection report → approval note, end to end (Checkpoint 2's flow)
3. A coding task executed and verified in the Python sandbox
4. A multimodal task (scanned drawing or handwritten note understood)
5. Zero-egress proof visible on screen the entire time

No individual dev "owns" Checkpoint 3 — it's run together, and it is the actual Definition of Done for the project, not any single folder's checklist.

---

## 8. Deliverable queues

### 8.1 Backend deliverables

| ID | Deliverable | Definition of Done |
|---|---|---|
| B1 | Model gateway + router | ≥2 open-weight models registered; task classifier correctly routes a coding prompt to the coding model and a document prompt to the reasoning/vision model in test suite; adding a third model requires only a config entry, no code change |
| B2 | Agent orchestrator loop | Plan → act → observe loop implemented in `orchestrator/`; can call at least 2 tools (file read/write, sandboxed code exec) across multiple turns without human intervention; full trace logged to `observability/agent-traces/` |
| B3 | OCR/vision ingestion pipeline | Scanned inspection report (from `data/demo/inspection-reports/`) produces structured findings JSON; handles at least one handwritten sample without failing |
| B4 | Local knowledge base / RAG grounding | SOPs and manuals in `data/demo/sop/` and `manuals/` are chunked, embedded, and queryable; agent cites the specific SOP clause when flagging an out-of-spec finding |
| B5 | Approval-note generation | `deliverables/generators/inspection.ts` produces a real, correctly formatted `.docx` file via `tools/office/docx.ts`, populated from B3+B4 output, not placeholder text |
| B6 | Zero-egress verification | `scripts/verify-zero-egress.ts` runs alongside the full B2–B5 flow and reports zero outbound connections; result is machine-checkable, not just a manual claim |
| B7 | API gateway surface | Routes for `chat`, `workflows`, `agents`, `documents`, `equipment`, `work-orders`, `approvals` implemented and match `packages/types` exactly; auth + RBAC middleware enforced on all of them |

### 8.2 Frontend deliverables

| ID | Deliverable | Definition of Done |
|---|---|---|
| F1 | Dashboard shell | Nav matches architecture mockup (Home, Chat, Work Orders, Equipment, Analytics, Knowledge, Settings); routes exist even if pages are stubs |
| F2 | Chat interface | Streams real responses from `backend/api/routes/chat.ts` via websocket, not a static mock |
| F3 | Approvals page | Upload a scanned report → trigger the B2–B5 workflow → preview the generated approval note inline → download the `.docx` |
| F4 | Equipment + alerts panel | Live alerts list (e.g. "High vibration detected") sourced from `packages/events`, matching the mockup's Active Alerts panel |
| F5 | Real-time layer | Websocket connection in `lib/websocket.ts` reconnects gracefully and reflects backend state changes without a page refresh |
| F6 | Knowledge browser | Documents and graph views under `knowledge/` render real ingested content from B4, with search |

### 8.3 Mobile deliverables

| ID | Deliverable | Definition of Done |
|---|---|---|
| M1 | App shell | All eight screens (Home, Equipment, Scan, WorkOrders, SOP, ReportIssue, VoiceAssistant, Notifications) navigable, even as stubs |
| M2 | Scan screen | Camera captures a photo of an inspection report or QR/barcode on equipment, uploads to backend ingestion pipeline, and shows extraction status |
| M3 | Voice assistant | Voice query hits the same chat API as F2, returns a spoken or text response |
| M4 | Offline sync | Actions taken with no plant network connectivity queue locally and sync automatically once connectivity returns, verified by a manual airplane-mode test |
| M5 | Report issue → work order | Field technician can report an issue that creates a real work order visible on the web dashboard's Work Orders page |

---

## 9. Setup

```bash
cp .env.example .env
pnpm install
docker-compose up -d          # spins up local models, databases, vector store
pnpm --filter web dev         # frontend
pnpm --filter mobile start    # mobile
pnpm --filter backend/api dev # backend
```

Each dev works only inside their `pnpm --filter` scope day to day. Full-stack runs (`docker-compose up`) are for integration checkpoints, not daily development.

---

## 10. Branching & PR conventions

- Branch names: `frontend/D<id>-short-name`, `backend/D<id>-short-name`, `mobile/D<id>-short-name`
- One deliverable per PR — no bundling F2 and F3 into one PR
- PR description must include the DoD checklist from Section 8 with each item checked and evidence linked
- Any PR touching `packages/` requires review from at least one of the other two devs before merge, since it's a shared contract change
- Merges to `main` only happen at integration checkpoints (Section 7), not continuously — feature branches can pile up against `develop` in between

---

## 11. Appendix — full folder ownership map

```text
apps/web/**                → FRONTEND
apps/mobile/**             → MOBILE
backend/**                 → BACKEND
packages/types/**          → BACKEND (writes) / FRONTEND, MOBILE (read-only)
packages/api-client/**     → BACKEND (writes) / FRONTEND, MOBILE (read-only)
packages/ui/**             → FRONTEND (writes) / MOBILE may fork patterns, doesn't share code
packages/validation/**     → BACKEND
packages/events/**         → BACKEND
packages/config/**         → BACKEND (writes) / all read
database/**                → BACKEND
infrastructure/**          → BACKEND
workflows/**                → BACKEND
data/**                     → BACKEND
tests/unit, integration,
  agents, workflows, memory,
  security, connectors,
  models, evaluation        → BACKEND (owns), FRONTEND/MOBILE contribute
                              their own app-level tests under
                              apps/web/**/*.test.* and apps/mobile/**/*.test.*
docs/architecture/**        → BACKEND
docs/demo/**                → SHARED (each dev's own subsection)
scripts/**                  → BACKEND
README.md, LICENSE, etc.    → SHARED, changes need all-three sign-off
```

When in doubt, this table wins. When this table doesn't cover something, default to: *if it's not explicitly yours, it's a contract-change request, not an edit.*
