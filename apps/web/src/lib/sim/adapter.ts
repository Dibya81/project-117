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

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

/**
 * Consecutive stream failures after which the console declares mock mode.
 * Three is the documented threshold: transient blips reconnect silently, but
 * an orchestrator that never answers is surfaced, not hidden.
 */
export const MOCK_RETRY_LIMIT = 3;

/**
 * Minimal GET against the simulation API.
 *
 * The embedded adapter has no request helper of its own because it used to read
 * bundled JSON; now that plant data lives only in the backend's SQLite store it
 * needs one.
 */
async function apiGet<T>(path: string): Promise<T> {
  const endpoint = `${API_BASE}/api/simulation${path}`;
  const res = await fetch(endpoint, { credentials: "same-origin" });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`simulation api ${res.status} ${detail}`.trim());
  }
  return (await res.json()) as T;
}

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
  /**
   * Read a plant's definition (and its scenarios).
   *
   * `topologyOnly` skips the runtime snapshot and returns the stored definition
   * instead. A decorative preview needs the topology and nothing else — the
   * snapshot carries every live sensor value and line state and is an order of
   * magnitude larger, which is real bytes for data no card renders.
   */
  loadPlant(id: string, options?: { topologyOnly?: boolean }): Promise<{ plant: PlantDef; scenarios: ScenarioDef[] }>;
  start(id: string): Promise<void>;
  pause(id: string): Promise<void>;
  /**
   * Inject a fault. Resolves to the backend incident id (the job id every
   * response event is bucketed under), or null when the transport cannot say.
   */
  injectFailure(plantId: string, equipmentId: string, modeId: string): Promise<string | null>;
  /**
   * Take a unit out of service. This is a plant-state action, not an incident:
   * the action policy will not auto-restore a disabled machine, so the agents
   * are engaged by a lost measurement or an injected fault instead.
   */
  disable(plantId: string, equipmentId: string): Promise<void>;
  remove(plantId: string, equipmentId: string): Promise<void>;
  /** Take one sensor out of service (session-scoped; reset restores it).
   *  `incidentId` is the agent run raised for the loss, or null if none. */
  disableSensor(plantId: string, sensorId: string): Promise<{ incidentId: string | null }>;
  /** Process-line actions. A blocked line starves everything downstream. */
  blockLine(plantId: string, connectionId: string): Promise<{ incidentId: string | null }>;
  restoreLine(plantId: string, connectionId: string): Promise<void>;
  leakLine(plantId: string, connectionId: string, leaking: boolean): Promise<{ incidentId: string | null }>;
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
  /**
   * The LIVE state only — equipment, sensors, line flow — without the plant
   * definition, which the caller already has. Use this for the periodic refresh;
   * `snapshot` is for a first load that has no definition yet.
   */
  frame(plantId: string): Promise<SimSnapshot>;
  /**
   * The incident's task DAG. `plan` is null while the backend is still building
   * it — a run that exists but has no tasks yet, not an error.
   */
  tasks(plantId: string, incidentId: string): Promise<{ tasks: AgentTask[]; plan: IncidentPlan | null }>;
  /**
   * Subscribe to the plant event stream. `onStatus` reports transport health
   * so the console can distinguish a live orchestrator from one that never
   * connected — it must never be inferred from the data itself.
   */
  subscribe(
    plantId: string,
    cb: (ev: SimEvent) => void,
    onStatus?: (status: StreamStatus) => void,
  ): () => void;
}

/**
 * Transport health, reported by the adapter (not derived from events).
 *
 *   connecting → the stream is being established / retried
 *   live       → the orchestrator stream is open
 *   mock       → the stream failed `MOCK_RETRY_LIMIT` times; the console may
 *                run a local development sequence, behind a permanent banner.
 */
export type StreamState = "connecting" | "live" | "mock";

export interface StreamStatus {
  state: StreamState;
  attempts: number;
  detail?: string;
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
    // Plant data comes from the backend's SQLite store, never from bundled
    // JSON. The embedded engine still runs in the browser, but it is fed the
    // same rows the live path reads, so the two transports cannot drift apart
    // about what a plant contains — which is exactly what happened when each
    // shipped its own copy of the dataset.
    const [def, sc] = await Promise.all([
      apiGet<{ plant: PlantDef }>(`/plants/${id}/definition`),
      apiGet<{ scenarios: ScenarioDef[] }>(`/plants/${id}/scenarios`).catch(() => ({
        scenarios: [] as ScenarioDef[],
      })),
    ]);
    const resolved = { plant: def.plant, scenarios: sc.scenarios };
    this.plants.set(id, resolved);
    return resolved;
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

  async injectFailure(plantId: string, equipmentId: string, modeId: string): Promise<string | null> {
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
    return incident.id;
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

  async blockLine(plantId: string, connectionId: string): Promise<{ incidentId: string | null }> {
    // The embedded engine has no line model; refusing beats pretending.
    void plantId; void connectionId;
    throw new Error("line actions require the backend engine (live mode)");
  }

  async restoreLine(plantId: string, connectionId: string): Promise<void> {
    void plantId; void connectionId;
    throw new Error("line actions require the backend engine (live mode)");
  }

  async leakLine(plantId: string, connectionId: string, leaking: boolean): Promise<{ incidentId: string | null }> {
    void plantId; void connectionId; void leaking;
    throw new Error("line actions require the backend engine (live mode)");
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
  async frame(plantId: string): Promise<SimSnapshot> {
    // Embedded has no wire, so there is nothing to trim.
    return this.engine(plantId).snapshot();
  }

  async tasks(plantId: string, incidentId: string): Promise<{ tasks: AgentTask[]; plan: IncidentPlan }> {
    const eng = this.engine(plantId);
    const tasks = eng.tasks.get(incidentId);
    const plan = eng.plans.get(incidentId);
    if (!tasks || !plan) throw new Error("unknown incident");
    return { tasks, plan };
  }

  subscribe(
    plantId: string,
    cb: (ev: SimEvent) => void,
    onStatus?: (status: StreamStatus) => void,
  ): () => void {
    // The embedded engine is local and always available: report it as live so
    // the console never shows the mock banner for a deliberate offline run.
    onStatus?.({ state: "live", attempts: 0, detail: "embedded engine" });
    return this.engine(plantId).onEvent(cb);
  }
}

/* -------------------------------------------------------------------- live */

class LiveAdapter implements SimAdapter {
  transport = "live" as const;

  /**
   * Simulation-API reads, de-duplicated.
   *
   * This transport has its own `fetch` (it needs `BackendUnavailableError`
   * semantics the console client does not), so it did not inherit the read cache
   * in `lib/api.ts` and every concurrent caller fetched again. The plant
   * definition is ~100 KB and the hub and the knowledge graph were each reading
   * it twice per load.
   *
   * Only *concurrent* identical GETs are collapsed. Nothing is cached past the
   * moment the callers are waiting on, so a snapshot polled every 250 ms is
   * always the current one.
   */
  private static _inflight = new Map<string, Promise<unknown>>();

  private async req<T>(path: string, init?: RequestInit): Promise<T> {
    const endpoint = `${API_BASE}/api/simulation${path}`;
    const method = (init?.method ?? "GET").toUpperCase();
    const key = method === "GET" && !init?.body ? endpoint : null;
    if (key) {
      const pending = LiveAdapter._inflight.get(key) as Promise<T> | undefined;
      if (pending) return pending;
    }
    const run = this.performReq<T>(endpoint, init);
    if (key) {
      LiveAdapter._inflight.set(key, run);
      try {
        return await run;
      } finally {
        LiveAdapter._inflight.delete(key);
      }
    }
    return run;
  }

  private async performReq<T>(endpoint: string, init?: RequestInit): Promise<T> {
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

  async loadPlant(
    id: string,
    options?: { topologyOnly?: boolean },
  ): Promise<{ plant: PlantDef; scenarios: ScenarioDef[] }> {
    if (options?.topologyOnly) {
      // The definition is the topology on its own — no live values, no line
      // state, and no scenarios. Used by surfaces that draw a plant rather than
      // operate one (the hub's card previews).
      const def = await this.req<{ plant: PlantDef }>(`/plants/${id}/definition`);
      return { plant: def.plant, scenarios: [] as ScenarioDef[] };
    }
    // Snapshot carries the full plant definition; scenarios come from the
    // store as well, so the console needs no bundled data copy at all.
    const snap = await this.req<SimSnapshot & { plant: PlantDef }>(`/plants/${id}/snapshot`);
    const scenarios = await this.req<{ scenarios: ScenarioDef[] }>(`/plants/${id}/scenarios`)
      .then((r) => r.scenarios)
      .catch(() => [] as ScenarioDef[]);
    return { plant: snap.plant, scenarios };
  }

  start(id: string) {
    return this.req(`/plants/${id}/start`, { method: "POST" }).then(() => undefined);
  }
  pause(id: string) {
    return this.req(`/plants/${id}/pause`, { method: "POST" }).then(() => undefined);
  }
  async injectFailure(plantId: string, equipmentId: string, modeId: string): Promise<string | null> {
    const r = await this.req<{ incident?: { id?: string } }>(
      `/plants/${plantId}/equipment/${equipmentId}/failure`,
      { method: "POST", body: JSON.stringify({ mode_id: modeId }) },
    );
    return r.incident?.id ?? null;
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
  async blockLine(plantId: string, connectionId: string): Promise<{ incidentId: string | null }> {
    const r = await this.req<{ incident_id?: string | null }>(
      `/plants/${plantId}/lines/${connectionId}/block`,
      { method: "POST" },
    );
    return { incidentId: r.incident_id ?? null };
  }
  restoreLine(plantId: string, connectionId: string) {
    return this.req(`/plants/${plantId}/lines/${connectionId}/restore`, { method: "POST" }).then(() => undefined);
  }
  async leakLine(plantId: string, connectionId: string, leaking: boolean): Promise<{ incidentId: string | null }> {
    const r = await this.req<{ incident_id?: string | null }>(
      `/plants/${plantId}/lines/${connectionId}/leak`,
      { method: "POST", body: JSON.stringify({ leaking }) },
    );
    return { incidentId: r.incident_id ?? null };
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
  frame(plantId: string) {
    return this.req<SimSnapshot>(`/plants/${plantId}/frame`);
  }
  tasks(plantId: string, incidentId: string) {
    return this.req<{ tasks: AgentTask[]; plan: IncidentPlan | null }>(`/plants/${plantId}/incidents/${incidentId}/tasks`);
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

  /**
   * The single live SSE subscription for a plant.
   *
   * The console consumes this through `useSimulation`; it must not open its
   * own EventSource. Connection health is reported out-of-band so the UI can
   * distinguish "no events yet" from "orchestrator not connected".
   *
   * WHY manual reconnect instead of EventSource's built-in one: we need to
   * count *consecutive* failures, and we must keep retrying even after the
   * mock threshold is crossed so a fresh successful connection can clear the
   * banner. `?after=<seq>` makes the replay loss-free across reconnects.
   */
  subscribe(
    plantId: string,
    cb: (ev: SimEvent) => void,
    onStatus?: (status: StreamStatus) => void,
  ): () => void {
    let lastSeq = 0;
    let attempts = 0;
    let es: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let closed = false;
    let connected = false;

    const open = () => {
      if (closed) return;
      onStatus?.({ state: connected ? "live" : "connecting", attempts });
      try {
        es = new EventSource(`${API_BASE}/api/simulation/plants/${plantId}/stream?after=${lastSeq}`);
      } catch (err) {
        scheduleRetry((err as Error).message);
        return;
      }
      es.onopen = () => {
        connected = true;
        attempts = 0;
        // A fresh successful connection is the ONLY thing that clears mock mode.
        onStatus?.({ state: "live", attempts: 0 });
      };
      es.onmessage = (msg) => {
        try {
          const ev = JSON.parse(msg.data) as SimEvent;
          if (typeof ev.seq === "number" && ev.seq > lastSeq) lastSeq = ev.seq;
          cb(ev);
        } catch {
          /* malformed frame */
        }
      };
      es.onerror = () => {
        es?.close();
        es = null;
        scheduleRetry("stream error");
      };
    };

    const scheduleRetry = (detail: string) => {
      if (closed) return;
      attempts += 1;
      if (attempts >= MOCK_RETRY_LIMIT) {
        // Mock mode is a terminal *for this connection*: the banner stays
        // until a real connection succeeds, but we keep retrying below.
        onStatus?.({ state: "mock", attempts, detail: "orchestrator not connected" });
      } else {
        onStatus?.({ state: "connecting", attempts, detail });
      }
      const delay = Math.min(8000, 500 * attempts);
      timer = setTimeout(open, delay);
    };

    open();
    return () => {
      closed = true;
      if (timer) clearTimeout(timer);
      es?.close();
    };
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
