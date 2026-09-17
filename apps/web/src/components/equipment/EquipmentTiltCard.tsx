"use client";

/**
 * EquipmentTiltCard — one asset card with pointer-tracked 3D tilt physics.
 *
 * Tilt
 * ----
 * The card reads the pointer through framer-motion motion values (`px`/`py`,
 * normalised to 0..1 across the card face), maps them onto `rotateX`/`rotateY`
 * with `useTransform` inside the card's own `transformPerspective`, and smooths
 * both axes with `useSpring` so the surface has weight. On pointer leave the
 * two source values return to 0.5 — the rest position — and the springs settle
 * the card back instead of snapping it. A `useMotionTemplate` glare follows the
 * same pointer so the highlight reads as light on glass.
 *
 * WHY this is not `<Tilt>` from components/fx/Tilt.tsx: that component does the
 * same visual job imperatively — it writes `el.style.transform` from a rAF.
 * Inline transforms cannot be composed with framer-motion's own transform
 * pipeline, so a `whileHover` lift or a layout animation would clobber the
 * tilt. This card owns the motion-value chain the brief asks for and keeps
 * Tilt's glare idiom. `prefers-reduced-motion` disables the pointer tracking
 * entirely, leaving a static card.
 *
 * Data
 * ----
 * Every number rendered here comes from `Equipment` as the adapter produced it:
 * status, sensors/values/units/limits, insight, last_inspection. Nothing is
 * synthesised. The trend strips below are the one place the card would like
 * more data than exists — see SensorTrend for why they render a real current
 * value and an explicit "no trend history" affordance rather than a curve.
 */
import { useRef, type PointerEvent as ReactPointerEvent } from "react";
import {
  motion,
  useMotionTemplate,
  useMotionValue,
  useReducedMotion,
  useSpring,
  useTransform,
} from "framer-motion";
import { Ring, StatusDot, Tag } from "@/components/ui/primitives";
import { Icon } from "@/components/ui/Icon";
import { EquipmentRenderer, normalizeEquipmentAsset, preferredAssetSize } from "./EquipmentRenderer";
import { SensorTrend, type TrendPoint } from "./SensorTrend";
import { LIFT_HOVER, SPRING, SPRING_OPTIONS } from "@/lib/ui/motion";
import type { Equipment, HealthState, SensorReading } from "@/types";

/** Peak rotation at the card edges. Kept small so dense ops pages stay readable. */
const MAX_TILT = 7;

const STATUS_RANK: Record<HealthState, number> = { critical: 0, warning: 1, ok: 2, unknown: 3 };
export { STATUS_RANK };

/** Health score heuristic from sensor threshold proximity (existing logic). */
export function healthOf(e: Equipment): number {
  let worst = 100;
  for (const s of e.sensors) {
    if (s.critAbove && s.value >= s.critAbove) worst = Math.min(worst, 35);
    else if (s.warnAbove && s.value >= s.warnAbove) worst = Math.min(worst, 62);
    else if (s.warnAbove && s.value >= s.warnAbove * 0.92) worst = Math.min(worst, 80);
  }
  return worst;
}

export function ringTone(h: number): "ok" | "warn" | "crit" {
  return h >= 85 ? "ok" : h >= 65 ? "warn" : "crit";
}

/**
 * The signals the brief names, in display order. Matched on the label prefix,
 * because the adapter labels redundant instruments "pressure (2)".
 */
const TREND_SIGNALS = ["vibration", "pressure"] as const;

function trendSensors(e: Equipment): SensorReading[] {
  return TREND_SIGNALS.map((sig) =>
    e.sensors.find((s) => s.label.toLowerCase().startsWith(sig)),
  ).filter((s): s is SensorReading => Boolean(s));
}

/**
 * Trend history for one sensor.
 *
 * There is none — see SensorTrend for the full audit of every candidate source
 * in this app. Returned as a typed empty series rather than omitted so the
 * sparkline path stays wired: the moment the data layer carries points, this
 * function is the single place that changes.
 */
const NO_TREND_HISTORY: TrendPoint[] = [];

function EquipmentAssetPreview({ equipment }: { equipment: Equipment }) {
  const asset = normalizeEquipmentAsset(equipment.kind, equipment.name, equipment.id);
  const preferred = preferredAssetSize[asset];
  const scale = Math.min(154 / preferred.w, 118 / preferred.h);
  const box = {
    x: (170 - preferred.w * scale) / 2,
    y: (126 - preferred.h * scale) / 2 + 2,
    w: preferred.w * scale,
    h: preferred.h * scale,
  };
  return (
    <svg className="cs-eqasset" viewBox="0 0 170 136" role="img" aria-label={`${equipment.name} equipment asset`}>
      <EquipmentRenderer asset={asset} kind={equipment.kind} name={equipment.name} id={equipment.id} status={equipment.status} box={box} />
    </svg>
  );
}

export function EquipmentTiltCard({
  equipment,
  attentionRank,
  onOpen,
}: {
  equipment: Equipment;
  /** 1-based risk rank; only shown while the AI-attention sort is active. */
  attentionRank?: number;
  onOpen: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();

  // Pointer position across the card face, 0..1, rest at the centre.
  const px = useMotionValue(0.5);
  const py = useMotionValue(0.5);

  const rotateX = useSpring(useTransform(py, [0, 1], [MAX_TILT, -MAX_TILT]), SPRING_OPTIONS.surface);
  const rotateY = useSpring(useTransform(px, [0, 1], [-MAX_TILT, MAX_TILT]), SPRING_OPTIONS.surface);

  // Glare follows the same pointer, so the highlight and the tilt agree.
  const glareX = useTransform(px, [0, 1], ["0%", "100%"]);
  const glareY = useTransform(py, [0, 1], ["0%", "100%"]);
  const glare = useMotionTemplate`radial-gradient(420px circle at ${glareX} ${glareY}, rgba(8,145,178,0.16), transparent 62%)`;

  const onPointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (reduce) return;
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    px.set((e.clientX - r.left) / r.width);
    py.set((e.clientY - r.top) / r.height);
  };

  const onPointerLeave = () => {
    px.set(0.5);
    py.set(0.5);
  };

  const health = healthOf(equipment);
  const trends = trendSensors(equipment);

  return (
    <div className="cs-eqtilt" onPointerMove={onPointerMove} onPointerLeave={onPointerLeave}>
      <motion.div
        ref={ref}
        className={`cs-eqcard cs-eqcard--${equipment.status} cs-eqcard--motion`}
        data-equipment-card={equipment.id}
        data-equipment-status={equipment.status}
        style={{ rotateX, rotateY, transformPerspective: 1100 }}
        whileHover={LIFT_HOVER}
        transition={SPRING.micro}
        onClick={onOpen}
        role="button"
        tabIndex={0}
        onKeyDown={(ev) => ev.key === "Enter" && onOpen()}
        aria-label={`Open ${equipment.name}`}
      >
        <motion.span className="cs-eqcard__glare" style={{ background: glare }} aria-hidden="true" />

        <div className="cs-eqcard__asset">
          <EquipmentAssetPreview equipment={equipment} />
        </div>

        <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <StatusDot state={equipment.status} pulse={equipment.status === "critical"} />
              <span className="cs-mono cs-text-cyan" style={{ fontSize: 12, fontWeight: 700 }}>{equipment.id}</span>
              <Tag>{equipment.kind}</Tag>
              {attentionRank != null && (
                <Tag tone={health < 65 ? "crit" : health < 85 ? "warn" : "ok"}>attention #{attentionRank}</Tag>
              )}
            </div>
            <h3 style={{ margin: "8px 0 3px", fontSize: 15.5, letterSpacing: "-0.01em" }}>{equipment.name}</h3>
            <p className="cs-mono cs-dim" style={{ margin: 0, fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase" }}>
              {equipment.zone}
            </p>
          </div>
          <Ring value={health} tone={ringTone(health)} size={58} label={`health ${health}`} />
        </div>

        <div style={{ display: "flex", gap: 7, flexWrap: "wrap", margin: "14px 0 0" }}>
          {equipment.sensors.map((s) => {
            const hot = (s.critAbove != null && s.value >= s.critAbove) || (s.warnAbove != null && s.value >= s.warnAbove);
            return (
              <span key={s.key} className={`cs-tag${hot ? " cs-tag--warn" : ""}`}>
                {s.label} <b className="cs-mono">{s.value} {s.unit}</b>
              </span>
            );
          })}
        </div>

        {trends.length > 0 && (
          <div className="cs-eqtrends">
            {trends.map((s) => (
              <SensorTrend key={s.key} sensor={s} points={NO_TREND_HISTORY} />
            ))}
          </div>
        )}

        {equipment.insight && (
          <p
            style={{
              margin: "13px 0 0",
              padding: "9px 12px",
              fontSize: 12,
              lineHeight: 1.55,
              color: "var(--ink-2)",
              borderLeft: "1px solid rgba(8,145,178,0.5)",
              background: "rgba(8,145,178,0.05)",
              borderRadius: "0 6px 6px 0",
            }}
          >
            <Icon name="zap" size={11} /> {equipment.insight}
          </p>
        )}

        <div className="cs-eqcard__foot cs-mono cs-dim">
          <span>inspected {equipment.last_inspection ?? "—"}</span>
          <span className="cs-text-cyan">OPEN →</span>
        </div>
      </motion.div>
    </div>
  );
}
