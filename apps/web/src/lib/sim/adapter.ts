"use client";

/**
 * Simulation adapter — one surface, two transports.
 *
 *   live      → backend engine over REST + SSE (the real thing)
 *   embedded  → the in-browser deterministic engine (zero-infrastructure demo)
 *
 * Selection follows the project's existing DATA_MODE flag; the UI never
 * branches on transport. The engine is the source of truth either way —
 * the UI renders events, it never invents them.
 */
import { SimEngine } from "./engine";
import type {
  Incident,
  IncidentPlan,
  AgentTask,
  PlantDef,
  PlantListItem,
  ScenarioDef,
  SimEvent,
  SimSnapshot,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
const RAW_MODE = process.env.NEXT_PUBLIC_DATA_MODE ?? "live";
/**
 * Data mode is explicit, never inferred.
 *
 *   live (default) - every read and write goes to the FastAPI backend.
 *   mock           - the in-browser engine, for offline UI development only.
 *                    It must be selected on purpose with
 *                    NEXT_PUBLIC_DATA_MODE=mock. There is no fallback into it:
 *                    if the backend is down, live mode raises and the UI shows
 *                    the connectivity error instead of inventing data.
 */
export const DATA_MODE: "live" | "mock" = RAW_MODE === "mock" ? "mock" : "live";
export const MOCK_MODE_EXPLICIT = RAW_MODE === "mock";

export class BackendUnavailableError extends Error {
  readonly endpoint: string;
  constructor(endpoint: string, detail: string) {
    super(`Backend unavailable at ${endpoint}: ${detail}`);
    this.name = "BackendUnavailableError";
    this.endpoint = endpoint;
  }
}

/** Probe the backend. Callers surface the failure; nothing degrades silently. */
export async function checkBackendHealth(): Promise<{
  ok: boolean;
  apiBase: string;
  detail: string;
  agents?: unknown;
  database?: string;
}> {
  if (DATA_MODE === "mock") {
    return { ok: false, apiBase: API_BASE, detail: "NEXT_PUBLIC_DATA_MODE=mock (development mode)" };
  }
  try {
    const res = await fetch(`${API_BASE}/api/simulation/health`, { credentials: "same-origin" });
    if (!res.ok) return { ok: false, apiBase: API_BASE, detail: `HTTP ${res.status}` };
    const body = (await res.json()) as { database?: string; agents?: unknown };
    return { ok: true, apiBase: API_BASE, detail: "ok", agents: body.agents, database: body.database };
  } catch (err) {
    return { ok: false, apiBase: API_BASE, detail: (err as Error).message };
  }
}

export interface SimAdapter {
  transport: "live" | "embedded";
  listPlants(): Promise<PlantListItem[]>;
  loadPlant(id: string): Promise<{ plant: PlantDef; scenarios: ScenarioDef[] }>;
  start(id: string): Promise<void>;
  pause(id: string): Promise<void>;
  injectFailure(plantId: string, equipmentId: string, modeId: string): Promise<void>;
  disable(plantId: string, equipmentId: string): Promise<void>;
  remove(plantId: string, equipmentId: string): Promise<void>;
  /** Take one sensor out of service (session-scoped; reset restores it).
   *  `incidentId` is the agent run raised for the loss, or null if none. */
  disableSensor(plantId: string, sensorId: string): Promise<{ incidentId: string | null }>;
  /** Delete one sensor. Terminal for the session — reset brings it back. */
  removeSensor(plantId: string, sensorId: string): Promise<{ incidentId: string | null }>;
  /** Return a disabled sensor to service. */
  restoreSensor(plantId: string, sensorId: string): Promise<void>;
  /**
   * Return the plant to its committed definition, discarding every operator
   * change made this session. This is what makes a reload restore normal.
   */
  resetPlant(plantId: string): Promise<void>;
  decide(plantId: string, incidentId: string, approved: boolean): Promise<void>;
  snapshot(plantId: string): Promise<SimSnapshot>;
  tasks(plantId: string, incidentId: string): Promise<{ tasks: AgentTask[]; plan: IncidentPlan }>;
  subscribe(plantId: string, cb: (ev: SimEvent) => void): () => void;
}

/** Backend-only capabilities (persistence). Absent in mock mode by design. */
export interface LiveAdapterApi extends SimAdapter {
  savePlant(plant: PlantDef): Promise<{ plant: string; saved: boolean }>;
  loadSavedPlant(plantId: string): Promise<PlantDef>;
  history(plantId: string): Promise<Record<string, unknown>[]>;
  incidentRecord(incidentId: string): Promise<Record<string, unknown>>;
  audit(plantId: string, incidentId?: string): Promise<Record<string, unknown>[]>;
}

export function asLive(a: SimAdapter): LiveAdapterApi | null {
  return a.transport === "live" ? (a as LiveAdapterApi) : null;
}

/* ---------------------------------------------------------------- embedded */

class EmbeddedAdapter implements SimAdapter {
  transport = "embedded" as const;
  engines = new Map<string, SimEngine>();
  private plants = new Map<string, { plant: PlantDef; scenarios: ScenarioDef[] }>();
  private timers = new Map<string, ReturnType<typeof setInterval>>();

  async listPlants(): Promise<PlantListItem[]> {
    const out: PlantListItem[] = [];
    for (const id of ["refinery", "steel"]) {
      const { plant, scenarios } = await this.loadPlant(id);
      out.push({
        id: plant.id,
        name: plant.name,
        industry: plant.industry,
        assets: plant.equipment.length + plant.equipment.reduce((n, e) => n + e.sensors.length, 0),
        sensors: plant.equipment.reduce((n, e) => n + e.sensors.length, 0),
        scenarios: scenarios.length,
        areas: plant.areas.length,
      });
    }
    return out;
  }

  async loadPlant(id: string): Promise<{ plant: PlantDef; scenarios: ScenarioDef[] }> {
    if (this.plants.has(id)) return this.plants.get(id)!;
    const [plant, areas, equipment, connections, failureModes, scenarios] = await Promise.all([
      fetch(`/simulation/${id}/plant.json`).then((r) => r.json()),
      fetch(`/simulation/${id}/areas.json`).then((r) => r.json()),
      fetch(`/simulation/${id}/equipment.json`).then((r) => r.json()),
      fetch(`/simulation/${id}/connections.json`).then((r) => r.json()),
      fetch(`/simulation/${id}/failure_modes.json`).then((r) => r.json()),
      fetch(`/simulation/${id}/scenarios.json`).then((r) => r.json()).catch(() => []),
    ]);
    const def = { plant: { ...plant, areas, equipment, connections, failure_modes: failureModes } as PlantDef, scenarios: scenarios as ScenarioDef[] };
    this.plants.set(id, def);
    return def;
  }

  registerCustomPlant(plant: PlantDef): void {
    this.plants.set(plant.id, { plant, scenarios: [] });
    this.engines.delete(plant.id); // fresh engine for a fresh topology
  }

  engine(plantId: string): SimEngine {
    if (!this.engines.has(plantId)) {
      const def = this.plants.get(plantId);
      if (!def) throw new Error(`plant ${plantId} not loaded`);
      this.engines.set(plantId, new SimEngine(def.plant));
    }
    return this.engines.get(plantId)!;
  }

  async start(id: string): Promise<void> {
    const eng = this.engine(id);
    if (this.timers.has(id)) return;
    eng.markStarted();
    this.timers.set(
      id,
      setInterval(() => eng.tick(), 1000),
    );
  }

  async pause(id: string): Promise<void> {
    const t = this.timers.get(id);
    if (t) clearInterval(t);
    this.timers.delete(id);
    this.engine(id).markPaused();
  }

  async injectFailure(plantId: string, equipmentId: string, modeId: string): Promise<void> {
    const eng = this.engine(plantId);
    const changed = eng.injectFailure(equipmentId, modeId);
    const eq = eng.plant.equipment.find((e) => e.id === equipmentId)!;
    const mode = eng.plant.failure_modes.find((m) => m.id === modeId)!;
    const incident = eng.createIncident({
      title: `${(changed.tag as string) ?? eq.tag} — ${mode.name}`,
      severity: mode.mechanism === "stop" || mode.mechanism === "leak" ? "critical" : "warning",
      originEquipment: equipmentId,
      originSensor: (changed.sensor_id as string) ?? null,
      failureMode: modeId,
    });
    // the pipeline runs against real engine state, then waits for the human
    setTimeout(() => eng.runAgentPipeline(incident.id), 400);
  }

  async disable(plantId: string, equipmentId: string): Promise<void> {
    this.engine(plantId).disableEquipment(equipmentId);
  }

  async remove(plantId: string, equipmentId: string): Promise<void> {
    this.engine(plantId).removeEquipment(equipmentId);
  }

  async disableSensor(plantId: string, sensorId: string): Promise<{ incidentId: string | null }> {
    const eng = this.engine(plantId);
    eng.disableSensor(sensorId);
    return { incidentId: this.raiseSensorIncident(plantId, sensorId, "disable") };
  }

  async removeSensor(plantId: string, sensorId: string): Promise<{ incidentId: string | null }> {
    const eng = this.engine(plantId);
    // Capture the model's tags BEFORE deleting, so the incident is named after
    // the instrument that was actually lost rather than a bare id.
    const incidentId = this.raiseSensorIncident(plantId, sensorId, "remove");
    eng.removeSensor(sensorId);
    return { incidentId };
  }

  /**
   * A lost transmitter is an anomaly, not a config change, so it engages the
   * same agents a fault injection does. The incident carries `originSensor`,
   * which is what makes the pipeline's redundancy reasoning run against the
   * point that was actually lost — the same path the backend takes.
   */
  private raiseSensorIncident(
    plantId: string,
    sensorId: string,
    action: "disable" | "remove",
  ): string | null {
    const eng = this.engine(plantId);
    let tag = sensorId;
    let equipmentId: string | null = null;
    for (const eq of eng.plant.equipment) {
      const s = eq.sensors.find((x) => x.id === sensorId);
      if (s) {
        tag = s.tag;
        equipmentId = eq.id;
        break;
      }
    }
    if (!equipmentId) return null;
    // Do not stack duplicates: one open incident per lost instrument.
    const open = [...eng.incidents.values()].find(
      (i) => i.origin_sensor === sensorId && i.status !== "resolved",
    );
    if (open) return open.id;
    const incident = eng.createIncident({
      title: `${action === "remove" ? "Instrument deleted" : "Loss of measurement"} — ${tag}`,
      severity: action === "remove" ? "critical" : "warning",
      originEquipment: equipmentId,
      originSensor: sensorId,
      failureMode: null,
    });
    setTimeout(() => eng.runAgentPipeline(incident.id), 400);
    return incident.id;
  }

  async restoreSensor(plantId: string, sensorId: string): Promise<void> {
    this.engine(plantId).restoreSensor(sensorId);
  }

  async resetPlant(plantId: string): Promise<void> {
    // Embedded mode has no server to ask, so reset means "throw the engine
    // away and rebuild it from the definition we were given on load" — the
    // same thing a page reload does, without the reload.
    const existing = this.engines.get(plantId);
    if (!existing) return;
    this.engines.delete(plantId);
    const fresh = new SimEngine(structuredClone(existing.plant), existing.seed);
    fresh.markPaused();
    this.engines.set(plantId, fresh);
  }

  async decide(plantId: string, incidentId: string, approved: boolean): Promise<void> {
    const eng = this.engine(plantId);
    eng.decide(incidentId, approved, () => eng.tick());
  }

  async snapshot(plantId: string): Promise<SimSnapshot> {
    return this.engine(plantId).snapshot();
  }

  async tasks(plantId: string, incidentId: string): Promise<{ tasks: AgentTask[]; plan: IncidentPlan }> {
    const eng = this.engine(plantId);
    const tasks = eng.tasks.get(incidentId);
    const plan = eng.plans.get(incidentId);
    if (!tasks || !plan) throw new Error("unknown incident");
    return { tasks, plan };
  }

  subscribe(plantId: string, cb: (ev: SimEvent) => void): () => void {
    return this.engine(plantId).onEvent(cb);
  }
}

/* -------------------------------------------------------------------- live */

class LiveAdapter implements SimAdapter {
  transport = "live" as const;

  private async req<T>(path: string, init?: RequestInit): Promise<T> {
    const endpoint = `${API_BASE}/api/simulation${path}`;
    let res: Response;
    try {
      res = await fetch(endpoint, {
        ...init,
        headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
        credentials: "same-origin",
      });
    } catch (err) {
      // Network-level failure: fail loudly. No embedded fallback.
      throw new BackendUnavailableError(endpoint, (err as Error).message);
    }
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      if (res.status >= 500) throw new BackendUnavailableError(endpoint, `HTTP ${res.status} ${detail}`.trim());
      throw new Error(`simulation api ${res.status} ${detail}`.trim());
    }
    return (await res.json()) as T;
  }

  listPlants(): Promise<PlantListItem[]> {
    return this.req<{ plants: PlantListItem[] }>("/plants").then((r) => r.plants);
  }

  async loadPlant(id: string): Promise<{ plant: PlantDef; scenarios: ScenarioDef[] }> {
    // snapshot carries the full plant definition; scenarios come from the dataset
    const snap = await this.req<SimSnapshot & { plant: PlantDef }>(`/plants/${id}/snapshot`);
    const scenarios = await fetch(`/simulation/${id}/scenarios.json`).then((r) => r.json()).catch(() => []);
    return { plant: snap.plant, scenarios };
  }

  start(id: string) {
    return this.req(`/plants/${id}/start`, { method: "POST" }).then(() => undefined);
  }
  pause(id: string) {
    return this.req(`/plants/${id}/pause`, { method: "POST" }).then(() => undefined);
  }
  injectFailure(plantId: string, equipmentId: string, modeId: string) {
    return this.req(`/plants/${plantId}/equipment/${equipmentId}/failure`, { method: "POST", body: JSON.stringify({ mode_id: modeId }) }).then(() => undefined);
  }
  disable(plantId: string, equipmentId: string) {
    return this.req(`/plants/${plantId}/equipment/${equipmentId}/disable`, { method: "POST" }).then(() => undefined);
  }
  remove(plantId: string, equipmentId: string) {
    return this.req(`/plants/${plantId}/equipment/${equipmentId}/remove`, { method: "POST" }).then(() => undefined);
  }
  async disableSensor(plantId: string, sensorId: string): Promise<{ incidentId: string | null }> {
    const r = await this.req<{ incident_id?: string | null }>(
      `/plants/${plantId}/sensors/${sensorId}/disable`,
      { method: "POST" },
    );
    return { incidentId: r.incident_id ?? null };
  }
  async removeSensor(plantId: string, sensorId: string): Promise<{ incidentId: string | null }> {
    const r = await this.req<{ incident_id?: string | null }>(
      `/plants/${plantId}/sensors/${sensorId}/remove`,
      { method: "POST" },
    );
    return { incidentId: r.incident_id ?? null };
  }
  restoreSensor(plantId: string, sensorId: string) {
    return this.req(`/plants/${plantId}/sensors/${sensorId}/restore`, { method: "POST" }).then(() => undefined);
  }
  resetPlant(plantId: string) {
    // Server-side the engine lives in RAM for the life of the process, so a
    // browser reload alone would keep an operator's changes. Resetting is what
    // makes "reload restores normal" true in live mode.
    return this.req(`/plants/${plantId}/reset`, { method: "POST" }).then(() => undefined);
  }
  decide(plantId: string, incidentId: string, approved: boolean) {
    return this.req(`/plants/${plantId}/incidents/${incidentId}/decision`, { method: "POST", body: JSON.stringify({ approved }) }).then(() => undefined);
  }
  snapshot(plantId: string) {
    return this.req<SimSnapshot>(`/plants/${plantId}/snapshot`);
  }
  tasks(plantId: string, incidentId: string) {
    return this.req<{ tasks: AgentTask[]; plan: IncidentPlan }>(`/plants/${plantId}/incidents/${incidentId}/tasks`);
  }

  /** Builder save - writes the plant graph to the backend database. */
  savePlant(plant: PlantDef) {
    return this.req<{ plant: string; saved: boolean }>("/plants", {
      method: "POST",
      body: JSON.stringify({ plant }),
    });
  }

  /** Builder load - reads the saved plant back out of the database. */
  loadSavedPlant(plantId: string) {
    return this.req<{ plant: PlantDef }>(`/plants/${plantId}/definition`).then((r) => r.plant);
  }

  /** Persisted incident history (survives a backend restart). */
  history(plantId: string) {
    return this.req<{ incidents: Record<string, unknown>[] }>(`/plants/${plantId}/history`).then((r) => r.incidents);
  }

  /** Full persisted record for one incident, used by the Command Center. */
  incidentRecord(incidentId: string) {
    return this.req<Record<string, unknown>>(`/incidents/${incidentId}/record`);
  }

  /** Persistent audit trail rows. */
  audit(plantId: string, incidentId?: string) {
    const q = incidentId ? `?plant_id=${plantId}&incident_id=${incidentId}` : `?plant_id=${plantId}`;
    return this.req<{ events: Record<string, unknown>[] }>(`/audit${q}`).then((r) => r.events);
  }

  subscribe(plantId: string, cb: (ev: SimEvent) => void): () => void {
    const es = new EventSource(`${API_BASE}/api/simulation/plants/${plantId}/stream`);
    es.onmessage = (msg) => {
      try {
        cb(JSON.parse(msg.data) as SimEvent);
      } catch {
        /* malformed frame */
      }
    };
    return () => es.close();
  }
}

/** Embedded adapters expose the engine for direct reads (renderer hot path). */
export interface EmbeddedAdapterApi extends SimAdapter {
  engine(plantId: string): SimEngine;
  registerCustomPlant(plant: PlantDef): void;
}

export function asEmbedded(a: SimAdapter): EmbeddedAdapterApi | null {
  return a.transport === "embedded" ? (a as EmbeddedAdapterApi) : null;
}

export function createSimAdapter(): SimAdapter {
  if (DATA_MODE === "mock") {
    // Explicit opt-in only. Loud in the console so nobody demos this by accident.
    // eslint-disable-next-line no-console
    console.warn(
      "[Project 117] NEXT_PUBLIC_DATA_MODE=mock - running the in-browser engine. " +
        "This is a development mode and is NOT connected to the backend, database, agents or audit trail.",
    );
    return new EmbeddedAdapter();
  }
  return new LiveAdapter();
}

/** Singleton for the console session. */
export const simAdapter = createSimAdapter();
