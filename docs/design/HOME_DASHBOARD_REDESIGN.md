# Console Home — Design Audit & Redesign Specification

**Scope:** `/console/home` (`apps/web/src/app/console/home/page.tsx`)
**Status:** specification. Nothing here is implemented.
**Audited against:** the real component tree, the real data the page already
fetches, and the existing `docs/design/GLASS_SYSTEM.md` system.

---

## 0. The finding that matters most

The page already fetches **nine** data sources:

```
consoleData.alerts.active()      consoleData.artifacts.list()
consoleData.equipment.list()     consoleData.jobs.list()
consoleData.workOrders.list()    consoleData.admin.posture()
consoleData.approvals.pending()  consoleData.plant.identity()
consoleData.agents.list()        consoleData.history
```

It surfaces **four numbers** — equipment, sensors, agents, critical alerts —
inside a 3D hero that occupies roughly 70 % of the viewport.

This is not a styling problem. **The dashboard is not missing data; it is
failing to display data it already has in memory.** Pending approvals, open
work orders, running jobs, recent artifacts and the security posture are all
fetched on mount and either relegated to a small side card or a strip below
the fold.

**Therefore the primary redesign move is not "make it prettier." It is
"promote the data you already paid for."** Every recommendation below serves
that.

---

## 1. Layout & grid structure

### Current
```
┌──────────────────────────────────────────────────────┐
│ pagehead (title + lede + Run simulation)             │
├───────────────────────────────────┬──────────────────┤
│                                   │  Plant Status    │
│      Knowledge Core (3D)          │  ────────────    │
│      ~70% × ~65vh                 │  Recent Activity │
│                                   │                  │
├───────────────────────────────────┴──────────────────┤
│ home-strip: health · agents · approvals              │
└──────────────────────────────────────────────────────┘
```

### Proposed — 12-column grid, three tiers

```
┌───────────────────────────────────────────────────────────────────────┐
│ TIER 1 · COMMAND BAR  (sticky, 56px)                                  │
│ Meridian Synthetic Refinery · LIVE · 0 alarms · posture · [Run sim]   │
├───────────────────────────────────────────────────────────────────────┤
│ TIER 2 · VITALS  (4 × 3 cols, ~120px)                                 │
│ Equipment 58 ▲   Sensors 224 ▲   Active agents 5   Alerts 0   Approvals 2 │
├──────────────────────────────────────────┬────────────────────────────┤
│ TIER 3a · TOPOLOGY  (8 cols)             │ TIER 3b · ACTION QUEUE (4) │
│                                          │ ┌────────────────────────┐ │
│   Knowledge Core, now a working          │ │ PENDING APPROVALS   2  │ │
│   graph — not a centrepiece              │ │ WO-9002 · HIGH · 12m   │ │
│   ┌──────┐                               │ ├────────────────────────┤ │
│   │ core │─── equipment (58)            │ │ OPEN WORK ORDERS    2  │ │
│   └──────┘─── documents                  │ │ RUNNING JOBS        0  │ │
│        └───── agents (5)                 │ ├────────────────────────┤ │
│        └───── telemetry                  │ │ RECENT ACTIVITY        │ │
│                                          │ │ (grouped, timestamped) │ │
└──────────────────────────────────────────┴────────────────────────────┘
```

### Placement decision: the Knowledge Core

**Do not delete it and do not keep it as a hero.** Demote it from *centre-
piece* to *navigational instrument*:

- **Size:** from ~70 % × 65 vh to **8 columns × ~420 px** (≈ 46 % of a
  1440 px viewport). Big enough to read, small enough to not be the page.
- **Why it earns its space:** it is the only element that shows *system
  topology* — what is connected to what. That is genuinely the product's
  thesis and belongs on the landing page and here. What it must stop doing
  is being the only thing here.
- **What replaces the reclaimed 30 %:** the Vitals tier and the Action Queue.
  Those are what an operator opens a dashboard for.

### Grid rules

| Token | Value |
|---|---|
| Container | `max-width: 1600px`, `padding-inline: clamp(16px, 2.5vw, 32px)` |
| Columns | `grid-template-columns: repeat(12, minmax(0, 1fr))` |
| Gutter | `16px` (`gap: 16px`) |
| Breakpoints | `≥1440` full 12 · `1024–1439` vitals 2×2, core 12, queue 12 · `<1024` single column |
| Vertical rhythm | 16 / 24 / 32 / 48 — a 4px base, not arbitrary values |
| Density | Target **≥ 70 % of the viewport height carrying data** (currently ~30 %) |

---

## 2. UI/UX improvements

### 2.1 Hero & onboarding → replace with a live status bar

**Delete** `Knowledge at the Core. / Everything Connected.` and the marketing
lede. That copy belongs on `/` (the landing page already says it, better).

**Replace with** a one-line live posture bar that answers *"is anything
wrong right now?"* in under a second:

```tsx
<header className="cs-pagehead cs-pagehead--status">
  <div className="posture">
    <span className="posture__dot" data-state={alarmState} />   {/* ok|warn|crit */}
    <b>{plantName}</b>
    <span className="posture__sep" />
    <span>{sim.alarms > 0 ? `${sim.alarms} alarm(s)` : "All systems nominal"}</span>
    <span className="posture__sep" />
    <span className="cs-mono">T+{sim.t}</span>          {/* the real engine clock */}
    <span className="posture__sep" />
    <span className="cs-mono">{posture?.egress ?? "—"}</span>
  </div>
  <Button>Run simulation</Button>
</header>
```

Rules: **colour is never the only signal** — pair every state dot with a word.
The engine clock (`sim.t`) already streams; showing it costs nothing and is
the single strongest "this is live" cue available.

### 2.2 Node visualisation — make the Core mean something

Right now the orbiting icons are decorative and the sphere pulses. Turn the
**existing** graph into a queryable instrument:

| Element | State | Encoding |
|---|---|---|
| **Node fill** | healthy / warning / critical | green / amber / red — driven by real equipment `state`, not decoration |
| **Node size** | criticality (1–3) — already in the dataset | larger = more critical |
| **Edge stroke** | *flow rate* from `runtime.pipes[id].flow` | thickness ∝ flow; **animated dash only when `enabled && flow > 0`** |
| **Edge colour** | `leaking` / `enabled` | red dashed = leaking, grey = isolated |
| **Halo** | `affected[]` from the active incident | pulse on the incident blast radius |

**Interaction — the part that changes the page's usefulness:**

- **Click a node** → the Action Queue panel filters to *that asset only*:
  its sensors, its open work orders, its documents, its recent history. No
  navigation, no modal — the same panel, scoped.
- **Hover** → an inline tooltip with tag, name, area, state, and current
  readings. Already-available data.
- **Click empty space** → clear the filter, back to plant-wide.

This converts the Core from a screensaver into the page's **primary navigation
control**, which is the only justification for it occupying 8 columns.

### 2.3 Telemetry cards → give the vitals tier sparklines

The four `home-stat` blocks are bare numbers. Add:

1. **Delta**: `▲ 3` / `▼ 1` against the previous reading, coloured by
   direction-and-goodness (more equipment is not "good", so no naive
   green-up/red-down).
2. **Sparkline**: the last N samples. Data already exists — `history.list()`
   and the telemetry stream.
3. **Status accent**: a 2px left border on the card in the state colour, so
   the tier reads at a glance from across a control room.

**Add a fifth card: Pending Approvals.** The page already fetches
`approvals.pending()` and it currently appears only in the strip. A pending
approval is a *human blocking a process* — it is the highest-priority number
on any operational dashboard and should sit in the vitals tier, with a red
accent when non-zero.

```
┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│ EQUIPMENT      │ │ SENSORS        │ │ ACTIVE AGENTS  │
│ 58       ▲ 0   │ │ 224      ▲ 0   │ │ 5        ·     │
│ ▁▂▃▄▅▆▇█       │ │ ▁▂▃▄▅▆▇█       │ │ ▂▂▃▃▃▃▃▃       │
└────────────────┘ └────────────────┘ └────────────────┘
┌────────────────┐ ┌────────────────┐
│ CRITICAL ALERTS│ │ APPROVALS ⚠    │   ← new; red accent when > 0
│ 0        ·     │ │ 2        ▲ 1   │
│ ▁▁▁▁▁▁▁▁       │ │ ▁▁▂▂██         │
└────────────────┘ └────────────────┘
```

### 2.4 Activity feed → from log lines to an audit trail

**Current:** `<ul>` of `<li>{action}</li>` — e.g. "mobile login" repeated four
times. No time, no actor, no severity, no way to filter.

**Proposed row anatomy:**

```
┌────┬──────────────────────────────────────────────────────┐
│ ⬤  │ mobile.login                        technician       │
│ 🟢 │ 2 min ago · 22:19:45 · e-P-1001                       │
├────┼──────────────────────────────────────────────────────┤
│ ⬤  │ document.uploaded                    technician       │
│ 🔵 │ 4 min ago · 22:17:02 · 1.2 MB                         │
└────┴──────────────────────────────────────────────────────┘
```

| Slot | Source | Rule |
|---|---|---|
| Severity dot | derived from action namespace | `incident.*`→amber, `*.failed`→red, `*.uploaded`/`.login`→neutral, `agent.*`→blue |
| Actor | `actor` / `user` field | Initial-avatar; agents get a distinct glyph from humans |
| Relative + absolute time | `at` | **both** — "2 min ago" for scanning, `22:19:45` for the audit record |
| Category chip | `historyKind(action)` | reuse the existing `KIND_STYLE` map from `/console/history` |
| Target | `resource_id` | link to the asset/work order |

**Quick filters** (segmented control, no new state library needed):
`All · Alerts · Agents · Approvals · Documents`. Reuse
`MaterialSegmented`'s pattern.

**Group by day** with a sticky sub-header. An ops feed without day grouping
becomes unreadable past ~30 rows.

### 2.5 Alerts & error handling → replace the floating toast

The red "1 error" badge in the screenshot is the **Next.js dev overlay
indicator**, not app UI — and it is the wrong pattern regardless.

**Three-tier model, by severity and persistence:**

| Tier | Pattern | Use |
|---|---|---|
| **Ambient** | Vitals card accent + count | Something is non-zero. No interruption. |
| **Inline** | A dismissible banner pinned under the Tier-1 command bar | Degraded state needing acknowledgement: egress blocked, model unavailable, backend offline. Includes a **primary action** (`Retry`, `Open settings`, `View incident`). |
| **Alert centre** | A bell in the command bar with a count → the existing `/console/alerts` surface | History, acknowledged state, per-alert detail. |

Rules that make this professional rather than noisy:

1. **Never overlay content.** A toast that covers a metric is a net negative.
2. **Every alert carries an action.** "Something failed" is not actionable;
   "Model unavailable — retry / switch to DEMO" is.
3. **One banner, not N.** Collapse multiple issues into
   "3 issues — view all" rather than stacking cards.
4. **Auto-dismiss only for success.** Errors persist until acknowledged or
   resolved. A vanishing error is an error nobody fixed.

---

## 3. Design system & aesthetics

### 3.1 Palette

The existing system is a **light glass** console
(`rounded-2xl border-slate-200/80 bg-white/80 backdrop-blur-xl`) over a
blue-tinted gradient. Keep that — it is coherent and already documented in
`GLASS_SYSTEM.md`. The problem is not the palette; it is **insufficient
contrast between surface tiers**, which makes dense layouts read as mush.

Add a stricter elevation ladder rather than a new palette:

| Tier | Token | Use |
|---|---|---|
| Canvas | `--surface-0` | page background (existing gradient) |
| Panel | `--surface-1` `bg-white/80` | cards, panels |
| Inset | `--surface-2` `bg-slate-50/70` | rows inside a panel, table stripes |
| Raised | `--surface-3` + `shadow-sm` | sticky command bar, popovers |

**Status accents** — keep semantic, restrain saturation (the dark theme was
already toned from neon; carry that discipline here):

| Meaning | Light theme | Note |
|---|---|---|
| Nominal | `#15803d` text / `#dcfce7` fill | not `#00E676` |
| Warning | `#b45309` text / `#fef3c7` fill | |
| Critical | `#b91c1c` text / `#fee2e2` fill | |
| Information / active | `#1d4ed8` text / `#dbeafe` fill | the Project 117 blue |
| Agent / AI | `#7c3aed` | distinguishes agent actions from human ones |

**Rule:** status colour appears as **text or a 2px accent**, never as a large
fill, except for the one critical alert that genuinely demands the whole
card.

### 3.2 Typography scale

For high-density dashboards the working range is 11–24 px. Anything above 24
belongs on a landing page.

| Role | Size / weight | Use |
|---|---|---|
| Metric | `28px / 600 / tabular-nums` | the big number in a vitals card |
| Page title | `20px / 600` | command bar |
| Section | `12px / 600 / 0.08em / uppercase` | "PLANT STATUS", "RECENT ACTIVITY" |
| Body | `13px / 400` | |
| Meta | `11px / 400` | timestamps, secondary labels |
| **Mono** | `12px / 500` | **every tag, ID, reading, timestamp** |

**`font-variant-numeric: tabular-nums` on every number that changes** — without
it, digits jitter as values update and the whole dashboard looks unstable.

The mono register for machine data is the single highest-leverage typographic
change: it is what makes industrial software look industrial.

### 3.3 Spacing & touch

- 4px base. Permitted steps: `4 · 8 · 12 · 16 · 24 · 32 · 48`.
- Card padding `16px`; panel gap `16px`; section gap `32px`.
- Row height in dense lists: `40px` (desktop) / `48px` (touch).
- Min interactive target `32×32` desktop, `44×44` touch.
- Borders: `1px` at `--surface-1` edge, `border-slate-200/80`. Never two
  competing borders.

### 3.4 Motion

Restraint is the brief. Permitted:

| Motion | Duration | Use |
|---|---|---|
| Value change | 180ms ease-out | number tick |
| Panel enter | 220ms `SPRING` (existing token) | route mount |
| Flow dash | continuous, only when `enabled && flow > 0` | the one ambient animation |
| Alert pulse | 2.4s, **max 3 cycles then stop** | new critical only |

**Forbidden:** particles, glow pulses, parallax, anything that animates while
the plant is nominal. A control-room display that is always moving is a
display nobody trusts.

Respect `prefers-reduced-motion` — the codebase already does this in places;
make it universal.

---

## 4. Prioritised implementation order

| # | Change | Effort | Impact |
|---|---|---|---|
| 1 | Replace hero copy with the live posture bar | S | High — removes the biggest "amateur" signal |
| 2 | Promote Pending Approvals into the vitals tier | S | High — surfaces already-fetched, high-value data |
| 3 | Activity feed: severity dot, actor, dual timestamp, filters | M | High |
| 4 | Delete the marketing lede; move it to `/` (already there) | XS | Medium |
| 5 | Resize the Core from 70 % to 8 columns | S | High — reclaims the viewport |
| 6 | Make Core nodes interactive → filter the Action Queue | L | High — turns decoration into navigation |
| 7 | Sparklines + deltas on vitals cards | M | Medium |
| 8 | Inline alert banner with actions, replacing the toast pattern | M | Medium |
| 9 | Apply the mono register + tabular-nums globally | S | Medium — cheap, large perceived quality gain |

Items **1–5 and 9** are the "10/10" jump. They are all small, and together
they convert the page from *a hero with a sidebar* into *a dashboard*.

---

## 5. What to keep

Worth stating explicitly, because a redesign often destroys good work:

- **The glass surface system** — coherent, documented, and already consistent
  across the console. Do not replace it.
- **The Knowledge Core as an idea** — it is the product's thesis and the only
  topology view. Keep it; change its *job*, not its existence.
- **`Counter`** for value transitions and **`home-glass`** for surface —
  reuse, don't rebuild.
- **The `data-testid` hooks** (`plant-status`, `recent-activity`,
  `system-health`, `active-agents`, `pending-approvals`) — the audit gates
  depend on them. Any redesign must preserve them or update the gates in the
  same change.
- **The honest empty states** — `equipment === null ? "—"` rather than a fake
  zero. Preserve that discipline; it is rarer than it should be.
