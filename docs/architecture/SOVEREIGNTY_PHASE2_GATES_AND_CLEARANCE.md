# Sovereign Workbench — Phase 2: what the gates were really doing

Status: implemented and verified. Supersedes nothing in
`SOVEREIGNTY_PHASE1_AUDIT.md`; it records what changed after it.

---

## 1. The sensor-failover gate: three distinct defects, not one flaky assertion

The brief diagnosed one race (panel assertions against the 20 s auto-close). The
timeline probe run for this pass found **four** failure modes, only one of which
was that race. Fixing only the diagnosed one would have left the gate red.

Measured on a live run (`/api/simulation/plants/refinery/snapshot`, 1 Hz DOM
sampling), from the click on "disable":

| t | backend | DOM |
|---|---|---|
| +0.0 s | `incidents=1`, `s-PT-1001A:bad` | — |
| +0.7 s | `incidents=1` | `[data-instrument-quality="bad"]` = 1 |
| +46 s | `alarms=1`, incident resolved | `substituted` = 1, overlay `verified` |
| +65 s | incident resolved | overlay dismissed, **dock = 1**, `bad` still 1 |

### 1a. The gate read a panel that had already closed — as diagnosed

The overlay is dismissed `AGENT_PANEL_DISMISS_MS` (20 s) after
`response.decision` by design. The panel assertions now read
`[data-testid="agent-rail"]`, whose cards carry the same
`data-agent` / `data-status` pair plus the real model and the agent's own
finding text. The 20 s dismissal is untouched.

### 1b. `[data-instrument-quality="bad"]` was collapsed into a window

The two "cut" assertions read `bad` **12 s after the click and never again**.
They now sample the DOM continuously from the moment the button is clicked,
concurrently with polling the backend for the live incident. The animation is
finite (`pmap-sensor-cut 1.5 s ease-out 2`), so it is read while it is running,
and the `@keyframes pmap-sensor-cut` rule is asserted directly against the
stylesheet as well.

### 1c. The gate read a plant a previous run had left broken — the crash

The dominant failure was not an assertion at all: the run **died** with
`page.click: Timeout 30000ms exceeded … subtree intercepts pointer events`,
where the intercepting subtree was
`<div class="rcx" data-testid="recovery-experience">`. A leftover incident from
the previous run mounted the full-screen overlay over the first click of the
next run.

Cause: every visit to the plant page calls `ensurePlantIsFresh` →
`POST /plants/{id}/reset`, but the overlay can already be mounted from events
the stream replayed for a runtime that no longer exists. The gate now resets the
plant explicitly, waits for the backend to report **no incident and no sensor
off its normal quality**, waits for the overlay to clear, and routes every
interaction through a retry that dismisses the overlay (what the operator would
do) rather than clicking through it.

### 1d. The P&ID selection was assumed, not verified

`button:has-text("P&ID")` matches two buttons — the map header's view toggle and
the "P&ID" button inside the Meridian canvas — and `$()` returns the first in
document order. The gate now selects the toggle, verifies
`aria-selected="true"` on it **and** that `[data-testid="process-map"]` is
mounted, retrying, and reports that as a check of its own.

**Why it still needed the reset even after 1a–1d:** the plant is process-wide
state. Any other browser tab, another agent's gate, or a second run of this gate
resets it. A reset mid-run wipes the incident the assertions are about. The gate
cannot prevent that, but it can start from a state it chose — and it now says so
in its own check ("the plant was at rest before the fault").

---

## 2. `verify.mjs`

The same residual-state problem made `verify` **crash** on its fault-injection
step, because the agent overlay covered the Equipment-view click. Its fault
injection now resets the plant, waits for it to be at rest, dismisses the
overlay, and retries a bounded number of times; it waits for the backend's
**real incident** rather than an 8 s guess; and the motion read fails as a check
rather than throwing and hiding every check after it.

---

## 3. Network Sentinel: the missing half of the loop

`record_decision()` already streamed to SSE. It did **not** write to the durable
audit log, so the Security Events panel could never show a blocked attempt —
"record_decision → audit event → SSE → live UI" was two thirds present.

Added:

* `backend/security/network/audit_sink.py` — a one-way seam. The API lifespan
  registers the audit service; the egress path reads it without importing the
  API (the httpx transport imports the monitor on a hot path).
* `record_decision()` now writes `network.egress_decision` with
  `outcome="refused"` for a block, carrying host, scheme, port, `local`,
  reason, and the ambient agent/task. The **full URL is never recorded** — path
  and query can carry document content.
* `backend/tools/registry/tool_registry.py` wraps every tool handler in
  `network_identity(agent=…, task_id=step_id)`, so an outbound request a tool
  makes is attributed to the agent and step that made it.
* `POST /api/security/egress-probe` takes one real decision **inside the API**
  against an RFC 5737 documentation address and refuses before any socket. A
  decision taken by a script is recorded in that script's monitor and reaches no
  stream, no audit log and no `/health` counter — the probe exists because
  process-local state cannot be proven from outside the process.

Evidence: `scripts/security_sentinel_proof.py` (ALLOW via the API's own call to
Ollama, BLOCK via the probe).

---

## 4. The Security Console

`GET /api/security/sovereignty` resolves every status line from a measurement
taken in that request, with the vocabulary **VERIFIED / IMPLEMENTED / PARTIAL /
NOT AVAILABLE**. Only `VERIFIED` may be shown as a pass. `POST
/api/security/evaluation` exercises the refusal controls that exist (RBAC,
clearance, egress) and reports the two the brief asks for that this build does
not have — prompt-injection detection and insufficient-evidence abstention — as
`NOT IMPLEMENTED`, because inventing them as passing would be the exact false
assurance the page exists to prevent.

The page lazy-loads every heavy panel (`next/dynamic`, `ssr: false`), subscribes
the sentinel stream only while mounted, and the home page carries none of its
chunks (asserted in the gate).

---

## 5. Clearance model

`backend/security/clearance/` adds an ordered level (`PUBLIC` … `HIGHLY_CONFIDENTIAL`)
and extends RBAC rather than replacing it: `ROLE_CLEARANCE` maps the existing
roles, an explicit badge on a principal overrides it in either direction, and
comparisons are `held >= required`.

Enforced at every retrieval surface, always **before** content reaches a model:

| surface | enforcement |
|---|---|
| vector/FTS retrieval | `RetrievalService.search` filters chunks **before the reranker** and before any `Evidence` exists; `withheld` is reported |
| chat grounding | the principal travels from the route into `evidence_for_chat` |
| direct document read | `read_document` returns `status="denied"` |
| graph traversal | nodes above the caller are hidden and edges with a hidden endpoint are dropped, so a document cannot be reached *or named* |
| agent tool calls | the tool context carries the caller's roles and badge; `search_documents` filters identically |

Defaults are deliberate and different: an unlabelled **document** is INTERNAL
(shipping this must not make every existing document world-readable), while an
unlabelled **graph entity** is PUBLIC (a plant tag is not a secret, and
defaulting it to INTERNAL would hide the whole topology from a viewer).

Tests: `tests/unit/test_clearance.py` — 16 tests, including proof that a
withheld chunk never reaches the reranker and never appears in the prompt
evidence.

---

## 6. What is still not available here

* **nftables/iptables egress (LAYER 1)** — Linux only; this host is macOS.
* **OpenSandbox network isolation (LAYER 3)** — OpenSandbox is not running;
  every `sandbox_command` returns `ACTION BLOCKED / SANDBOX UNAVAILABLE`.
* **Local OCR/Vision for agents** — Docling can run at ingestion, but no OCR or
  image tool is registered, so an agent cannot call it.
* **Local knowledge graph** — implemented, clearance-aware, tested, but mounted
  on no route and consumed by nothing in the request path.
* **Prompt-injection detection, insufficient-evidence abstention** — absent.
