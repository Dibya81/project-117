"use client";

/**
 * SensorTrend — the per-sensor trend strip on an equipment card.
 *
 * ---------------------------------------------------------------- data honesty
 *
 * The brief asked for a real-time mini sparkline of the vibration and pressure
 * trends. Before wiring anything I read every candidate source in the app, and
 * a per-asset time series does not exist anywhere:
 *
 *   * `consoleData.equipment.list()` — `toEquipment()` in lib/data/console.ts
 *     maps each `keySignals` entry onto `SensorReading`, which carries exactly
 *     one scalar `value` (plus an optional `limit`). There is no points array,
 *     no ring buffer and no history field on the type.
 *   * `consoleData.equipment.detail()` builds `telemetry: []` and says so in a
 *     comment: "the dataset genuinely carries no persisted time series".
 *   * The only trend endpoint, `GET /api/analytics/trends`, reads
 *     `operations.analytics()["trends"]`, which `OperationsStore.analytics`
 *     returns as `{}` — every series is empty. Its one vibration series,
 *     `vibrationC3`, is plant-wide and is not keyed by asset.
 *   * `lib/sim/store.ts` keeps the ring buffer of *events*, plus incidents and
 *     tasks. It never samples `SimSnapshot.sensors`, so no sensor history is
 *     accumulated client side either.
 *
 * So `points` is empty today. A hand-drawn curve here would look exactly like a
 * real measurement and an operator could not tell them apart — that is the
 * fabrication this console exists to avoid. Instead the strip shows the
 * sensor's REAL current measured value (and its real warn limit) beside an
 * explicit, unmistakable "no trend history" placeholder: a dashed hatched box,
 * not a flat line that could be mistaken for a trend.
 *
 * The wiring is not thrown away: hand this component a real series and it
 * renders the existing `TrendChart` unchanged. The day the backend persists
 * history there is exactly one call site to point at it.
 */

import { TrendChart } from "@/components/ui/TrendChart";

export interface TrendPoint {
  t: number;
  value: number;
}

export interface TrendSensor {
  key: string;
  label: string;
  unit: string;
  value: number;
  warnAbove?: number;
  critAbove?: number;
}

type Tone = "cyan" | "amber" | "green" | "red";

function toneOf(s: TrendSensor): Tone {
  if (s.critAbove != null && s.value >= s.critAbove) return "red";
  if (s.warnAbove != null && s.value >= s.warnAbove) return "amber";
  return "cyan";
}

function stateOf(s: TrendSensor): "ok" | "warn" | "crit" {
  const t = toneOf(s);
  return t === "red" ? "crit" : t === "amber" ? "warn" : "ok";
}

export function SensorTrend({ sensor, points }: { sensor: TrendSensor; points: TrendPoint[] }) {
  const state = stateOf(sensor);

  // A line needs at least two samples to be a line. One point is not a trend.
  if (points.length >= 2) {
    return (
      <div className="cs-eqtrend" data-sensor-trend={sensor.key} data-trend-source="history">
        <TrendChart
          points={points}
          height={44}
          unit={sensor.unit}
          tone={toneOf(sensor)}
          {...(sensor.warnAbove != null ? { threshold: sensor.warnAbove } : {})}
          {...(sensor.critAbove != null ? { critThreshold: sensor.critAbove } : {})}
          live
        />
      </div>
    );
  }

  return (
    <div
      className={`cs-eqtrend cs-eqtrend--${state}`}
      data-sensor-trend={sensor.key}
      data-trend-source="no-history"
      aria-label={`${sensor.label}: ${sensor.value} ${sensor.unit}. No trend history is stored for this instrument.`}
    >
      <div className="cs-eqtrend__head">
        <span className="cs-eqtrend__label">{sensor.label}</span>
        <span className="cs-eqtrend__value cs-mono">
          {sensor.value} {sensor.unit}
        </span>
      </div>
      <div className="cs-eqtrend__nodata" aria-hidden="true">
        <span>no trend history</span>
      </div>
      {sensor.warnAbove != null && (
        <div className="cs-eqtrend__limit cs-mono">
          warn ≥ {sensor.warnAbove} {sensor.unit}
        </div>
      )}
    </div>
  );
}
