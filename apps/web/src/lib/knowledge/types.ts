/**
 * Knowledge Universe — shared graph model.
 *
 * Two namespaces, one renderer:
 *
 *   plant   — the refinery. Built at runtime from the plant definition served
 *             by the simulation API (local SQLite store) plus the console
 *             records (documents, work orders, anomalies, history, rules).
 *   system  — Project 117's own source graph, compiled from graphify's
 *             graph.json by scripts/build_knowledge_graph.py.
 *
 * Every node carries a stable, namespaced id (`equipment:C-3`,
 * `document:d-1`) so the same concept can be referenced from the app, from
 * the simulation, and from the Obsidian vault written by
 * scripts/graphify-obsidian.sh.
 */

export type Namespace = "plant" | "system";

/** How an edge came to exist. Never inferred by the UI — always from data. */
export type Provenance =
  | "EXTRACTED" // parsed straight out of a dataset field
  | "INFERRED" // derived by graphify's semantic pass
  | "OBSERVED" // read from live/simulated telemetry
  | "SIMULATED" // produced by the simulation engine
  | "AI-DERIVED" // produced by an agent
  | "HUMAN-CONFIRMED"; // approved or authored by a person

export interface KNode {
  id: string;
  label: string;
  /** equipment | sensor | document | work_order | anomaly | rule | … */
  type: string;
  /** Community name (system graph) or area name (plant graph). */
  group?: string;
  /** Short state word shown on the node: warning, verified, open… */
  status?: string;
  /** Where this node came from, shown as provenance in the detail panel. */
  source?: string;
  /** Real plant coordinates where the dataset provides them. */
  x?: number;
  y?: number;
  /** Free-form facts rendered in the detail panel. */
  facts?: Record<string, string | number | undefined>;
  /** Deep link this node opens, if it has one. */
  href?: string;
}

export interface KEdge {
  id: string;
  from: string;
  to: string;
  /** HAS_SENSOR, SUPPORTED_BY, FLOWS_TO, calls, imports… */
  relation: string;
  provenance: Provenance;
  /** File or document the relationship was read from. */
  source?: string;
  /** 0–1. Only present when the producer supplied one. */
  confidence?: number;
}

export interface KCommunity {
  id: string;
  name: string;
  size: number;
  degree?: number;
  major?: { id: string; label: string; kind: string }[];
}

export interface KGraph {
  namespace: Namespace;
  nodes: KNode[];
  edges: KEdge[];
  communities: KCommunity[];
  /** Provenance tally for the legend / stats strip. */
  stats: {
    nodes: number;
    edges: number;
    communities: number;
    byProvenance: Record<string, number>;
    byType: Record<string, number>;
  };
}

/* -------------------------------------------------------------- helpers */

export function indexGraph(g: KGraph): {
  byId: Map<string, KNode>;
  adjacency: Map<string, { edge: KEdge; other: string; out: boolean }[]>;
} {
  const byId = new Map(g.nodes.map((n) => [n.id, n]));
  const adjacency = new Map<string, { edge: KEdge; other: string; out: boolean }[]>();
  for (const e of g.edges) {
    if (!byId.has(e.from) || !byId.has(e.to)) continue;
    if (!adjacency.has(e.from)) adjacency.set(e.from, []);
    if (!adjacency.has(e.to)) adjacency.set(e.to, []);
    adjacency.get(e.from)!.push({ edge: e, other: e.to, out: true });
    adjacency.get(e.to)!.push({ edge: e, other: e.from, out: false });
  }
  return { byId, adjacency };
}

/**
 * Breadth-first shortest path between two nodes. Returns the node ids in
 * order, or null when the two are not connected. Only real edges are walked —
 * nothing is invented to bridge a gap.
 */
export function shortestPath(
  adjacency: ReturnType<typeof indexGraph>["adjacency"],
  from: string,
  to: string,
  maxHops = 8,
): string[] | null {
  if (from === to) return [from];
  const prev = new Map<string, string>();
  const seen = new Set([from]);
  let frontier = [from];
  for (let hop = 0; hop < maxHops && frontier.length; hop++) {
    const next: string[] = [];
    for (const id of frontier) {
      for (const { other } of adjacency.get(id) ?? []) {
        if (seen.has(other)) continue;
        seen.add(other);
        prev.set(other, id);
        if (other === to) {
          const path = [to];
          let cur = to;
          while (prev.has(cur)) {
            cur = prev.get(cur)!;
            path.unshift(cur);
          }
          return path;
        }
        next.push(other);
      }
    }
    frontier = next;
  }
  return null;
}

/** Neighbourhood within `depth` hops, nearest first. */
export function neighborhood(
  adjacency: ReturnType<typeof indexGraph>["adjacency"],
  start: string,
  depth: number,
): Set<string> {
  const seen = new Set([start]);
  let frontier = [start];
  for (let d = 0; d < depth; d++) {
    const next: string[] = [];
    for (const id of frontier) {
      for (const { other } of adjacency.get(id) ?? []) {
        if (!seen.has(other)) {
          seen.add(other);
          next.push(other);
        }
      }
    }
    frontier = next;
  }
  return seen;
}

export function summarize(nodes: KNode[], edges: KEdge[], communities: KCommunity[]): KGraph["stats"] {
  const byProvenance: Record<string, number> = {};
  const byType: Record<string, number> = {};
  for (const e of edges) byProvenance[e.provenance] = (byProvenance[e.provenance] ?? 0) + 1;
  for (const n of nodes) byType[n.type] = (byType[n.type] ?? 0) + 1;
  return { nodes: nodes.length, edges: edges.length, communities: communities.length, byProvenance, byType };
}

/**
 * Node colour by semantic type — the bright palette. Colour carries meaning,
 * not decoration: equipment blue, anomalies red/amber, documents grey,
 * sensors green, knowledge violet.
 *
 * These are literal hex values because canvas 2D cannot read CSS custom
 * properties; they are kept in sync with the `.cs` tokens in console.css.
 */
export const TYPE_COLOR: Record<string, string> = {
  // plant
  plant: "#475569",
  area: "#64748b",
  equipment: "#2563eb",
  sensor: "#10b981",
  document: "#64748b",
  work_order: "#f59e0b",
  anomaly: "#dc2626",
  event: "#64748b",
  rule: "#7c3aed",
  approval: "#f59e0b",
  agent: "#2563eb",
  failure_mode: "#dc2626",
  scenario: "#f59e0b",
  // system
  file: "#64748b",
  class: "#2563eb",
  function: "#10b981",
  symbol: "#64748b",
  doc: "#64748b",
  community: "#475569",
};

export const PROVENANCE_TONE: Record<Provenance, string> = {
  EXTRACTED: "var(--ink-2)",
  INFERRED: "var(--violet)",
  OBSERVED: "var(--green)",
  SIMULATED: "var(--amber)",
  "AI-DERIVED": "var(--blue)",
  "HUMAN-CONFIRMED": "var(--amber)",
};

export const colorOf = (type: string) => TYPE_COLOR[type] ?? "#64748b";
