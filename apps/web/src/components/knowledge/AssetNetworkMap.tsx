"use client";

/**
 * AssetNetworkMap — the home dashboard's interactive asset network.
 *
 * It is a thin, opinionated shell over the *existing* knowledge graph stack:
 *
 *   data    `buildPlantGraph()` — the same cached build /console/knowledge uses,
 *           so mounting both pages in one session performs one build, not two.
 *   layout  `layoutPlant()` — the same deterministic force layout, seeded from
 *           the plant dataset's own coordinates.
 *   render  `GraphCanvas` — the same canvas renderer, with its own pan, wheel
 *           zoom and click-to-focus. No gesture code is reimplemented here.
 *
 * What this wrapper adds is only what the home page needs and the Knowledge
 * page deliberately does not do:
 *
 *   · a node-type filter sidebar (Equipment / Documents / Agents / Materials)
 *     plus a live search box, so the map can be narrowed to an asset class;
 *   · real equipment-state colouring and real criticality sizing, handed to the
 *     canvas through its optional `colorOfNode` / `radiusOfNode` props;
 *   · a keyboard-reachable entity list, because a `<canvas>` is not itself
 *     focusable and every node a mouse can select must also be reachable by Tab
 *     and Enter;
 *   · `onSelect` bubbling the node id up so the Action Queue can filter to it.
 *
 * Nothing here invents a node, an edge or a state: every node is a row the
 * backend served, and a node with no dataset `state` falls back to its type
 * colour rather than being painted a status it does not have.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import GraphCanvas, { type GraphHandle } from "@/components/knowledge/GraphCanvas";
import { buildPlantGraph } from "@/lib/knowledge/plant";
import { layoutPlant, type Pt } from "@/lib/knowledge/layout";
import {
  colorOf,
  indexGraph,
  neighborhood,
  summarize,
  type KEdge,
  type KGraph,
  type KNode,
} from "@/lib/knowledge/types";

import "@/styles/knowledge.css";

/* ------------------------------------------------------------- categories */

type Category = "equipment" | "document" | "agent" | "material";

/**
 * The four asset classes the operator filters by. `types` are the real graph
 * node types each class covers — the counts beside each chip are read off the
 * graph, never assumed.
 */
const CATEGORIES: { id: Category; label: string; types: string[] }[] = [
  { id: "equipment", label: "Equipment", types: ["equipment"] },
  { id: "document", label: "Documents", types: ["document"] },
  { id: "agent", label: "Agents", types: ["agent"] },
  { id: "material", label: "Materials", types: ["material", "storage", "supplier", "price_history"] },
];

/**
 * The plant dataset's own equipment `state` vocabulary → colour. The word is
 * always rendered in the legend beside the swatch, so colour is never the only
 * signal. A state the dataset does not use falls through to the type colour.
 */
const STATE_TONE: Record<string, "ok" | "warn" | "crit"> = {
  normal: "ok",
  ok: "ok",
  healthy: "ok",
  warning: "warn",
  warn: "warn",
  critical: "crit",
  crit: "crit",
};

const STATE_COLOR: Record<string, string> = {
  ok: "#10b981",
  warn: "#f59e0b",
  crit: "#dc2626",
};

function stateTone(status?: string): "ok" | "warn" | "crit" | null {
  if (!status) return null;
  return STATE_TONE[status.toLowerCase()] ?? null;
}

/** Real criticality (the dataset's 1–3, builder topology's own scale) → radius. */
function criticalityRadius(n: KNode): number {
  const c = Number(n.facts?.criticality);
  if (!Number.isFinite(c)) return 4.6;
  return 3.6 + Math.min(Math.max(c, 1), 5) * 1.25;
}

/* ------------------------------------------------------------ canonicalise */

/**
 * Collapse the duplicated asset nodes the shared builder currently emits.
 *
 * `buildPlantGraph` merges a console equipment record into the refinery record
 * it is the same physical unit as — but it keys the merge on the console `id`
 * (`e-P-1001`) while the refinery set is keyed by `tag` (`P-1001`), so the two
 * never match and every asset lands in the graph twice, with its sensors
 * doubled. In the live dataset that is 116 equipment nodes and 448 sensors for
 * a plant of 58 units and 224 instruments (measured on /console/knowledge:
 * "Equipment 135" = 116 + plant + 18 areas).
 *
 * The home map shows machines, so it collapses the pair onto the refinery-keyed
 * canonical node and rewrites every edge endpoint through the same map — a
 * work order that pointed at `equipment:e-P-1001` still reaches `P-1001`. This
 * is a display-level de-duplication of identical real assets, not a new graph.
 * The builder itself is shared with /console/knowledge and is left untouched.
 */
function canonicalAssets(graph: KGraph): { graph: KGraph; collapsed: number } {
  const ids = new Set(graph.nodes.map((n) => n.id));
  const remap = new Map<string, string>();
  for (const n of graph.nodes) {
    const m = /^equipment:e-(.+)$/.exec(n.id);
    if (m && ids.has(`equipment:${m[1]}`)) remap.set(n.id, `equipment:${m[1]}`);
  }
  if (!remap.size) return { graph, collapsed: 0 };

  const map = (id: string) => remap.get(id) ?? id;
  const seen = new Set<string>();
  const edges: KEdge[] = [];
  for (const e of graph.edges) {
    const from = map(e.from);
    const to = map(e.to);
    if (from === to) continue;
    const key = `${from}|${to}|${e.relation}`;
    if (seen.has(key)) continue;
    seen.add(key);
    edges.push(from === e.from && to === e.to ? e : { ...e, from, to });
  }
  const drop = new Set(remap.keys());
  const nodes = graph.nodes.filter((n) => !drop.has(n.id));
  return {
    graph: { ...graph, nodes, edges, stats: summarize(nodes, edges, graph.communities) },
    collapsed: remap.size,
  };
}

/* --------------------------------------------------------------- component */

export function AssetNetworkMap({
  selected,
  onSelect,
}: {
  /** Selected graph node id (`equipment:P-1001`), owned by the page. */
  selected: string | null;
  onSelect: (id: string | null) => void;
}) {
  const graphRef = useRef<GraphHandle>(null);
  const [full, setFull] = useState<KGraph | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [active, setActive] = useState<Set<Category>>(() => new Set<Category>(["equipment", "document"]));
  const [query, setQuery] = useState("");

  // One build. `buildPlantGraph` caches both the result and the in-flight
  // promise, so a re-mount (or the Knowledge page mounted in the same session)
  // awaits this build instead of starting a second one.
  useEffect(() => {
    let alive = true;
    buildPlantGraph()
      .then((g) => {
        if (alive) setFull(canonicalAssets(g).graph);
      })
      .catch((e) => {
        if (alive) setFailed(String((e as Error)?.message ?? e));
      });
    return () => {
      alive = false;
    };
  }, []);

  const visibleTypes = useMemo(
    () => new Set(CATEGORIES.filter((c) => active.has(c.id)).flatMap((c) => c.types)),
    [active],
  );

  /** The filtered graph: active types ∩ the search query, edges kept only
   *  between visible nodes so no line points at a node that is not drawn. */
  const graph = useMemo<KGraph | null>(() => {
    if (!full) return null;
    const q = query.trim().toLowerCase();
    const nodes = full.nodes.filter((n) => {
      if (!visibleTypes.has(n.type)) return false;
      if (!q) return true;
      return `${n.label} ${n.id} ${n.group ?? ""} ${n.status ?? ""}`.toLowerCase().includes(q);
    });
    const ids = new Set(nodes.map((n) => n.id));
    const edges = full.edges.filter((e) => ids.has(e.from) && ids.has(e.to));
    return { ...full, nodes, edges, stats: summarize(nodes, edges, full.communities) };
  }, [full, visibleTypes, query]);

  // Deterministic force layout over the filtered set; no new layout maths.
  const positions = useMemo<Map<string, Pt>>(
    () => (graph ? layoutPlant(graph) : new Map<string, Pt>()),
    [graph],
  );

  const adjacency = useMemo(
    () =>
      graph
        ? indexGraph(graph).adjacency
        : new Map<string, { edge: KEdge; other: string; out: boolean }[]>(),
    [graph],
  );
  const highlight = useMemo(
    () => (selected ? neighborhood(adjacency, selected, 1) : new Set<string>()),
    [adjacency, selected],
  );

  /** Real per-class counts, so a chip never advertises a number it cannot back. */
  const counts = useMemo(() => {
    const m = new Map<Category, number>();
    if (!full) return m;
    for (const c of CATEGORIES) m.set(c.id, full.nodes.filter((n) => c.types.includes(n.type)).length);
    return m;
  }, [full]);

  const toggle = useCallback((id: Category) => {
    setActive((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const select = useCallback(
    (id: string | null) => {
      onSelect(id);
      if (id) graphRef.current?.focusNode(id);
    },
    [onSelect],
  );

  /** Keyboard/assistive fallback for the canvas: real nodes as real buttons. */
  const listed = useMemo(() => {
    if (!graph) return [] as KNode[];
    return [...graph.nodes]
      .sort((a, b) => {
        const ca = a.type === "equipment" ? -(Number(a.facts?.criticality) || 0) : 1;
        const cb = b.type === "equipment" ? -(Number(b.facts?.criticality) || 0) : 1;
        return ca - cb || a.label.localeCompare(b.label);
      })
      .slice(0, 90);
  }, [graph]);

  const nodeCount = graph?.nodes.length ?? 0;

  return (
    <div className="home-net">
      {/* ---- the filter sidebar ---- */}
      <div className="home-net__side">
        <p className="home-net__label" id="home-net-types">
          Node types
        </p>
        <div className="home-net__toggles" role="group" aria-labelledby="home-net-types">
          {CATEGORIES.map((c) => {
            const on = active.has(c.id);
            const count = counts.get(c.id);
            return (
              <button
                key={c.id}
                type="button"
                className="home-net__toggle"
                aria-pressed={on}
                onClick={() => toggle(c.id)}
                title={`${on ? "Hide" : "Show"} ${c.label.toLowerCase()}`}
              >
                <span className="home-net__check" aria-hidden="true">
                  {on ? "✓" : ""}
                </span>
                <span className="home-net__tname">{c.label}</span>
                <em className="home-net__tcount">{count === undefined ? "—" : count}</em>
              </button>
            );
          })}
        </div>

        <label className="home-net__search">
          <span className="home-sr">Search the asset network</span>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search tag, name…"
            aria-label="Search the asset network"
          />
          {query && (
            <button type="button" onClick={() => setQuery("")} aria-label="Clear search">
              ×
            </button>
          )}
        </label>

        <p className="home-net__label">
          Entities <em className="home-net__count">{nodeCount}</em>
        </p>
        <ul className="home-net__list" aria-label="Visible entities">
          {listed.map((n) => {
            const isOn = selected === n.id;
            return (
              <li key={n.id}>
                <button
                  type="button"
                  className="home-net__entity"
                  aria-pressed={isOn}
                  onClick={() => (isOn ? select(null) : select(n.id))}
                  title={`${n.type}${n.status ? ` · ${n.status}` : ""}`}
                >
                  <span
                    className="home-net__swatch"
                    data-tone={stateTone(n.status) ?? undefined}
                    style={{ background: colorFor(n) }}
                    aria-hidden="true"
                  />
                  {shortLabel(n)}
                </button>
              </li>
            );
          })}
          {!listed.length && <li className="home-net__none">No entity matches.</li>}
        </ul>
      </div>

      {/* ---- the canvas ---- */}
      <div className="home-net__stage ku-stage">
        <div className="ku-controls" role="toolbar" aria-label="Network zoom and pan controls">
          <button type="button" onClick={() => graphRef.current?.zoomIn()} title="Zoom in" aria-label="Zoom in">
            ＋
          </button>
          <button type="button" onClick={() => graphRef.current?.zoomOut()} title="Zoom out" aria-label="Zoom out">
            －
          </button>
          <button type="button" onClick={() => graphRef.current?.fit()} title="Fit to view" aria-label="Fit to view">
            ⤢
          </button>
          <button
            type="button"
            onClick={() => selected && graphRef.current?.focusNode(selected)}
            title="Focus selection"
            aria-label="Focus selection"
            disabled={!selected}
          >
            ◎
          </button>
          <button type="button" onClick={() => graphRef.current?.reset()} title="Reset camera" aria-label="Reset camera">
            ↺
          </button>
        </div>

        {failed ? (
          <p className="home-net__state" role="alert">
            Asset network unavailable. {failed}
          </p>
        ) : !graph ? (
          <p className="home-net__state">Building the asset network from the plant dataset…</p>
        ) : nodeCount === 0 ? (
          <p className="home-net__state">
            No entity matches the current filters. Enable a node type or clear the search.
          </p>
        ) : (
          <GraphCanvas
            ref={graphRef}
            graph={graph}
            positions={positions}
            selected={selected}
            highlight={highlight}
            path={[]}
            onSelect={select}
            fontSize={11}
            colorOfNode={colorFor}
            radiusOfNode={radiusFor}
          />
        )}

        {/* Legend — colour plus the word, never colour alone. */}
        <div className="home-net__legend" aria-label="Legend">
          <span className="home-net__legenditem">
            <i style={{ background: STATE_COLOR.ok }} aria-hidden="true" /> normal
          </span>
          <span className="home-net__legenditem">
            <i style={{ background: STATE_COLOR.warn }} aria-hidden="true" /> warning
          </span>
          <span className="home-net__legenditem">
            <i style={{ background: STATE_COLOR.crit }} aria-hidden="true" /> critical
          </span>
          <span className="home-net__legenditem home-net__legenditem--note">
            size ∝ criticality
          </span>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------- helpers */

/** Equipment keeps its real state colour; everything else keeps its type
 *  colour, so the map is legible without pretending a document has a state. */
function colorFor(n: KNode): string {
  const tone = stateTone(n.status);
  if (n.type === "equipment" && tone) return STATE_COLOR[tone];
  return colorOf(n.type);
}

function radiusFor(n: KNode): number {
  return n.type === "equipment" ? criticalityRadius(n) : 4.4;
}

function shortLabel(n: KNode): string {
  const tag = typeof n.facts?.tag === "string" ? n.facts.tag : null;
  if (n.type === "equipment" && tag) return tag;
  return n.label.replace(/\s*\(([^)]+)\)\s*$/, " · $1").slice(0, 34);
}
