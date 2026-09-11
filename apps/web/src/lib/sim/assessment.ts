/**
 * Post-incident assessment: root cause and next-failure prediction.
 *
 * Pure functions over `(plant, snapshot, incident)` rather than methods on the
 * engine. That matters: in live mode the engine runs on the backend and only
 * the snapshot crosses the wire, so anything computed off engine internals
 * would silently do nothing in the default configuration. Building on the
 * snapshot means the prebuilt refinery and a hand-built plant are assessed
 * identically, and it stays correct under both transports.
 *
 * Every input here is recorded state — the injected failure mode, live
 * telemetry quality, sensor configuration, topology adjacency and real dates.
 * Confidence is capped below 1.0 on purpose: this is an assessment, never a
 * proof, and the returned `caveat` says so.
 */
import type {
  Incident,
  NextFailureCandidate,
  NextFailurePrediction,
  PlantDef,
  RootCauseAssessment,
  RootCauseEvidence,
  RootCauseHypothesis,
  SensorDef,
  SimSnapshot,
} from "./types";

const DAY = 86_400_000;
const clamp = (v: number, lo = 0.15, hi = 0.95) => Math.max(lo, Math.min(hi, v));

interface Topology {
  up: Map<string, string[]>;
  down: Map<string, string[]>;
}

/** Equipment adjacency, ignoring sensor endpoints (they are not process nodes). */
function topology(plant: PlantDef): Topology {
  const ids = new Set(plant.equipment.map((e) => e.id));
  const up = new Map<string, string[]>();
  const down = new Map<string, string[]>();
  for (const c of plant.connections) {
    if (!ids.has(c.source) || !ids.has(c.target)) continue;
    (down.get(c.source) ?? down.set(c.source, []).get(c.source)!).push(c.target);
    (up.get(c.target) ?? up.set(c.target, []).get(c.target)!).push(c.source);
  }
  return { up, down };
}

function neighbourIds(topo: Topology, start: string, depth: number): string[] {
  const seen = new Set([start]);
  let frontier = [start];
  const out: string[] = [];
  for (let d = 0; d < depth; d++) {
    const next: string[] = [];
    for (const cur of frontier) {
      for (const nb of [...(topo.down.get(cur) ?? []), ...(topo.up.get(cur) ?? [])]) {
        if (seen.has(nb)) continue;
        seen.add(nb);
        out.push(nb);
        next.push(nb);
      }
    }
    frontier = next;
  }
  return out;
}

/** Sensors on a unit plus on its immediate neighbours, same measurement first. */
function alternatesFor(plant: PlantDef, topo: Topology, sensorId: string): SensorDef[] {
  const owner = plant.equipment.find((e) => e.sensors.some((s) => s.id === sensorId));
  if (!owner) return [];
  const me = owner.sensors.find((s) => s.id === sensorId)!;
  const out: SensorDef[] = owner.sensors.filter((s) => s.id !== sensorId && s.measurement === me.measurement);
  for (const nb of [...(topo.up.get(owner.id) ?? []), ...(topo.down.get(owner.id) ?? [])]) {
    const eq = plant.equipment.find((e) => e.id === nb);
    if (eq) out.push(...eq.sensors.filter((s) => s.measurement === me.measurement));
  }
  if (me.measurement === "pressure") {
    out.push(...owner.sensors.filter((s) => s.id !== sensorId && (s.measurement === "flow" || s.measurement === "vibration")));
  }
  return out;
}

const yearsSince = (iso: string): number | null => {
  const t = Date.parse(iso);
  return Number.isNaN(t) ? null : (Date.now() - t) / (365.25 * DAY);
};

/* ------------------------------------------------------------- root cause */

export function assessRootCause(
  plant: PlantDef,
  snapshot: SimSnapshot,
  incident: Incident,
): RootCauseAssessment {
  const eq = plant.equipment.find((e) => e.id === incident.origin_equipment);
  if (!eq) {
    return { available: false, reason: "Origin equipment is no longer in the plant.", hypotheses: [], evidence: [] };
  }

  const mode = incident.failure_mode
    ? plant.failure_modes.find((m) => m.id === incident.failure_mode)
    : undefined;
  const sensor = incident.origin_sensor ? eq.sensors.find((s) => s.id === incident.origin_sensor) : undefined;
  const reading = incident.origin_sensor ? snapshot.sensors[incident.origin_sensor] : undefined;
  const topo = topology(plant);

  const evidence: RootCauseEvidence[] = [];
  let instrument = 0.4;

  if (mode) {
    evidence.push({
      id: "E-mode",
      source: "failure mode",
      detail: `${mode.name} — mechanism "${mode.mechanism}", magnitude ${mode.magnitude}`,
      supports: "instrument",
    });
    if (mode.mechanism === "sensor") instrument += 0.18;
    else if (mode.mechanism === "drift") instrument += 0.12;
    else if (mode.mechanism === "degrade" || mode.mechanism === "surge") instrument -= 0.14;
    else instrument -= 0.2;
  }

  if (sensor) {
    evidence.push({
      id: "E-config",
      source: "sensor configuration",
      detail: `${sensor.tag} · ${sensor.measurement} · sampling ${sensor.sampling_ms} ms · configured drift ${sensor.drift_rate}`,
      supports: "instrument",
    });
    if (sensor.drift_rate > 0) instrument += 0.08;
  }

  let consistent = 0;
  let diverging = 0;
  if (incident.origin_sensor) {
    for (const alt of alternatesFor(plant, topo, incident.origin_sensor)) {
      const rt = snapshot.sensors[alt.id];
      if (!rt) continue;
      const inBand = rt.value >= alt.normal_min && rt.value <= alt.normal_max;
      if (rt.quality === "good" && inBand) consistent += 1;
      else diverging += 1;
    }
  }
  if (consistent > 0) {
    instrument += Math.min(0.16, 0.06 * consistent);
    evidence.push({
      id: "E-alternates",
      source: "topology",
      detail: `${consistent} alternate measurement(s) sit inside their normal band — the process itself reads healthy, which points at the instrument.`,
      supports: "instrument",
    });
  }
  if (diverging > 0) {
    instrument -= Math.min(0.18, 0.06 * diverging);
    evidence.push({
      id: "E-divergence",
      source: "topology",
      detail: `${diverging} related measurement(s) are also outside band — this is not isolated to one instrument.`,
      supports: "process",
    });
  }

  const years = yearsSince(eq.last_inspection);
  if (years !== null) {
    const days = Math.round(years * 365.25);
    evidence.push({
      id: "E-maint",
      source: "maintenance history",
      detail: `${eq.tag} last inspected ${eq.last_inspection} (${days} days ago) · installed ${eq.installed}`,
      supports: "instrument",
    });
    if (days > 180) instrument += 0.1;
    if (days > 365) instrument += 0.06;
  }

  if (reading && sensor) {
    evidence.push({
      id: "E-reading",
      source: "telemetry",
      detail:
        reading.quality === "good"
          ? `${sensor.tag} reads ${reading.value.toFixed(2)} ${sensor.unit}, quality GOOD`
          : `${sensor.tag} quality is ${reading.quality.toUpperCase()}${reading.failed ? " (failed)" : ""}`,
      supports: "instrument",
    });
  }

  const primary = clamp(instrument);
  const hypotheses: RootCauseHypothesis[] = [
    {
      id: "instrument",
      label: sensor ? "Instrument degradation / signal-path fault" : "Component degradation",
      confidence: primary,
      rationale: sensor
        ? "Confined to a single measurement while related readings stay in band — the signature of the instrument rather than the process."
        : "The equipment itself is faulted; no single instrument explains it.",
    },
    {
      id: "process",
      label: "Process upset upstream of the measurement",
      confidence: clamp((1 - primary) * 0.55),
      rationale: "Would require unrelated measurements to move together; only weakly supported by current evidence.",
    },
    {
      id: "maintenance",
      label: "Deferred maintenance / wear beyond interval",
      confidence: clamp((1 - primary) * 0.35),
      rationale: "Age and inspection interval contribute but do not by themselves explain a single-point loss.",
    },
  ].sort((a, b) => b.confidence - a.confidence);

  return {
    available: true,
    incidentId: incident.id,
    equipmentTag: eq.tag,
    sensorTag: sensor?.tag,
    hypotheses,
    evidence,
    caveat:
      "Derived from recorded evidence only. Confidence is not certainty and no cause is confirmed without physical inspection.",
  };
}

/* -------------------------------------------------------------- prediction */

export function predictNextFailure(
  plant: PlantDef,
  snapshot: SimSnapshot,
  incident: Incident,
  limit = 3,
): NextFailurePrediction {
  const origin = plant.equipment.find((e) => e.id === incident.origin_equipment);
  if (!origin) {
    return { available: false, reason: "Origin equipment is no longer in the plant.", candidates: [] };
  }
  const topo = topology(plant);
  const originSensor = incident.origin_sensor
    ? origin.sensors.find((s) => s.id === incident.origin_sensor)
    : undefined;

  const direct = new Set([...(topo.up.get(origin.id) ?? []), ...(topo.down.get(origin.id) ?? [])]);
  const candidates: NextFailureCandidate[] = [];

  for (const id of neighbourIds(topo, origin.id, 2)) {
    const eq = plant.equipment.find((e) => e.id === id);
    if (!eq) continue;

    let risk = 0.08;
    const reasons: string[] = [];

    // 1. telemetry headroom — the strongest real signal available
    let worst = 0;
    let worstTag = "";
    for (const s of eq.sensors) {
      const rt = snapshot.sensors[s.id];
      if (!rt || rt.quality !== "good" || s.is_detector) continue;
      const span = Math.abs(s.critical_max - s.normal_max) || Math.abs(s.normal_max - s.normal_min) || 1;
      const intoCritical = (rt.value - s.normal_max) / span;
      const intoWarning = (rt.value - s.warning_max) / span;
      const score = Math.max(intoCritical, intoWarning * 0.6, 0);
      if (score > worst) {
        worst = score;
        worstTag = `${s.tag} at ${rt.value.toFixed(1)} ${s.unit}`;
      }
    }
    if (worst > 0) {
      risk += Math.min(0.4, worst * 0.5);
      reasons.push(`${worstTag} is trending toward its limit`);
    }

    // 2. service life
    const years = yearsSince(eq.installed);
    if (years !== null) {
      risk += Math.min(0.18, (years / 15) * 0.18);
      if (years / 15 > 0.75) reasons.push(`${years.toFixed(1)} years in service`);
    }

    // 3. carries the same instrument family that just failed
    if (originSensor && eq.sensors.some((s) => s.measurement === originSensor.measurement)) {
      risk += 0.12;
      reasons.push(`same ${originSensor.measurement} instrumentation family as the failed point`);
    }

    // 4. proximity
    if (direct.has(id)) {
      risk += 0.08;
      reasons.push("directly connected to the incident origin");
    } else {
      risk += 0.03;
    }

    if (eq.criticality >= 2) {
      risk += 0.06;
      reasons.push(`criticality class ${eq.criticality}`);
    }
    if (!reasons.length) reasons.push("shares a process path with the incident origin");

    const r = Math.max(0.05, Math.min(0.92, risk));
    candidates.push({
      equipmentId: eq.id,
      tag: eq.tag,
      name: eq.name,
      risk: r,
      reasons,
      horizon: r > 0.5 ? "next 30 days" : r > 0.3 ? "next quarter" : "monitor",
    });
  }

  candidates.sort((a, b) => b.risk - a.risk);
  return {
    available: true,
    incidentId: incident.id,
    candidates: candidates.slice(0, limit),
    caveat: "Ranked from current telemetry, service age and topology — an early warning, not a guaranteed prediction.",
  };
}
