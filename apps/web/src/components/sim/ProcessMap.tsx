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

import { useCallback, useMemo, useRef, useState, type CSSProperties } from "react";
import { SimSymbol, symbolForEquipment } from "@/lib/sim/symbols";
import type { ConnectionDef, EquipmentDef, PlantDef, SensorDef } from "@/lib/sim/types";
import type { CanvasRuntime, SpatialReading } from "@/components/sim/SchematicCanvas";

/* ------------------------------------------------------------------ geometry */

/** Equipment footprint in plant units. The dataset's x/y is the centre. */
const EQ_W = 74;
const EQ_H = 62;
/** Lettering is placed below the body so it never covers the linework. */
const LABEL_H = 30;

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
 * Process media, coloured the way a refinery draws them: restrained, and
 * distinguishable without relying on hue alone (each also carries a label).
 */
export const MEDIUM_COLOR: Record<string, string> = {
  crude: "#6b5a3e",
  "atm-resid": "#7a6242",
  "vac-resid": "#8a6a44",
  naphtha: "#c9a227",
  jet: "#b98a2e",
  diesel: "#9a7d2a",
  reformate: "#a8862f",
  vgo: "#8f7a3a",
  slurry: "#5f5136",
  hydrogen: "#5fa8c9",
  "recycle-gas": "#6f9fc0",
  "sour-gas": "#8a9a5b",
  amine: "#7fae9a",
  gas: "#8d9aa6",
  vapor: "#a9b4bd",
  steam: "#b9c2c9",
  water: "#4a7fb5",
  wastewater: "#5a6f7a",
  brine: "#6f9aa8",
  air: "#7fa8c4",
  control: "#7c3aed",
};

export const DEFAULT_MEDIUM_COLOR = "#8794a1";

/**
 * Media that are signals rather than process fluid. A control loop drawn as a
 * solid process line misreads as something flowing, which is why a real drawing
 * dashes instrument wiring.
 */
export const SIGNAL_MEDIA = new Set(["control", "signal", "power"]);

export function mediumColor(medium: string | undefined): string {
  return MEDIUM_COLOR[medium ?? ""] ?? DEFAULT_MEDIUM_COLOR;
}

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
  blocked: "#5b6c81",
  leaking: "#dc2626",
};

/* ------------------------------------------------------------------- routing */

/**
 * Orthogonal route between two boxes.
 *
 * A process line is drawn as horizontal and vertical runs, never as a curve —
 * a curve hides where a line actually goes, which is the one thing the drawing
 * exists to communicate. The route leaves the source on the side facing the
 * target and enters the target on the side facing the source.
 */
function route(a: Box, b: Box): { d: string; mid: { x: number; y: number }; horizontal: boolean } {
  const aMidY = a.y + a.h / 2;
  const bMidY = b.y + b.h / 2;
  const goingRight = b.x >= a.x;

  const startX = goingRight ? a.x + a.w : a.x;
  const endX = goingRight ? b.x : b.x + b.w;

  // Vertical separation decides whether a single elbow is enough.
  const gap = Math.abs(endX - startX);
  const dy = Math.abs(bMidY - aMidY);

  if (dy < EQ_H * 0.75 || gap < EQ_W * 1.2) {
    // Straight run: leave and enter at the same height.
    const y = aMidY;
    return {
      d: `M ${startX} ${y} H ${endX}`,
      mid: { x: (startX + endX) / 2, y },
      horizontal: true,
    };
  }

  // H-V-H: run out horizontally, turn once, run in horizontally.
  const turnX = goingRight ? startX + Math.max(20, gap * 0.45) : startX - Math.max(20, gap * 0.45);
  return {
    d: `M ${startX} ${aMidY} H ${turnX} V ${bMidY} H ${endX}`,
    mid: { x: turnX, y: (aMidY + bMidY) / 2 },
    horizontal: false,
  };
}

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
}: ProcessMapProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [view, setView] = useState({ x: 0, y: 0, k: 1 });
  /** Print every instrument readout, rather than only the ones that need eyes. */
  const [showAllInstruments, setShowAllInstruments] = useState(false);
  const drag = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);

  const areas = useMemo(
    () => (isolateArea ? plant.areas.filter((a) => a.id === isolateArea) : plant.areas),
    [plant.areas, isolateArea],
  );

  const equipment = useMemo(() => {
    const ids = new Set(areas.map((a) => a.id));
    return plant.equipment.filter((e) => ids.has(e.area_id));
  }, [plant.equipment, areas]);

  const equipmentIds = useMemo(() => new Set(equipment.map((e) => e.id)), [equipment]);

  /** Every pipe whose both ends are drawn. A half-drawn line is not a line. */
  const pipes = useMemo(
    () => plant.connections.filter((c) => equipmentIds.has(c.source) && equipmentIds.has(c.target)),
    [plant.connections, equipmentIds],
  );

  const boxes0 = useMemo(() => {
    const m = new Map<string, Box>();
    for (const e of equipment) {
      m.set(e.id, { x: e.x - EQ_W / 2, y: e.y - EQ_H / 2, w: EQ_W, h: EQ_H });
    }
    return m;
  }, [equipment]);

  const boxes = boxes0;

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

  const extent = useMemo(() => {
    if (!areas.length) return { x: 0, y: 0, w: 800, h: 600 };
    const x0 = Math.min(...areas.map((a) => a.x));
    const y0 = Math.min(...areas.map((a) => a.y));
    const x1 = Math.max(...areas.map((a) => a.x + a.w));
    const y1 = Math.max(...areas.map((a) => a.y + a.h));
    const pad = 48;
    return { x: x0 - pad, y: y0 - pad, w: x1 - x0 + pad * 2, h: y1 - y0 + pad * 2 };
  }, [areas]);

  /* -------------------------------------------------------------- interaction */

  const onPointerDown = useCallback(
    (ev: React.PointerEvent<SVGSVGElement>) => {
      if (ev.button !== 0) return;
      // Only start a pan on the background. A node OR a line is a click
      // target, not a drag: capturing the pointer here swallowed the click
      // before it could reach the line, so lines were drawn but unselectable.
      if ((ev.target as Element).closest("[data-node], [data-pipe-hit]")) return;
      drag.current = { x: ev.clientX, y: ev.clientY, vx: view.x, vy: view.y };
      (ev.currentTarget as SVGSVGElement).setPointerCapture(ev.pointerId);
    },
    [view.x, view.y],
  );

  const onPointerMove = useCallback((ev: React.PointerEvent<SVGSVGElement>) => {
    const d = drag.current;
    if (!d) return;
    const scale = extent.w / (svgRef.current?.clientWidth || extent.w);
    setView((v) => ({ ...v, x: d.vx + (ev.clientX - d.x) * scale, y: d.vy + (ev.clientY - d.y) * scale }));
  }, [extent.w]);

  const endDrag = useCallback(() => {
    drag.current = null;
  }, []);

  const zoom = useCallback((factor: number) => {
    setView((v) => ({ ...v, k: Math.min(6, Math.max(0.35, v.k * factor)) }));
  }, []);

  /**
   * Fit the plant, or one area. `k` is applied about the viewBox centre, so the
   * offsets are computed to bring the target rectangle to the middle.
   */
  const fit = useCallback(
    (box?: Box) => {
      const t = box ?? extent;
      const k = Math.min(6, Math.max(0.35, Math.min(extent.w / t.w, extent.h / t.h) * 0.92));
      setView({
        k,
        x: t.x + t.w / 2 - extent.x - extent.w / 2,
        y: t.y + t.h / 2 - extent.y - extent.h / 2,
      });
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
    <div className="pmap" data-testid="process-map" data-assets={equipment.length} data-pipes={pipes.length}>
      <div className="pmap__tools" role="toolbar" aria-label="Process map controls">
        <button type="button" onClick={() => zoom(1.25)} title="Zoom in" aria-label="Zoom in">＋</button>
        <button type="button" onClick={() => zoom(0.8)} title="Zoom out" aria-label="Zoom out">−</button>
        <button type="button" onClick={() => fit()} title="Fit plant" aria-label="Fit plant">⤢</button>
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
        {isolateArea && (
          <button type="button" onClick={() => fit(areas[0])} title="Fit area" aria-label="Fit area">⊡</button>
        )}
        {focusId && (
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
            <div className="pmap__inspect-trace">
              <p>
                <b>Upstream</b> {upstream.length ? upstream.map((id) => plant.equipment.find((e) => e.id === id)?.tag ?? id).join(" · ") : "nothing feeds this line"}
              </p>
              <p>
                <b>Downstream</b> {downstream.length ? downstream.map((id) => plant.equipment.find((e) => e.id === id)?.tag ?? id).join(" · ") : "nothing downstream"}
              </p>
            </div>
            {/* Leak and block are genuinely not implemented: Connection carries
                `leaking` and `enabled` and the drawing renders both, but no
                endpoint mutates them. Saying so beats two dead buttons. */}
            <p className="pmap__inspect-note">
              Leak and block simulation have no endpoint yet — the drawing shows both
              states, but nothing on the backend can set them.
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
              <text className="pmap__area-name" x={a.x + 10} y={a.y + 17}>
                {a.name}
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
              const colour = mediumColor(c.medium);
              const selected = selection?.kind === "pipe" && selection.id === c.id;
              return (
                <g
                  key={c.id}
                  data-node="pipe"
                  data-pipe={c.id}
                  data-line-state={st}
                  data-line-medium={c.medium}
                  className={`pmap__pipe${selected ? " is-selected" : ""}`}
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
          {equipment.map((eq) => {
            const state = runtime?.states?.[eq.id] ?? eq.state ?? "normal";
            const tone = stateTone(state);
            const selected = selection?.kind === "equipment" && selection.id === eq.id;
            const flagged = highlight.includes(eq.id);
            const box = boxes.get(eq.id)!;
            return (
              <g
                key={eq.id}
                data-node="equipment"
                data-unit={eq.id}
                data-state={state}
                data-flagged={flagged ? "true" : undefined}
                data-failover-target={failover?.to === eq.id ? "true" : undefined}
                className={`pmap__eq${selected ? " is-selected" : ""}${flagged ? " is-flagged" : ""}`}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect?.({ kind: "equipment", id: eq.id });
                }}
              >
                {flagged && (
                  <rect
                    className="pmap__eq-flag"
                    x={box.x - 7}
                    y={box.y - 7}
                    width={box.w + 14}
                    height={box.h + 14}
                    rx={7}
                  />
                )}
                <rect
                  className="pmap__eq-body"
                  x={box.x}
                  y={box.y}
                  width={box.w}
                  height={box.h}
                  rx={4}
                  style={{ ["--tone" as string]: TONE_COLOR[tone] } as CSSProperties}
                />
                <g
                  transform={`translate(${eq.x - 24} ${eq.y - 24})`}
                  className="pmap__eq-glyph"
                  style={{ color: tone === "normal" ? "#243447" : TONE_COLOR[tone] }}
                >
                  <SimSymbol type={symbolForEquipment(eq.kind, eq.name)} state={state} size={48} label={`${eq.tag} — ${eq.name}`} />
                </g>
                <text className="pmap__eq-tag" x={eq.x} y={box.y + box.h + 13}>
                  {eq.tag}
                </text>
                {/* Names are printed only where they earn the space. At plant
                    zoom, 58 of them collided into an unreadable ribbon; a real
                    HMI leads with the tag and reveals the description on
                    selection, which is what a tag is for. */}
                {(selected || flagged || showAllInstruments) && (
                  <text className="pmap__eq-name" x={eq.x} y={box.y + box.h + 24}>
                    {eq.name.length > 22 ? `${eq.name.slice(0, 21)}…` : eq.name}
                  </text>
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
                  abnormal || unitSelected || unitFlagged || showAllInstruments;
                const spacing = 46;
                const x = eq.x + (i - (eq.sensors.length - 1) / 2) * spacing;
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
                    <circle cx={x} cy={y} r={8} className="pmap__inst-bubble" style={{ ["--tone" as string]: TONE_COLOR[tone] } as CSSProperties} />
                    <text className="pmap__inst-code" x={x} y={y + 2.8}>{instrumentCode(s)}</text>
                    {showReadout && (
                      <>
                        <rect
                          className="pmap__inst-plate"
                          x={x - 30}
                          y={y + 12}
                          width={60}
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
