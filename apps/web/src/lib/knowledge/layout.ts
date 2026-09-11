/**
 * Force-directed graph layout.
 *
 * The canvas is an open plane, so the layout must be too: nodes are placed by
 * a real force simulation — charge repulsion between every nearby pair, link
 * springs along every edge, and a mild centring pull that keeps disconnected
 * components from drifting away — rather than by a fixed grid or an orbit
 * ring. The result reads as one connected organism that breathes into place.
 *
 * The simulation is:
 *
 *   deterministic   every random draw comes from a fixed-seed PRNG
 *                   (`FORCE_SEED`), and node order is the graph's own order,
 *                   so the same graph always produces the same picture.
 *   bounded         `createForceSim` exposes `tick(count)` / `settle()`;
 *                   the alpha cooling schedule stops on its own at
 *                   `maxTicks`, so a caller can never spin forever.
 *   fast            repulsion uses a uniform-grid cutoff so each tick is
 *                   O(n · neighbours + edges), not O(n²). 500 nodes settle
 *                   in a few milliseconds of synchronous ticking.
 *
 * The exported `layout*` helpers are thin wrappers the Knowledge page calls;
 * `forceLayout` / `createForceSim` are the lower-level API.
 */
import type { KGraph, KNode } from "./types";

export interface Pt { x: number; y: number }

/** Fixed seed. The layout is byte-identical on every run. */
export const FORCE_SEED = 0x1170de;

/** Small, fast, deterministic PRNG (mulberry32). Used only for tie-breaking. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Stable FNV-1a hash → [0,1). Used for deterministic per-node angular jitter. */
function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 4294967295;
}

/** The golden angle — the most even deterministic spread there is. */
const GOLDEN_ANGLE = 2.399963229728653;

export interface ForceOptions {
  /** Seed positions (e.g. the previous layout) instead of a fresh scatter. */
  initial?: Map<string, Pt>;
  seed?: number;
  /** Rest length of an edge spring, in graph units. */
  linkDistance?: number;
  linkStrength?: number;
  /** Charge magnitude; larger = nodes push further apart. */
  repulsion?: number;
  /** Pull toward the seed centroid. Small — this only stops drift. */
  centering?: number;
  /** Repulsion is ignored beyond this distance (grid acceleration). */
  cutoff?: number;
  /** Velocity retained per tick. */
  damping?: number;
  startAlpha?: number;
  minAlpha?: number;
  alphaDecay?: number;
  maxTicks?: number;
  /** Base radius of the deterministic phyllotaxis seed scatter. */
  spread?: number;
  maxVelocity?: number;
}

export interface ForceSim {
  /** Live positions. The map is updated after each `tick`. */
  readonly positions: Map<string, Pt>;
  alpha: number;
  ticks: number;
  maxTicks: number;
  readonly settled: boolean;
  /** Advance at most `count` ticks (bounded by `maxTicks`). */
  tick(count?: number): ForceSim;
  /** Advance until settled or `limit` ticks have run. Returns positions. */
  settle(limit?: number): Map<string, Pt>;
}

const DEFAULTS = {
  seed: FORCE_SEED,
  linkDistance: 46,
  linkStrength: 0.8,
  repulsion: 6200,
  centering: 0.012,
  cutoff: 200,
  damping: 0.6,
  startAlpha: 1,
  minAlpha: 0.02,
  alphaDecay: 0.985,
  maxTicks: 320,
  spread: 32,
  maxVelocity: 26,
};

/** Grid cell key. Wraps harmlessly — a colliding key only costs one distance test. */
const GRID_BIAS = 1 << 11;
const GRID_SPAN = 1 << 12;
function cellKey(cx: number, cy: number): number {
  const x = (((cx + GRID_BIAS) % GRID_SPAN) + GRID_SPAN) % GRID_SPAN;
  const y = (((cy + GRID_BIAS) % GRID_SPAN) + GRID_SPAN) % GRID_SPAN;
  return x * GRID_SPAN + y;
}

/**
 * Deterministic seed scatter. Nodes with dataset coordinates keep a scaled
 * hint of the real plant geometry; everything else lands on a phyllotaxis
 * spiral. Both are centred on the same origin so the two groups mix cleanly
 * instead of one dwarfing the other.
 */
function seedPositions(
  nodes: KNode[],
  initial: Map<string, Pt> | undefined,
  spread: number,
  rng: () => number,
  px: Float64Array,
  py: Float64Array,
): void {
  const n = nodes.length;
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity, haveCoords = false;
  for (const nd of nodes) {
    if (initial?.has(nd.id)) continue;
    if (nd.x != null && nd.y != null) {
      haveCoords = true;
      minX = Math.min(minX, nd.x); maxX = Math.max(maxX, nd.x);
      minY = Math.min(minY, nd.y); maxY = Math.max(maxY, nd.y);
    }
  }
  let scale = 1, ox = 0, oy = 0;
  if (haveCoords) {
    const w = Math.max(maxX - minX, 1);
    const h = Math.max(maxY - minY, 1);
    const span = spread * Math.sqrt(Math.max(n, 1)) * 2.4;
    scale = span / Math.max(w, h);
    ox = (minX + maxX) / 2;
    oy = (minY + maxY) / 2;
  }

  for (let i = 0; i < n; i++) {
    const nd = nodes[i];
    const init = initial?.get(nd.id);
    if (init) { px[i] = init.x; py[i] = init.y; continue; }
    if (haveCoords && nd.x != null && nd.y != null) {
      px[i] = (nd.x - ox) * scale;
      py[i] = (nd.y - oy) * scale;
      continue;
    }
    const r = spread * Math.sqrt(i + 0.5) * 1.7 + 14;
    const ang = i * GOLDEN_ANGLE + (rng() - 0.5) * 0.5;
    px[i] = Math.cos(ang) * r;
    py[i] = Math.sin(ang) * r;
  }
}

/**
 * Build a bounded, deterministic force simulation for a graph.
 *
 * Forces per tick:
 *   repulsion   ~ repulsion / d²  for every pair within `cutoff`
 *   springs     (d − linkDistance) · linkStrength along every edge
 *   centring    −(p − centroid) · centering
 */
export function createForceSim(graph: KGraph, opts: ForceOptions = {}): ForceSim {
  const o = { ...DEFAULTS, ...opts };
  const nodes = graph.nodes;
  const n = nodes.length;

  const index = new Map<string, number>();
  for (let i = 0; i < n; i++) index.set(nodes[i].id, i);

  const px = new Float64Array(n);
  const py = new Float64Array(n);
  const vx = new Float64Array(n);
  const vy = new Float64Array(n);
  const fx = new Float64Array(n);
  const fy = new Float64Array(n);

  const rng = mulberry32(o.seed);
  seedPositions(nodes, o.initial, o.spread, rng, px, py);

  // Mild centring pulls toward the seed centroid, not the world origin, so a
  // graph seeded from real coordinates is not dragged across the plane.
  let cx = 0, cy = 0;
  for (let i = 0; i < n; i++) { cx += px[i]; cy += py[i]; }
  cx = n ? cx / n : 0;
  cy = n ? cy / n : 0;

  const ea = new Int32Array(graph.edges.length);
  const eb = new Int32Array(graph.edges.length);
  let edgeCount = 0;
  for (const e of graph.edges) {
    const a = index.get(e.from);
    const b = index.get(e.to);
    if (a == null || b == null || a === b) continue;
    ea[edgeCount] = a;
    eb[edgeCount] = b;
    edgeCount++;
  }

  const positions = new Map<string, Pt>();
  const syncPositions = () => {
    for (let i = 0; i < n; i++) positions.set(nodes[i].id, { x: px[i], y: py[i] });
  };
  syncPositions();

  let alpha = o.startAlpha;
  let ticks = 0;
  const cell = o.cutoff;
  const cut2 = o.cutoff * o.cutoff;
  const buckets = new Map<number, number[]>();

  const advance = () => {
    alpha *= o.alphaDecay;
    fx.fill(0);
    fy.fill(0);

    // ---- charge repulsion, accelerated by a uniform grid ---------------
    buckets.clear();
    for (let i = 0; i < n; i++) {
      const key = cellKey(Math.floor(px[i] / cell), Math.floor(py[i] / cell));
      const bucket = buckets.get(key);
      if (bucket) bucket.push(i);
      else buckets.set(key, [i]);
    }
    for (let i = 0; i < n; i++) {
      const gx = Math.floor(px[i] / cell);
      const gy = Math.floor(py[i] / cell);
      for (let ax = -1; ax <= 1; ax++) {
        for (let ay = -1; ay <= 1; ay++) {
          const bucket = buckets.get(cellKey(gx + ax, gy + ay));
          if (!bucket) continue;
          for (let bi = 0; bi < bucket.length; bi++) {
            const j = bucket[bi];
            if (j <= i) continue;
            let dx = px[i] - px[j];
            let dy = py[i] - py[j];
            let d2 = dx * dx + dy * dy;
            if (d2 > cut2) continue;
            if (d2 < 1e-4) {
              // Deterministic tie-break so perfectly coincident seeds separate.
              dx = (i % 7) - 2.5;
              dy = (j % 5) - 1.5;
              d2 = dx * dx + dy * dy || 1;
            }
            const inv = 1 / Math.sqrt(d2);
            const mag = Math.min(o.repulsion / d2, 8);
            const ux = dx * inv * mag;
            const uy = dy * inv * mag;
            fx[i] += ux; fy[i] += uy;
            fx[j] -= ux; fy[j] -= uy;
          }
        }
      }
    }

    // ---- link springs --------------------------------------------------
    for (let e = 0; e < edgeCount; e++) {
      const a = ea[e];
      const b = eb[e];
      const dx = px[b] - px[a];
      const dy = py[b] - py[a];
      let d = Math.sqrt(dx * dx + dy * dy);
      if (d < 1e-3) d = 1e-3;
      const f = ((d - o.linkDistance) / d) * o.linkStrength;
      fx[a] += dx * f; fy[a] += dy * f;
      fx[b] -= dx * f; fy[b] -= dy * f;
    }

    // ---- mild centring -------------------------------------------------
    for (let i = 0; i < n; i++) {
      fx[i] -= (px[i] - cx) * o.centering;
      fy[i] -= (py[i] - cy) * o.centering;
    }

    // ---- integrate -----------------------------------------------------
    for (let i = 0; i < n; i++) {
      let nvx = (vx[i] + fx[i] * alpha) * o.damping;
      let nvy = (vy[i] + fy[i] * alpha) * o.damping;
      const speed = Math.sqrt(nvx * nvx + nvy * nvy);
      if (speed > o.maxVelocity) {
        const s = o.maxVelocity / speed;
        nvx *= s;
        nvy *= s;
      }
      vx[i] = nvx;
      vy[i] = nvy;
      px[i] += nvx;
      py[i] += nvy;
    }
  };

  const sim: ForceSim = {
    get positions() { return positions; },
    get alpha() { return alpha; },
    set alpha(v: number) { alpha = v; },
    get ticks() { return ticks; },
    get maxTicks() { return o.maxTicks; },
    get settled() { return alpha <= o.minAlpha || ticks >= o.maxTicks; },
    tick(count = 1) {
      const steps = Math.max(1, Math.min(count, o.maxTicks - ticks));
      for (let s = 0; s < steps; s++) {
        if (alpha <= o.minAlpha || ticks >= o.maxTicks) break;
        advance();
        ticks++;
      }
      syncPositions();
      return sim;
    },
    settle(limit = o.maxTicks) {
      const cap = Math.min(limit, o.maxTicks);
      while (!sim.settled && ticks < cap) sim.tick(1);
      return positions;
    },
  };

  return sim;
}

/** Run a graph through the force simulation to convergence and return positions. */
export function forceLayout(graph: KGraph, opts: ForceOptions = {}): Map<string, Pt> {
  return createForceSim(graph, opts).settle();
}

/**
 * Plant knowledge: one force-directed field over the whole refinery. Dataset
 * coordinates seed the simulation so equipment starts where the plant really
 * is; repulsion then makes room for the sensors, documents and work orders
 * that hang off each asset.
 */
export function layoutPlant(graph: KGraph): Map<string, Pt> {
  return forceLayout(graph, {
    linkDistance: 40,
    linkStrength: 0.85,
    repulsion: 5400,
    cutoff: 190,
    centering: 0.012,
    spread: 30,
    maxTicks: 320,
  });
}

/**
 * System knowledge overview: the community graph. Fewer, larger nodes, so the
 * springs run longer to let the 226 communities spread into a readable map.
 */
export function layoutSystemOverview(graph: KGraph): Map<string, Pt> {
  return forceLayout(graph, {
    linkDistance: 96,
    linkStrength: 0.7,
    repulsion: 26000,
    cutoff: 360,
    centering: 0.01,
    spread: 62,
    maxTicks: 340,
  });
}

/**
 * Members of one expanded community, relaxed around their community centre.
 * Deterministic: ring seed, then a bounded repulsion pass that removes
 * overlaps without moving anyone far from the centre they belong to.
 */
export function layoutCommunityMembers(
  members: KNode[],
  center: Pt,
  radius = 190,
): Map<string, Pt> {
  const n = members.length;
  const out = new Map<string, Pt>();
  if (!n) return out;

  const px = new Float64Array(n);
  const py = new Float64Array(n);
  const vx = new Float64Array(n);
  const vy = new Float64Array(n);
  const fx = new Float64Array(n);
  const fy = new Float64Array(n);

  for (let i = 0; i < n; i++) {
    const ang = (i / n) * Math.PI * 2 + hash(members[i].id) * 0.5;
    const r = radius * (0.62 + 0.38 * ((i % 3) / 2));
    px[i] = center.x + Math.cos(ang) * r;
    py[i] = center.y + Math.sin(ang) * r;
  }

  const spacing = Math.max(20, Math.min(70, (2 * radius * Math.PI) / n));
  const minDist2 = spacing * spacing;
  const iters = n > 120 ? 40 : 80;
  for (let s = 0; s < iters; s++) {
    const alpha = 1 - s / iters;
    fx.fill(0);
    fy.fill(0);
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let dx = px[i] - px[j];
        let dy = py[i] - py[j];
        let d2 = dx * dx + dy * dy;
        if (d2 >= minDist2) continue;
        if (d2 < 1e-4) { dx = (i % 5) - 1.5; dy = (j % 3) - 0.5; d2 = dx * dx + dy * dy || 1; }
        const d = Math.sqrt(d2);
        const f = ((spacing - d) / d) * 0.5;
        fx[i] += dx * f; fy[i] += dy * f;
        fx[j] -= dx * f; fy[j] -= dy * f;
      }
    }
    for (let i = 0; i < n; i++) {
      const dx = px[i] - center.x;
      const dy = py[i] - center.y;
      const d = Math.sqrt(dx * dx + dy * dy) || 1;
      const f = ((radius - d) / d) * 0.05;
      fx[i] -= dx * f;
      fy[i] -= dy * f;
      vx[i] = (vx[i] + fx[i] * alpha) * 0.7;
      vy[i] = (vy[i] + fy[i] * alpha) * 0.7;
      px[i] += vx[i];
      py[i] += vy[i];
    }
  }

  for (let i = 0; i < n; i++) out.set(members[i].id, { x: px[i], y: py[i] });
  return out;
}

/** Bounding box of a layout, used to fit the camera. */
export function bounds(pos: Map<string, Pt>): { minX: number; minY: number; maxX: number; maxY: number } {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const p of pos.values()) {
    minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x);
    minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y);
  }
  if (!Number.isFinite(minX)) return { minX: 0, minY: 0, maxX: 1000, maxY: 700 };
  return { minX, minY, maxX, maxY };
}
