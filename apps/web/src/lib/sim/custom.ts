"use client";

/**
 * Build-your-own support — user-authored plants run on the SAME engine with
 * the SAME failure modes as the prebuilt plants. This module only builds the
 * dataset the user drew; it contains no behavior of its own.
 */
import { kindForRelation } from "./relations";
import type { EquipmentDef, EquipmentKind, FailureModeDef, PlantDef, RelationType, SensorDef } from "./types";

/** Mirrors scripts/generate_simulation_data.py FAILURE_MODES (keep in sync). */
export const FAILURE_MODES: FailureModeDef[] = [
  { id: "sensor_failure", name: "Sensor failure", applies_to: ["pressure"], mechanism: "sensor", magnitude: 1, description: "Primary measurement element fails; quality goes BAD." },
  { id: "instrument_drift", name: "Instrument drift", applies_to: ["temperature", "pressure", "flow"], mechanism: "drift", magnitude: 1, description: "Transmitter reading drifts away from true value." },
  { id: "bearing_wear", name: "Bearing wear", applies_to: ["pump", "compressor", "motor"], mechanism: "degrade", magnitude: 0.25, description: "Vibration signature rises; capacity degrades." },
  { id: "cavitation", name: "Pump cavitation", applies_to: ["pump"], mechanism: "degrade", magnitude: 0.4, description: "Suction lost; flow and pressure become unstable." },
  { id: "bearing_overheat", name: "Bearing overheating", applies_to: ["pump", "motor", "compressor"], mechanism: "drift", magnitude: 1, description: "Bearing temperature climbs toward trip." },
  { id: "valve_stuck", name: "Valve failure (stuck)", applies_to: ["valve"], mechanism: "degrade", magnitude: 0.6, description: "Valve stops responding; flow restricted." },
  { id: "seal_leak", name: "Seal failure / oil leak", applies_to: ["pump", "vessel"], mechanism: "leak", magnitude: 0.45, description: "Medium escapes; detectors trip." },
  { id: "pressure_surge", name: "Pressure surge", applies_to: ["vessel", "column", "exchanger"], mechanism: "surge", magnitude: 0.35, description: "Excursion drives pressures over envelope." },
  { id: "trip", name: "Equipment trip", applies_to: ["compressor", "pump", "motor"], mechanism: "stop", magnitude: 1, description: "Machine trips offline; dependent flow collapses." },
  { id: "fouling", name: "Heat exchanger fouling", applies_to: ["exchanger"], mechanism: "degrade", magnitude: 0.3, description: "Duty and outlet temperature sag." },
  { id: "overload", name: "Motor overload", applies_to: ["motor", "conveyor"], mechanism: "degrade", magnitude: 0.5, description: "Current draw exceeds rated." },
  { id: "esd", name: "Emergency shutdown", applies_to: ["safety"], mechanism: "stop", magnitude: 1, description: "Controlled area shutdown." },
];

export const FM_BY_KIND: Record<EquipmentKind, string[]> = {
  pump: ["sensor_failure", "instrument_drift", "bearing_wear", "cavitation", "bearing_overheat", "seal_leak", "trip"],
  valve: ["valve_stuck", "instrument_drift"],
  tank: ["instrument_drift"],
  vessel: ["pressure_surge", "seal_leak", "instrument_drift"],
  column: ["pressure_surge", "instrument_drift"],
  exchanger: ["fouling", "pressure_surge", "instrument_drift"],
  furnace: ["pressure_surge", "instrument_drift"],
  compressor: ["bearing_wear", "bearing_overheat", "trip", "sensor_failure"],
  motor: ["overload", "bearing_overheat", "trip"],
  conveyor: ["overload", "trip"],
  safety: ["esd"],
  utility: ["instrument_drift"],
};

const UNITS: Record<string, string> = {
  pressure: "bar", temperature: "°C", flow: "m³/h", level: "%", vibration: "mm/s",
  rpm: "rpm", current: "A", power: "kW", gas: "ppm", leak: "0/1", position: "%", speed: "m/s",
};

function mkSensor(tag: string, eqId: string, measurement: SensorDef["measurement"], nominal: number, detector = false): SensorDef {
  const r = (n: number, f: number) => Math.round(n * f * 100) / 100;
  return {
    id: `s-${tag}`, tag, equipment_id: eqId, measurement, unit: UNITS[measurement],
    nominal,
    normal_min: r(nominal, 0.96), normal_max: r(nominal, 1.04),
    warning_min: r(nominal, 0.9), warning_max: r(nominal, 1.08),
    critical_min: r(nominal, 0.82), critical_max: r(nominal, 1.16),
    sampling_ms: 1000, noise: 0.01, drift_rate: 0.02, is_detector: detector,
  };
}

/** Defaults for a point an engineer adds by hand, per measurement. */
const NOMINAL: Record<string, number> = {
  pressure: 9.5, temperature: 180, flow: 100, level: 60, vibration: 5.7,
  rpm: 3000, current: 90, power: 460, gas: 0, leak: 0, position: 60, speed: 2.2,
};

/** Measurements the Builder can attach to a unit. */
export const SENSOR_MEASUREMENTS: SensorDef["measurement"][] = [
  "pressure", "temperature", "flow", "level", "vibration", "rpm",
  "current", "power", "gas", "leak", "position", "speed",
];

/**
 * One instrument, built exactly the way the per-kind defaults are built, so a
 * point added by hand carries the same bands, units and detector flag as one
 * that shipped with the asset.
 */
export function makeSensorOf(
  equipmentId: string,
  tag: string,
  measurement: SensorDef["measurement"],
): SensorDef {
  return mkSensor(
    tag,
    equipmentId,
    measurement,
    NOMINAL[measurement] ?? 50,
    measurement === "gas" || measurement === "leak",
  );
}

/** Default instrumentation per kind — mirrors the dataset generator. */
export function defaultSensors(kind: EquipmentKind, eqId: string, tag: string): SensorDef[] {
  if (kind === "pump")
    return [
      mkSensor(`PT-${tag}A`, eqId, "pressure", 18.5),
      mkSensor(`PT-${tag}B`, eqId, "pressure", 18.5),
      mkSensor(`FT-${tag}`, eqId, "flow", 96),
      mkSensor(`TT-${tag}`, eqId, "temperature", 73),
      mkSensor(`VIB-${tag}`, eqId, "vibration", 5.7),
    ];
  if (kind === "valve") return [mkSensor(`ZT-${tag}`, eqId, "position", 62)];
  if (kind === "tank") return [mkSensor(`LT-${tag}`, eqId, "level", 62), mkSensor(`TT-${tag}`, eqId, "temperature", 41)];
  if (kind === "vessel" || kind === "column")
    return [mkSensor(`PT-${tag}`, eqId, "pressure", 9.5), mkSensor(`TT-${tag}`, eqId, "temperature", 188), mkSensor(`LT-${tag}`, eqId, "level", 55)];
  if (kind === "exchanger") return [mkSensor(`TT-${tag}I`, eqId, "temperature", 210), mkSensor(`TT-${tag}O`, eqId, "temperature", 188), mkSensor(`FT-${tag}`, eqId, "flow", 88)];
  if (kind === "furnace") return [mkSensor(`TT-${tag}`, eqId, "temperature", 620), mkSensor(`PT-${tag}`, eqId, "pressure", 3.4), mkSensor(`GD-${tag}`, eqId, "gas", 0, true)];
  if (kind === "compressor")
    return [mkSensor(`PT-${tag}S`, eqId, "pressure", 6.8), mkSensor(`PT-${tag}D`, eqId, "pressure", 19.5), mkSensor(`VIB-${tag}`, eqId, "vibration", 5.7), mkSensor(`RPM-${tag}`, eqId, "rpm", 8840)];
  if (kind === "motor") return [mkSensor(`A-${tag}`, eqId, "current", 96), mkSensor(`KW-${tag}`, eqId, "power", 460), mkSensor(`RPM-${tag}`, eqId, "rpm", 1480)];
  if (kind === "conveyor") return [mkSensor(`ST-${tag}`, eqId, "speed", 2.2), mkSensor(`A-${tag}`, eqId, "current", 64)];
  if (kind === "safety") return [mkSensor(`GD-${tag}`, eqId, "gas", 0, true), mkSensor(`LK-${tag}`, eqId, "leak", 0, true)];
  return [mkSensor(`FT-${tag}`, eqId, "flow", 120)];
}

const KIND_PREFIX: Record<EquipmentKind, string> = {
  pump: "P", valve: "V", tank: "TK", vessel: "VS", column: "COL", exchanger: "E",
  furnace: "F", compressor: "C", motor: "M", conveyor: "CV", safety: "ESD", utility: "UT",
};

export function makeEquipment(kind: EquipmentKind, name: string, x: number, y: number, seq: number): EquipmentDef {
  const num = String(9000 + seq);
  const tag = `${KIND_PREFIX[kind]}-${num}`;
  const id = `e-${tag}`;
  return {
    id, tag, name, kind, area_id: "custom", x, y,
    criticality: 2, capacity: 1, state: "normal",
    sensors: defaultSensors(kind, id, num),
    failure_modes: FM_BY_KIND[kind],
    manufacturer: "User Built", model: "CUSTOM-1",
    installed: "2026-09-11", last_inspection: "2026-09-11",
  };
}

export function assemblePlant(equipment: EquipmentDef[], connections: PlantDef["connections"]): PlantDef {
  return {
    id: "custom",
    name: "Custom Plant",
    industry: "custom",
    areas: [{ id: "custom", name: "User Plant", x: 0, y: 0, w: 2000, h: 1200 }],
    equipment,
    connections,
    failure_modes: FAILURE_MODES,
  };
}

/**
 * Build a connection. The relation is chosen by the engineer in the connect
 * dialog; the physical `kind` is derived from it so the two axes can never
 * disagree. Defaults to MATERIAL_FLOW / pipe for callers that predate this.
 */
export function makeConnection(
  source: string,
  target: string,
  seq: number,
  relation: RelationType = "MATERIAL_FLOW",
): PlantDef["connections"][number] {
  return {
    id: `pl-c${seq}`,
    kind: kindForRelation(relation),
    relation,
    source,
    target,
    // The wire is made port-to-port, so the record keeps the ports it was made
    // on. Written from the same constants the canvas draws, never re-derived.
    source_port: "out",
    target_port: "in",
    medium: relation === "MATERIAL_FLOW" ? "process" : relation.toLowerCase(),
    capacity: 100,
    flow: 0,
    status: "normal",
    leaking: false,
    enabled: true,
  };
}
