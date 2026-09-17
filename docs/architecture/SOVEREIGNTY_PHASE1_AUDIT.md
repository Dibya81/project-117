# Sovereign Workbench — Phase 1 Architecture Audit

**Status:** Phase 1 complete. **No code changed.**
**Method:** read the actual tree and grepped the real implementations. Every claim
below cites a path or a command result.

> **Phase 2 note (implementation).** Gaps 1, 2, 4 and 5 below have since been
> built, in the order §4 recommended. Where each one lives now:
>
> | Gap | Implementation |
> |---|---|
> | 1 tamper-evident audit chain | `backend/security/audit/audit_chain.py` (chain, migration, verifier), wired into `AuditService`; `GET /api/audit/integrity`; `AuditChainChecker` in `backend/verification/` |
> | 2 Ed25519 artifact signing | `backend/security/signing.py`, `ArtifactService(signing_key=…)`, `backend/security/verify_artifact.py` + `scripts/verify_artifact` |
> | 4 Sovereignty Center | `apps/web/src/app/console/sovereignty/page.tsx` + `SentinelStreamPanel` (lazy) |
> | 5 network event stream | `backend/security/network/sentinel_stream.py`, emitted from the existing `record_decision()`; `GET /api/network/stream` |
> | 3 clearance model | **not built** — still needs the design decision §4 asks for |
> | 6 nftables / sandbox isolation | **not built** — Linux deployment task; shown as PLANNED in the UI |
>
> Gap 3 and gap 6 remain open exactly as this audit recommended. §5's
> prohibitions were honoured: no second audit system, monitor, event bus or
> verification concept was created, and `backend/simulation/**` was not modified.

---

## 0. The finding that governs this whole plan

**The brief asks for at least six subsystems that already exist and work.**

Its own rule says: *"Do NOT create duplicate: orchestrators, RAG systems, tool
registries, model routers, audit systems, permission systems, event systems."*
Auditing first is therefore not a formality — building the brief as written would
have violated its primary constraint on six counts.

| Brief section | What it asks for | What already exists |
|---|---|---|
| §9 LAYER 2 | Orchestrator-level egress policy | `backend/security/network/egress_policy.py` — `check_and_record()` enforces a policy and raises `EgressBlocked` |
| §10 | Network Sentinel event stream | `backend/security/network/network_monitor.py` — `record_decision()` already records every allow/block |
| §4 | Structured tool registry + execution loop | `backend/tools/` — 19 tools across `builtin/ files/ materials/ office/ python/`, permission-gated |
| §3 | Agent plan → tool loop → artifact | `backend/orchestrator/` + `backend/deliverables/generators/` (docx, pdf, pptx, report, analysis, inspection, maintenance) |
| §5 | Multimodal ingestion | `backend/ingestion/{document,indexing,multimodal}/` |
| §6 | Model routing | `backend/models/{coding,domain,embeddings,gateway}/` with role-based resolution |
| §7 | RBAC | `backend/security/rbac/` + route-prefix permission middleware |

Egress enforcement alone already has **two dedicated test files**
(`tests/unit/test_egress.py`, `test_egress_enforcement.py`).

## 1. Genuinely missing — the real work

| # | Gap | Evidence it is missing |
|---|---|---|
| 1 | **Tamper-evident audit chain** | Audit is durable (SQLite `audit_events`) but **not hash-linked**. `grep -E "prev\|previous\|hash\|chain" backend/security/audit/audit_log.py` → **no matches**. `event_store.py` itself notes it is *not* "retained, tamper-evident". |
| 2 | **Ed25519 artifact signing** | `grep -rln "ed25519\|Ed25519\|sign(" backend/ --include=*.py` → only `mobile_auth.py`, which is HMAC for mobile tokens. No artifact signing exists. |
| 3 | **Clearance metadata on documents/chunks** | `grep -rn "CLEARANCE\|clearance"` → only false positives ("bearing clearance limits"). No permission-before-retrieval model. |
| 4 | **Sovereignty Center UI** | No `/console/sovereignty` route. Security posture is only visible as JSON at `/health` and a panel on `/console/admin`. |
| 5 | **Real network event stream to the UI** | `record_decision()` records, but does not emit an SSE event the console can subscribe to. |
| 6 | **OS-level egress (LAYER 1)** | Not present. Also **not achievable on this machine** — nftables/iptables are Linux; the dev host is macOS. |

## 2. Environment constraints that change the plan

| Constraint | Consequence |
|---|---|
| **macOS host** | Brief §9 LAYER 1 (nftables/iptables) is **not implementable here**. It is a Linux deployment-time task, not a code change. |
| **OpenSandbox is not running** | Any `sandbox_command` action returns `ActionOutcome(status="blocked", "ACTION BLOCKED / SANDBOX UNAVAILABLE")`. Brief §9 LAYER 3 (sandbox network isolation) **cannot be verified on this machine** — and the brief says not to claim it until it is enforced and tested. |
| **Single-user local install** | `P117_AUTH_REQUIRED` defaults false and anonymous is capped at `operator`. Clearance levels would be real code with no second user to test against unless demo accounts are used. |
| **Frontend perf is already tight** | Brief §21 forbids making it slower. Home is 166 kB; a security graph would need lazy-loading like the asset network map. |

## 3. Dependency map (what plugs into what)

```
backend/security/
  egress.py              URL-level guard, exact-host allowlist (no wildcards)
  network/egress_policy.py   check_and_record() -> raises EgressBlocked  [LAYER 2 DONE]
  network/network_monitor.py record_decision()   -> allow/block record    [SENTINEL SEED]
  audit/audit_log.py         durable audit (NOT chained)                  [GAP 1]
  audit/event_store.py       in-process event store
  rbac/                      roles + permissions                          [REUSE]

backend/tools/         19 permission-gated tools                         [REUSE]
backend/orchestrator/  task router -> planner -> execution manager       [REUSE]
backend/models/        role-based gateway -> Ollama                      [REUSE]
backend/ingestion/     document + multimodal + indexing                  [REUSE]
backend/deliverables/generators/  docx/pdf/pptx/report                   [GAP 2: unsigned]

simulation is a SEPARATE, PROTECTED subtree:
backend/simulation/    engine, service, decision, agents, persistence
                       -> brief §17 forbids touching its behaviour
```

## 4. Recommended sequencing (differs from the brief's)

The brief's 19 phases assume a greenfield build. Given §0, the honest order is:

**Do first — small, high value, zero risk to simulation:**
1. **Audit chain** (gap 1) — add `previous_hash`/`current_hash` columns + a verifier, *extending* `audit_log.py`. Touches no simulation code.
2. **Network Sentinel stream** (gap 5) — emit an SSE `network.connection_attempt` event from the **existing** `record_decision()`. Real events, no new monitor.
3. **Sovereignty Center UI** (gap 4) — a page that reads *real* state from `/health`, the egress policy, the audit chain and the sentinel. Lazy-loaded, per §21.
4. **Signed artifacts** (gap 2) — Ed25519 sign in the existing `deliverables` path + a `verify_artifact` utility.

**Do second — needs a decision from you:**
5. **Clearance model** (gap 3) — the real design question. Metadata on documents/chunks plus a pre-retrieval filter. This changes retrieval behaviour, so it needs its own pass.

**Do not do here:**
6. **nftables (LAYER 1)** — Linux deployment task. Document it, do not fake it.
7. **Sandbox network isolation (LAYER 3)** — requires a running OpenSandbox. Until then it must be reported as **PLANNED**, never IMPLEMENTED. The brief's §22 forbids claiming it otherwise.

## 5. What I will not do

- I will not build a second tool registry, monitor, audit system or model router.
- I will not touch `backend/simulation/**` behaviour. Brief §17 protects it, and this
  session has already verified the sensor → 3 agents → RecoveryDecision → route →
  resolve flow end to end. Any workbench integration will **read** simulation events,
  never alter them.
- I will not claim air-gap, zero-egress, or sandbox isolation at any level without a
  test that demonstrates it.

## 6. Test surface that must stay green

- `pytest tests/` — currently **389 passed**
- `tests/unit/test_egress.py`, `test_egress_enforcement.py` — the security baseline
- `ruff check backend tests` — currently clean
- `pnpm run typecheck` / `lint` — currently 0 errors
- Six browser gates: verify 28/28 · sensor-failover 13/13 · simulation-views 31/31 ·
  process-map 18/18 · mock-banner 9/9 · posture 9/9
- Simulation regression: sensor disable → isolation → 3 agents → decision → route →
  resolve (the flow the brief calls out as CRITICAL in §17 and §23)
