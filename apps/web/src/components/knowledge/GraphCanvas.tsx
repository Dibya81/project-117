"use client";

/**
 * GraphCanvas — one renderer for both namespaces.
 *
 * Canvas 2D rather than SVG/DOM: the system graph expands to thousands of
 * nodes and SVG would drown in layout and paint cost. Drawing happens on
 * change, plus a rAF loop only while something is actually animating (a path
 * pulse, or the click-to-focus fade), so an idle graph costs nothing.
 *
 * Visual language — bright spatial computing, drawn on an open white plane:
 *   EXTRACTED        precise solid line
 *   INFERRED         dashed line
 *   OBSERVED         dotted line
 *   SIMULATED        long-dash line
 *   AI-DERIVED       short-dash line
 *   HUMAN-CONFIRMED  dash-dot line
 *   rest edges       #e2e8f0, ~1px
 *   focus            path violet, selection blue; everything else recedes
 *   selected node    flat filled disc + soft blue drop shadow
 *
 * Palette note: canvas 2D cannot read CSS custom properties, so the `.cs`
 * tokens are mirrored in PALETTE below and must be kept in sync with
 * styles/console.css and styles/knowledge.css.
 */
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import { colorOf, type KGraph, type KNode } from "@/lib/knowledge/types";
import { bounds, type Pt } from "@/lib/knowledge/layout";

export interface GraphHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  fit: () => void;
  focusNode: (id: string) => void;
  reset: () => void;
  fullscreen: () => void;
  center: () => void;
}

interface Props {
  graph: KGraph;
  positions: Map<string, Pt>;
  selected: string | null;
  /** Neighbourhood of the selection; everything else recedes. */
  highlight: Set<string>;
  /** Ordered node ids of the active relationship path. */
  path: string[];
  onSelect: (id: string | null) => void;
  onHover?: (id: string | null) => void;
  onExpand?: (id: string) => void;
  /** Ids that reveal more when double-clicked. */
  expandable?: Set<string>;
  /** Live activity: relation keys currently pulsing (real-time graph updates). */
  pulses?: { edgeId: string; at: number }[];
  fontSize?: number;
}

/* ---------------------------------------------------------------- palette */
/** Mirrors the `.cs` token layer (console.css) for canvas use. */
const PALETTE = {
  canvas: "#ffffff",
  ink1: "#0f172a",
  ink2: "#475569",
  ink3: "#64748b",
  blue: "#2563eb",
  amber: "#f59e0b",
  red: "#dc2626",
  green: "#10b981",
  violet: "#7c3aed",
  line: "#e2e8f0",
  labelPlate: "rgba(255,255,255,0.92)",
  labelPlateSel: "rgba(239,246,255,0.96)",
  labelRule: "rgba(15,23,42,0.06)",
} as const;

/**
 * Provenance is expressed with dash patterns plus a hair of weight, never
 * with neon colour: at rest every edge is the same quiet grey (#e2e8f0).
 */
const EDGE_STYLE: Record<string, { dash: number[]; width: number }> = {
  EXTRACTED: { dash: [], width: 1 },
  INFERRED: { dash: [4, 5], width: 1 },
  OBSERVED: { dash: [1.5, 3.5], width: 1 },
  SIMULATED: { dash: [7, 4], width: 1.05 },
  "AI-DERIVED": { dash: [2, 3], width: 1.1 },
  "HUMAN-CONFIRMED": { dash: [10, 3, 2, 3], width: 1.1 },
};

/** Base radius by semantic type; degree adds a modest amount on top. */
const NODE_BASE: Record<string, number> = {
  community: 7.5,
  plant: 6.5,
  area: 5,
  equipment: 5.5,
  anomaly: 5,
  failure_mode: 5,
  scenario: 4.5,
  work_order: 4.5,
  document: 4,
  rule: 4.5,
  approval: 4.5,
  agent: 5,
  sensor: 3,
  event: 3.5,
};

/** Fade duration for click-to-focus, in ms (spec: 200–300ms). */
const FADE_MS = 250;

const GraphCanvas = forwardRef<GraphHandle, Props>(function GraphCanvas(
  { graph, positions, selected, highlight, path, onSelect, onHover, onExpand, expandable, pulses, fontSize = 11 },
  ref,
) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const cam = useRef({ x: 0, y: 0, k: 0.5 });
  const size = useRef({ w: 0, h: 0, dpr: 1 });
  const hit = useRef<{ id: string; x: number; y: number; r: number }[]>([]);
  const drag = useRef<{ x: number; y: number; moved: boolean } | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [cursor, setCursor] = useState<"grab" | "grabbing" | "pointer">("grab");
  /** False until the canvas has been measured — framing must not run before. */
  const [ready, setReady] = useState(false);

  /** Animated click-to-focus amount: 0 = whole graph, 1 = selection focused. */
  const focus = useRef({ v: 0, target: 0 });

  const byId = useMemo(() => new Map(graph.nodes.map((n) => [n.id, n])), [graph.nodes]);
  const pathSet = useMemo(() => new Set(path), [path]);
  const pathEdge = useMemo(() => {
    const s = new Set<string>();
    for (let i = 0; i + 1 < path.length; i++) s.add(`${path[i]}|${path[i + 1]}`);
    return s;
  }, [path]);

  /** Degree drives a modest radius boost so hubs read as hubs. */
  const degree = useMemo(() => {
    const m = new Map<string, number>();
    for (const e of graph.edges) {
      m.set(e.from, (m.get(e.from) ?? 0) + 1);
      m.set(e.to, (m.get(e.to) ?? 0) + 1);
    }
    return m;
  }, [graph.edges]);

  const bb = useMemo(() => bounds(positions), [positions]);

  /** Local adjacency so `focusNode` can frame a neighbourhood the moment it is
   *  clicked, without waiting for the parent's derived highlight to update. */
  const localAdj = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const e of graph.edges) {
      if (!positions.has(e.from) || !positions.has(e.to)) continue;
      if (!m.has(e.from)) m.set(e.from, []);
      if (!m.has(e.to)) m.set(e.to, []);
      m.get(e.from)!.push(e.to);
      m.get(e.to)!.push(e.from);
    }
    return m;
  }, [graph.edges, positions]);

  const draw = useCallback(
    (t: number) => {
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext("2d");
      if (!canvas || !ctx) return;
      const { w, h, dpr } = size.current;
      if (!w || !h) return;

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      // The open plane: pure white, unbounded, no frame and no gradient.
      ctx.fillStyle = PALETTE.canvas;
      ctx.fillRect(0, 0, w, h);

      const k = cam.current.k;
      const toScreen = (p: Pt) => ({
        x: (p.x - cam.current.x) * k + w / 2,
        y: (p.y - cam.current.y) * k + h / 2,
      });

      const hasFocus = selected != null;
      const f = focus.current.v;
      const active = (id: string) =>
        !hasFocus || highlight.has(id) || pathSet.has(id) || id === selected;

      const hits: { id: string; x: number; y: number; r: number }[] = [];

      /* ---------------- edges ---------------- */
      for (const e of graph.edges) {
        const pa = positions.get(e.from);
        const pb = positions.get(e.to);
        if (!pa || !pb) continue;
        const a = toScreen(pa);
        const b = toScreen(pb);
        if (Math.max(a.x, b.x) < -40 || Math.min(a.x, b.x) > w + 40) continue;
        if (Math.max(a.y, b.y) < -40 || Math.min(a.y, b.y) > h + 40) continue;

        const onPath = pathEdge.has(`${e.from}|${e.to}`) || pathEdge.has(`${e.to}|${e.from}`);
        const inFocus = selected != null && (e.from === selected || e.to === selected);
        const lit = onPath || inFocus;
        // Unrelated edges fade to (almost) nothing over the fade window.
        const alpha = lit ? 1 : 1 - f * 0.98;
        if (alpha < 0.015) continue;

        const style = EDGE_STYLE[e.provenance] ?? EDGE_STYLE.EXTRACTED;
        ctx.globalAlpha = alpha;
        ctx.strokeStyle = onPath ? PALETTE.violet : lit ? PALETTE.blue : PALETTE.line;
        ctx.lineWidth = onPath ? 2 : lit ? 1.6 : style.width;
        if (onPath) {
          // marching ants along the focused path
          ctx.setLineDash([6, 6]);
          ctx.lineDashOffset = -((t * 0.03) % 12);
        } else {
          ctx.setLineDash(style.dash.map((d) => d * Math.max(k, 0.6)));
          ctx.lineDashOffset = 0;
        }
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        // gentle bezier curve so parallel edges stay readable
        const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
        ctx.quadraticCurveTo(mx, my, b.x, b.y);
        ctx.stroke();
        ctx.setLineDash([]);

        // AI-derived edges carry a travelling pulse — motion = live inference
        if (alpha > 0.1 && (e.provenance === "AI-DERIVED" || onPath) && k > 0.25) {
          const ph = onPath ? (t * 0.00045 + 0.5) : (t * 0.00035 + hashNum(e.id) * 0.01);
          const q = ph % 1;
          const px = a.x + (b.x - a.x) * q;
          const py = a.y + (b.y - a.y) * q;
          ctx.globalAlpha = alpha * 0.9;
          ctx.fillStyle = onPath ? PALETTE.violet : PALETTE.blue;
          ctx.beginPath();
          ctx.arc(px, py, onPath ? 3 : 2, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;

      /* ---------------- nodes ---------------- */
      // Labels are de-collided: a label is dropped rather than allowed to
      // overlap one already drawn. Anchors (selection, path, equipment) claim
      // their space first because they are drawn in priority order.
      const drawn: { x1: number; y1: number; x2: number; y2: number }[] = [];
      const canPlace = (x1: number, y1: number, x2: number, y2: number) =>
        !drawn.some((r) => x1 < r.x2 && x2 > r.x1 && y1 < r.y2 && y2 > r.y1);

      const ordered = [...graph.nodes].sort((a, b) => {
        const rank = (n: KNode) =>
          n.id === selected ? 0 : pathSet.has(n.id) ? 1 : n.type === "equipment" || n.type === "community" ? 2 : 3;
        return rank(a) - rank(b);
      });

      for (const n of ordered) {
        const p = positions.get(n.id);
        if (!p) continue;
        const s = toScreen(p);
        if (s.x < -60 || s.x > w + 60 || s.y < -60 || s.y > h + 60) continue;

        const isSel = n.id === selected;
        const isHover = n.id === hover;
        const onPath = pathSet.has(n.id);
        const dim = !active(n.id);
        const color = colorOf(n.type);
        const deg = degree.get(n.id) ?? 0;
        const base = NODE_BASE[n.type] ?? 4;
        const r = (base + Math.min(deg, 10) * 0.62) * Math.max(k, 0.6);

        const alpha = dim ? 1 - f * 0.9 : 1;
        ctx.globalAlpha = alpha;

        // Soft, light drop shadow marks the active neighbourhood; the
        // selection gets the stronger (still light) version.
        const halo = (isSel || (hasFocus && !dim)) && f > 0.01;
        if (halo) {
          ctx.save();
          ctx.shadowColor = isSel ? "rgba(37,99,235,0.35)" : "rgba(37,99,235,0.18)";
          ctx.shadowBlur = (isSel ? 16 : 8) * Math.max(0.4, f);
          ctx.shadowOffsetY = 1;
          ctx.beginPath();
          ctx.arc(s.x, s.y, r, 0, Math.PI * 2);
          ctx.fillStyle = color;
          ctx.fill();
          ctx.restore();
        }

        // Flat filled disc.
        ctx.beginPath();
        ctx.arc(s.x, s.y, r, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();

        // A hairline white rim separates touching discs without reading as a ring.
        if (r > 3) {
          ctx.beginPath();
          ctx.arc(s.x, s.y, r, 0, Math.PI * 2);
          ctx.strokeStyle = "rgba(255,255,255,0.85)";
          ctx.lineWidth = 1;
          ctx.stroke();
        }

        // Path membership and selection get a light ring, never a glow.
        if (isSel) {
          ctx.beginPath();
          ctx.arc(s.x, s.y, r + 3.5, 0, Math.PI * 2);
          ctx.strokeStyle = "rgba(37,99,235,0.5)";
          ctx.lineWidth = 1.6;
          ctx.stroke();
        } else if (onPath) {
          ctx.beginPath();
          ctx.arc(s.x, s.y, r + 3, 0, Math.PI * 2);
          ctx.strokeStyle = "rgba(124,58,237,0.45)";
          ctx.lineWidth = 1.3;
          ctx.stroke();
        } else if (isHover) {
          ctx.beginPath();
          ctx.arc(s.x, s.y, r + 2.5, 0, Math.PI * 2);
          ctx.strokeStyle = "rgba(15,23,42,0.28)";
          ctx.lineWidth = 1.2;
          ctx.stroke();
        }

        // Anomalies and failure modes carry a white pip, like a target.
        if ((n.type === "anomaly" || n.type === "failure_mode") && r > 3) {
          ctx.beginPath();
          ctx.arc(s.x, s.y, r * 0.34, 0, Math.PI * 2);
          ctx.fillStyle = "rgba(255,255,255,0.92)";
          ctx.fill();
        }

        // Labels: dark ink on a near-white plate, de-collided.
        const big = n.type === "community" || n.type === "area" || n.type === "equipment" || n.type === "plant";
        const wants = !dim && (isSel || isHover || onPath || !!path.length || k > 0.85 || (big && k > 0.45));
        if (wants) {
          const label = n.label.length > 30 && k < 0.9 ? `${n.label.slice(0, 28)}…` : n.label;
          ctx.font = `${isSel || big ? 600 : 500} ${fontSize}px ui-monospace, SFMono-Regular, Menlo, monospace`;
          ctx.textAlign = "center";
          ctx.textBaseline = "top";
          const tw = ctx.measureText(label).width;
          const bx1 = s.x - tw / 2 - 3;
          const by1 = s.y + r + 3;
          if (isSel || isHover || canPlace(bx1, by1, bx1 + tw + 6, by1 + fontSize + 4)) {
            if (!(isSel || isHover)) drawn.push({ x1: bx1, y1: by1, x2: bx1 + tw + 6, y2: by1 + fontSize + 4 });
            ctx.fillStyle = isSel ? PALETTE.labelPlateSel : PALETTE.labelPlate;
            ctx.fillRect(bx1, by1, tw + 6, fontSize + 4);
            ctx.strokeStyle = PALETTE.labelRule;
            ctx.lineWidth = 1;
            ctx.strokeRect(bx1 + 0.5, by1 + 0.5, tw + 5, fontSize + 3);
            ctx.fillStyle = PALETTE.ink1;
            ctx.fillText(label, s.x, s.y + r + 5);
          }
        }

        hits.push({ id: n.id, x: s.x, y: s.y, r: Math.max(r + 5, 10) });
      }
      ctx.globalAlpha = 1;
      hit.current = hits;
    },
    [graph, positions, selected, highlight, path, pathSet, pathEdge, hover, degree, fontSize],
  );

  /* ---------------- sizing ---------------- */
  useEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    if (!wrap || !canvas) return;
    const resize = () => {
      // dpr is capped at 2 — beyond that costs pixels, not clarity.
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = wrap.clientWidth;
      const h = wrap.clientHeight;
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
      }
      size.current = { w, h, dpr };
      setReady(true);
      draw(performance.now());
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(wrap);
    return () => ro.disconnect();
  }, [draw]);

  /* ---------------- animation loop ----------------
     The rAF loop runs only while something is actually moving: the
     click-to-focus fade, an active path, or prop-driven pulses. An idle
     graph draws once and stops. */
  const rafRef = useRef(0);
  const runningRef = useRef(false);
  const lastTRef = useRef(0);
  const tickRef = useRef<(t: number, dt: number) => boolean>(() => false);

  const tick = useCallback(
    (t: number, dt: number): boolean => {
      const fa = focus.current;
      if (fa.v !== fa.target) {
        const step = dt / FADE_MS;
        fa.v = fa.target > fa.v ? Math.min(fa.target, fa.v + step) : Math.max(fa.target, fa.v - step);
      }
      draw(t);
      return focus.current.v !== focus.current.target || path.length > 1 || !!pulses?.length;
    },
    [draw, path.length, pulses],
  );

  // Keep the loop's callback fresh without restarting the loop.
  useEffect(() => { tickRef.current = tick; });

  const ensureRunning = useCallback(() => {
    if (runningRef.current) return;
    runningRef.current = true;
    lastTRef.current = 0;
    const loop = (t: number) => {
      const dt = lastTRef.current ? Math.min(t - lastTRef.current, 64) : 16;
      lastTRef.current = t;
      if (tickRef.current(t, dt)) {
        rafRef.current = requestAnimationFrame(loop);
      } else {
        runningRef.current = false;
        rafRef.current = 0;
      }
    };
    rafRef.current = requestAnimationFrame(loop);
  }, []);

  useEffect(() => () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    runningRef.current = false;
  }, []);

  // Selection changed → fade in/out over FADE_MS.
  useEffect(() => {
    focus.current.target = selected ? 1 : 0;
    if (focus.current.v !== focus.current.target) ensureRunning();
  }, [selected, ensureRunning]);

  // An active path or live pulses keep the loop alive.
  useEffect(() => {
    if (path.length > 1 || pulses?.length) ensureRunning();
  }, [path.length, pulses?.length, ensureRunning]);

  /* ---------------- camera helpers ---------------- */
  const fit = useCallback(() => {
    const { w, h } = size.current;
    const pad = 80;
    const bw = Math.max(bb.maxX - bb.minX, 1);
    const bh = Math.max(bb.maxY - bb.minY, 1);
    const k = Math.min((w - pad * 2) / bw, (h - pad * 2) / bh, 2.2);
    cam.current = { k, x: (bb.minX + bb.maxX) / 2, y: (bb.minY + bb.maxY) / 2 };
    draw(performance.now());
  }, [bb, draw]);

  const focusNode = useCallback(
    (id: string) => {
      const { w, h } = size.current;
      if (!w || !h) return; // not measured yet; the effect below retries
      // Frame the node together with its direct neighbours, so selecting an
      // asset shows its whole constellation rather than one dot at 1.15×.
      const ids = [id, ...(localAdj.get(id) ?? [])];
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      for (const i of ids) {
        const p = positions.get(i);
        if (!p) continue;
        minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x);
        minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y);
      }
      if (!Number.isFinite(minX)) {
        const p = positions.get(id);
        if (!p) return;
        cam.current = { ...cam.current, x: p.x, y: p.y, k: 1.15 };
        draw(performance.now());
        return;
      }
      const padX = Math.min(120, w * 0.14);
      const padY = Math.min(96, h * 0.16);
      const bw = Math.max(maxX - minX, 60);
      const bh = Math.max(maxY - minY, 60);
      const k = Math.min(Math.max(Math.min((w - padX * 2) / bw, (h - padY * 2) / bh), 0.28), 2.4);
      cam.current = { k, x: (minX + maxX) / 2, y: (minY + maxY) / 2 };
      draw(performance.now());
    },
    [positions, localAdj, draw],
  );

  const reset = useCallback(() => {
    cam.current = { x: 0, y: 0, k: 0.5 };
    fit();
  }, [fit]);

  // Fit once when the graph identity or layout changes — but not when something
  // is already selected, because the selection frames itself below.
  const fitKey = `${graph.namespace}:${graph.nodes.length}:${positions.size}`;
  const lastFit = useRef("");
  useEffect(() => {
    if (!ready || lastFit.current === fitKey) return;
    lastFit.current = fitKey;
    if (selected) return;
    fit();
  }, [ready, fitKey, fit, selected]);

  // Whenever the selection changes to a node we have not framed yet, frame its
  // neighbourhood. This is what makes the page open on C-3 properly framed
  // instead of on the whole refinery.
  //
  // `framedRef` is only written once the timer actually fires: marking it
  // eagerly would let a dependency change cancel the timer via this effect's
  // own cleanup and leave the camera where it started.
  const framedRef = useRef<string | null>(null);
  useEffect(() => {
    if (!ready || !selected || framedRef.current === selected) return;
    if (!positions.has(selected)) return;
    const id = selected;
    const t = setTimeout(() => {
      framedRef.current = id;
      focusNode(id);
    }, 30);
    return () => clearTimeout(t);
  }, [ready, selected, positions, focusNode]);

  useImperativeHandle(ref, () => ({
    zoomIn: () => { cam.current = { ...cam.current, k: Math.min(cam.current.k * 1.25, 6) }; draw(performance.now()); },
    zoomOut: () => { cam.current = { ...cam.current, k: Math.max(cam.current.k / 1.25, 0.08) }; draw(performance.now()); },
    fit,
    focusNode,
    reset,
    center: fit,
    fullscreen: () => {
      const el = wrapRef.current?.parentElement;
      if (!el) return;
      if (document.fullscreenElement) void document.exitFullscreen();
      else void el.requestFullscreen?.();
    },
  }));

  /* ---------------- interaction ----------------
     Zoom is bound natively rather than through React's synthetic `onWheel`:
     React attaches wheel listeners passively, so calling preventDefault there
     logs a console error and cannot actually stop the page from scrolling. */
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const { w, h } = size.current;
      const before = cam.current;
      const k2 = Math.min(Math.max(before.k * (e.deltaY < 0 ? 1.12 : 1 / 1.12), 0.08), 6);
      // keep the point under the cursor fixed
      const wx = before.x + (mx - w / 2) / before.k;
      const wy = before.y + (my - h / 2) / before.k;
      cam.current = { k: k2, x: wx - (mx - w / 2) / k2, y: wy - (my - h / 2) / k2 };
      draw(performance.now());
    };
    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", onWheel);
  }, [draw]);

  const pick = (clientX: number, clientY: number): string | null => {
    const rect = canvasRef.current!.getBoundingClientRect();
    const x = clientX - rect.left;
    const y = clientY - rect.top;
    let best: { id: string; d: number } | null = null;
    for (const hnode of hit.current) {
      const d = Math.hypot(hnode.x - x, hnode.y - y);
      if (d <= hnode.r && (!best || d < best.d)) best = { id: hnode.id, d };
    }
    return best?.id ?? null;
  };

  const onPointerDown = (e: React.PointerEvent) => {
    (e.target as Element).setPointerCapture?.(e.pointerId);
    drag.current = { x: e.clientX, y: e.clientY, moved: false };
    setCursor("grabbing");
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (drag.current) {
      const dx = e.clientX - drag.current.x;
      const dy = e.clientY - drag.current.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) drag.current.moved = true;
      cam.current = { ...cam.current, x: cam.current.x - dx / cam.current.k, y: cam.current.y - dy / cam.current.k };
      drag.current.x = e.clientX;
      drag.current.y = e.clientY;
      draw(performance.now());
      return;
    }
    const id = pick(e.clientX, e.clientY);
    if (id !== hover) {
      setHover(id);
      onHover?.(id);
      setCursor(id ? "pointer" : "grab");
    }
  };

  const onPointerUp = (e: React.PointerEvent) => {
    setCursor("grab");
    const wasDrag = drag.current?.moved;
    drag.current = null;
    if (wasDrag) return;
    const id = pick(e.clientX, e.clientY);
    onSelect(id);
    if (id) focusNode(id);
  };

  const onDoubleClick = (e: React.MouseEvent) => {
    const id = pick(e.clientX, e.clientY);
    if (!id) return;
    if (!expandable || expandable.has(id)) onExpand?.(id);
  };

  const hoverNode = hover ? byId.get(hover) : null;

  return (
    <div ref={wrapRef} className="ku-canvas-wrap">
      <canvas
        ref={canvasRef}
        className="ku-canvas"
        style={{ cursor }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={() => { setHover(null); onHover?.(null); }}
        onDoubleClick={onDoubleClick}
        role="application"
        aria-label={`${graph.namespace} knowledge graph, ${graph.nodes.length} nodes. Use the entity list to navigate.`}
      />
      {hoverNode && hoverNode.id !== selected && (
        <div className="ku-tip" aria-hidden="true">
          <b>{hoverNode.label}</b>
          <i>{hoverNode.type}{hoverNode.status ? ` · ${hoverNode.status}` : ""}</i>
          <em>{graph.edges.filter((e) => e.from === hoverNode.id || e.to === hoverNode.id).length} relationships</em>
        </div>
      )}
      {!graph.nodes.length && <p className="ku-empty">No nodes in this view.</p>}
    </div>
  );
});

function hashNum(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 1000;
  return h / 1000;
}

export default GraphCanvas;
