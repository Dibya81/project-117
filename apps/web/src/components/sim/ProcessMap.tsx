"use client";

/**
 * ProcessMap — the refinery as a continuous industrial process schematic.
 *
 * This replaces a layout of equipment cards in a grid joined by bezier links.
 * An operator reads a plant as pipes: what flows where, at what rate, and what
 * has stopped. So the map is drawn from the three things the dataset actually
 * carries:
 *
 *   areas      18 rectangles with real x/y/w/h — the process compartments
 *   equipment  58 units with real x/y inside those rectangles
 *   pipes      60 connections with medium, capacity, flow, status, leaking,
 *              enabled — the thing the diagram is really about
 *
 * Everything is real geometry from the plant definition. Nothing is auto-laid
 * out by a graph algorithm, because a refinery's drawing is part of its
 * engineering record, not a rendering detail.
 *
 * Symbols come from lib/sim/symbols.tsx — original ISA-5.1 vector artwork — so
 * a pump is drawn as a volute pump and a valve as a bow-tie, not as an icon in
 * a white card.
 *
 * State is read from the engine runtime: equipment state, sensor quality, and
 * per-pipe leaking/enabled/flow. No state is held here.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { EquipmentShape } from "@/components/sim/EquipmentShape";
import type { ConnectionDef, EquipmentDef, PlantDef, SensorDef } from "@/lib/sim/types";
import type { CanvasRuntime, SpatialReading } from "@/components/sim/SchematicCanvas";

/* ------------------------------------------------------------------ geometry */

/** Default equipment footprint in plant units. The dataset's x/y is the centre. */
const EQ_W = 74;
const EQ_H = 62;
/** Lettering is placed below the body so it never covers the linework. */
const LABEL_H = 30;
/** Instrument bubble spacing and readout-plate width, in plant units. */
const INST_SPACING = 46;
const INST_PLATE_W = 60;

/**
 * Footprint by equipment kind.
 *
 * A refinery drawing has physical hierarchy: a column is tall and narrow, a
 * tank is squat and wide, a pump is small. Drawing every asset in the same box
 * threw that away and made the plant read as a diagram of identical nodes. The
 * dataset's x/y is the centre, so a larger box simply claims more of its own
 * area — which is how a real plot plan looks.
 */
/**
 * Visual tier. A refinery drawing is not a uniform grid of equal boxes: the
 * crude tower, the furnace and the storage drums are what the eye should find
 * first, and the valves and motors hang off them. Drawing all 58 assets at one
 * size is why the plant read as a flowchart — everything was equally important,
 * so nothing was.
 */
export type Tier = "major" | "process" | "minor";

export function tierOf(kind: string): Tier {
  if (kind === "tank" || kind === "column" || kind === "furnace" || kind === "compressor") return "major";
  if (kind === "vessel" || kind === "exchanger" || kind === "reactor" || kind === "utility") return "process";
  return "minor";
}

export interface ProcessMapSelection {
  kind: "equipment" | "pipe";
  id: string;
}

interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

/**
 * Process media, coloured the way a refinery draws them: warm for hot feed and
 * hydrocarbons, cool for water and gas, distinct for hydrogen and products.
 * Saturated, because on this drawing the pipe colour carries the medium and the
 * equipment is deliberately quiet.
 */
export const MEDIUM_COLOR: Record<string, string> = {
  crude: "#c2761c",
  "atm-resid": "#9c6414",
  "vac-resid": "#8a5a12",
  naphtha: "#d8a520",
  jet: "#c99a1e",
  diesel: "#b58a1c",
  reformate: "#caa02a",
  vgo: "#a8841c",
  slurry: "#7a5f16",
  hydrogen: "#7c5cf0",
  "recycle-gas": "#6f7ff0",
  "sour-gas": "#8a9a4b",
  amine: "#2fa88a",
  gas: "#6f8ba6",
  vapor: "#8fa4bb",
  steam: "#d4564a",
  water: "#2f7fd4",
  wastewater: "#4a7f96",
  brine: "#2f92a8",
  air: "#4d9fd6",
  control: "#7c3aed",
};

export const DEFAULT_MEDIUM_COLOR = "#8794a1";

export function mediumColor(medium: string | undefined): string {
  return MEDIUM_COLOR[medium ?? ""] ?? DEFAULT_MEDIUM_COLOR;
}

/**
 * Thermal bands, in °C.
 *
 * The thresholds are process-engineering ones, not styling ones: above ~150 °C a
 * stream is hot enough to need tracing and personal protection, below ~60 °C it
 * is at or under ambient-cooled temperature. Anything between is "warm" and keeps
 * its medium colour, because painting every line orange would say nothing.
 */
export const HOT_C_MIN = 150;
export const COLD_C_MAX = 60;
export const HOT_STROKE = "#ea580c";
export const COLD_STROKE = "#2563eb";

/**
 * The hottest temperature actually measured on an asset.
 *
 * Read from the live readings, never from the drawing: a line is orange because
 * a thermocouple says the fluid in it is hot, not because someone chose orange.
 * Bad-quality points are ignored — an out-of-service transmitter's last value is
 * not evidence.
 */
function hottestTemperature(eq: EquipmentDef | undefined, readings: Record<string, SpatialReading>): number | null {
  if (!eq) return null;
  let best: number | null = null;
  for (const s of eq.sensors) {
    if (s.measurement !== "temperature") continue;
    const r = readings[s.id];
    if (!r || r.quality === "bad" || r.quality === "stale") continue;
    if (best === null || r.value > best) best = r.value;
  }
  return best;
}

/**
 * The colour a process line is drawn in.
 *
 * Hot and cold streams override the medium colour because temperature is what an
 * operator reads a P&ID for — the medium is already named in the legend, but a
 * hot line is a hazard and a cold one is a different operating regime. Signal
 * media are never tinted: instrument wiring has no temperature.
 */
export function streamStroke(
  conn: ConnectionDef,
  source: EquipmentDef | undefined,
  readings: Record<string, SpatialReading>,
): string {
  if (SIGNAL_MEDIA.has(conn.medium ?? "")) return mediumColor(conn.medium);
  const temp = hottestTemperature(source, readings);
  if (temp === null) return mediumColor(conn.medium);
  if (temp >= HOT_C_MIN) return HOT_STROKE;
  if (temp <= COLD_C_MAX) return COLD_STROKE;
  return mediumColor(conn.medium);
}

/** How a line's temperature reads, for the legend and the inspector. */
export function thermalClass(temp: number | null): "hot" | "cold" | "warm" | "unknown" {
  if (temp === null) return "unknown";
  if (temp >= HOT_C_MIN) return "hot";
  if (temp <= COLD_C_MAX) return "cold";
  return "warm";
}

/**
 * Media that are signals rather than process fluid. A control loop drawn as a
 * solid process line misreads as something flowing, which is why a real drawing
 * dashes instrument wiring.
 */
export const SIGNAL_MEDIA = new Set(["control", "signal", "power"]);

export function lineState(
  conn: ConnectionDef,
  runtime: CanvasRuntime | null,
): "normal" | "warning" | "critical" | "blocked" | "leaking" {
  const p = runtime?.pipes?.[conn.id];
  const enabled = p ? p.enabled : conn.enabled !== false;
  const leaking = Boolean(p ? p.leaking : conn.leaking);
  if (!enabled) return "blocked";
  if (leaking) return "leaking";
  if (conn.status === "failed" || conn.status === "critical") return "critical";
  if (conn.status === "warning") return "warning";
  return "normal";
}

const STATE_STROKE: Record<string, string> = {
  normal: "",
  warning: "#f59e0b",
  critical: "#dc2626",
  blocked: "#94a3b8",
  leaking: "#dc2626",
};

/** Orthogonal route between two boxes. Process lines run square, never curved. */
function route(a: Box, b: Box): { d: string; mid: { x: number; y: number }; horizontal: boolean } {
  const aMidY = a.y + a.h / 2;
  const bMidY = b.y + b.h / 2;
  const goingRight = b.x >= a.x;
  const startX = goingRight ? a.x + a.w : a.x;
  const endX = goingRight ? b.x : b.x + b.w;
  const gap = Math.abs(endX - startX);
  const dy = Math.abs(bMidY - aMidY);
  if (dy < 42 || gap < 80) {
    const y = aMidY;
    return { d: `M ${startX} ${y} H ${endX}`, mid: { x: (startX + endX) / 2, y }, horizontal: true };
  }
  const turnX = goingRight ? startX + Math.max(24, gap * 0.45) : startX - Math.max(24, gap * 0.45);
  return {
    d: `M ${startX} ${aMidY} H ${turnX} V ${bMidY} H ${endX}`,
    mid: { x: turnX, y: (aMidY + bMidY) / 2 },
    horizontal: false,
  };
}

/** Footprint in plant units, by kind, at the tier's own scale. */
export function sizeForKind(kind: string): { w: number; h: number } {
  const tier = tierOf(kind);
  // Sized so a major unit reads as a major unit at fit-plant zoom: roughly a
  // tenth of the plot width, which is the proportion a real refinery drawing
  // gives its towers and drums. The plant is wider than the viewport as a
  // result, and that is the point — the drawing is panned and zoomed like a
  // plot plan rather than compressed until nothing is legible.
  if (tier === "major") {
    switch (kind) {
      case "column":
        return { w: 104, h: 246 };
      case "tank":
        return { w: 232, h: 138 };
      case "furnace":
        return { w: 188, h: 164 };
      default:
        return { w: 178, h: 132 };
    }
  }
  if (tier === "process") {
    switch (kind) {
      case "vessel":
        return { w: 136, h: 142 };
      case "exchanger":
        return { w: 182, h: 92 };
      default:
        return { w: 152, h: 116 };
    }
  }
  switch (kind) {
    case "pump":
      return { w: 78, h: 62 };
    case "valve":
      return { w: 60, h: 50 };
    case "motor":
      return { w: 72, h: 58 };
    case "safety":
      return { w: 66, h: 58 };
    default:
      return { w: 70, h: 58 };
  }
}

/**
 * Orthogonal route between two boxes.
 *
 * A process line is drawn as horizontal and vertical runs, never as a curve —
 * a curve hides where a line actually goes, which is the one thing the drawing
 * exists to communicate. The route leaves the source on the side facing the
 * target and enters the target on the side facing the source.
 */

/* --------------------------------------------------------------------- label */

function stateTone(state: string): "normal" | "warning" | "critical" {
  if (state === "critical" || state === "failed") return "critical";
  if (state === "warning" || state === "investigating" || state === "action") return "warning";
  return "normal";
}

const TONE_COLOR = {
  normal: "#3ddc97",
  warning: "#f59e0b",
  critical: "#dc2626",
} as const;

/* ------------------------------------------------------------------ component */

export interface ProcessMapProps {
  plant: PlantDef;
  runtime: CanvasRuntime | null;
  readings?: Record<string, SpatialReading>;
  selection?: ProcessMapSelection | null;
  onSelect?: (sel: ProcessMapSelection | null) => void;
  /** Equipment ids to emphasise (incident origin + affected). */
  highlight?: string[];
  /** Restrict the drawing to one area. */
  isolateArea?: string | null;
  /** Pan/zoom target. */
  focusId?: string | null;
  /** The switch the backend actually made: origin equipment -> alternate. */
  failover?: { from: string; to: string } | null;
  /** Real line actions. Each hits the endpoint that mutates engine state. */
  onLineAction?: (lineId: string, action: "block" | "restore" | "leak" | "seal") => void;
  /** Lines the operator has acted on this session, so the panel can offer undo. */
  busyLine?: string | null;
  lineError?: string | null;
  recoveryDecision?: {
    available: boolean;
    route: string[];
    block: string[];
    restore: string[];
    safety_confirmed: boolean;
  } | null;
  /**
   * Lock the camera to one full-plant framing — the live refinery's control-room
   * view. Wheel, trackpad, pinch and drag do nothing; equipment and lines stay
   * clickable. Editing surfaces (the builder) leave this off and keep pan/zoom.
   */
  fixedCamera?: boolean;
  /**
   * EDIT MODE (the builder): units can be dragged to a new position, snapped to
   * the drawing grid, and wired port-to-port. All off by default, so the live
   * plant is unaffected.
   */
  editable?: boolean;
  onEquipmentMove?: (id: string, x: number, y: number) => void;
  connectMode?: boolean;
  connectFromId?: string | null;
  /** `port` is the unit's own end: "out" feeds the next unit, "in" receives. */
  onPortClick?: (equipmentId: string, port: "in" | "out") => void;
  /**
   * The fault's own isolation, before any agent has spoken.
   *
   * Distinct from a decision's `block`: these lines were taken out of service by
   * the failure, so they are drawn red and dashed — a section that is cut and
   * unsafe, not one an operator closed. Cleared when the incident ends, at which
   * point the verified decision owns the drawing.
   */
  isolatedLines?: string[];
  /** Assets inside the isolated section, drawn in the fault treatment. */
  isolatedEquipment?: string[];
}

/** Grid the builder snaps dropped/moved units to, in plant units. */
export const GRID = 20;
export const snapToGrid = (v: number) => Math.round(v / GRID) * GRID;

/** The whole plant, framed once. `fit()` uses the same margin. */
const FIT_K = 0.92;
/** The zoom an editor opens at — close enough to place and wire a unit. */
const WORKING_K = 1.75;
/** Camera limits. Every path that writes `view` clamps through these. */
export const MIN_K = 0.35;
export const MAX_K = 6;
/** Fallback drawing extent, used before the plant has been measured. */
const FALLBACK_EXTENT = { x: 0, y: 0, w: 800, h: 600 };

/**
 * Coerce a camera into a state the renderer can actually draw.
 *
 * The camera is written from four places — the initial state, `zoom`, `fit` and
 * pan — and any of them could previously put a non-finite number into
 * `scale()`/`translate()` and blank the whole drawing. An unmeasured container
 * or an empty plant produces a zero-width extent, division by which is
 * `Infinity`; SVG then drops every child silently, which reads to the operator
 * as "the canvas went black". This is the single choke point that makes that
 * impossible: scale is clamped into range, offsets are bounded to a sane
 * multiple of the plant, and anything non-finite falls back to a framed view.
 *
 * Exported so the builder and the tests share one definition of "in bounds".
 */
export function clampView(
  view: { x: number; y: number; k: number },
  extent: { w: number; h: number },
): { x: number; y: number; k: number } {
  const w = Number.isFinite(extent.w) && extent.w > 0 ? extent.w : FALLBACK_EXTENT.w;
  const h = Number.isFinite(extent.h) && extent.h > 0 ? extent.h : FALLBACK_EXTENT.h;
  const k = Number.isFinite(view.k) ? Math.min(MAX_K, Math.max(MIN_K, view.k)) : FIT_K;
  // Panning is bounded to the plant plus one screen of slack, so the drawing
  // can always be brought back by dragging rather than only by "Fit plant".
  const limitX = w * 1.5;
  const limitY = h * 1.5;
  const x = Number.isFinite(view.x) ? Math.min(limitX, Math.max(-limitX, view.x)) : 0;
  const y = Number.isFinite(view.y) ? Math.min(limitY, Math.max(-limitY, view.y)) : 0;
  return { x, y, k };
}

/** A rectangle a camera can be fitted to. Degenerate boxes are refused. */
function isFittable(box: { w: number; h: number }): boolean {
  return Number.isFinite(box.w) && Number.isFinite(box.h) && box.w > 1 && box.h > 1;
}

export function ProcessMap({
  plant,
  runtime,
  readings = {},
  selection,
  onSelect,
  highlight = [],
  isolateArea = null,
  focusId = null,
  failover = null,
  onLineAction,
  busyLine = null,
  lineError = null,
  recoveryDecision = null,
  fixedCamera = false,
  editable = false,
  onEquipmentMove,
  connectMode = false,
  connectFromId = null,
  onPortClick,
  isolatedLines = [],
  isolatedEquipment = [],
}: ProcessMapProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  /**
   * The camera.
   *
   * The LIVE refinery (fixedCamera) opens fitted to the whole plant and stays
   * there: the operator inspects and acts, and never loses the plant to a stray
   * scroll. An editor (the builder) opens at a working zoom and pans, because
   * placing equipment needs that. "Fit plant" is one click away either way.
   */
  const [view, setView] = useState(() =>
    clampView({ x: 0, y: 0, k: fixedCamera ? FIT_K : WORKING_K }, FALLBACK_EXTENT),
  );
  /** Print every instrument readout, rather than only the ones that need eyes. */
  const [showAllInstruments, setShowAllInstruments] = useState(false);

  /**
   * Level of detail, driven by the camera.
   *
   * 224 instrument bubbles with 224 readouts is a wall of microscopic text at
   * overview zoom, and it buries the plant the drawing exists to show. At the
   * working zoom only the abnormal points and the selected asset carry a
   * readout; bubbles appear as the camera closes in; everything appears when
   * the operator asks for it. The fixed control-room framing is the overview, so
   * the sensor bubbles stay visible there — the readouts do not.
   */
  const showBubbles = fixedCamera || view.k >= 1.15 || showAllInstruments;
  const showReadouts = view.k >= 3.2 || showAllInstruments;
  const drag = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);

  // The area chips filter WHICH equipment is drawn. In the locked live view they
  // must not also reframe the camera: the frame is the whole plant, always, so
  // the drawing extent stays the full set of areas. Editors keep the old
  // behaviour (isolating an area frames that area).
  const areas = useMemo(
    () => (isolateArea && !fixedCamera ? plant.areas.filter((a) => a.id === isolateArea) : plant.areas),
    [plant.areas, isolateArea, fixedCamera],
  );

  /** Fast lookup for the fault-isolation overlay. */
  const isolatedSet = useMemo(() => new Set(isolatedLines), [isolatedLines]);
  const isolatedEqSet = useMemo(() => new Set(isolatedEquipment), [isolatedEquipment]);

  const equipment = useMemo(() => {
    const scope = isolateArea ? plant.equipment.filter((e) => e.area_id === isolateArea) : plant.equipment;
    const ids = new Set(areas.map((a) => a.id));
    return scope.filter((e) => ids.has(e.area_id));
  }, [plant.equipment, areas, isolateArea]);

  const equipmentIds = useMemo(() => new Set(equipment.map((e) => e.id)), [equipment]);

  /** Every pipe whose both ends are drawn. A half-drawn line is not a line. */
  const pipes = useMemo(
    () => plant.connections.filter((c) => equipmentIds.has(c.source) && equipmentIds.has(c.target)),
    [plant.connections, equipmentIds],
  );

  const boxes0 = useMemo(() => {
    const m = new Map<string, Box>();
    for (const e of equipment) {
      const { w, h } = sizeForKind(e.kind);
      m.set(e.id, { x: e.x - w / 2, y: e.y - h / 2, w, h });
    }
    return m;
  }, [equipment]);

  const boxes = boxes0;

  /**
   * Where each unit's instrument row sits.
   *
   * Bubbles are centred on their machine, but a seven-point pump fans three of
   * them past each side — outside its own process area, which is what forced the
   * frame wider than the plant. The row is therefore fitted to its compartment:
   * spacing tightens only as far as it must, and the row is nudged so its
   * outermost readout plate stays inside the area. Nothing clips at a tighter
   * frame.
   */
  const instrumentLayout = useMemo(() => {
    const m = new Map<string, { cx: number; spacing: number }>();
    for (const eq of equipment) {
      if (!eq.sensors.length) continue;
      const n = eq.sensors.length;
      const area = plant.areas.find((a) => a.id === eq.area_id);
      let spacing = INST_SPACING;
      let cx = eq.x;
      if (area && n > 1) {
        const available = area.w - 16 - INST_PLATE_W;
        spacing = Math.max(12, Math.min(INST_SPACING, available / (n - 1)));
        const halfRow = ((n - 1) / 2) * spacing + INST_PLATE_W / 2;
        const minCx = area.x + 8 + halfRow;
        const maxCx = area.x + area.w - 8 - halfRow;
        if (minCx <= maxCx) cx = Math.min(maxCx, Math.max(minCx, cx));
      }
      m.set(eq.id, { cx, spacing });
    }
    return m;
  }, [equipment, plant.areas]);

  /**
   * Geometry for every line, computed once. The visible linework is drawn under
   * the equipment (correct: a pipe passes behind a machine), but the HIT areas
   * are drawn in a layer above everything — otherwise a line that runs under a
   * unit is unclickable, which is how the first version shipped.
   */
  const routes = useMemo(() => {
    const m = new Map<string, { d: string; mid: { x: number; y: number } }>();
    for (const c of pipes) {
      const a = boxes0.get(c.source);
      const b = boxes0.get(c.target);
      if (!a || !b) continue;
      const r = route(a, b);
      m.set(c.id, { d: r.d, mid: r.mid });
    }
    return m;
  }, [pipes, boxes0]);

  const decisionLineIds = useMemo(
    () => ({
      route: new Set(recoveryDecision?.available ? recoveryDecision.route : []),
      block: new Set(recoveryDecision?.available ? recoveryDecision.block : []),
      restore: new Set(recoveryDecision?.available ? recoveryDecision.restore : []),
      // Position in the ordered route. The route is real topology order, so its
      // index is a real sequence: the recovery reveals along it, first line
      // first — no timer, just the decision's own order.
      routeIndex: new Map(
        (recoveryDecision?.available ? recoveryDecision.route : []).map((id, i) => [id, i]),
      ),
    }),
    [recoveryDecision],
  );

  /**
   * How many real hops each asset is downstream of a restored line.
   *
   * The recovery travels the plant's own topology: a restored line feeds its
   * target, that target feeds the next unit, and so on, stopping at any line
   * the decision shuts. Using the BFS depth as each node's animation delay is
   * what makes the recovery visibly node-by-node without a scripted timeline —
   * the sequence is the plant graph, not a clock.
   */
  const recoveringEquipmentDepths = useMemo(() => {
    const out = new Map<string, number>();
    if (!recoveryDecision?.available || !recoveryDecision.safety_confirmed) return out;
    const blocked = new Set(recoveryDecision.block);
    const restoredTargets = recoveryDecision.restore
      .map((id) => plant.connections.find((c) => c.id === id)?.target)
      .filter(Boolean) as string[];
    let frontier = restoredTargets;
    for (let depth = 0; depth < 5 && frontier.length; depth++) {
      const next: string[] = [];
      for (const eqId of frontier) {
        if (out.has(eqId)) continue;
        out.set(eqId, depth);
        for (const c of plant.connections) {
          if (blocked.has(c.id) || c.source !== eqId) continue;
          next.push(c.target);
        }
      }
      frontier = next;
    }
    return out;
  }, [plant.connections, recoveryDecision]);

  const extent = useMemo(() => {
    if (!areas.length) return FALLBACK_EXTENT;
    const x0 = Math.min(...areas.map((a) => a.x));
    let y0 = Math.min(...areas.map((a) => a.y));
    const x1 = Math.max(...areas.map((a) => a.x + a.w));
    let y1 = Math.max(...areas.map((a) => a.y + a.h));
    // Instrumentation is drawn attached below its unit; the frame extends down
    // to include the reading plates. It does NOT extend sideways: each unit's
    // instrument row is laid out to fit inside its own process area (see the
    // renderer below), so the areas still bound the drawing horizontally and the
    // frame stays as tight as the plant allows.
    for (const eq of equipment) {
      if (!eq.sensors.length) continue;
      const box = boxes0.get(eq.id);
      if (!box) continue;
      const lead = box.y + box.h + LABEL_H + 22;
      y0 = Math.min(y0, lead - 14);
      y1 = Math.max(y1, lead + 40);
    }
    const pad = 10;
    const box = { x: x0 - pad, y: y0 - pad, w: x1 - x0 + pad * 2, h: y1 - y0 + pad * 2 };
    // A plant whose areas are all zero-sized (or a partially built one) must
    // still yield a rectangle the camera maths can divide by.
    return isFittable(box) ? box : FALLBACK_EXTENT;
  }, [areas, equipment, boxes0]);

  /* -------------------------------------------------------------- interaction */

  const onPointerDown = useCallback(
    (ev: React.PointerEvent<SVGSVGElement>) => {
      // A locked camera does not pan: the plant is framed once, and a drag that
      // shifted it would move the whole overview off the operator's mental map.
      if (fixedCamera) return;
      if (ev.button !== 0) return;
      // Only start a pan on the background. A node OR a line is a click
      // target, not a drag: capturing the pointer here swallowed the click
      // before it could reach the line, so lines were drawn but unselectable.
      if ((ev.target as Element).closest("[data-node], [data-pipe-hit]")) return;
      drag.current = { x: ev.clientX, y: ev.clientY, vx: view.x, vy: view.y };
      (ev.currentTarget as SVGSVGElement).setPointerCapture(ev.pointerId);
    },
    [view.x, view.y, fixedCamera],
  );

  const onPointerMove = useCallback((ev: React.PointerEvent<SVGSVGElement>) => {
    const d = drag.current;
    if (!d) return;
    const scale = extent.w / (svgRef.current?.clientWidth || extent.w);
    setView((v) =>
      clampView({ ...v, x: d.vx + (ev.clientX - d.x) * scale, y: d.vy + (ev.clientY - d.y) * scale }, extent),
    );
  }, [extent]);

  const endDrag = useCallback(() => {
    drag.current = null;
  }, []);

  /* ------------------------------------------------- builder: move + wire --- */

  /** A unit being dragged in edit mode. */
  const moveDrag = useRef<{ id: string; ox: number; oy: number; moved: boolean } | null>(null);
  /** A drag just ended, so the click it produced must not also select. */
  const suppressClick = useRef(false);

  /** Screen point → drawing coordinates, through whatever camera is active. */
  const toPlant = useCallback((ev: React.PointerEvent, el: Element) => {
    const svg = svgRef.current;
    const ctm = (el as SVGGraphicsElement).getScreenCTM?.();
    if (!svg || !ctm) return null;
    const pt = svg.createSVGPoint();
    pt.x = ev.clientX;
    pt.y = ev.clientY;
    const p = pt.matrixTransform(ctm.inverse());
    return { x: p.x, y: p.y };
  }, []);

  const onUnitPointerDown = useCallback(
    (ev: React.PointerEvent<SVGGElement>, eq: EquipmentDef) => {
      if (!editable || !onEquipmentMove) return;
      // A press that starts ON A PORT is a wiring click, not a drag. Capturing
      // the pointer here retargets the click to the unit, so the port's own
      // onClick never ran and connect mode appeared to do nothing.
      if ((ev.target as Element).closest("[data-port]")) return;
      ev.stopPropagation();
      const p = toPlant(ev, ev.currentTarget);
      if (!p) return;
      moveDrag.current = { id: eq.id, ox: eq.x - p.x, oy: eq.y - p.y, moved: false };
      (ev.currentTarget as Element).setPointerCapture?.(ev.pointerId);
    },
    [editable, onEquipmentMove, toPlant],
  );

  const onUnitPointerMove = useCallback(
    (ev: React.PointerEvent<SVGGElement>) => {
      const m = moveDrag.current;
      if (!m || !onEquipmentMove) return;
      const p = toPlant(ev, ev.currentTarget);
      if (!p) return;
      // Snap to the drawing grid: a built plant's coordinates must land on the
      // same grid the drawing is ruled with, or pipes read as almost-straight.
      m.moved = true;
      onEquipmentMove(m.id, snapToGrid(p.x + m.ox), snapToGrid(p.y + m.oy));
    },
    [onEquipmentMove, toPlant],
  );

  const onUnitPointerUp = useCallback(() => {
    suppressClick.current = moveDrag.current?.moved ?? false;
    moveDrag.current = null;
  }, []);

  /**
   * A locked camera must also stop the BROWSER from zooming.
   *
   * React attaches `onWheel` passively, so `preventDefault()` there is ignored
   * with a console warning and a trackpad pinch (ctrl-wheel) still zooms the
   * page. Binding natively with `passive: false` makes the block authoritative:
   * no canvas zoom, no page zoom, no scroll stealing while the pointer is over
   * the plant. Editors (fixedCamera off) keep their wheel zoom.
   */
  useEffect(() => {
    if (!fixedCamera) return;
    const el = svgRef.current;
    if (!el) return;
    const blockZoom = (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();
    };
    el.addEventListener("wheel", blockZoom, { passive: false });
    return () => el.removeEventListener("wheel", blockZoom);
  }, [fixedCamera]);

  const zoom = useCallback(
    (factor: number) => setView((v) => clampView({ ...v, k: v.k * factor }, extent)),
    [extent],
  );

  /**
   * Fit the plant, or one area. `k` is applied about the viewBox centre, so the
   * offsets are computed to bring the target rectangle to the middle.
   */
  const fit = useCallback(
    (box?: Box) => {
      const t = box ?? extent;
      // An unmeasured or zero-sized target would divide through to Infinity and
      // blank the drawing, so a fit that cannot be computed leaves the camera
      // where it is instead of destroying it.
      if (!isFittable(t) || !isFittable(extent)) return;
      const k = Math.min(MAX_K, Math.max(MIN_K, Math.min(extent.w / t.w, extent.h / t.h) * FIT_K));
      setView(
        clampView(
          {
            k,
            x: t.x + t.w / 2 - extent.x - extent.w / 2,
            y: t.y + t.h / 2 - extent.y - extent.h / 2,
          },
          extent,
        ),
      );
    },
    [extent],
  );

  const focusEquipment = useCallback(() => {
    if (!focusId) return;
    const b = boxes.get(focusId);
    if (b) fit({ x: b.x - 90, y: b.y - 90, w: b.w + 180, h: b.h + 180 });
  }, [focusId, boxes, fit]);

  const instrumented = useMemo(
    () => equipment.filter((e) => e.sensors.length > 0),
    [equipment],
  );

  const transform = `translate(${extent.w / 2} ${extent.h / 2}) scale(${view.k}) translate(${-extent.w / 2 + view.x} ${-extent.h / 2 + view.y})`;

  return (
    <div
      className={`pmap${fixedCamera ? " is-fixed" : ""}`}
      data-testid="process-map"
      data-assets={equipment.length}
      data-pipes={pipes.length}
      data-camera={fixedCamera ? "fixed" : "free"}
      style={fixedCamera ? { aspectRatio: `${extent.w} / ${extent.h}` } : undefined}
    >
      <div className="pmap__tools" role="toolbar" aria-label="Process map controls">
        {/* Camera controls exist only where the camera may move. The live
            refinery is a fixed control-room framing, so it gets none — no zoom
            buttons, no fit/reset, no slider. */}
        {!fixedCamera && (
          <>
            <button type="button" onClick={() => zoom(1.25)} title="Zoom in" aria-label="Zoom in">＋</button>
            <button type="button" onClick={() => zoom(0.8)} title="Zoom out" aria-label="Zoom out">−</button>
            <button type="button" onClick={() => fit()} title="Fit the whole plant" aria-label="Fit plant">⤢</button>
            <button
              type="button"
              onClick={() => setView(clampView({ x: 0, y: 0, k: WORKING_K }, extent))}
              title="Reset to the working view"
              aria-label="Reset view"
            >
              ↺
            </button>
          </>
        )}
        <button
          type="button"
          onClick={() => setShowAllInstruments((v) => !v)}
          title={showAllInstruments ? "Show only abnormal instruments" : "Show every instrument reading"}
          aria-label="Toggle all instrument readings"
          aria-pressed={showAllInstruments}
          className={showAllInstruments ? "is-active" : undefined}
        >
          ◎
        </button>
        {!fixedCamera && isolateArea && (
          <button type="button" onClick={() => fit(areas[0])} title="Fit area" aria-label="Fit area">⊡</button>
        )}
        {!fixedCamera && focusId && (
          <button type="button" onClick={focusEquipment} title="Focus selection" aria-label="Focus selection">◎</button>
        )}
      </div>

      {selection?.kind === "pipe" && (() => {
        const conn = plant.connections.find((c) => c.id === selection.id);
        if (!conn) return null;
        const st = lineState(conn, runtime);
        const flow = runtime?.pipes?.[conn.id]?.flow ?? conn.flow ?? 0;
        const src = plant.equipment.find((e) => e.id === conn.source);
        const dst = plant.equipment.find((e) => e.id === conn.target);
        // Tracing walks the real topology. Depth-limited because a refinery has
        // loops, and an unbounded walk on a loop never terminates.
        const walk = (start: string, dir: "up" | "down", depth = 4): string[] => {
          const out: string[] = [];
          const seen = new Set([start]);
          let frontier = [start];
          for (let d = 0; d < depth; d++) {
            const next: string[] = [];
            for (const id of frontier) {
              for (const c of plant.connections) {
                const hit = dir === "down" ? c.source === id : c.target === id;
                const other = dir === "down" ? c.target : c.source;
                if (hit && !seen.has(other)) {
                  seen.add(other);
                  out.push(other);
                  next.push(other);
                }
              }
            }
            frontier = next;
          }
          return out;
        };
        const upstream = walk(conn.source, "up");
        const downstream = walk(conn.target, "down");
        return (
          <aside className="pmap__inspect" data-testid="pipe-inspector" data-line={conn.id}>
            <header className="pmap__inspect-head">
              <span className="pmap__inspect-id">{conn.id}</span>
              <button type="button" onClick={() => onSelect?.(null)} aria-label="Close line inspector">×</button>
            </header>
            <dl className="pmap__inspect-grid">
              <div><dt>Source</dt><dd>{src?.tag ?? conn.source}</dd></div>
              <div><dt>Destination</dt><dd>{dst?.tag ?? conn.target}</dd></div>
              <div><dt>Medium</dt><dd>{conn.medium ?? "—"}</dd></div>
              <div><dt>Flow</dt><dd>{fmt(flow)} / {fmt(conn.capacity)} m³/h</dd></div>
              <div><dt>Kind</dt><dd>{conn.kind}</dd></div>
              <div><dt>Status</dt><dd className={`is-${st}`}>{st.toUpperCase()}</dd></div>
            </dl>
            {/* Real actions. Blocking a line starves everything downstream on
                the next tick and raises an incident the agents respond to; a
                leak keeps the line running at reduced capacity. */}
            <div className="pmap__inspect-actions">
              <button
                type="button"
                data-line-action="block"
                disabled={!onLineAction || busyLine === conn.id || !conn.enabled}
                onClick={() => onLineAction?.(conn.id, "block")}
              >
                {busyLine === conn.id ? "…" : "Block line"}
              </button>
              <button
                type="button"
                data-line-action="restore"
                disabled={!onLineAction || busyLine === conn.id || conn.enabled}
                onClick={() => onLineAction?.(conn.id, "restore")}
              >
                Restore
              </button>
            </div>
            <div className="pmap__inspect-actions">
              <button
                type="button"
                data-line-action="leak"
                disabled={!onLineAction || busyLine === conn.id || conn.leaking}
                onClick={() => onLineAction?.(conn.id, "leak")}
              >
                Simulate leak
              </button>
              <button
                type="button"
                data-line-action="seal"
                disabled={!onLineAction || busyLine === conn.id || !conn.leaking}
                onClick={() => onLineAction?.(conn.id, "seal")}
              >
                Seal
              </button>
            </div>
            <div className="pmap__inspect-actions">
              <button
                type="button"
                onClick={() => onSelect?.({ kind: "equipment", id: conn.source })}
                disabled={!src}
              >
                Source →
              </button>
              <button
                type="button"
                onClick={() => onSelect?.({ kind: "equipment", id: conn.target })}
                disabled={!dst}
              >
                Destination →
              </button>
            </div>
            {lineError && <p className="pmap__inspect-err">{lineError}</p>}
            <div className="pmap__inspect-trace">
              <p>
                <b>Upstream</b> {upstream.length ? upstream.map((id) => plant.equipment.find((e) => e.id === id)?.tag ?? id).join(" · ") : "nothing feeds this line"}
              </p>
              <p>
                <b>Downstream</b> {downstream.length ? downstream.map((id) => plant.equipment.find((e) => e.id === id)?.tag ?? id).join(" · ") : "nothing downstream"}
              </p>
            </div>
            <p className="pmap__inspect-note">
              Blocking starves everything downstream on the next tick and raises an
              incident the agents respond to. A leak keeps the line running at reduced
              capacity.
            </p>
          </aside>
        );
      })()}

      <svg
        ref={svgRef}
        className="pmap__svg"
        viewBox={`${extent.x} ${extent.y} ${extent.w} ${extent.h}`}
        preserveAspectRatio="xMidYMid meet"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerLeave={endDrag}
        onWheel={(e) => {
          // A locked camera swallows every wheel gesture over the drawing —
          // notched wheel, trackpad scroll and two-finger pinch (which arrives
          // as a ctrl-wheel) — so nothing zooms the plant, and the page does not
          // scroll or browser-zoom out from under the operator.
          if (fixedCamera) {
            e.preventDefault();
            return;
          }
          if (!e.ctrlKey && !e.metaKey) return;
          e.preventDefault();
          zoom(e.deltaY < 0 ? 1.12 : 0.89);
        }}
        role="img"
        aria-label={`${plant.name} process map — ${equipment.length} assets, ${pipes.length} process lines`}
      >
        <defs>
          {/* Arrowhead per medium would be 23 markers; one arrow recoloured via
              context-stroke keeps the drawing honest without the bloat. */}
          <marker id="pmap-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke" />
          </marker>
          <pattern id="pmap-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="rgba(91,108,129,0.35)" strokeWidth="2" />
          </pattern>
        </defs>

        <g transform={transform}>
          {/* ---- process areas: the compartments the plant is organised into */}
          {areas.map((a) => (
            <g key={a.id} data-area={a.id}>
              <rect
                className="pmap__area"
                x={a.x}
                y={a.y}
                width={a.w}
                height={a.h}
                rx={6}
              />
              {/* Zone header band. A process drawing is read by zone, so each
                  compartment is titled with a band rather than a caption, and
                  the band carries the unit count so density is legible. */}
              <path
                className="pmap__area-band"
                d={`M ${a.x} ${a.y + 6} a 6 6 0 0 1 6 -6 h ${a.w - 12} a 6 6 0 0 1 6 6 v 20 h ${-a.w} z`}
              />
              <text className="pmap__area-name" x={a.x + 10} y={a.y + 14.5}>
                {a.name}
              </text>
              <text className="pmap__area-count" x={a.x + a.w - 10} y={a.y + 14.5}>
                {plant.equipment.filter((e) => e.area_id === a.id).length}
              </text>
            </g>
          ))}

          {/* ---- process lines, drawn under the equipment they join */}
          <g className="pmap__pipes">
            {pipes.map((c) => {
              const r = routes.get(c.id);
              if (!r) return null;
              const st = lineState(c, runtime);
              const flow = runtime?.pipes?.[c.id]?.flow ?? c.flow ?? 0;
              // Temperature beats the medium colour: a hot line is a hazard and
              // a cold one is a different regime, and both are read from the
              // live thermocouples rather than chosen by hand.
              const srcEq = equipment.find((e) => e.id === c.source);
              const temp = hottestTemperature(srcEq, readings);
              const thermal = thermalClass(temp);
              const colour = streamStroke(c, srcEq, readings);
              const selected = selection?.kind === "pipe" && selection.id === c.id;
              const isDecisionRoute = decisionLineIds.route.has(c.id);
              const isDecisionBlock = decisionLineIds.block.has(c.id);
              const isDecisionRestore = decisionLineIds.restore.has(c.id);
              return (
                <g
                  key={c.id}
                  data-node="pipe"
                  data-pipe={c.id}
                  data-line-state={st}
                  data-line-medium={c.medium}
                  data-thermal={thermal}
                  data-line-temp={temp === null ? undefined : temp.toFixed(1)}
                  data-recovery-route={isDecisionRoute ? "true" : undefined}
                  data-recovery-block={isDecisionBlock ? "true" : undefined}
                  data-recovery-restore={isDecisionRestore ? "true" : undefined}
                  data-isolated={isolatedSet.has(c.id) ? "true" : undefined}
                  className={`pmap__pipe${selected ? " is-selected" : ""}${isDecisionRoute ? " is-route" : ""}${isDecisionBlock ? " is-blocking" : ""}${isDecisionRestore ? " is-restoring" : ""}`}
                >
                  <path
                    d={r.d}
                    className={`pmap__pipe-line${SIGNAL_MEDIA.has(c.medium ?? "") ? " is-signal" : ""}`}
                    style={{ stroke: STATE_STROKE[st] || colour }}
                    markerEnd="url(#pmap-arrow)"
                  />
                  {st === "normal" && (
                    <path
                      d={r.d}
                      className="pmap__pipe-flow"
                      style={{ stroke: colour, animationDuration: `${Math.max(0.7, 8 / Math.max(6, flow))}s` }}
                    />
                  )}
                  {/* Direction chevrons. `markerEnd` puts one arrow at the end
                      of the line; on a long run that is easy to miss, so the
                      same direction is repeated along it as a marching dash.
                      Speed follows the real flow rate. */}
                  {st === "normal" && flow > 0.5 && (
                    <path
                      d={r.d}
                      className="pmap__pipe-chevrons"
                      data-flow-chevrons={c.id}
                      style={{
                        stroke: colour,
                        animationDuration: `${Math.max(1.1, 14 / Math.max(8, flow))}s`,
                      }}
                    />
                  )}
                  {isDecisionRoute && recoveryDecision?.safety_confirmed && (
                    <path
                      d={r.d}
                      className="pmap__pipe-route"
                      style={{
                        stroke: isDecisionRestore ? "#16a34a" : colour,
                        ["--route-delay" as string]: `${(decisionLineIds.routeIndex.get(c.id) ?? 0) * 260}ms`,
                      }}
                    />
                  )}
                  {st === "blocked" && (
                    <g className="pmap__pipe-block">
                      <circle cx={r.mid.x} cy={r.mid.y} r={7} />
                      <path d={`M ${r.mid.x - 3.6} ${r.mid.y - 3.6} L ${r.mid.x + 3.6} ${r.mid.y + 3.6}`} />
                      <path d={`M ${r.mid.x + 3.6} ${r.mid.y - 3.6} L ${r.mid.x - 3.6} ${r.mid.y + 3.6}`} />
                    </g>
                  )}
                  {st === "leaking" && (
                    <g className="pmap__pipe-leak">
                      <circle cx={r.mid.x} cy={r.mid.y} r={4.2} />
                      <path d={`M ${r.mid.x} ${r.mid.y + 5} q 2 5 0 9 q -2 4 0 8`} />
                    </g>
                  )}
                  {c.medium && (
                    <text className="pmap__pipe-label" x={r.mid.x + 5} y={r.mid.y - 5}>
                      {c.medium}
                    </text>
                  )}
                </g>
              );
            })}
          </g>

          {/* ---- the switch the backend made -------------------------------
               A measurement moved to another transmitter. Drawn on the process
               drawing because that is where an operator looks for it. */}
          {failover && (() => {
            const a = boxes.get(failover.from);
            const b = boxes.get(failover.to);
            if (!a || !b) return null;
            const ax = a.x + a.w / 2;
            const ay = a.y + a.h / 2;
            const bx = b.x + b.w / 2;
            const by = b.y + b.h / 2;
            if (failover.from === failover.to) {
              // Same asset: the alternate transmitter sits on the same machine,
              // which is the common case. Draw the switch as a loop over it.
              const d = `M ${ax} ${a.y} C ${ax - 34} ${a.y - 40}, ${ax + 34} ${a.y - 40}, ${ax} ${a.y}`;
              return (
                <g data-testid="failover-link" data-kind="same-asset" data-from={failover.from} data-to={failover.to}>
                  <path className="pmap__failover-halo" d={d} />
                  <path className="pmap__failover" d={d} />
                </g>
              );
            }
            const d = `M ${ax} ${ay} L ${ax} ${Math.min(ay, by) - 34} L ${bx} ${Math.min(ay, by) - 34} L ${bx} ${by}`;
            return (
              <g data-testid="failover-link" data-kind="cross-asset" data-from={failover.from} data-to={failover.to}>
                <path className="pmap__failover-halo" d={d} />
                <path className="pmap__failover" d={d} />
              </g>
            );
          })()}

          {/* ---- equipment and its instrumentation */}
          {[...equipment].sort((a, b) => a.y - b.y).map((eq) => {
            const state = runtime?.states?.[eq.id] ?? eq.state ?? "normal";
            const tone = stateTone(state);
            const selected = selection?.kind === "equipment" && selection.id === eq.id;
            const flagged = highlight.includes(eq.id);
            // A live warning the operator must see without reading the panel.
            // Driven by the engine's own asset state and by the incident
            // highlight — never by a decorative condition.
            const alarming = state === "warning" || state === "critical" || state === "failed" || flagged;
            const recoveringDepth = recoveringEquipmentDepths.get(eq.id);
            const recovering = recoveringDepth !== undefined;
            const box = boxes.get(eq.id)!;
            return (
              <g
                key={eq.id}
                data-node="equipment"
                data-unit={eq.id}
                data-kind={eq.kind}
                data-state={state}
                data-flagged={flagged ? "true" : undefined}
                data-recovering={recovering ? "true" : undefined}
                data-recovering-depth={recovering ? String(recoveringDepth) : undefined}
                data-failover-target={failover?.to === eq.id ? "true" : undefined}
                data-connect-from={connectFromId === eq.id ? "true" : undefined}
                data-isolated={isolatedEqSet.has(eq.id) ? "true" : undefined}
                className={`pmap__eq${selected ? " is-selected" : ""}${flagged ? " is-flagged" : ""}${recovering ? " is-recovering" : ""}${editable ? " is-editable" : ""}`}
                style={recovering ? { animationDelay: `${recoveringDepth * 220}ms` } : undefined}
                onPointerDown={editable ? (ev) => onUnitPointerDown(ev, eq) : undefined}
                onPointerMove={editable ? onUnitPointerMove : undefined}
                onPointerUp={editable ? onUnitPointerUp : undefined}
                onClick={(e) => {
                  e.stopPropagation();
                  // A drag ends in a click; do not also select on it.
                  if (suppressClick.current) {
                    suppressClick.current = false;
                    return;
                  }
                  onSelect?.({ kind: "equipment", id: eq.id });
                }}
              >
                {/* The equipment itself — no frame, no card, no badge. A flag
                    marks an incident by tinting the ground under the asset
                    rather than boxing it in. */}
                {flagged && (
                  <ellipse
                    className="pmap__eq-mark"
                    cx={eq.x}
                    cy={box.y + box.h * 0.95}
                    rx={box.w * 0.54}
                    ry={box.h * 0.14}
                  />
                )}
                {selected && (
                  <ellipse
                    className="pmap__eq-mark is-selected"
                    cx={eq.x}
                    cy={box.y + box.h * 0.95}
                    rx={box.w * 0.54}
                    ry={box.h * 0.14}
                  />
                )}
                {/* Pulsing alert indicator. Two concentric rings expanding from
                    the unit's centre line, one delayed, so it reads as a live
                    beacon rather than a static badge. `data-alerting` is the
                    hook the gates and the CSS both key off. */}
                {alarming && (
                  <g
                    className="pmap__alert"
                    data-alerting="true"
                    data-alert-state={state}
                    pointerEvents="none"
                  >
                    <ellipse
                      className="pmap__alert-ring"
                      cx={eq.x}
                      cy={box.y + box.h / 2}
                      rx={Math.max(box.w * 0.44, 18)}
                      ry={Math.max(box.h * 0.44, 14)}
                    />
                    <ellipse
                      className="pmap__alert-ring is-delayed"
                      cx={eq.x}
                      cy={box.y + box.h / 2}
                      rx={Math.max(box.w * 0.44, 18)}
                      ry={Math.max(box.h * 0.44, 14)}
                    />
                  </g>
                )}
                <EquipmentShape
                  kind={eq.kind}
                  box={box}
                  id={eq.tag}
                  name={eq.name}
                  status={recovering ? "recovering" : state}
                  selected={selected}
                />
                <text className="pmap__eq-tag" x={eq.x} y={box.y + box.h + 14}>
                  {eq.tag}
                </text>
                {(selected || flagged || showAllInstruments) && (
                  <text className="pmap__eq-name" x={eq.x} y={box.y + box.h + 26}>
                    {eq.name.length > 24 ? `${eq.name.slice(0, 23)}…` : eq.name}
                  </text>
                )}
                {/* Wire mode: this unit's input (left) and output (right) ports.
                    A pipe is made output → input, so the drawing carries the
                    process-flow direction rather than the click order. */}
                {connectMode && (
                  <g className="pmap__ports">
                    <circle
                      className="pmap__port pmap__port--in"
                      data-port="in"
                      data-port-unit={eq.id}
                      cx={box.x}
                      cy={box.y + box.h / 2}
                      r={9}
                      onClick={(e) => {
                        e.stopPropagation();
                        onPortClick?.(eq.id, "in");
                      }}
                    >
                      <title>{`${eq.tag} input`}</title>
                    </circle>
                    <circle
                      className="pmap__port pmap__port--out"
                      data-port="out"
                      data-port-unit={eq.id}
                      cx={box.x + box.w}
                      cy={box.y + box.h / 2}
                      r={9}
                      onClick={(e) => {
                        e.stopPropagation();
                        onPortClick?.(eq.id, "out");
                      }}
                    >
                      <title>{`${eq.tag} output`}</title>
                    </circle>
                  </g>
                )}
              </g>
            );
          })}

          {/* ---- instrumentation, drawn attached to the machine it measures
               An ISA bubble on every point keeps the plant dense the way a real
               drawing is. The READOUT is printed selectively: all 224 at once
               produced a solid band of overlapping text, which is worse than no
               numbers. A readout appears when the instrument is abnormal (an
               operator must see that), when its unit is selected or flagged, or
               when the operator asks for everything. */}
          <g className="pmap__inst">
            {instrumented.map((eq) =>
              eq.sensors.map((s, i) => {
                const r = readings[s.id];
                const q = runtime?.qualities?.[s.id] ?? "good";
                const tone = q === "bad" ? "critical" : q === "stale" ? "warning" : readingTone(s, r);
                const box = boxes.get(eq.id)!;
                const unitSelected = selection?.kind === "equipment" && selection.id === eq.id;
                const unitFlagged = highlight.includes(eq.id) || (runtime?.states?.[eq.id] ?? eq.state) !== "normal";
                const abnormal = tone !== "normal" || q !== "good";
                const showReadout =
                  abnormal || unitSelected || unitFlagged || showReadouts;
                if (!showBubbles && !showReadout) return null;
                const layout = instrumentLayout.get(eq.id) ?? { cx: eq.x, spacing: INST_SPACING };
                const x = layout.cx + (i - (eq.sensors.length - 1) / 2) * layout.spacing;
                const y = box.y + box.h + LABEL_H + 22;
                return (
                  <g
                    key={s.id}
                    className="pmap__inst-item"
                    data-instrument={s.id}
                    data-instrument-quality={q}
                    data-instrument-tone={tone}
                    data-readout={showReadout ? "true" : "false"}
                  >
                    <line x1={x} y1={box.y + box.h} x2={x} y2={y - 8} className="pmap__inst-lead" />
                    <circle cx={x} cy={y} r={fixedCamera ? 10 : 8} className="pmap__inst-bubble" style={{ ["--tone" as string]: TONE_COLOR[tone] } as CSSProperties} />
                    <text className="pmap__inst-code" x={x} y={y + 2.8}>{instrumentCode(s)}</text>
                    {showReadout && (
                      <>
                        <rect
                          className="pmap__inst-plate"
                          x={x - INST_PLATE_W / 2}
                          y={y + 12}
                          width={INST_PLATE_W}
                          height={q === "substituted" || q === "bad" ? 26 : 17}
                          rx={2.5}
                        />
                        <text className="pmap__inst-value" x={x} y={y + 23}>
                          {r ? `${fmt(r.value)} ${s.unit}` : "—"}
                        </text>
                        {(abnormal || unitSelected) && (
                          <text className="pmap__inst-state" x={x} y={y + 33} style={{ fill: TONE_COLOR[tone] }}>
                            {q === "substituted"
                              ? "SUBSTITUTED"
                              : q === "bad"
                                ? "OUT OF SERVICE"
                                : tone.toUpperCase()}
                          </text>
                        )}
                        <text className="pmap__inst-tag" x={x} y={y - 12}>{s.tag}</text>
                      </>
                    )}
                  </g>
                );
              }),
            )}
          </g>
        </g>

        {/* Hit layer, above everything. A line must be selectable wherever it
            is drawn, including where it passes behind a machine. */}
        <g className="pmap__pipe-hits" transform={transform}>
          {pipes.map((c) => {
            const r = routes.get(c.id);
            if (!r) return null;
            const selected = selection?.kind === "pipe" && selection.id === c.id;
            return (
              <path
                key={c.id}
                d={r.d}
                className={`pmap__pipe-hit${selected ? " is-selected" : ""}`}
                data-pipe-hit={c.id}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect?.({ kind: "pipe", id: c.id });
                }}
              />
            );
          })}
        </g>
      </svg>
    </div>
  );
}

/* -------------------------------------------------------------------- helpers */

function fmt(v: number): string {
  if (!Number.isFinite(v)) return "—";
  const a = Math.abs(v);
  if (a >= 1000) return v.toFixed(0);
  if (a >= 100) return v.toFixed(1);
  return v.toFixed(2);
}

/** ISA tag letters for a measurement, e.g. pressure → PT. */
export function instrumentCode(s: SensorDef): string {
  const m = (s.measurement ?? "").toLowerCase();
  const first =
    m.startsWith("press") ? "P"
    : m.startsWith("temp") ? "T"
    : m.startsWith("flow") ? "F"
    : m.startsWith("level") ? "L"
    : m.startsWith("vib") ? "V"
    : m.startsWith("rpm") ? "S"
    : m.startsWith("amp") || m.startsWith("current") ? "E"
    : m.startsWith("power") ? "E"
    : m.startsWith("gas") ? "A"
    : m.startsWith("conduct") ? "C"
    : m.startsWith("dens") ? "D"
    : "X";
  return `${first}T`;
}

/** Reading state from the instrument's own band, when the wire carries one. */
export function readingTone(s: SensorDef, r?: SpatialReading): "normal" | "warning" | "critical" {
  if (!r || !Number.isFinite(r.value)) return "normal";
  const crit = s.critical_max;
  const warn = s.warning_max;
  const critLow = s.critical_min;
  const warnLow = s.warning_min;
  if (crit != null && r.value >= crit) return "critical";
  if (critLow != null && r.value <= critLow) return "critical";
  if (warn != null && r.value >= warn) return "warning";
  if (warnLow != null && r.value <= warnLow) return "warning";
  return "normal";
}
