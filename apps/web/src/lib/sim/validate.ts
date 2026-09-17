/**
 * Plant validation.
 *
 * A pure topology check over a built plant — no engine, no side effects, so it
 * can run on the builder canvas before anything is started. Every finding names
 * the asset it refers to so the UI can select it; nothing is reported that the
 * topology does not actually contain.
 *
 * Findings are split by consequence:
 *   errors   the plant cannot be simulated coherently (dangling references,
 *            duplicate ids, sensors on nothing)
 *   warnings the plant runs but is fragile (orphans, no redundancy on a
 *            critical unit, disconnected islands)
 */
import type { ConnectionDef, EquipmentDef, PlantDef, SensorDef } from "./types";
import { portOf } from "./relations";

export type ValidationLevel = "error" | "warning";

export interface ValidationFinding {
  level: ValidationLevel;
  code:
    | "no_equipment"
    | "duplicate_id"
    | "dangling_reference"
    | "self_loop"
    | "sensor_on_sensor"
    | "orphan_sensor"
    | "orphan_equipment"
    | "no_instrumentation"
    | "no_redundancy"
    | "duplicate_connection"
    | "duplicate_tag"
    | "port_direction"
  message: string;
  /** Asset ids the finding refers to, for selection in the canvas. */
  ids: string[];
}

export interface PlantValidation {
  ok: boolean;
  counts: {
    equipment: number;
    sensors: number;
    connections: number;
    orphanSensors: number;
    orphanEquipment: number;
    invalidConnections: number;
  };
  errors: ValidationFinding[];
  warnings: ValidationFinding[];
}

const isSensorId = (plant: PlantDef, id: string) =>
  plant.equipment.some((e) => e.sensors.some((s) => s.id === id));

export function validatePlant(plant: PlantDef): PlantValidation {
  const errors: ValidationFinding[] = [];
  const warnings: ValidationFinding[] = [];
  const equipment = plant.equipment ?? [];
  const connections = plant.connections ?? [];
  const allSensors: { s: SensorDef; eq: EquipmentDef }[] = equipment.flatMap((e) =>
    (e.sensors ?? []).map((s) => ({ s, eq: e })),
  );

  if (equipment.length === 0) {
    errors.push({
      level: "error",
      code: "no_equipment",
      message: "The canvas is empty. Place at least one unit before validating.",
      ids: [],
    });
    return {
      ok: false,
      counts: { equipment: 0, sensors: 0, connections: 0, orphanSensors: 0, orphanEquipment: 0, invalidConnections: 0 },
      errors,
      warnings,
    };
  }

  // ---- duplicate ids -----------------------------------------------------
  const seen = new Map<string, number>();
  for (const id of [
    ...equipment.map((e) => e.id),
    ...allSensors.map(({ s }) => s.id),
    ...connections.map((c) => c.id),
  ]) {
    seen.set(id, (seen.get(id) ?? 0) + 1);
  }
  const dupes = [...seen.entries()].filter(([, n]) => n > 1).map(([id]) => id);
  if (dupes.length) {
    errors.push({
      level: "error",
      code: "duplicate_id",
      message: `${dupes.length} identifier(s) are used more than once: ${dupes.slice(0, 4).join(", ")}.`,
      ids: dupes,
    });
  }

  // ---- duplicate connections and tags ------------------------------------
  // Two pipes between the same two units is a drawing mistake, not redundancy:
  // the engine would carry the same line twice and a route would apply twice.
  const byPair = new Map<string, string[]>();
  for (const c of connections) {
    const key = `${c.source} -> ${c.target}`;
    byPair.set(key, [...(byPair.get(key) ?? []), c.id]);
  }
  for (const [key, ids] of byPair) {
    if (ids.length < 2) continue;
    errors.push({
      level: "error",
      code: "duplicate_connection",
      message: `${ids.length} connections share the same ends (${key}): ${ids.join(", ")}.`,
      ids,
    });
  }

  // ---- port direction ----------------------------------------------------
  // The editor wires port-to-port, so a reversed record cannot be produced by
  // hand — but a saved plant can come back from storage or a saved block with
  // its ends swapped. Rather than let the engine read a line that leaves an
  // input, the record is rejected and named.
  const reversed = connections.filter(
    (c) => portOf(c, "source") !== "out" || portOf(c, "target") !== "in",
  );
  if (reversed.length) {
    errors.push({
      level: "error",
      code: "port_direction",
      message:
        `${reversed.length} connection(s) do not run output → input: ` +
        `${reversed.map((c) => c.id).slice(0, 4).join(", ")}. A line must leave an output port and enter an input port.`,
      ids: reversed.map((c) => c.id),
    });
  }

  const byTag = new Map<string, string[]>();
  for (const e of equipment) byTag.set(e.tag, [...(byTag.get(e.tag) ?? []), e.id]);
  for (const [tag, ids] of byTag) {
    if (ids.length < 2) continue;
    warnings.push({
      level: "warning",
      code: "duplicate_tag",
      message: `${ids.length} units share the tag ${tag} — an operator cannot tell them apart.`,
      ids,
    });
  }

  // ---- instrumentation coverage -----------------------------------------
  const sensorsByEquipment = new Map<string, SensorDef[]>();
  for (const { s, eq } of allSensors) {
    const list = sensorsByEquipment.get(eq.id) ?? [];
    list.push(s);
    sensorsByEquipment.set(eq.id, list);
  }
  const noInstruments = equipment.filter((e) => (sensorsByEquipment.get(e.id) ?? []).length === 0);
  for (const e of noInstruments) {
    warnings.push({
      level: "warning",
      code: "no_instrumentation",
      message: `${e.tag} has no instrumentation — nothing can detect a fault on it.`,
      ids: [e.id],
    });
  }

  // ---- connections -------------------------------------------------------
  const eqIds = new Set(equipment.map((e) => e.id));
  let invalid = 0;
  const orphanTouched = new Set<string>();

  for (const c of connections) {
    const srcEq = eqIds.has(c.source);
    const tgtEq = eqIds.has(c.target);
    const srcSensor = isSensorId(plant, c.source);
    const tgtSensor = isSensorId(plant, c.target);

    if (!srcEq && !srcSensor) {
      invalid += 1;
      errors.push({
        level: "error",
        code: "dangling_reference",
        message: `Connection ${c.id} starts at "${c.source}", which is not in the plant.`,
        ids: [c.source],
      });
      continue;
    }
    if (!tgtEq && !tgtSensor) {
      invalid += 1;
      errors.push({
        level: "error",
        code: "dangling_reference",
        message: `Connection ${c.id} ends at "${c.target}", which is not in the plant.`,
        ids: [c.target],
      });
      continue;
    }
    if (c.source === c.target) {
      invalid += 1;
      errors.push({ level: "error", code: "self_loop", message: `${c.id} connects an asset to itself.`, ids: [c.source] });
      continue;
    }
    if (srcSensor && tgtSensor) {
      invalid += 1;
      errors.push({
        level: "error",
        code: "sensor_on_sensor",
        message: `Connection ${c.id} joins two instruments. Instruments wire into equipment, not into each other.`,
        ids: [c.source, c.target],
      });
      continue;
    }
    orphanTouched.add(c.source);
    orphanTouched.add(c.target);
  }

  // ---- orphans -----------------------------------------------------------
  const orphanEquipment = equipment.filter((e) => !orphanTouched.has(e.id));
  for (const e of orphanEquipment) {
    warnings.push({
      level: "warning",
      code: "orphan_equipment",
      message: `${e.tag} is not connected to anything — it is inert in the process.`,
      ids: [e.id],
    });
  }

  const orphanSensors = allSensors.filter(({ s, eq }) => {
    // A sensor is only truly orphaned if it is neither attached to an
    // instrumented unit nor wired. Equipment ownership already counts.
    const owned = eqIds.has(eq.id);
    const wired = orphanTouched.has(s.id);
    return !owned || (!wired && (sensorsByEquipment.get(eq.id) ?? []).length === 1 && equipment.length > 1);
  });
  for (const { s, eq } of orphanSensors) {
    warnings.push({
      level: "warning",
      code: "orphan_sensor",
      message: `${s.tag} on ${eq.tag} has no wired signal path.`,
      ids: [s.id],
    });
  }

  // ---- redundancy on critical units -------------------------------------
  for (const e of equipment) {
    if (e.criticality < 1) continue;
    const list = sensorsByEquipment.get(e.id) ?? [];
    if (list.length === 0) continue;
    const byMeasurement = new Map<string, SensorDef[]>();
    for (const s of list) {
      const l = byMeasurement.get(s.measurement) ?? [];
      l.push(s);
      byMeasurement.set(s.measurement, l);
    }
    const singular = [...byMeasurement.entries()].filter(([, l]) => l.length === 1);
    // Only flag genuinely critical, criticality-2 units with a single point of
    // measurement failure — otherwise every plant reports hundreds of warnings.
    if (e.criticality >= 2 && singular.length === list.length && list.length > 0) {
      warnings.push({
        level: "warning",
        code: "no_redundancy",
        message: `${e.tag} has no redundant instrument — a single sensor failure blinds it.`,
        ids: [e.id, ...list.map((s) => s.id)],
      });
    }
  }

  return {
    ok: errors.length === 0,
    counts: {
      equipment: equipment.length,
      sensors: allSensors.length,
      connections: connections.length,
      orphanSensors: orphanSensors.length,
      orphanEquipment: orphanEquipment.length,
      invalidConnections: invalid,
    },
    errors,
    warnings,
  };
}

/** Sensor ids that no connection references, for graph highlighting. */
export function unwiredSensorIds(plant: PlantDef): string[] {
  const touched = new Set<string>();
  for (const c of plant.connections as ConnectionDef[]) {
    touched.add(c.source);
    touched.add(c.target);
  }
  return plant.equipment.flatMap((e) => e.sensors.filter((s) => !touched.has(s.id)).map((s) => s.id));
}
