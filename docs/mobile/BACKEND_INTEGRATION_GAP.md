# Mobile ↔ Backend Integration Gap

**Status:** **CLOSED (2026-09-15)** — the `/api/v1` mobile field API is
implemented. See "Resolution" at the end of this document. The analysis below is
kept as the record of what was wrong and why.
**Measured:** 2026-09-15 against the running backend (`/openapi.json`, 94 routes).

> **Correction (post-implementation).** An earlier revision of this document
> listed `POST equipment/identify` as having an existing backend route. That was
> wrong — the mapping was produced by a pattern match that let `/api/equipment/{id}`
> match `equipment/identify`. **No such backend route existed.** It has since been
> implemented at `/api/v1/equipment/identify` against `OperationsStore.equipment_item`,
> the same store the other equipment routes use. The count below is therefore
> 9 mapped / 15 missing, not 10 / 14.

## Summary

The Android client and the Project 117 backend speak **two different API
contracts**. This is not a host, port, firewall or networking problem — the
client's request paths do not exist on the server.

| | |
|---|---|
| Mobile base URL | `http://<host>:8000/api/v1/` (the app normalises the `/api/v1/` suffix) |
| Backend actual prefix | `/api/` — and `/health` is at the root |
| Backend routes under `/api/v1/` | **none** (0 of 94) |

So `GET /api/v1/health` returns **404** while `GET /health` returns **200** from
the same host. The app surfaces this honestly:
`Failed: health endpoint not found (404) — check the /api/v1/ path`.

## Endpoint-by-endpoint

Of **24** endpoints the client calls, **10** have a real backend route and **14**
do not.

### Have a backend equivalent (only the path prefix differs)

| Mobile call | Backend route |
|---|---|
| `GET health` | `/health` |
| `GET auth/me` | `/api/auth/me` |
| `GET equipment` | `/api/equipment` |
| `GET equipment/{id}` | `/api/equipment/{id}` |
| `GET work-orders` | `/api/work-orders` |
| `GET work-orders/{id}` | `/api/work-orders/{id}` |
| `GET approvals` | `/api/approvals` |
| `POST chat` | `/api/chat` |
| `POST documents/upload` | `/api/documents/upload` |

A reverse proxy rewriting `/api/v1/*` → `/api/*` (plus `/api/v1/health` →
`/health`) would make these ten work without touching either codebase.

### Have NO backend route — these block `LiveBackend` entirely

| Mobile call | Consequence |
|---|---|
| `POST auth/login` | **Cannot sign in. This alone blocks the whole live flow.** |
| `POST auth/enroll` | Device enrolment impossible |
| `POST auth/refresh` | Session cannot be renewed |
| `POST auth/logout` | — |
| `POST work-orders/{id}/update` | Cannot close out a job |
| `GET agents/tasks` | Agent Tasks screen has no data |
| `POST agents/tasks/{id}/acknowledge` | — |
| `POST agents/tasks/{id}/complete` | — |
| `POST approvals/{id}/decide` | **Supervisor approval cannot be recorded** |
| `GET knowledge/sop` | SOP library has no data |
| `GET knowledge/sop/{id}` | — |
| `POST issues` | **Report Issue cannot be submitted** |
| `GET notifications` | — |
| `POST notifications/{id}/read` | — |

The backend's auth surface is `/api/auth/me`, `/api/auth/roles`,
`/api/auth/session` — there is **no login endpoint** at all.

## Why this was not fixed here

The integration brief was explicit:

> Do NOT change API contracts. Do NOT change DTOs. Do NOT invent a new backend.
> If an integration gap exists: document it instead of silently changing
> behavior.

Implementing 14 endpoints would change the backend API; rewriting
`Project117Api.kt` and `Dtos.kt` would change the mobile contract. Both were
out of scope, so the gap is recorded instead of papered over.

## What works today

**`DEMO` mode is fully functional.** `DemoBackend` is entirely in-process, needs
no network, and is what the 7 unit tests exercise — the complete field workflow
(equipment, P-102 telemetry, work orders, inspection, QR scanning, evidence
capture, report issue, SOP, agent tasks, approvals, role permissions, offline
queue) runs against it.

**`LOCAL` and `PRODUCTION` cannot work against this backend** until the gap is
closed.

## Options to close it

1. **Adapt the mobile client to the real API** — change `Project117Api.kt` and
   `Dtos.kt` to the `/api/...` routes and find or add a login equivalent. Changes
   the mobile contract. Smallest backend impact.
2. **Implement the missing endpoints on the backend** — 14 routes, including a
   real login. Changes the backend API. Largest effort, and crosses the
   "do not change the backend" boundary.
3. **Do both**: proxy the 10 that map, implement only the 4 that block the live
   path (`login`, `work-orders/{id}/update`, `approvals/{id}/decide`,
   `issues`). Pragmatic middle path.


---

## Resolution

Implemented as a mobile field API mounted at `/api/v1`, reusing the backend's own
stores and services rather than duplicating logic. The backend now exposes **118
operations (94 existing + 24 mobile)**.

**Auth.** The backend previously had no user or password concept at all — its
identity model was a header-based API key (`X-P117-Api-Key` / `X-P117-User` /
`X-P117-Roles`) whose own docstring read *"no sessions, no JWT… nothing needs a
token service."* A real credential layer was added on top:

- `hashlib.scrypt` with a per-user random salt; constant-time verification; a
  dummy scrypt round for unknown usernames so accounts cannot be enumerated by
  timing.
- `p117a.` / `p117r.` HMAC-SHA256 signed tokens, type-checked so a refresh token
  cannot be replayed as an access token. Access 30 min, refresh 30 days.
- Sessions are re-checked on every protected request, so logout genuinely
  invalidates an outstanding access token.
- Device enrolment (`POST /auth/enroll`) is a real gate: login refuses an
  unrecognised device.
- Seeded SYNTHETIC DEMO accounts (`is_demo = 1`), one per role.

**Honest empty states** — no fabricated data. Where no backing store exists the
endpoint returns an honest empty/null rather than invented content: work-order
steps, equipment readings (no telemetry persistence), issue→work-order linkage,
approval deadlines, notification history (the feed starts empty and is written by
real events), and SOP metadata the source document does not carry. SOP content
itself is real, served from the indexed `SOP_Pump_Startup_Shutdown.docx`.

**Also fixed:** a pre-existing bug in which `/api/chat` returned **400 on every
real reply** because the `usage` field was typed `dict[str, int]` while Ollama
returns a nested `prompt_tokens_details`. No test had covered it.
