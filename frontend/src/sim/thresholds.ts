/**
 * Sensor thresholds.
 *
 * The dataset gives a normal band (`normal_min` / `normal_max`) but no separate
 * warning and alarm bands, so the two levels are derived from the band width
 * rather than invented as absolute numbers. A reading up to 10% of the band
 * width outside normal is a warning; beyond that it is critical. Band width is
 * used so a 0–1 bar transmitter and a 0–250 °C transmitter escalate on
 * comparable terms.
 */
import type { Sensor, SensorType } from "../types";

export type ReadingLevel = "normal" | "warning" | "critical";

const WARN_FRACTION = 0.1;

export function readingLevel(value: number, normalMin: number, normalMax: number): ReadingLevel {
  const width = Math.abs(normalMax - normalMin) || 1;
  if (value >= normalMin && value <= normalMax) return "normal";
  const deviation = value < normalMin ? normalMin - value : value - normalMax;
  return deviation <= width * WARN_FRACTION ? "warning" : "critical";
}

export function sensorLevel(sensor: Sensor): ReadingLevel {
  return readingLevel(sensor.current_value, sensor.normal_min, sensor.normal_max);
}

export function formatValue(sensor: Sensor): string {
  const v = sensor.current_value;
  const digits = Math.abs(v) >= 100 ? 0 : Math.abs(v) >= 10 ? 1 : 2;
  return `${v.toFixed(digits)}${sensor.unit ? ` ${sensor.unit}` : ""}`;
}

export function formatBand(sensor: Sensor): string {
  return `${sensor.normal_min}–${sensor.normal_max}${sensor.unit ? ` ${sensor.unit}` : ""}`;
}

/** Full measurement name for the sensor type, for labels and tooltips. */
export const SENSOR_LABEL: Record<SensorType, string> = {
  PT: "Pressure",
  TT: "Temperature",
  FT: "Flow",
  LT: "Level",
  VT: "Vibration",
};

export const SENSOR_COLOR: Record<SensorType, string> = {
  PT: "#4aa3ff",
  TT: "#ff8a4a",
  FT: "#39d5b0",
  LT: "#b79cff",
  VT: "#ffd166",
};

export const LEVEL_COLOR: Record<ReadingLevel, string> = {
  normal: "#3ddc97",
  warning: "#ffb454",
  critical: "#ff5d5d",
};

/**
 * Age against expected life. The register carries both, so wear is a fact from
 * the data rather than a guess.
 */
export function lifeUsed(ageYears: number, expectedYears: number): number {
  if (expectedYears <= 0) return 0;
  return Math.max(0, Math.min(1, ageYears / expectedYears));
}
