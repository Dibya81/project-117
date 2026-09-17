# Project 117 — Repository Audit & Integration Decisions

Status: accepted · Date: 2026-09-09

> Historical audit. Only the localGPT integration remains vendored (at
> `vendor/localGPT`); `ToolOrchestra-main/` was removed per
> `docs/decisions/0002-remove-toolorchestra.md`, and the other repositories are
> no longer present in the working tree. The console port is `3017`, not the
> `3000` guessed below.

## 1. The five vendored repositories

All five were downloaded as GitHub archives (no `.git` directories) and, at
audit time, sat unmodified at the workspace root. They are vendored third-party
code; the backend integrates with them through adapters, never by editing them.

| Repo | Verified purpose (from source) | Role in Project 117 |
|---|---|---|
| `localGPT-main/` | Local document intelligence: Docling ingestion + OCR, LanceDB vector+FTS hybrid retrieval with RRF, cross-encoder rerank, query decomposition, semantic cache, verification. Python, stdlib HTTP RAG API (:8001), backend gateway (:8000), SQLite. | **Primary ingestion + RAG engine** (Phase 3/4). Imported as a Python library. |
| `LightRAG-main/` | Graph-based RAG: per-chunk entity/relation extraction, dual-layer KG + vector, 4 pluggable storage backends, role-based LLMs (EXTRACT/QUERY/KEYWORD/VLM), 5 query modes, FastAPI server (:9621), 542 test files. Core has **no torch/transformers dependency**. | **Knowledge-graph memory** (Phase 5): graph extraction over the same corpus; multi-hop industrial reasoning. Not a second vector store. |
| `OpenSandbox-main/` | General-purpose sandbox platform: FastAPI control plane (:8080), Docker/K8s runtimes, lifecycle/command/filesystem APIs, per-sandbox egress policy + ingress proxy + credential vault, gVisor/Kata/Firecracker, multi-language SDKs, MCP, CLI. 158 test files. | **Isolated code/artifact execution** (Phase 9). Called via its Python SDK. |
| `ToolOrchestra-main/` | NVIDIA **research/RL-training** repo for a tool-orchestrator model (verl training, HLE/FRAMES/τ²-Bench eval harnesses, `tools.json`, prompt templates). Not embeddable as a runtime. | **Reference only**: orchestration prompt template + the `nvidia/Orchestrator-8B` model (servable later via vLLM/Ollama as the orchestrator's planner model). No code reuse. **Removed — see ADR 0002.** |
| `graphify-8/` | Code knowledge-graph CLI/MCP: tree-sitter AST → `graph.json`, communities, `query/path/explain`, HTML viz, optional Neo4j/FalkorDB push. Code pass is fully local; doc pass can call cloud LLMs. | **Dev tooling only**: maps `backend/` code; its `graph.html` + MCP-serve patterns are reference for future graph visualization. Not in the production document path. |

## 2. Conflict analysis

- **Overlap:** localGPT and LightRAG both parse/chunk/embed/retrieve. Resolved:
  localGPT owns the canonical RAG pipeline (its page/section/chunk metadata is
  what the citation requirement needs); LightRAG contributes graph extraction
  and graph-query only.
- **Dependencies:** localGPT pins `torch==2.4.1, transformers==4.51.0`;
  LightRAG core needs neither; OpenSandbox needs docker/psycopg/redis.
  → localGPT's pinned stack lives in the backend runtime env; OpenSandbox runs
  in its own container.
- **Ports:** localGPT gateway :8000 (we take :8000 for our gateway and run
  localGPT's RAG API in-process or on :8001), LightRAG server :9621,
  OpenSandbox :8080 (also graphify's MCP-HTTP default — graphify is on-demand
  only), Ollama :11434, console :3017. No conflicts at these defaults.
- **Databases:** localGPT SQLite + LanceDB; LightRAG in-memory/file (or
  Postgres/Neo4j/…); OpenSandbox Postgres + Redis. Consolidation decision:
  **one PostgreSQL** (relational data: users/sessions/documents/artifacts/
  audit/jobs) + **LanceDB** (RAG vectors) + LightRAG graph storage (file-based
  Phase 1 → Postgres/pgvector later). No Neo4j/Milvus/Redis "because they
  appear in AI architectures".
- **Models:** all repos speak OpenAI-compatible/Ollama → one shared local
  Ollama (+ optional vLLM) serves localGPT generation, LightRAG roles, and the
  future Orchestrator-8B. HF embedder/reranker weights must be pre-cached for
  air-gapped installs.
- **Docker:** vendor compose files are NOT combined. One Project 117
  `docker-compose.yml` pins the services we actually run.
- **Security:** LightRAG server binds 0.0.0.0 with auth off by default →
  bind localhost or enable API-key auth. localGPT has no auth → localhost
  only. OpenSandbox control plane touches the Docker socket → dedicated
  user, restricted images, default-deny egress, no host secrets into
  sandboxes. graphify's doc pass may call cloud LLMs → excluded from the
  document path.

## 3. Approved decisions

1. **Backend language: Python (FastAPI).** All five repos are Python; the
   backend imports localGPT + LightRAG as libraries and calls OpenSandbox via
   its Python SDK. No duplicated schemas, no HTTP-wrapping of every component.
2. **Workspace layout: the current root IS the `sih/` workspace.** Repos stay
   in place, unmodified; the backend lives in `backend/`.
3. **RAG strategy: localGPT RAG + LightRAG graph.** localGPT owns
   ingestion/embeddings/retrieval/citations; LightRAG runs graph extraction on
   the same corpus for graph memory. No duplicate vector stores or embedding
   pipelines.

## 4. What we will NOT build

- No second RAG engine, vector store, or embedding pipeline (localGPT owns it).
- No homemade sandbox (OpenSandbox).
- No re-implementation of graph-RAG (LightRAG).
- No tool-orchestration framework reimplementation (our orchestrator is thin;
  ToolOrchestra's *model* is an optional later add-on).
- No localGPT/LightRAG/graphify UIs in the product path.
- No fake SAP/CMMS/historian/DMS connectors (interfaces + mocks only).

## 5. Implementation order

Phase 0 audit ✅ → Phase 1 foundation (this) → Phase 2 model gateway →
Phase 3 ingestion → Phase 4 RAG → Phase 5 graph memory → Phases 6–8
orchestrator/agents/tools → Phase 9 sandbox → Phases 10–11
deliverables/verification → Phases 12–17 security/connectors/memory/
workflows/observability/database → Phases 18–19 tests + end-to-end demo.