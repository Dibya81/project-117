"use client";

/**
 * System Graph — Project 117's own source, as compiled by graphify.
 *
 * 4,159 nodes is far too many to hand the renderer on first paint, so the page
 * works in two stages:
 *
 *   1. `systemOverview()` builds a graph of graphify's 226 communities and the
 *      550 edges between them. That is what loads first.
 *   2. `loadSystemFull()` pulls the complete node/link set on demand and
 *      `expandCommunity()` splices one community's members in at a time.
 *
 * Community names are graphify's own — read from the artifact, never renamed
 * or invented here.
 */
import { summarize, type KCommunity, type KEdge, type KGraph, type KNode } from "./types";

const INDEX_URL = "/knowledge/system-index.json";
const FULL_URL = "/knowledge/system-graph.json";

export interface SystemIndex {
  generated: string;
  source: string;
  generator: string;
  nodeCount: number;
  edgeCount: number;
  communityCount: number;
  relations: Record<string, number>;
  communities: { id: number; name: string; size: number; degree: number; major: { id: string; label: string; kind: string }[] }[];
  communityEdges: { a: number; b: number; w: number }[];
}

interface FullNode { i: string; l: string; c: number | null; k: string; f: string; o: string }
interface FullLink { s: string; t: string; r: string; c: string; f: string; o: string }
export interface SystemFull { nodes: FullNode[]; links: FullLink[] }

export const COMMUNITY_NODE = (id: number) => `community:${id}`;

let indexCache: Promise<SystemIndex> | null = null;
let fullCache: Promise<SystemFull> | null = null;

export function loadSystemIndex(): Promise<SystemIndex> {
  indexCache ??= fetch(INDEX_URL).then((r) => {
    if (!r.ok) throw new Error(`system-index.json → HTTP ${r.status}`);
    return r.json() as Promise<SystemIndex>;
  });
  return indexCache;
}

export function loadSystemFull(): Promise<SystemFull> {
  fullCache ??= fetch(FULL_URL).then((r) => {
    if (!r.ok) throw new Error(`system-graph.json → HTTP ${r.status}`);
    return r.json() as Promise<SystemFull>;
  });
  return fullCache;
}

/** 226 communities as nodes, their 550 inter-community edges as links. */
export function systemOverview(idx: SystemIndex): KGraph {
  const nodes: KNode[] = idx.communities.map((c) => ({
    id: COMMUNITY_NODE(c.id),
    label: c.name,
    type: "community",
    group: c.name,
    status: `${c.size} nodes`,
    source: "graphify community detection",
    facts: {
      nodes: c.size,
      connections: c.degree,
      major: c.major.map((m) => m.label).slice(0, 5).join(", "),
    },
  }));

  const edges: KEdge[] = idx.communityEdges.map((e, i) => ({
    id: `se-${i}`,
    from: COMMUNITY_NODE(e.a),
    to: COMMUNITY_NODE(e.b),
    relation: `${e.w} edges`,
    provenance: "EXTRACTED",
    source: "graphify-out/graph.json",
    confidence: Math.min(1, e.w / 20),
  }));

  const communities: KCommunity[] = idx.communities.map((c) => ({
    id: String(c.id), name: c.name, size: c.size, degree: c.degree, major: c.major,
  }));

  return {
    namespace: "system",
    nodes,
    edges,
    communities,
    stats: summarize(nodes, edges, communities),
  };
}

/** Every member of one community, plus the edges among them. */
export function expandCommunity(full: SystemFull, communityId: number): { nodes: KNode[]; edges: KEdge[] } {
  const members = full.nodes.filter((n) => n.c === communityId);
  const ids = new Set(members.map((m) => m.i));
  const nodes: KNode[] = members.map((n) => ({
    id: n.i,
    label: n.l,
    type: n.k,
    group: String(n.c),
    source: n.f ? `${n.f}${n.o ? ` ${n.o}` : ""}` : "graphify",
    facts: { file: n.f, location: n.o, kind: n.k },
  }));
  const edges: KEdge[] = full.links
    .filter((l) => ids.has(l.s) && ids.has(l.t))
    .map((l, i) => ({
      id: `sx-${communityId}-${i}`,
      from: l.s,
      to: l.t,
      relation: l.r,
      provenance: l.c === "INFERRED" ? "INFERRED" : "EXTRACTED",
      source: l.f ? `${l.f}${l.o ? ` ${l.o}` : ""}` : undefined,
    }));
  return { nodes, edges };
}

/** Search across the full system graph (loads it if needed). */
export function searchSystem(full: SystemFull, query: string, limit = 40): KNode[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const out: KNode[] = [];
  for (const n of full.nodes) {
    if (n.l.toLowerCase().includes(q) || n.i.toLowerCase().includes(q) || n.f.toLowerCase().includes(q)) {
      out.push({
        id: n.i, label: n.l, type: n.k, group: String(n.c),
        source: n.f ? `${n.f}${n.o ? ` ${n.o}` : ""}` : "graphify",
        facts: { file: n.f, location: n.o, kind: n.k },
      });
      if (out.length >= limit) break;
    }
  }
  return out;
}
