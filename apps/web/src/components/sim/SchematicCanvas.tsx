"use client";

/**
 * SchematicCanvas — the P&ID-grade plant renderer.
 * SVG (not canvas): 60 nodes + 60 edges stay 60fps under pan/zoom, and every
 * node is a real DOM element (hover/click/keyboard). Wheel = zoom to cursor,
 * drag = pan, minimap = click-to-jump. Sensor micro-dots show live quality.
 *
 * Two layouts share this module:
 *   · "schematic" (default) — the classic P&ID view used by the simulation hub
 *     cards and the builder. Untouched behaviour.
 *   · "spatial" (opt-in)    — a bright, sweeping left-to-right process map with
 *     live telemetry pills, anomaly pulses and an animated agent investigation
 *     link. Only the plant twin routes opt in.
 */
import {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  type WheelEvent as ReactWheelEvent,
} from "react";
import { SimSymbol, symbolForEquipment, type SimVisualState } from "@/lib/sim/symbols";
import type { EquipmentDef, PlantDef, SensorDef } from "@/lib/sim/types";

export interface CanvasRuntime {
  /** equipmentId → visual state */
  states: Record<string, SimVisualState>;
  /** sensorId → quality */
  qualities: Record<string, "good" | "bad" | "stale" | "substituted">;
  /** connection id → leaking/enabled */
  pipes: Record<string, { leaking: boolean; enabled: boolean; flow: number }>;
}

export interface SpatialReading {
  value: number;
  quality: "good" | "bad" | "stale" | "substituted";
}

export interface SchematicCanvasProps {
  plant: PlantDef;
  runtime: CanvasRuntime;
  selectedId: string | null;
  affected: string[];
  onSelect: (eq: EquipmentDef) => void;
  onHover: (eq: EquipmentDef | null) => void;
  onBackground?: () => void;
  /** Opt-in bright spatial layout. Defaults to the classic schematic view. */
  layout?: "schematic" | "spatial";
  /** sensorId → live reading, consumed by the spatial telemetry pills. */
  readings?: Record<string, SpatialReading>;
  /** equipment linked to the floating investigation panel (spatial layout). */
  anomalyId?: string | null;
  /** whether the investigation panel is open (spatial layout). */
  panelOpen?: boolean;
  /** investigation panel contents rendered inside the spatial overlay. */
  children?: ReactNode;
}

const KIND_NODE: Record<string, number> = { pump: 46, valve: 42, tank: 50, vessel: 46, column: 52, exchanger: 48, furnace: 50, compressor: 48, motor: 42, conveyor: 52, safety: 46, utility: 46 };

const EDGE_STYLE: Record<string, { dash?: string; width: number; color: string }> = {
  pipe: { width: 2.2, color: "rgba(157,177,199,0.5)" },
  signal: { width: 1.1, dash: "3 5", color: "rgba(69,213,255,0.4)" },
  control: { width: 1.2, dash: "8 3 2 3", color: "rgba(255,180,84,0.45)" },
  power: { width: 1.4, dash: "10 4", color: "rgba(183,156,255,0.4)" },
};

function EquipmentNode({
  eq,
  state,
  qualities,
  selected,
  affected,
  onSelect,
  onHover,
}: {
  eq: EquipmentDef;
  state: SimVisualState;
  qualities: Record<string, "good" | "bad" | "stale" | "substituted">;
  selected: boolean;
  affected: boolean;
  onSelect: (eq: EquipmentDef) => void;
  onHover: (eq: EquipmentDef | null) => void;
}) {
  const size = KIND_NODE[eq.kind] ?? 46;
  return (
    <g
      transform={`translate(${eq.x - size / 2}, ${eq.y - size / 2})`}
      style={{ cursor: "pointer" }}
      onPointerDown={(e) => {
        e.stopPropagation();
        onSelect(eq);
      }}
      onPointerEnter={() => onHover(eq)}
      onPointerLeave={() => onHover(null)}
      role="button"
      aria-label={`${eq.tag} ${eq.name}`}
    >
      {(selected || affected) && (
        <rect
          x={-7}
          y={-7}
          width={size + 14}
          height={size + 14}
          rx={10}
          fill="none"
          stroke={selected ? "#45d5ff" : "#ff5d5d"}
          strokeWidth={selected ? 1.8 : 1.2}
          strokeDasharray={affected && !selected ? "5 4" : undefined}
          opacity={selected ? 0.95 : 0.6}
        />
      )}
      <foreignObject x={0} y={0} width={size} height={size} style={{ overflow: "visible" }}>
        <SimSymbol
          type={symbolForEquipment(eq.kind, eq.name)}
          state={state}
          size={size}
          label={`${eq.tag} — ${eq.name}`}
        />
      </foreignObject>
      <text
        x={size / 2}
        y={size + 13}
        textAnchor="middle"
        fontSize="9.5"
        fontFamily="ui-monospace, monospace"
        fontWeight={selected ? 700 : 500}
        fill={selected ? "#45d5ff" : state !== "normal" ? "#ffb454" : "#9db1c7"}
        stroke="none"
      >
        {eq.tag}
      </text>
      {eq.sensors.slice(0, 4).map((s, i) => {
        const q = qualities[s.id] ?? "good";
        const c = q === "bad" ? "#ff5d5d" : q === "stale" ? "#ffb454" : "#3ddc97";
        return (
          <circle key={s.id} cx={4 + i * 8} cy={-5} r={2.4} fill={c} stroke="none" opacity={q === "good" ? 0.55 : 1}>
            {q === "bad" && <animate attributeName="opacity" values="1;0.2;1" dur="1s" repeatCount="indefinite" />}
          </circle>
        );
      })}
    </g>
  );
}

const EquipmentNodeMemo = memo(EquipmentNode);

/* ==========================================================================
   Classic schematic layout — unchanged. This is what the simulation hub card
   previews and the builder render.
   ========================================================================== */

function SchematicView({
  plant,
  runtime,
  selectedId,
  affected,
  onSelect,
  onHover,
  onBackground,
}: SchematicCanvasProps) {
  const [cam, setCam] = useState({ x: 0, y: 0, k: 1 });
  /**
   * Zoom limits. Deliberately conservative: at 0.25 the whole plant still reads
   * as a schematic and at 3.0 a single instrument is legible. Beyond either the
   * user loses the context that makes the drawing a plant rather than a picture.
   */
  const MIN_ZOOM = 0.25;
  const MAX_ZOOM = 3.0;
  const dragRef = useRef<{ sx: number; sy: number; cx: number; cy: number; active: boolean; moved: boolean } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  /**
   * Camera target. Wheel input writes here; a rAF loop eases the rendered
   * camera toward it. Previously each wheel event snapped `cam` directly, so a
   * trackpad — which fires dozens of small deltas per gesture — flew across the
   * plant and the user lost spatial orientation.
   */
  const targetRef = useRef({ x: 0, y: 0, k: 1 });
  const rafRef = useRef(0);

  const bounds = useMemo(() => {
    const xs = plant.equipment.map((e) => e.x);
    const ys = plant.equipment.map((e) => e.y);
    if (!xs.length) return { minX: 0, minY: 0, maxX: 1800, maxY: 1100 };
    return {
      minX: Math.min(...xs) - 90,
      minY: Math.min(...ys) - 90,
      maxX: Math.max(...xs) + 130,
      maxY: Math.max(...ys) + 130,
    };
  }, [plant]);

  const W = bounds.maxX - bounds.minX;
  const H = bounds.maxY - bounds.minY;

  /** Ease the rendered camera toward the target; stops when it has settled. */
  const startEasing = useCallback(() => {
    if (rafRef.current) return;
    const step = () => {
      const t = targetRef.current;
      let done = true;
      setCam((c) => {
        const nx = c.x + (t.x - c.x) * 0.22;
        const ny = c.y + (t.y - c.y) * 0.22;
        const nk = c.k + (t.k - c.k) * 0.22;
        if (Math.abs(t.x - nx) > 0.4 || Math.abs(t.y - ny) > 0.4 || Math.abs(t.k - nk) > 0.0015) {
          done = false;
        }
        return { x: nx, y: ny, k: nk };
      });
      if (done) {
        setCam({ x: t.x, y: t.y, k: t.k });
        rafRef.current = 0;
        return;
      }
      rafRef.current = requestAnimationFrame(step);
    };
    rafRef.current = requestAnimationFrame(step);
  }, []);

  /**
   * Wheel zoom, normalised across input devices.
   *
   * `deltaY` is 1–4 on a trackpad and ~100 on a notched mouse wheel, and
   * `deltaMode` is lines (1) on Firefox. Multipliers were being applied per
   * event with no regard for magnitude, which is why a trackpad gesture shot
   * the camera off-screen. Here the delta is normalised to a bounded step, so
   * one gesture and one notch feel comparable.
   */
  const onWheel = useCallback(
    (e: ReactWheelEvent) => {
      const rect = svgRef.current?.getBoundingClientRect();
      if (!rect) return;
      e.preventDefault();

      let dy = e.deltaY;
      if (e.deltaMode === 1) dy *= 16; // lines → px
      else if (e.deltaMode === 2) dy *= 400; // pages → px
      // Bounded, sign-preserving step. Cmd/Ctrl gives finer control.
      const precision = e.metaKey || e.ctrlKey ? 0.35 : 1;
      const stepMag = Math.min(0.12, Math.abs(dy) / 900) * precision;
      const factor = dy > 0 ? 1 - stepMag : 1 + stepMag;

      const t = targetRef.current;
      const k = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, t.k * factor));
      const px = (e.clientX - rect.left) / rect.width;
      const py = (e.clientY - rect.top) / rect.height;
      // Keep the point under the cursor fixed while zooming.
      targetRef.current = { k, x: t.x - (k - t.k) * W * px, y: t.y - (k - t.k) * H * py };
      startEasing();
    },
    [W, H, startEasing],
  );

  /** Predictable zoom increments for the +/- controls. */
  const zoomBy = useCallback(
    (factor: number) => {
      const t = targetRef.current;
      const k = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, t.k * factor));
      targetRef.current = { ...t, k };
      startEasing();
    },
    [startEasing],
  );

  const fitView = useCallback(() => {
    targetRef.current = { x: 0, y: 0, k: 1 };
    startEasing();
  }, [startEasing]);

  const resetView = useCallback(() => {
    targetRef.current = { x: 0, y: 0, k: 1 };
    startEasing();
  }, [startEasing]);

  useEffect(() => () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); }, []);

  /**
   * React attaches `onWheel` passively, so `preventDefault()` inside it logs
   * "Unable to preventDefault inside passive event listener" and the page keeps
   * scrolling while the user zooms. Binding natively with `passive: false`
   * makes the zoom authoritative.
   */
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const handler = (e: WheelEvent) => onWheel(e as unknown as ReactWheelEvent);
    el.addEventListener("wheel", handler, { passive: false });
    return () => el.removeEventListener("wheel", handler);
  }, [onWheel]);

  const onPointerDown = (e: ReactPointerEvent) => {
    dragRef.current = { sx: e.clientX, sy: e.clientY, cx: cam.x, cy: cam.y, active: true, moved: false };
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e: ReactPointerEvent) => {
    const d = dragRef.current;
    if (!d?.active) return;
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const dx = ((e.clientX - d.sx) / rect.width) * W;
    const dy = ((e.clientY - d.sy) / rect.height) * H;
    if (Math.abs(dx) + Math.abs(dy) > 2) d.moved = true;
    setCam((c) => ({ ...c, x: d.cx - dx, y: d.cy - dy }));
  };
  const onPointerUp = () => {
    if (dragRef.current && !dragRef.current.moved) onBackground?.();
    dragRef.current = null;
  };

  const MM_W = 168;
  const MM_H = (MM_W * H) / W;
  const viewW = W / cam.k;
  const viewH = H / cam.k;
  const mmX = (cam.x / W) * MM_W;
  const mmY = (cam.y / H) * MM_H;
  const mmW = (viewW / W) * MM_W;
  const mmH = (viewH / H) * MM_H;

  return (
    <div style={{ position: "relative", width: "100%", height: "100%", overflow: "hidden", borderRadius: 10 }}>
      <svg
        ref={svgRef}
        width="100%"
        height="100%"
        viewBox={`${bounds.minX + cam.x} ${bounds.minY + cam.y} ${viewW} ${viewH}`}
        style={{ display: "block", background: "transparent", touchAction: "none" }}
          onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        role="application"
        aria-label="Plant schematic — drag to pan, scroll to zoom"
      >
        {plant.areas.map((a) => (
          <g key={a.id}>
            <rect x={a.x} y={a.y} width={a.w} height={a.h} rx={10} fill="rgba(69,213,255,0.025)" stroke="rgba(140,180,220,0.18)" strokeWidth={1} strokeDasharray="7 5" />
            <text x={a.x + 12} y={a.y + 18} fontSize="10" fontFamily="ui-monospace, monospace" letterSpacing="2.5" fill="rgba(91,108,129,0.9)" stroke="none">
              {a.name.toUpperCase()}
            </text>
          </g>
        ))}

        {plant.connections.map((c) => {
          const src = plant.equipment.find((e) => e.id === c.source);
          const dst = plant.equipment.find((e) => e.id === c.target);
          if (!src || !dst) return null;
          const st = EDGE_STYLE[c.kind] ?? EDGE_STYLE.pipe;
          const rt = runtime.pipes[c.id];
          const leaking = rt?.leaking ?? c.leaking;
          const enabled = rt?.enabled ?? c.enabled;
          return (
            <g key={c.id}>
              <line
                x1={src.x}
                y1={src.y}
                x2={dst.x}
                y2={dst.y}
                stroke={!enabled ? "rgba(91,108,129,0.25)" : leaking ? "rgba(255,93,93,0.7)" : st.color}
                strokeWidth={st.width}
                strokeDasharray={st.dash}
                strokeLinecap="round"
              >
                {c.kind === "pipe" && enabled && !leaking && (
                  <animate attributeName="stroke-dashoffset" from="0" to="-28" dur="1.4s" repeatCount="indefinite" />
                )}
              </line>
              {leaking && (
                <circle cx={(src.x + dst.x) / 2} cy={(src.y + dst.y) / 2} r="4" fill="#ff5d5d" stroke="none">
                  <animate attributeName="r" values="3;7;3" dur="1.1s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.9;0.2;0.9" dur="1.1s" repeatCount="indefinite" />
                </circle>
              )}
            </g>
          );
        })}

        {plant.equipment.map((eq) => (
          <EquipmentNodeMemo
            key={eq.id}
            eq={eq}
            state={runtime.states[eq.id] ?? "normal"}
            qualities={runtime.qualities}
            selected={selectedId === eq.id}
            affected={affected.includes(eq.id)}
            onSelect={onSelect}
            onHover={onHover}
          />
        ))}
      </svg>

      {/* Zoom controls. The wheel is the fast path; these are the predictable
          one, with fixed increments and an explicit fit/reset. */}
      <div className="sc-zoom" role="group" aria-label="Zoom and pan controls">
        <button type="button" onClick={() => zoomBy(1.25)} aria-label="Zoom in" title="Zoom in">+</button>
        <button type="button" onClick={() => zoomBy(1 / 1.25)} aria-label="Zoom out" title="Zoom out">−</button>
        <button type="button" onClick={fitView} aria-label="Fit plant to view" title="Fit to screen">⤢</button>
        <button type="button" onClick={resetView} aria-label="Reset view" title="Reset view">↺</button>
        <span className="sc-zoom__level" aria-live="polite">{Math.round(cam.k * 100)}%</span>
      </div>

      <div
        style={{
          position: "absolute",
          right: 14,
          bottom: 14,
          width: MM_W,
          height: MM_H,
          border: "1px solid var(--line-2, rgba(140,180,220,.16))",
          borderRadius: 8,
          background: "rgba(6,10,16,0.85)",
          backdropFilter: "blur(8px)",
          overflow: "hidden",
          cursor: "pointer",
        }}
        onClick={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const fx = (e.clientX - r.left) / MM_W;
          const fy = (e.clientY - r.top) / MM_H;
          setCam((c) => ({ ...c, x: fx * W - viewW / 2, y: fy * H - viewH / 2 }));
        }}
        aria-label="Minimap"
        role="img"
      >
        <svg width={MM_W} height={MM_H}>
          {plant.areas.map((a) => (
            <rect key={a.id} x={((a.x - bounds.minX) / W) * MM_W} y={((a.y - bounds.minY) / H) * MM_H} width={(a.w / W) * MM_W} height={(a.h / H) * MM_H} fill="rgba(69,213,255,0.06)" rx={2} />
          ))}
          {plant.equipment.map((e) => {
            const st = runtime.states[e.id] ?? "normal";
            return (
              <circle
                key={e.id}
                cx={((e.x - bounds.minX) / W) * MM_W}
                cy={((e.y - bounds.minY) / H) * MM_H}
                r={1.7}
                fill={st === "critical" || st === "failed" ? "#ff5d5d" : st === "warning" ? "#ffb454" : "#45d5ff"}
                opacity={st === "normal" ? 0.5 : 1}
              />
            );
          })}
          <rect x={mmX} y={mmY} width={mmW} height={mmH} fill="none" stroke="#45d5ff" strokeWidth={1} opacity={0.8} rx={2} />
        </svg>
      </div>
    </div>
  );
}

/* ==========================================================================
   Spatial layout — the sweeping left-to-right process map.
   Stages are the plant's own areas (topology data, in dataset order); units
   keep their real sensors and readings. Nothing is invented here.
   ========================================================================== */

type PillTone = "normal" | "warning" | "critical";

const STAGE_W = 236;
const STAGE_GAP = 104;
const UNIT_W = 176;
const UNIT_H = 170;
const UNIT_GAP = 18;
const HEAD_H = 62;
const PAD_X = 52;
const PAD_Y = 26;

const MEASURE_CODE: Record<string, string> = {
  pressure: "PRES",
  temperature: "TEMP",
  flow: "FLOW",
  level: "LVL",
  vibration: "VIB",
  rpm: "RPM",
  current: "CURR",
  power: "PWR",
  gas: "GAS",
  leak: "LEAK",
  position: "POS",
  speed: "SPD",
};

function measureCode(s: SensorDef): string {
  return MEASURE_CODE[s.measurement] ?? s.measurement.slice(0, 4).toUpperCase();
}

function fmtNum(v: number): string {
  const abs = Math.abs(v);
  if (!Number.isFinite(v)) return "—";
  if (abs >= 100) return v.toFixed(0);
  if (abs >= 10) return v.toFixed(1);
  return v.toFixed(2);
}

function readingTone(s: SensorDef, r: SpatialReading | undefined): PillTone {
  if (!r) return "normal";
  if (r.quality === "bad") return "critical";
  if (r.quality === "stale") return "warning";
  const v = r.value;
  // Detectors read ~0 in normal operation (the engine skips them in
  // evaluateAlarms for the same reason): only a rising concentration is a fault.
  if (s.is_detector) {
    if (v >= s.critical_max) return "critical";
    if (v >= s.warning_max) return "warning";
    return "normal";
  }
  if (v <= s.critical_min || v >= s.critical_max) return "critical";
  if (v <= s.warning_min || v >= s.warning_max) return "warning";
  return "normal";
}

function toneToken(s: SensorDef, r: SpatialReading | undefined, tone: PillTone): string | null {
  if (tone === "normal") return null;
  if (r?.quality === "bad") return "BAD";
  if (r?.quality === "stale") return "STALE";
  if (r && r.value >= (tone === "critical" ? s.critical_max : s.warning_max)) return tone === "critical" ? "CRIT HIGH" : "HIGH";
  if (r && r.value <= (tone === "critical" ? s.critical_min : s.warning_min)) return tone === "critical" ? "CRIT LOW" : "LOW";
  return tone === "critical" ? "CRITICAL" : "WARNING";
}

function stateTone(state: SimVisualState | undefined): PillTone {
  if (state === "critical" || state === "failed") return "critical";
  if (state === "warning") return "warning";
  return "normal";
}

interface PillDatum {
  key: string;
  label: string;
  value: string;
  unit: string;
  tone: PillTone;
  token: string | null;
}

function buildPills(eq: EquipmentDef, readings: Record<string, SpatialReading>, unitTone: PillTone): PillDatum[] {
  const infos: PillDatum[] = eq.sensors.map((s) => {
    const r = readings[s.id];
    const tone = readingTone(s, r);
    return {
      key: s.id,
      label: measureCode(s),
      value: r ? fmtNum(r.value) : "—",
      unit: s.unit,
      tone,
      token: toneToken(s, r, tone),
    };
  });
  const anomalies = infos.filter((p) => p.tone !== "normal");
  let shown = anomalies.length ? [anomalies[0], ...infos.filter((p) => p !== anomalies[0])].slice(0, 3) : infos.slice(0, 3);
  // A unit flagged warning/critical by the engine but with no band-crossing pill
  // still needs a visible state — carry it on the lead pill.
  if (!shown.some((p) => p.tone !== "normal") && unitTone !== "normal") {
    shown = shown.map((p, i) =>
      i === 0 ? { ...p, tone: unitTone, token: unitTone === "critical" ? "CRITICAL" : "WARNING" } : p,
    );
  }
  return shown;
}

interface StageModel {
  id: string;
  name: string;
  units: EquipmentDef[];
  x: number;
  unitsH: number;
}

function buildStages(plant: PlantDef): { stages: StageModel[]; bandW: number; bandH: number } {
  const byArea = new Map<string, EquipmentDef[]>();
  for (const a of plant.areas) byArea.set(a.id, []);
  const orphans: EquipmentDef[] = [];
  for (const e of plant.equipment) {
    const arr = byArea.get(e.area_id);
    if (arr) arr.push(e);
    else orphans.push(e);
  }
  const stages: StageModel[] = plant.areas
    .filter((a) => (byArea.get(a.id)?.length ?? 0) > 0)
    .map((a, i) => {
      const units = [...byArea.get(a.id)!].sort((p, q) => (p.y === q.y ? p.x - q.x : p.y - q.y));
      return {
        id: a.id,
        name: a.name,
        units,
        x: PAD_X + i * (STAGE_W + STAGE_GAP),
        unitsH: units.length * UNIT_H + Math.max(0, units.length - 1) * UNIT_GAP,
      };
    });
  if (orphans.length) {
    const i = stages.length;
    stages.push({
      id: "__unassigned",
      name: "Unassigned",
      units: orphans,
      x: PAD_X + i * (STAGE_W + STAGE_GAP),
      unitsH: orphans.length * UNIT_H + Math.max(0, orphans.length - 1) * UNIT_GAP,
    });
  }
  const maxStageH = stages.reduce((m, s) => Math.max(m, HEAD_H + s.unitsH), 240);
  const bandW = stages.length ? PAD_X * 2 + stages.length * STAGE_W + (stages.length - 1) * STAGE_GAP : 1200;
  return { stages, bandW, bandH: PAD_Y * 2 + maxStageH };
}

function unitCenter(stage: StageModel, index: number): { x: number; y: number } {
  return {
    x: stage.x + STAGE_W / 2,
    y: PAD_Y + HEAD_H + index * (UNIT_H + UNIT_GAP) + 34,
  };
}

function SpatialLayout({
  plant,
  runtime,
  selectedId,
  affected,
  onSelect,
  onHover,
  readings,
  anomalyId,
  panelOpen,
  children,
}: SchematicCanvasProps) {
  const { stages, bandW, bandH } = useMemo(() => buildStages(plant), [plant]);
  const live = readings ?? {};

  const rootRef = useRef<HTMLDivElement>(null);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const unitRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  const centers = useMemo(() => {
    const map = new Map<string, { x: number; y: number }>();
    for (const stage of stages) stage.units.forEach((u, i) => map.set(u.id, unitCenter(stage, i)));
    return map;
  }, [stages]);

  /* animated connection from the anomalous unit to the floating panel --------- */
  const [link, setLink] = useState<{ d: string; from: { x: number; y: number }; to: { x: number; y: number } } | null>(null);
  const rafRef = useRef(0);

  const measure = useCallback(() => {
    const root = rootRef.current;
    const el = anomalyId ? unitRefs.current[anomalyId] : null;
    if (!root || !el) {
      setLink(null);
      return;
    }
    const rr = root.getBoundingClientRect();
    const er = el.getBoundingClientRect();
    const from = {
      x: Math.max(6, Math.min(rr.width - 6, er.left - rr.left + er.width / 2)),
      y: Math.max(6, Math.min(rr.height - 6, er.top - rr.top + 34)),
    };
    const pr = panelRef.current?.getBoundingClientRect();
    const to = pr
      ? { x: pr.left - rr.left, y: pr.top - rr.top + 40 }
      : { x: rr.width - 388, y: 48 };
    const dx = Math.max(48, Math.abs(to.x - from.x) * 0.42);
    const d = `M ${from.x} ${from.y} C ${from.x + dx} ${from.y}, ${to.x - dx} ${to.y}, ${to.x} ${to.y}`;
    setLink({ d, from, to });
  }, [anomalyId]);

  const schedule = useCallback(() => {
    if (typeof window === "undefined") return;
    window.cancelAnimationFrame(rafRef.current);
    rafRef.current = window.requestAnimationFrame(measure);
  }, [measure]);

  useEffect(() => {
    if (!anomalyId || !panelOpen) {
      setLink(null);
      return;
    }
    schedule();
    const scroller = scrollerRef.current;
    const root = rootRef.current;
    scroller?.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(schedule) : null;
    if (ro && root) ro.observe(root);
    const settle = window.setTimeout(schedule, 480);
    const focus = window.setTimeout(() => {
      unitRefs.current[anomalyId]?.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
    }, 60);
    return () => {
      scroller?.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      ro?.disconnect();
      window.clearTimeout(settle);
      window.clearTimeout(focus);
      window.cancelAnimationFrame(rafRef.current);
    };
  }, [anomalyId, panelOpen, schedule]);

  return (
    <div className="pt-spatial-root" ref={rootRef} data-layout="spatial">
      <div className="pt-spatial" ref={scrollerRef} data-testid="spatial-scroller">
        <div
          className="pt-spatial__band"
          style={{ "--band-w": `${bandW}px`, "--band-h": `${bandH}px` } as CSSProperties}
        >
          {/* process flow lines — a spatial mesh, drawn behind the unit plates */}
          <svg className="pt-flow" viewBox={`0 0 ${bandW} ${bandH}`} width={bandW} height={bandH} aria-hidden="true">
            {plant.connections.map((c) => {
              const a = centers.get(c.source);
              const b = centers.get(c.target);
              if (!a || !b) return null;
              const rt = runtime.pipes[c.id];
              const leaking = rt?.leaking ?? c.leaking;
              const enabled = rt?.enabled ?? c.enabled;
              const dir = Math.sign(b.x - a.x) || 1;
              const x1 = a.x + dir * (UNIT_W / 2 + 6);
              const x2 = b.x - dir * (UNIT_W / 2 + 6);
              const dx = Math.max(48, Math.abs(x2 - x1) * 0.42);
              const d = `M ${x1} ${a.y} C ${x1 + dir * dx} ${a.y}, ${x2 - dir * dx} ${b.y}, ${x2} ${b.y}`;
              const cls = `pt-flow__pipe${!enabled ? " is-off" : leaking ? " is-leak" : c.kind === "pipe" ? " is-live" : ""}`;
              return (
                <g key={c.id}>
                  <path className={cls} d={d} />
                  {leaking && (
                    <circle className="pt-flow__dot" cx={(x1 + x2) / 2} cy={(a.y + b.y) / 2} r={3.4}>
                      <animate attributeName="r" values="2.4;5;2.4" dur="1.2s" repeatCount="indefinite" />
                      <animate attributeName="opacity" values="0.85;0.2;0.85" dur="1.2s" repeatCount="indefinite" />
                    </circle>
                  )}
                </g>
              );
            })}
          </svg>

          {stages.map((stage, si) => (
            <section
              key={stage.id}
              className="pt-stage"
              data-stage={stage.id}
              style={{ "--sx": `${stage.x}px`, "--sy": `${PAD_Y}px`, "--sw": `${STAGE_W}px` } as CSSProperties}
            >
              <header className="pt-stage__head">
                <span className="pt-stage__index">{String(si + 1).padStart(2, "0")}</span>
                <span className="pt-stage__name" title={stage.name}>{stage.name}</span>
                <span className="pt-stage__count">{stage.units.length}</span>
              </header>
              <div className="pt-stage__rule" />
              <div
                className="pt-stage__units"
                style={{ "--units-h": `${stage.unitsH}px` } as CSSProperties}
              >
                {stage.units.map((eq, ui) => {
                  const state = (runtime.states[eq.id] ?? eq.state ?? "normal") as SimVisualState;
                  const unitTone = stateTone(state);
                  const pills = buildPills(eq, live, unitTone);
                  const isAnomaly = anomalyId === eq.id;
                  const anomalyTone = pills.find((p) => p.tone !== "normal")?.tone ?? "normal";
                  const flagTone: PillTone = unitTone !== "normal" ? unitTone : anomalyTone;
                  const flagged = flagTone !== "normal";
                  return (
                    <button
                      key={eq.id}
                      type="button"
                      ref={(el) => {
                        unitRefs.current[eq.id] = el;
                      }}
                      className={`pt-unit${selectedId === eq.id ? " is-selected" : ""}${isAnomaly ? " is-anomaly" : ""}`}
                      data-unit={eq.id}
                      data-state={state}
                      data-anomaly={isAnomaly ? "true" : undefined}
                      data-affected={affected.includes(eq.id) ? "true" : undefined}
                      style={
                        {
                          "--ux": `${(STAGE_W - UNIT_W) / 2}px`,
                          "--uy": `${ui * (UNIT_H + UNIT_GAP)}px`,
                          "--uw": `${UNIT_W}px`,
                          "--uh": `${UNIT_H}px`,
                        } as CSSProperties
                      }
                      onClick={() => onSelect(eq)}
                      onPointerEnter={() => onHover(eq)}
                      onPointerLeave={() => onHover(null)}
                      aria-label={`${eq.tag} — ${eq.name}${flagged ? ` · ${flagTone}` : ""}`}
                    >
                      {flagged && <span className="pt-unit__flag" data-tone={flagTone}>{flagTone === "critical" ? "CRIT" : "WARN"}</span>}
                      <span className="pt-unit__glyph">
                        <SimSymbol type={symbolForEquipment(eq.kind, eq.name)} state={state} size={40} label={`${eq.tag} — ${eq.name}`} />
                      </span>
                      <span className="pt-unit__tag">{eq.tag}</span>
                      <span className="pt-unit__name" title={eq.name}>{eq.name}</span>
                      <span className="pt-unit__pills">
                        {pills.map((p) => (
                          <span
                            key={p.key}
                            className={`pt-pill is-${p.tone}`}
                            data-pill=""
                            data-pill-state={p.tone}
                            data-pill-sensor={p.key}
                            title={`${p.label} ${p.value} ${p.unit}${p.token ? ` · ${p.token}` : ""}`}
                            aria-label={`${p.label} ${p.value} ${p.unit}${p.token ? ` ${p.token}` : ""}`}
                          >
                            <span className="pt-pill__label">{p.label}</span>
                            <span className="pt-pill__val">{p.value}</span>
                            <span className="pt-pill__unit">{p.unit}</span>
                            {p.token && <b className="pt-pill__state">{p.token}</b>}
                          </span>
                        ))}
                      </span>
                    </button>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      </div>

      {/* animated agent link + floating investigation panel (never permanently visible) */}
      {anomalyId && panelOpen && link && (
        <svg className="pt-link" width="100%" height="100%" aria-hidden="true">
          <path className="pt-link__halo" d={link.d} />
          <path className="pt-link__path" d={link.d} />
          <circle className="pt-link__origin" cx={link.from.x} cy={link.from.y} r={7} />
          <circle className="pt-link__marker" r={3.6}>
            <animateMotion dur="1.6s" repeatCount="indefinite" path={link.d} />
          </circle>
          <circle className="pt-link__origin" cx={link.to.x} cy={link.to.y} r={4.5} />
        </svg>
      )}

      <div
        ref={panelRef}
        className={`pt-investigator${panelOpen ? " is-open" : ""}`}
        data-testid="agent-investigation-panel"
        data-open={panelOpen ? "true" : "false"}
        aria-hidden={panelOpen ? undefined : true}
      >
        {children}
      </div>
    </div>
  );
}

/* ==========================================================================
   Public component — branches on the opt-in layout prop. Default behaviour is
   byte-for-byte the classic schematic so the hub and builder are unaffected.
   ========================================================================== */

export function SchematicCanvas(props: SchematicCanvasProps) {
  if (props.layout === "spatial") return <SpatialLayout {...props} />;
  return <SchematicView {...props} />;
}

export function emptyRuntime(plant: PlantDef): CanvasRuntime {
  const states: Record<string, SimVisualState> = {};
  const qualities: Record<string, "good"> = {};
  const pipes: Record<string, { leaking: boolean; enabled: boolean; flow: number }> = {};
  for (const e of plant.equipment) {
    states[e.id] = "normal";
    for (const s of e.sensors) qualities[s.id] = "good";
  }
  for (const c of plant.connections) pipes[c.id] = { leaking: c.leaking, enabled: c.enabled, flow: c.flow };
  return { states, qualities, pipes };
}

/** Derive canvas runtime from engine state (called at the store cadence). */
export function runtimeFromEngine(
  plant: PlantDef,
  eng: {
    snapshot: () => {
      equipment: Record<string, { state: string; capacity: number }>;
      sensors: Record<string, { value: number; quality: string; failed: boolean }>;
    };
    plant: PlantDef;
  },
): CanvasRuntime {
  const snap = eng.snapshot();
  const base = emptyRuntime(plant);
  for (const [id, st] of Object.entries(snap.equipment)) {
    base.states[id] = st.state as SimVisualState;
  }
  for (const [id, s] of Object.entries(snap.sensors)) {
    base.qualities[id] = s.quality as CanvasRuntime["qualities"][string];
  }
  for (const c of plant.connections) {
    base.pipes[c.id] = { leaking: c.leaking, enabled: c.enabled, flow: c.flow };
  }
  return base;
}
