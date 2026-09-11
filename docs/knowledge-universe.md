# Knowledge Universe

`/console/knowledge` is a real interface over two live graphs, not a diagram.

| Namespace | Source | Size |
| --- | --- | --- |
| **Plant Knowledge** | `public/simulation/refinery/*.json` + the console's own records | 376 nodes, 634 relationships, 18 areas |
| **System Knowledge** | `graphify-out/graph.json` via `scripts/build_knowledge_graph.py` | 4,159 nodes, 9,114 edges, 226 communities |

Both share one renderer (`src/components/knowledge/GraphCanvas.tsx`), one layout
engine (`src/lib/knowledge/layout.ts`) and one model
(`src/lib/knowledge/types.ts`).

## Plant graph — where the data comes from

Nothing in the plant graph is invented. Every node is a record and every edge
is read from a field that exists:

| Edge | Read from |
| --- | --- |
| `CONTAINS` area → equipment | `equipment.json` `area_id` |
| `HAS_SENSOR` equipment → sensor | `equipment.json` `sensors[]` |
| `FLOWS_TO` equipment → equipment | `connections.json` `source`/`target` |
| `CAN_FAIL_WITH` sensor → failure mode | `failure_modes.json` `applies_to` |
| `INJECTS` scenario → equipment | `scenarios.json` `steps[].target` |
| `FOR_EQUIPMENT` work order → equipment | `WorkOrder.equipment_id` |
| `SUPPORTED_BY` work order → document | `WorkOrder.evidence[].document_id` |
| `OBSERVED_ON` anomaly → equipment | `Alert.equipment_id` |
| `ABOUT` event → equipment | `HistoryEvent.equipment_id` |
| `LEARNED_FROM` rule → equipment | tag named in the rule's own text |
| `AUTHORIZES` approval → equipment | `ApprovalRequest.equipment_id` |
| `GOVERNS` approval → work order | `WO-\d+` in the approval action |
| `PRODUCED` agent → work order | `WorkOrder.assignee` |
| `MENTIONS` document → equipment | tag in the filename |

Equipment coordinates are the dataset's own: `equipment.json` `x`/`y` are
area-relative, so the layout adds the area rect origin. The graph is literally
the plant. Knowledge entities orbit the asset they are anchored to, at a radius
set by type — anchored to a *single* asset rather than a centroid, so a
document that mentions three units does not get dragged into the empty space
between them.

## System graph — progressive, not all at once

4,159 nodes cannot be handed to the renderer on first paint. Two artifacts:

- `public/knowledge/system-index.json` (167 KB) — 226 communities, the 550
  edges between them, and each community's major nodes. This is what renders
  first.
- `public/knowledge/system-graph.json` (2.36 MB) — the full node/link set,
  fetched only when a community is expanded or a full search runs.

Community names are graphify's own, read straight from the artifact. None are
renamed or invented.

Rebuild after the graph changes:

```bash
python3 scripts/build_knowledge_graph.py
```

## Provenance

Every edge carries a classification, shown in the detail panel (right-click a
relationship to pin the card):

`EXTRACTED` parsed from a field · `INFERRED` graphify semantic pass ·
`OBSERVED` telemetry · `SIMULATED` engine output · `AI-DERIVED` agent output ·
`HUMAN-CONFIRMED` approved or authored by a person.

Each also records the **source** (`equipment.json`, `console telemetry`,
`inspection_report_aug.pdf`) and, where the producer supplied one, a confidence.

## Interaction

Scroll to zoom · drag to pan · click to select · double-click a community to
expand. Selecting a node frames its neighbourhood and recedes everything else.
Controls: zoom in/out, fit, focus selection, reset, fullscreen. `⌘K` focuses
search; `Esc` clears the selection.

Path exploration: *Set path start* on one node and *Set path end* on another
runs a BFS over real edges only (max 8 hops). The path illuminates and the
edges animate. No relationship is invented to bridge a gap.

## Deep links

Selecting an entity offers real navigation, and each target honours the context:

| Action | Destination | Context handling |
| --- | --- | --- |
| Open digital twin | `/console/equipment/C-3` | route param |
| Open in simulation | `/console/simulation/builder?focus=C-3` | loads the refinery template, selects C-3 |
| Ask AI about this | `/console/workspace?entity=…` | pre-fills `Investigate …` |
| Work order | `/console/work-orders/WO-8852` | route param |
| Document | `/console/documents?doc=d-1` | existing `useSearchParams` handling |
| Event | `/console/history?event=h-3` | scrolls to and outlines the event |

The builder templates ship a simplified tag set (`TK-100`, `P-110`…). When a
deep link names a unit they do not contain, the builder materialises the real
record from `consoleData.equipment` instead of silently doing nothing.

## Obsidian / stable ids

Node ids are namespaced and stable — `equipment:C-3`, `document:d-1`,
`event:h-3`, `work_order:WO-8852` — so the same concept can be referenced by
the app, the simulation, and the Obsidian vault written by
`scripts/graphify-obsidian.sh`.

## Performance notes

- Canvas 2D, not SVG/DOM — the system graph would drown in layout cost.
- The rAF loop runs **only** while a path is animating. An idle graph draws
  once per change and costs nothing.
- Device pixel ratio capped at 2.
- Labels are de-collided: a label is dropped rather than allowed to overlap one
  already drawn; selection and anchors claim space first.
- `ResizeObserver` drives canvas sizing; framing waits for the first measure.
