# Project 117 — Backend

Sovereign, local, agentic industrial AI backend (Python / FastAPI).

## Run

```bash
# from the repository root — pyproject.toml, uv.lock and tests/ live there,
# and `backend.*` only imports from here.
uv sync
uv run uvicorn backend.api.src.main:create_app --factory --host 127.0.0.1 --port 8000
```

Interactive docs: <http://127.0.0.1:8000/docs> · Health: <http://127.0.0.1:8000/health>

Phase 1 binds to `127.0.0.1` and performs **no authentication** (auth/RBAC
arrives in Phase 12). Do not expose it to a network yet.

## API reference

| Method | Path | Status | Phase |
|---|---|---|---|
| GET | `/health` | ✅ real (db, model backend, uploads checks) | 1/2 |
| GET | `/api/metrics` | ✅ real (in-memory counters/timings) | 1 |
| GET | `/api/models` | ✅ real (served models + role mapping) | 2 |
| POST | `/api/chat` | ✅ real (model gateway; no RAG yet) | 2 |
| POST | `/api/chat/stream` | ✅ real (SSE streaming) | 2 |
| POST | `/api/documents/upload` | ✅ real (validate → store → audit) | 1 |
| GET | `/api/documents` | ✅ real | 1 |
| GET | `/api/documents/{id}` | ✅ real | 1 |
| DELETE | `/api/documents/{id}` | ✅ real (file + metadata + audit) | 1 |
| POST | `/api/documents/{id}/reindex` | ✅ real (localGPT: parse → OCR → chunk → embed → LanceDB+FTS) | 3 |
| POST | `/api/search` | ✅ real (localGPT hybrid: vector+FTS → RRF → optional rerank → citations) | 4 || GET | `/api/agents` | ✅ real (registry; empty until Phase 7) | 1 |
| POST | `/api/agents/run` | ⏳ 501 | 7 |
| GET | `/api/workflows` | ✅ real (registry; empty until Phase 15) | 1 |
| POST | `/api/workflows/run` | ⏳ 501 | 15 |
| POST | `/api/tools/execute` | ⏳ 501 | 8/9 |
| POST | `/api/artifacts/generate` | ⏳ 501 | 10 |
| GET | `/api/artifacts/{id}` | ⏳ 501 | 10 |
| GET | `/api/audit/{id}` | ✅ real (audit events) | 1 |
| GET | `/api/audit` | ✅ real (filtered listing) | 1 |

**Chat in Phase 2 is direct-to-model** (no document grounding). To enable it,
set `P117_REASONING_MODEL` to one of the models listed by `GET /api/models`.

**Phase 4 adds document grounding**: send `"use_rag": true` (and optionally
`document_ids`) to `/api/chat` or `/api/chat/stream` and the turn retrieves
evidence through the hybrid index first. The model is instructed to answer
only from the evidence and cite it as `[S1]`, `[S2]`; the evidence chunks
(with `citation: {document_id, page, heading_path, block_type, chunk_index}`)
are returned in the response payload — or as an SSE `evidence` event between
`start` and the first `delta`. Grounding is best-effort: with nothing indexed
the turn answers ungrounded instead of failing.

Every 501 returns `{"error": {"code": "not_implemented", "phase": N, "message": "..."}}`
— endpoints are real, their phases are not.

## Layout

```
backend/
├── backend/
│   ├── api/            # routers + error envelope
│   ├── orchestrator/   # result envelope (engine lands Phase 6)
│   ├── agents/         # spec + registry (agents land Phase 7)
│   ├── workflows/      # registry (engine lands Phase 15)
│   ├── models/         # model roles + gateway + router
│   │   └── providers/  # pluggable backends (OpenAI-compatible: Ollama/vLLM)
│   ├── chat/           # sessions (in-memory) + turn/streaming service
│   ├── ingestion/      # Phase 3: staging → localGPT adapter → orchestration
│   ├── rag/            # Phase 4: hybrid retrieval adapter + service (citations)
│   ├── security/       # audit service + egress policy (auth lands Phase 12)
│   ├── observability/  # metrics registry + request middleware
│   ├── storage/        # document file + metadata storage
│   ├── database/       # SQLAlchemy engine/session/models
│   ├── config.py       # P117_* env-driven settings
│   └── main.py         # app factory
├── tests/              # pytest suite
└── pyproject.toml      # uv-managed
```

## Ingestion (Phase 3)

`POST /api/documents/{id}/reindex` runs the vendored localGPT pipeline
(docling parse → OCR when needed → chunk → embed → LanceDB vectors + FTS
index). Design points:

- **No duplicate pipeline.** Parsing/chunking/embedding/indexing belong to
  localGPT; `backend/ingestion/` only stages files and orchestrates state.
- **UUID↔index bridging.** localGPT derives `document_id` from the file
  basename, so uploads are staged as `<uuid><ext>` symlinks — LanceDB rows
  resolve back to `documents.id` for citations.
- **Embeddings stay local.** The default embedder is an Ollama tag
  (`nomic-embed-text:latest`). HuggingFace paths work too but download
  weights on first use — avoid for air-gapped installs.
- **Citation metadata preserved.** Every chunk row carries `document_id`,
  `page`, `heading_path`, `block_type`, `chunk_index` — exactly what the
  Phase 4 evidence/citation layer will cite.
- Document status flow: `stored → indexing → indexed | failed` (with
  `last_index_error` in metadata), all audited.

End-to-end check against a live stack:

```bash
make run   # with P117_EMBEDDING_MODEL served by Ollama
uv run python ../scripts/smoke_phase3.py
```

## Retrieval (Phase 4)

`POST /api/search` runs the vendored localGPT `MultiVectorRetriever` over the
same LanceDB table ingestion fills — vector leg + full-text leg fused with
reciprocal rank fusion (`hybrid`, `vector_only` or `fts_only` mode), then an
optional rerank when `P117_RERANKER_MODEL` is configured. Design points:

- **No duplicate retrieval.** Search legs, fusion, embedder-mismatch guards
  and reranker loading all belong to localGPT; `backend/rag/` only bridges
  identity and orchestration.
- **UUID↔index bridging, both directions.** Requests scope by UUID
  (`document_ids`) and the service compiles them to the staged basenames
  (`<uuid><ext>`) the index keys; results map back to UUIDs with original
  filenames attached for citations.
- **Fail loud.** A filter that cannot be compiled is a 422, never a silently
  unfiltered search; a scope naming an unknown/not-indexed document is a
  404/409 with the offending ids — not an empty result.
- **Filters are localGPT's DSL.** `filters` accepts the vendored
  `compile_filters` surface (`document_id`, `document_name`, `chunk_id`,
  `chunk_index`) — the same validated, deterministic compiler the vendor
  uses. No free-string where-clauses cross the API.
- Reranking re-scores the top fused candidates; it is a no-op while
  `P117_RERANKER_MODEL` is unconfigured (the default local setup).

End-to-end check against a live stack:

```bash
make run   # with P117_EMBEDDING_MODEL + P117_REASONING_MODEL served by Ollama
uv run python ../scripts/smoke_phase4.py
```

## Tests

```bash
uv run pytest -q
uv run ruff check backend tests
```

## Phase roadmap

| Phase | Content | Status |
|---|---|---|
| 1 | Foundation | ✅ |
| 2 | Model gateway + router (Ollama → vLLM) | ✅ |
| 3 | Document ingestion (localGPT adapter) | ✅ |
| 4 | Hybrid RAG + citations (localGPT) | ✅ |
| 5 | Graph memory (LightRAG) | pending |
| 6–8 | Orchestrator / agents / tool registry | pending |
| 9 | Sandbox (OpenSandbox adapter) | pending |
| 10–11 | Artifacts / verification | pending |
| 12–17 | Security / connectors / memory / workflows / observability / database | pending |