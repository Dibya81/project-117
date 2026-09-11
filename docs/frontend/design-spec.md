# Project 117 — Frontend Design Specification

## 1. Information architecture

Two experiences, one product:

- **Experience A — Story (route `/` when unauthenticated or first visit):** six-scene
  scroll narrative (problem → AI evolution → Project 117 reveal → architecture stack →
  digital factory → ENTER THE WORKBENCH).
- **Experience B — Command Center (route group `(console)` under `/console/*`):** the
  operational application.

Navigation hierarchy (left rail, icon + label, keyboard reachable):

```
COMMAND CENTER        /console
AI WORKSPACE
  Chat                /console/chat
  Active Tasks        /console/jobs          (via chat page tab)
OPERATIONS
  Equipment           /console/equipment
  Work Orders         /console/work-orders
INTELLIGENCE
  Agents              /console/agents
  Knowledge           /console/knowledge
  Analytics           /console/analytics
CONTROL
  Workflows           /console/workflows
  Approvals           /console/approvals
SYSTEM
  Settings            /console/settings
```

> The app routes in `src/app/` keep the brief's exact paths (`/chat`, `/equipment`, ...)
> as thin re-exports of the console pages so the required file structure is preserved
> verbatim; the console shell is applied by a route group layout.

## 2. Design tokens (Tailwind theme extension + CSS variables)

| Token | Value | Use |
|---|---|---|
| `bg-canvas` | `#0b0f14` | page background (graphite-navy) |
| `bg-panel` | `#111720` | primary panels |
| `bg-raised` | `#161e29` | cards, popovers |
| `line-subtle` | `#1f2a38` | hairline borders |
| `ink-1/2/3` | `#e6edf4 / #9fb0c3 / #5c6b7e` | text hierarchy |
| `accent` | `#38bdf8` (cyan-400) | primary action, AI identity |
| `accent-dim` | `#0c4a6e` | accent surfaces |
| `warn` | `#f59e0b` | warning state |
| `crit` | `#ef4444` | critical state |
| `ok` | `#34d399` | verified / healthy |

Typography: UI sans = system stack mapped to `Inter`; data/mono = `JetBrains Mono`
fallback `ui-monospace`. Monospace is reserved for telemetry, IDs, model names, logs.

Radius: `4px` default, `8px` panels. Shadows: minimal, elevation via border + bg delta.
Density: compact 13px base for ops pages, 15px for narrative.

## 3. Component hierarchy

```
AppShell
├── TopBar (SovereigntyIndicator, SystemStatus, CommandPalette trigger, UserRole)
├── Sidebar (nav sections, collapse)
└── <page>
    ├── CommandCenter → FactoryScene(3D) + TelemetryPanel + AlertPanel + AgentActivity
    ├── AgentWorkspace → TaskFlow (Context/Plan/Execution/Evidence/Verification/Artifact)
    ├── Agents → AgentCard grid → AgentDetail (ExecutionTrace)
    ├── Workflows → WorkflowGraph (SVG) + WorkflowStep states
    ├── Equipment → EquipmentTable → EquipmentDetail (telemetry charts, insights)
    ├── WorkOrders → WorkOrderPanel
    ├── Knowledge → DocumentList + UploadZone / KnowledgeGraph (SVG)
    ├── Approvals → ApprovalCard list
    └── Settings → sovereignty-first status panels
```

Reusable primitives in `components/ui/`: `Panel`, `StatusDot`, `Tag`, `Button`,
`KbdHint`, `EmptyState`, `Spinner`, `Drawer`, `Dialog`, `Tabs`, `Metric`, `SectionHeading`.

## 4. Interaction model

- PERCEIVE → PLAN → ACT → VERIFY is a persistent element: `ProcessRail` in the command
  center bottom bar and embedded per-task in the Agent Workspace.
- Every async surface has explicit states: `idle | loading | streaming | done | error |
  offline | denied`. `EmptyState` covers empty/error/offline uniformly.
- Command palette (`Ctrl/Cmd+K`) navigates and triggers agent tasks.
- Feedback language is consistent: Queued→Planning→Executing→Verifying→Complete,
  Normal→Warning→Critical, Pending→Approved/Rejected.

## 5. Real-time architecture

`lib/websocket.ts`: single reconnecting WS client + tiny typed event emitter.
`stores/`: zustand stores per domain (`useSystemStore`, `useAgentStore`, `useJobStore`,
`useTelemetryStore`, `useAlertStore`, `useApprovalStore`). Hooks in `hooks/` subscribe
stores to WS topics and throttle telemetry to 4 Hz render budget. Components never talk
to the socket directly.

## 6. API / data model

`lib/api.ts` is the only place with `fetch`. Namespaced typed calls matching the backend:
`chat`, `agents`, `jobs`, `workflows`, `documents`, `search`, `artifacts`, `tools`,
`models`, `audit`, `health`. `lib/mock.ts` implements the same surface for demo mode;
selection is a single env flag (`NEXT_PUBLIC_DATA_MODE`) — never an in-component branch.
Capabilities that have no backend route yet (equipment telemetry, work orders, graph,
approvals) are mock-only and labeled as demo data in the UI footer strip.

## 7. 3D architecture

`components/equipment/FactoryScene.tsx` — React Three Fiber, lazy via `next/dynamic`.
Procedural plant: ground grid, pipe runs, vessels, pumps (instanced), each mapped to an
`EquipmentStatus` driving emissive color (ok/warn/crit) and pulse animation for active
agent investigation. `EquipmentMarker` handles click → `useSceneStore` selection →
camera focus + `EquipmentPanel` drawer. Telemetry overlays are DOM (Html) to keep the
GL scene cheap. Pixel-ratio capped, `<Canvas frameloop="demand">` when idle.

## 8. Responsive / a11y / performance

- Primary 1440–1920px; below 1024px the 3D view collapses behind a tab and the rail
  becomes a drawer.
- Semantic landmarks, visible focus rings (`outline: 2px accent`), all icon buttons
  labeled, tables with `th scope`, dialogs via focus-trap.
- Code splitting per route, dynamic 3D import, memoized telemetry rows, virtualized
  document list.
