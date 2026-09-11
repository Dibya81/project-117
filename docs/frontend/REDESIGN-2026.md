# Project 117 — Frontend Redesign (2026)

> Status: IMPLEMENTED. Backend untouched. All console data flows through the
> existing mock adapter (`lib/data/console.ts` + `lib/mock/*`) — zero
> integration work, per plan. Swapping to live endpoints later is a
> mechanical change inside that one adapter file.

---

## 0. What was broken (and why "nothing worked")

| Problem | Evidence | Fix |
|---|---|---|
| **Compile blocker** | `lib/api.ts` + `lib/websocket.ts` imported 6 types (`ChatTurnRequest`, `ChatTurnResult`, `HealthResponse`, `ToolDescriptor`, `WorkflowDefinition`, `ServerEvent`) that did not exist in `types/` → `tsc`/`next build` fails | Contracts added to `types/index.ts`, mirroring the backend Pydantic schemas |
| **10 of 11 console routes 404** | Rail/palette link to `/console/workspace`, `/documents`, `/knowledge`, `/history`, `/equipment`, `/work-orders`, `/insights`, `/approvals`, `/admin`; only `/console/home` existed | All pages built (§4) |
| Landing CTA → dead placeholder | `/workbench` was a monochrome stub | `/workbench` now redirects to `/console/home` |
| "Looks AI-generated" | flat panels, no motion system, no signature element | "Obsidian Reactor" design language (§1) on every pixel |
| 3D deps unused | `three`, `@react-three/fiber`, `@react-three/drei` in package.json, nothing rendered | WebGL reactor core (landing finale + console home hero), lazy-loaded, SSR-safe |

## 1. Design language — "OBSIDIAN REACTOR"

A reactor control room built by a film studio: obsidian glass, cyan energy,
ember heat, hairline HUD chrome. One DNA, two registers (cinematic landing /
calm console).

Tokens live in `src/styles/tokens.css` (imported by `app/globals.css`):
canvas `#03060b/#070b12` · glass panels · ink `#eaf2fa/#9db1c7/#5b6c81` ·
cyan `#45d5ff` (AI/interactive) · ember `#ff7a3d` (brand) ·
ok `#3ddc97` / warn `#ffb454` / crit `#ff5d5d`.

Signature elements (repeated everywhere = cohesion):
1. **Aurora** — fixed ambient background: drifting cyan/ember energy fields,
   blueprint grid, film grain, vignette (`components/fx/Aurora`).
2. **HUD corner brackets** on hero panels (`cs-panel--hud`).
3. **Glow-dot status language** — every state is a halo-lit dot.
4. **Scanline sweeps** on live surfaces (`cs-scan`).
5. **Reactor core** — the 3D brand object.

## 2. Motion system (zero new dependencies)

| Effect | Where |
|---|---|
| `Reveal` (IO entrance: rise + de-blur, stagger) | insights, lists |
| `Counter` (rAF count-up) | home hero, insights, landing finale stats |
| `Magnetic` (pointer-attracted CTA) | landing finale CTA |
| `Tilt` (perspective + glare) | equipment cards |
| Page transitions | `app/console/template.tsx` (fade/rise per route) |
| Live telemetry drift (2 Hz) | home plant state, equipment detail charts |
| SVG stroke-draw + live head | `TrendChart`; knowledge-graph edge flow |
| Typewriter streaming | AI workspace result |
| Shimmer skeletons / staggered `cs-fade-list` | all loading states |
| `prefers-reduced-motion` → instant states | global |

## 3. WebGL — `components/fx/ReactorCoreScene.tsx`

Wireframe containment cage + pulsing emissive core + two gyroscope rings +
orbital sparkles, mouse parallax. Mounted via `ReactorOrb` (`next/dynamic`,
`ssr: false`) with a pure-CSS fallback orb. Hero size in the landing finale
(mounted only when the final chapter is near), compact on the console home
hero card.

## 4. Pages delivered

| Route | Highlights |
|---|---|
| `/` | preloader (% + brand) → film → problem → security → network → action → finale with 3D core, stats, magnetic CTA |
| `/console/home` | status strip, reactor hero + counters, ranked Needs Attention / Plant State (live) / AI Activity, anomaly trend |
| `/console/workspace` | sessions rail, live TaskCard stepper via demo runner, streaming result, evidence/execution/artifacts/verify tabs, working composer |
| `/console/documents` | filterable library table, upload modal with real pipeline stepper, viewer drawer, `?doc=` deep links from citations |
| `/console/knowledge` | SVG graph explorer: search, node focus, neighborhood highlight, flowing edges, relation panel |
| `/console/history` | draw-in timeline + Learned Rules panel, kind filter |
| `/console/equipment` | status-sorted tilt cards, health rings, sensor chips, AI insights |
| `/console/equipment/[id]` | KPI chips + tabs (Overview/Sensors/Maintenance/Documents/History), threshold telemetry charts |
| `/console/work-orders` | 5-column status board, priority filter, create modal (`?new=1` from palette) |
| `/console/work-orders/[id]` | details, AI recommendation + evidence drawer links, approval gate, timeline |
| `/console/insights` | headline counters + 4 question-titled chart sections with sources |
| `/console/approvals` | risk meters, expandable evidence, working approve/reject with ledger flash |
| `/console/admin` | tabs: Security posture (sovereignty gauge) · Users & Roles · Models · Audit (filterable) · System |

Shell: glass rail (sections, badges, active glow), topbar with sovereignty
cluster popover, ⌘K palette (navigates every page + all entities),
notification drawer, agent roster drawer.

## 5. Verification performed here

- `esbuild` parse of all 60 source files — clean
- `tsc --strict` over the whole app (with local declaration shims for
  react/next/three, since this sandbox has no registry access) — **0 errors**;
  the shims are stricter stand-ins for the real `@types/*` in package.json
- No new npm dependencies — everything uses what `package.json` already pins

## 6. Run it (your machine)

```bash
cd apps/web
npm install
npm run dev        # http://localhost:3000  (mock mode, no backend needed)
npm run build      # production build
npm run typecheck  # real @types/* strict pass
```

`NEXT_PUBLIC_DATA_MODE` stays `mock`; flipping to `live` later only touches
`lib/data/console.ts`.

---

## 7. Flagship pass (v2) — the 2026 bar

Semantic effect registry (every effect = meaning):
cyan = AI/intelligence · amber = human decision · red = anomaly · green =
verification · violet = knowledge/memory · pulse = live activity ·
scanline = extraction · orbit = interconnection · camera = context change.

| Area | v2 addition |
|---|---|
| Global | **Journey bar** (`lib/journey.tsx`) — investigation trail persists across pages, clickable chips; **spatial warp transitions** with destination announcement; mobile bottom tabs; ⌘K palette now carries TYPE/STATUS/CONTEXT + agents + workflows + investigations |
| Home | **Live plant map** (procedural canvas: real layout positions, kind glyphs, pipe energy flow, hover telemetry tooltip, click to dive) + **Intelligence Chain** (Sensor→Anomaly→Knowledge→Agent→Recommendation→Work Order→Verification, traveling pulse, every stage links) |
| Workspace | Structured investigation answer: Executive answer / Primary finding / Contributing factors / Recommended action / Risk / Next action; journey visit per run |
| Documents | 8-stage ingest pipeline (received→parse→OCR→chunk→embed→extract→graph→ready); **Evidence Mode** on citation deep-links (Claim→Evidence→Source→Verification); violet entity chips |
| Knowledge | **Camera moves to focused node** (zoom+pan), unrelated dims, "Trace the C-3 story" walks the golden path lighting it violet, exit chip into the work order |
| History | OBSERVED/DECIDED/ACTED/VERIFIED categories; Learned Rules carry origin, evidence count, confidence meter, usage count |
| Equipment | **AI Attention** ranking mode (lowest health first + rank badges) |
| Equipment detail | **Procedural digital twin** SVG per asset kind with spatial sensor hotspots (hover = reading, click = telemetry tab); chain-of-evidence panel |
| Work Orders | Cards carry AI recommendation / evidence count / verified tags |
| WO Detail | 8-stage **provenance spine**: Observed→Analyzed→Recommended→Drafted→Approved→Executing→Completed→Verified |
| Approvals | **Authorization sequence** (Policy check → Authorized → Audit recorded) before state flip; reject requires a ledger reason |
| Admin | **Security perimeter** visualization (trust zones + blocked-egress ticks dissolving at the boundary) + sovereignty 100% statement + system gauges |
| Insights | AI observation blocks: confidence meter + affected-equipment chips that deep-link |
| States | Contextual loading verbs ("Extracting knowledge…", "Synchronizing telemetry…"), designed empty states with actions |
| Landing | Finale ring = Documents · Telemetry · Memory · Agents · Tools · Verification (inputs to sovereign intelligence) |

All v2 work re-verified: esbuild parse clean on every file; strict tsc clean.
