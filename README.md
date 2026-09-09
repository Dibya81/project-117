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
