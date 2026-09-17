# Project 117 — Frontend Architecture Blueprint (v1, for approval)

Status: PROPOSED. No implementation until approved.
Prerequisite: cinematic landing page exists (entry point + brand). The workbench is the product behind "Enter the Workbench".

> Historical proposal: the console shipped in `apps/web/` and its live surface
> contract is `docs/design/GLASS_SYSTEM.md`. This document is kept for the
> original page-count and interaction rationale, not as current-state
> description.

---

## 1. Product experience overview

Two registers, deliberately different:

- **Landing (`/`)** — cinematic film. Emotion, story, brand.
- **Workbench (`/console/*`)** — calm industrial operations environment. Clarity, speed, evidence, action. No scroll-jacking, no cinematic effects; motion is reserved for state feedback (agent activity, verification, live data).

The workbench communicates three layers on every screen: **the plant** (equipment, telemetry, work orders), **the AI workforce** (agents, tasks, artifacts), and **the trust boundary** (evidence, verification, sovereignty, audit).

## 2. Information architecture

```
PROJECT 117
│
├── Home                        (command center)
├── AI Workspace                (ask, tasks, evidence, artifacts — one surface)
├── Knowledge
│   ├── Documents               (library + viewer + analysis, unified)
│   ├── Knowledge Graph         (explorer)
│   └── Operational History     (organizational memory, human terms)
├── Operations
│   ├── Equipment               (asset explorer)
│   └── Work Orders
├── Insights                    (analytics — question-driven, not chart dump)
├── Approvals                   (queue; badge when pending)
└── Admin                       (role-gated; tabbed, one page)
      Users & Roles · Models · Connectors · Security · Audit Log · System
```

Deliberately NOT pages: Sandbox (Execution panel in Workspace), Verification (panel/drawer wherever results appear), Agents (activity lives in Home rail + Workspace; roster is a drawer), Search (command palette), Alerts (notification drawer + filtered views), Upload (modal), Artifact preview (modal).

**Counts: 10 primary pages · 2 secondary pages · 12 overlays/drawers/modals.**

## 3. Complete page inventory

### PRIMARY (10)

1. **Home** — "What is happening in my plant right now?" Users: all. Layout: status strip → tri-column: Needs Attention (alerts ranked, pending approvals, maintenance due) | Plant State (equipment health by zone, trend strip) | AI Activity (live agents, recent artifacts, recommendations). Entry: landing CTA. Exit: rows drill into domain pages.
2. **AI Workspace** — the core conversation + task execution surface (§7). Users: engineer, operator, manager. Entry: nav, contextual "Ask AI" everywhere, palette.
3. **Documents** — unified library + viewer + analysis (§8). Users: all.
4. **Knowledge Graph** — explorer: search entity, inspect neighborhood, highlight paths (equipment → component → anomaly → inspection → maintenance). Users: engineer, safety.
5. **Operational History** — memory in human terms: event/decision timeline + Learned Rules taught by humans. Users: engineer, safety, manager.
6. **Equipment** — zone-grouped asset explorer with status, health, open WOs, alerts. Users: all ops roles.
7. **Work Orders** — filterable list; create via modal (manual or AI-drafted). Users: maintenance, engineer, manager.
8. **Insights** — four question-driven sections (§11). Users: manager, engineer, safety.
9. **Approvals** — queue of pending AI-proposed actions with risk/evidence/reason; Approve · Reject · View context. Nav badge. Users: manager, admin.
10. **Admin** — one page, seven tabs: Users & Roles, Models (local gateway), Connectors (status), Security (sovereignty posture), Audit Log, System, Settings. Users: admin.

### SECONDARY (2)

11. **Equipment Detail** — flagship reusable template (§9).
12. **Work Order Detail** — deep-linkable page on desktop; wide drawer when opened from lists.

### OVERLAYS (12)

Command palette (Ctrl/Cmd+K) · Notification center drawer · Approval detail drawer · Agent roster/detail drawer · Artifact preview modal (provenance) · Evidence/citation drawer · New work order modal · Upload modal (pipeline states) · Equipment quick-view drawer · Share/export modal · Destructive-action confirm modal · Mobile bottom sheets.

## 4. Primary navigation

Left rail: 64px icon rail, 232px expanded (persists). Sections: OPERATE (Home, AI Workspace, Approvals) / KNOWLEDGE (Documents, Graph, Operational History) / PLANT (Equipment, Work Orders, Insights) / SYSTEM (Admin, role-gated). Badges: pending approvals, running tasks. Bottom: status dot + sovereignty indicator + user.

## 5. Application shell

- **Top bar (persistent):** plant/unit label (single-plant MVP), global search (Ctrl/Cmd+K), sovereignty cluster (LOCAL MODELS ● · SANDBOX ● · EGRESS: DENIED · EXTERNAL: 0 — subtle, hover popover for detail), notifications, user/role chip.
- **Rail (persistent):** §4.
- **Page header (per page):** title + contextual primary action (Upload / New Work Order / Ask AI) + saved filters.
- **No breadcrumbs in MVP** (rail + title suffice at this depth).
- **Mobile shell:** rail → bottom tabs (Home, Ask, Work Orders, More); sovereignty cluster moves under More → System.

## 6. Home / Command Center

One ranked hierarchy, not a wall of cards:

```
Status strip: SYSTEM OK · MODELS LOCAL · SANDBOX SECURE · EGRESS DENIED
┌ NEEDS ATTENTION ─┬─ PLANT STATE ──────────┬─ AI ACTIVITY ────────┐
│ alerts (severity) │ equipment health, zone │ live: agent, task, % │
│ approvals pending │ anomaly trend spark    │ recent: artifacts ✓  │
│ maintenance due   │ open work orders       │ recommendations      │
└──────────────────┴────────────────────────┴──────────────────────┘
30-day strip: anomalies · WOs closed · verified agent tasks
```

3D plant twin is Phase 2 (optional toggle). MVP: fast status board — clarity never waits for WebGL.

## 7. AI Workspace

Three zones: **left** session/task list · **center** conversation · **right** contextual panel (tabs: Evidence / Execution / Artifacts / Verification; collapsible; bottom drawer < 1280px).

Every request that triggers work renders a **Task Card**:

```
REQUEST   "Analyze Compressor C-3…"
STATUS    Queued → Retrieving → Analyzing → Executing → Verifying → Complete (live stepper)
CONTEXT   3 documents · graph neighborhood · telemetry window
RESULT    answer with citation chips per claim
ARTIFACT  maintenance_recommendation.pdf — VERIFIED ✓
CHECKS    evidence ✓ citations ✓ calculation ✓ policy ✓
```

No chain-of-thought. Citation chips open the evidence drawer at the exact source page. Approval-gated steps pause the card with an inline Review action.

## 8. Document intelligence

One page, three modes: **Library** (dense table: status pipeline stored→indexing→indexed, entities, citation counts, filters) · **Viewer** (render, page nav, evidence highlights, extracted tables, OCR inspect, metadata panel) · **Analyze** (scoped Q&A with page-region citations; create artifact from document). Upload modal shows real pipeline states. Compare documents: Phase 2.

## 9. Equipment

List: zone-grouped, status-sorted. **Detail template:** header (identity, status, live KPI chips, "Ask AI about this equipment") → tabs: Overview (AI insight banner, health, related equipment) · Sensors (telemetry + threshold lines) · Maintenance (history + WOs) · Documents · History (incidents) · Graph (embedded neighborhood).

## 10. Work orders

List with filters, grouped by status. Create = modal. Detail = page/drawer hybrid: issue, equipment link, AI recommendation + evidence, approval status, timeline, artifacts, completion. AI-generated WOs carry agent badge + provenance.

## 11. Analytics (Insights)

Four question-titled sections: "Are anomalies increasing?" (rate by zone) · "Where is maintenance effort going?" (WO hours by class, MTBF/MTTR) · "Which assets are degrading?" (health movers) · "What did the AI workforce do?" (tasks by agent, verification pass rate, execution time, artifacts). Every chart has a question title + source note. No decorative charts.

## 12. Knowledge / memory

Documents (§8) · Graph explorer · **Operational History**: timeline of anomalies/inspections/decisions/approvals + **Learned Rules** ("P-1042 threshold 17 bar — set by R. Kapoor, 12 Aug, verified"). Backend jargon (episodic memory, vector store) never surfaces; users see History, Search, Rules.

## 13. Agents

No developer console. Presence: Home AI rail, Workspace task cards, roster drawer (five agents: status, current task, capabilities, permissions summary, success/verification rate), agent detail drawer (execution timeline, audit link). Framing: what is it doing · what did it find · what needs me.

## 14. Artifacts

Surface in task cards + preview modal: rendered preview, metadata, trust block ("Generated from 14 sources · Verified against 11 · sha256 9f2c…a1 · by Maintenance Agent, job-71"), download/export. Library tab + versioning: Phase 2.

## 15. Verification / trust

Reusable **VerificationSummary** wherever results appear: evidence / citations / calculation / execution / artifact / policy → verified | pending | failed, expandable to short findings. Unsupported claims get amber "unverified" chips — quarantined, never hidden. Approval status is part of the trust block.

## 16. Security

Login/session (shared deployments), role chip, permission-denied states with reason, Audit Log (timestamp, actor, action, tool, model, job, approval linkage), Security posture tab (gateway local, sandbox isolated, egress denied + allowlist, external APIs disabled). Boundary story lives in posture panel + landing — no inline banners.

## 17. Admin

MVP tabs: Users & Roles · Models (health, loaded local models, routing) · Security (posture) · Audit Log · System (health, storage, version). Phase 2: Connectors config, data sources, retention.

## 18. Mobile app (separate IA — field workflows)

Bottom tabs: **Scan** (QR → equipment) · **Work Orders** (mine, today) · **Ask** (voice-first) · **Equipment** · **More** (SOPs, alerts, offline sync, settings). Single-column details; "Report issue" (photo/video/voice → AI-drafted WO); offline badge with queued actions.

## 19. Design system

Landing identity, calmer register: canvas #0b0f14 · panel #111720 · raised #161e29 · hairline #1f2a38 · ink ×3 · cyan = AI/interactive · amber = warning/pending · red = critical · green = verified. Inter (UI) + JetBrains Mono (IDs, telemetry, code). 8pt grid, 4/8px radii, 13px ops density. Components: Panel, StatusDot, Tag, Button, Input, Table, Chart spec (threshold lines), Drawer, Modal, Tabs, CommandPalette, TaskCard, ExecutionTrace, EvidenceChip, VerificationSummary, ArtifactCard, ApprovalCard, Timeline, EmptyState (all variants), UploadZone.

## 20. Animation system

Workbench budget: 120–240ms ease-out; drawer slides, status pulse, stepper advance, check-draw on verification, skeleton shimmer, throttled telemetry ticks. No scroll-jacking/parallax/WebGL in the MVP workbench. prefers-reduced-motion → instant state changes.

## 21. User flows

1. Landing → Enter → Home (loading→ready) → Ask AI → Task Card → result/artifact.
2. Documents → Upload (pipeline states) → indexed → ask → evidence drawer at page → answer. (Failures: OCR failed, unsupported type, indexing failed + retry.)
3. Equipment → C-3 → Ask AI → verified recommendation → Create WO modal → WO detail (approval gate if policy).
4. Document → Ask → Generate presentation → sandbox execution → verification → artifact preview → export.
5. Mobile: Scan → equipment → SOP → voice ask → answer → Report issue → AI-drafted WO (offline: queued → syncs).
6. Manager: Home → Needs Attention → AI investigation (evidence + verification) → approval drawer → Approve → audit entry.
7. Admin: Security posture → Audit Log → filter actor/action → event detail.

## 22. Role-based UX (maps to backend viewer/analyst/operator/admin)

- **Operator:** Home, Ask, Equipment, alerts. No upload/delete/config.
- **Engineer:** + Documents upload, sandboxed analysis, graph, artifact generation.
- **Maintenance:** Work Orders first, equipment, mobile app.
- **Safety:** Documents/SOPs, Operational History, Approvals review, audit read.
- **Manager:** Home, Approvals (decide), Insights, artifacts.
- **Admin:** everything + Admin tabs.
UI changes: nav items hidden (not disabled) by permission; approval buttons only for approvers; destructive actions gated; role chip always visible.

## 23. Responsive strategy

Desktop-first 1440/1600/1920. <1280px: right panels → drawers, rail → icons. Tablet: workspace panel = bottom drawer; tables horizontal-scroll with sticky first column. Mobile web: read-mostly (Home, alerts, approve/reject); creation flows point to desktop. Field work = native app (§18).

## 24. States

Per surface: loading (skeleton) · empty (guidance + action) · error (reason + retry) · offline (banner, read-only) · permission denied (reason + role) · processing (pipeline stepper) · AI working (stepper + cancel) · AI failed (typed error + safe retry) · verification pending (amber) · verification failed (red, claim quarantined as unverified).

## 25. MVP vs future

- **Phase 1 — SIH demo (MUST):** Landing, Shell, Home (demo P-1042 story; mock adapter where backend routes don't exist), AI Workspace, Documents, Equipment + detail, Work Orders, Approvals, Knowledge Graph (basic), Admin Security posture.
- **SHOULD:** Operational History, Insights, roster drawer, artifact provenance.
- **Phase 2:** 3D plant twin toggle, connectors UI, document compare, artifact library/versioning, learned-rules editor, deeper analytics.
- **Phase 3:** native mobile app, multi-plant, offline depth, SSO, deployment tooling.

## 26. Final page count

- **Primary: 10** — Home · AI Workspace · Documents · Knowledge Graph · Operational History · Equipment · Work Orders · Insights · Approvals · Admin
- **Secondary: 2** — Equipment Detail · Work Order Detail
- **Overlays: 12**
- **Not built:** sandbox page, vector-store UI, model playground, search page, alerts page, agents-as-console page, billing/tenancy, social features — each backend concept surfaces contextually where its output is consumed.

## 27. Recommended folder structure

```
apps/web/src/
├── app/
│   ├── page.tsx                 # landing (done)
│   ├── layout.tsx
│   └── console/
│       ├── layout.tsx           # AppShell
│       ├── page.tsx             # Home
│       ├── workspace/page.tsx
│       ├── documents/page.tsx
│       ├── graph/page.tsx
│       ├── history/page.tsx
│       ├── equipment/page.tsx + [id]/page.tsx
│       ├── work-orders/page.tsx + [id]/page.tsx
│       ├── insights/page.tsx
│       ├── approvals/page.tsx
│       └── admin/page.tsx       # tabbed
├── components/
│   ├── landing/ (done)
│   ├── shell/      Rail · TopBar · SovereigntyCluster · CommandPalette · NotificationCenter
│   ├── ui/         Panel · StatusDot · Tag · Button · Input · Table · Drawer · Modal · Tabs · EmptyState
│   ├── workspace/  TaskCard · Stepper · ExecutionTrace · EvidencePanel · VerificationSummary · ArtifactCard · Composer
│   ├── documents/  Library · Viewer · UploadZone · CitationList · MetadataPanel
│   ├── equipment/  StatusBoard · EquipmentHeader · TelemetryChart · InsightBanner · GraphNeighborhood
│   ├── workorders/ List · Detail · CreateModal · Timeline
│   ├── approvals/  Queue · ApprovalDrawer
│   ├── agents/     ActivityRail · RosterDrawer · AgentDetail
│   ├── insights/   QuestionSection · TrendChart · MoversList
│   └── admin/      PosturePanel · AuditTable · UsersTable · ModelsTable
├── lib/    api · data · sim · knowledge · documents · motion · ui (implemented; no mock/websocket/uploads/auth modules)
├── hooks/  useJobEvents · useAgentEvents · useTelemetry · useAlerts · useApprovals · useHealth
├── stores/ system · agents · jobs · telemetry · alerts · approvals
├── types/  (exists)
└── styles/ globals · tokens
```
