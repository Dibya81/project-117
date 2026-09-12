/**
 * Sensor recovery reasoning — pure functions over the plant topology.
 *
 * This exists so one rule answers "what can still measure this point?" for
 * everyone who asks: the simulation engine (which uses it to decide whether a
 * process is still readable and to drive the agent pipeline's evidence), and
 * the console's recovery panel (which uses it to show the operator the circuit
 * the agents are working). Two copies of this logic would drift, and a
 * recovery panel that disagrees with the engine is worse than no panel.
 *
 * The ordering encodes engineering precedence, strongest evidence first:
 *
 *   1. DECLARED redundancy  — an engineer wrote a REDUNDANCY relation, so a
 *      second instrument was deliberately installed for this duty. This beats
 *      anything inferred.
 *   2. Same measurement, same unit — a genuine second reading of the point.
 *   3. Same measurement on an adjacent unit — correlated, weaker, and the
 *      panel labels it as inferred rather than presenting it as a substitute.
 *   4. Process correlates — for pressure, flow and vibration move together, so
 *      they can bound the value when no second pressure reading exists.
 *
 * Every function is pure and takes the plant explicitly, so callers can pass an
 * out-of-service predicate to exclude instruments that are themselves down.
 */

import type { EquipmentDef, PlantDef, SensorDef } from "./types";
import { isProcessRelation, relationOf } from "./relations";

export type OutOfService = (sensorId: string) => boolean;

const NEVER_OUT: OutOfService = () => false;

/** How a candidate fallback was found — the panel shows this to the operator. */
export type AlternateBasis = "declared" | "same-unit" | "adjacent-unit" | "process-correlate";

export interface AlternateSensor {
  sensor: SensorDef;
  basis: AlternateBasis;
  /** One line an operator can read, in engineering terms. */
  why: string;
}

const BASIS_WHY: Record<AlternateBasis, string> = {
  declared: "declared redundancy — installed for this duty",
  "same-unit": "second instrument on the same unit and measurement",
  "adjacent-unit": "same measurement on a connected unit (inferred, correlated)",
  "process-correlate": "process correlate — moves with the lost measurement",
};

export function equipmentById(plant: PlantDef, id: string): EquipmentDef | undefined {
  return plant.equipment.find((e) => e.id === id);
}

export function sensorById(plant: PlantDef, sensorId: string): SensorDef | undefined {
  for (const eq of plant.equipment) {
    const hit = eq.sensors.find((s) => s.id === sensorId);
    if (hit) return hit;
  }
  return undefined;
}

/** Equipment directly connected to `equipmentId` by a process relation. */
export function processNeighbors(plant: PlantDef, equipmentId: string): EquipmentDef[] {
  const ids = new Set<string>();
  for (const c of plant.connections) {
    if (!isProcessRelation(relationOf(c))) continue;
    if (c.source === equipmentId) ids.add(c.target);
    else if (c.target === equipmentId) ids.add(c.source);
  }
  return [...ids].map((id) => equipmentById(plant, id)).filter((e): e is EquipmentDef => Boolean(e));
}

/** Sensors wired to `sensorId` with an explicit REDUNDANCY relation. */
export function declaredRedundancyIds(plant: PlantDef, sensorId: string): string[] {
  const out: string[] = [];
  for (const c of plant.connections) {
    if (relationOf(c) !== "REDUNDANCY") continue;
    if (c.source === sensorId) out.push(c.target);
    else if (c.target === sensorId) out.push(c.source);
  }
  return out;
}

/**
 * Instruments that can still read the point `sensorId` was reading.
 *
 * Returned in precedence order with no duplicates. Out-of-service sensors are
 * excluded: pointing an operator at a second dead transmitter is not a
 * recovery, and the caller must be able to conclude "nothing left".
 */
export function alternateSensorsFor(
  plant: PlantDef,
  sensorId: string,
  isOut: OutOfService = NEVER_OUT,
): AlternateSensor[] {
  const origin = sensorById(plant, sensorId);
  if (!origin) return [];
  const owner = equipmentById(plant, origin.equipment_id);
  if (!owner) return [];

  const usable = (s: SensorDef) => s.id !== sensorId && !isOut(s.id);
  const found = new Map<string, AlternateSensor>();
  const push = (s: SensorDef, basis: AlternateBasis) => {
    if (!usable(s) || found.has(s.id)) return;
    found.set(s.id, { sensor: s, basis, why: BASIS_WHY[basis] });
  };

  // 1 — declared redundancy, strongest evidence available.
  for (const id of declaredRedundancyIds(plant, sensorId)) {
    const s = sensorById(plant, id);
    if (s) push(s, "declared");
  }
  // 2 — a second instrument for the same measurement on the same unit.
  for (const s of owner.sensors) {
    if (s.measurement === origin.measurement) push(s, "same-unit");
  }
  // 3 — the same measurement one hop away.
  for (const nb of processNeighbors(plant, owner.id)) {
    for (const s of nb.sensors) {
      if (s.measurement === origin.measurement) push(s, "adjacent-unit");
    }
  }
  // 4 — process correlates, only when nothing else can read the point.
  if (found.size === 0 && origin.measurement === "pressure") {
    for (const nb of processNeighbors(plant, owner.id)) {
      for (const s of nb.sensors) {
        if (s.measurement === "flow" || s.measurement === "vibration") push(s, "process-correlate");
      }
    }
    for (const s of owner.sensors) {
      if (s.measurement === "flow" || s.measurement === "vibration") push(s, "process-correlate");
    }
  }

  return [...found.values()];
}

export interface RecoveryCircuit {
  origin: SensorDef;
  equipment: EquipmentDef;
  alternates: AlternateSensor[];
  /** Units that depended on this measurement, nearest first. */
  downstream: EquipmentDef[];
}

/** Everything the recovery panel needs about the affected circuit, in one call. */
export function recoveryCircuit(
  plant: PlantDef,
  sensorId: string,
  isOut: OutOfService = NEVER_OUT,
): RecoveryCircuit | null {
  const origin = sensorById(plant, sensorId);
  if (!origin) return null;
  const equipment = equipmentById(plant, origin.equipment_id);
  if (!equipment) return null;
  return {
    origin,
    equipment,
    alternates: alternateSensorsFor(plant, sensorId, isOut),
    downstream: processNeighbors(plant, equipment.id),
  };
}
