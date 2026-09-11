# apps/

Front-end applications in the pnpm workspace.

- **`web/`** — the Next.js 14 (App Router) operator console **and** the
  cinematic landing page. This is the primary UI and it is implemented:
  simulation workbench, plant schematics, knowledge graph, history, jobs,
  agents, approvals, equipment, documents and admin. It runs on
  **<http://127.0.0.1:3017>** (`pnpm --filter web dev` from the repository
  root, or `pnpm dev` from `apps/web`).
  - `/` — the landing page: a 121-frame WebP cinematic sequence driven by
    `src/lib/cinematic/director.js`. **Treated as frozen during console work —
    do not change its layout, styling or tokens.** Console design tokens are
    scoped to `.cs` and landing tokens to `.p117`, which is what keeps the two
    independent.
  - `/console/*` — the console itself.
  - Configuration: copy `apps/web/.env.example` to `apps/web/.env.local`.
    `NEXT_PUBLIC_DATA_MODE` defaults to `live` (the real backend); `mock` is an
    explicit, badged, development-only in-browser engine. There is no silent
    fallback from `live` to `mock`.

There is no `mobile/` app. Earlier revisions of this file described `web/` as a
future placeholder and listed a mobile client; neither was ever added, and a
placeholder description in the workspace root is worse than none.

Backend API reference: <http://127.0.0.1:8000/docs> while the service is
running. Architectural context lives in `docs/architecture/`, setup steps in
`docs/SETUP.md`.
