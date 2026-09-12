/**
 * EMBEDDED DEMO ENGINE — the same deterministic simulation semantics as
 * backend/simulation/engine.py, ported line-for-line so Project 117 can be
 * demonstrated with zero infrastructure. Same seed → same plant behavior.
 *
 * This is NOT a fake: it is a real stateful engine (telemetry, propagation,
 * alarms, incidents, agent pipeline, verification) running client-side.
 * When the backend is up, lib/sim/adapter.ts streams the live engine via SSE
 * instead and this module is never constructed.
 */
import { isProcessRelation, relationOf } from "./relations";
import { alternateSensorsFor, declaredRedundancyIds } from "./recovery";
import type {
  AgentEvidence,
  AgentTask,
  Alarm,
  AssetState,
  EquipmentDef,
  Incident,
  IncidentPlan,
  IncidentStatus,
  PlantDef,
  SimEvent,
  SimSnapshot,
  TelemetryQuality,
  ToolCall,
} from "./types";

/** mulberry32 — identical to backend engine._Rng. */
class Rng {
  private s: number;
  constructor(seed: number) {
    this.s = seed >>> 0;
  }
  next(): number {
    this.s = (this.s + 0x6d2b79f5) >>> 0;
    let t = this.s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  uniform(lo: number, hi: number): number {
    return lo + (hi - lo) * this.next();
  }
}

interface EqRt {
  capacity: number;
  state: AssetState;
  faults: Set<string>;
}
interface SensorRt {
  value: number;
  quality: TelemetryQuality;
  failed: boolean;
  drifting: boolean;
}

type Listener = (ev: SimEvent) => void;

export class SimEngine {
  readonly plant: PlantDef;
  /** The deterministic seed this engine was built with. Exposed so a reset can
   *  rebuild an identical twin rather than silently reseeding the plant. */
  readonly seed: number;
  t = 0;
  readonly tickS = 1;
  private rng: Rng;
  private eq = new Map<string, EqRt>();
  private sensors = new Map<string, SensorRt>();
  private sensorModel = new Map<string, PlantDef["equipment"][number]["sensors"][number]>();
  private sensorOwner = new Map<string, string>();
  private byMeas = new Map<string, PlantDef["equipment"][number]["sensors"][number]>();
  private downstream = new Map<string, string[]>();
  private upstream = new Map<string, string[]>();
  private pipesOut = new Map<string, string[]>();
  private pipeById = new Map<string, PlantDef["connections"][number]>();
  alarms = new Map<string, Alarm>();
  incidents = new Map<string, Incident>();
  plans = new Map<string, IncidentPlan>();
  tasks = new Map<string, AgentTask[]>();
  artifacts: Record<string, unknown>[] = [];
  private alarmSeq = 0;
  private incidentSeq = 0;
  private seq = 0;
  private listeners = new Set<Listener>();

  // --- session-only out-of-service state ---------------------------------
  // Operator changes (a sensor taken out of service, a sensor deleted) live
  // here and nowhere else. Nothing is written to the plant definition or to
  // the database, and a page reload builds a brand-new engine from the
  // committed dataset — which is exactly the promise the console makes:
  // "changes are temporary; reloading restores the plant to normal".
  //
  // Deletion is tracked as an overlay rather than by splicing the shared
  // PlantDef, because that object is also read by other views; filtering
  // through one accessor keeps "gone" meaning the same thing everywhere.
  private disabledSensors = new Set<string>();
  private removedSensors = new Set<string>();
  private disabledEquipment = new Set<string>();

  constructor(plant: PlantDef, seed = 117) {
    this.plant = plant;
    this.seed = seed;
    this.rng = new Rng(seed);
    for (const e of plant.equipment) {
      this.eq.set(e.id, { capacity: e.capacity, state: e.state, faults: new Set() });
      for (const s of e.sensors) {
        this.sensors.set(s.id, { value: s.nominal, quality: "good", failed: false, drifting: false });
        this.sensorModel.set(s.id, s);
        this.sensorOwner.set(s.id, e.id);
        if (!this.byMeas.has(`${e.id}:${s.measurement}`)) this.byMeas.set(`${e.id}:${s.measurement}`, s);
      }
    }
    for (const c of plant.connections) {
      this.pipeById.set(c.id, c);
      // Topology follows the RELATION, not the carrier: a process dependency
      // drawn as a control wire still puts the two units in series.
      if (!isProcessRelation(relationOf(c))) continue;
      if (!this.downstream.has(c.source)) this.downstream.set(c.source, []);
      this.downstream.get(c.source)!.push(c.target);
      if (!this.upstream.has(c.target)) this.upstream.set(c.target, []);
      this.upstream.get(c.target)!.push(c.source);
      if (!this.pipesOut.has(c.source)) this.pipesOut.set(c.source, []);
      this.pipesOut.get(c.source)!.push(c.id);
    }
  }

  /** Lifecycle events (public so the adapter doesn't touch privates). */
  markStarted(): void {
    this.emit("simulation.started", { plant: this.plant.id });
  }
  markPaused(): void {
    this.emit("simulation.paused", { plant: this.plant.id });
  }

  onEvent(l: Listener): () => void {
    this.listeners.add(l);
    return () => this.listeners.delete(l);
  }

  private emit(type: string, payload: Record<string, unknown>): void {
    this.seq += 1;
    const ev: SimEvent = { seq: this.seq, plant_id: this.plant.id, type, payload, at: this.t };
    this.listeners.forEach((l) => l(ev));
  }

  // ------------------------------------------------------------------ tick

  tick(): void {
    this.t += this.tickS;
    const flow = this.propagateFlow();
    const readings: { sensor_id: string; value: number; quality: TelemetryQuality }[] = [];
    for (const [sid, rt] of this.sensors) {
      const m = this.sensorModel.get(sid)!;
      if (rt.failed) {
        readings.push({ sensor_id: sid, value: rt.value, quality: "bad" });
        continue;
      }
      const span = m.normal_max - m.normal_min || 1;
      const noise = this.rng.uniform(-m.noise, m.noise) * span;
      const process = this.processFactor(m.equipment_id, m.measurement, flow);
      const drift = rt.drifting ? Math.max(m.drift_rate, span * 0.02) : 0;
      if (!m.is_detector) {
        const revert = rt.drifting ? 0 : (m.nominal - rt.value) * 0.03;
        rt.value = Math.max(0, rt.value + noise + process + drift + revert);
      }
      readings.push({ sensor_id: sid, value: Math.round(rt.value * 1000) / 1000, quality: rt.quality });
    }
    this.emit("telemetry.batch", { t: this.t, readings });
    this.evaluateAlarms();
  }

  private processFactor(eqId: string, measurement: string, flow: Map<string, number>): number {
    const m = this.byMeas.get(`${eqId}:${measurement}`);
    if (!m) return 0;
    const span = m.normal_max - m.normal_min || 1;
    if (measurement === "flow") {
      const f = this.eq.get(eqId)!.capacity * (flow.get(eqId) ?? 1);
      return (f - 1) * span * 0.9;
    }
    if (measurement === "pressure") {
      const ups = this.upstream.get(eqId) ?? [];
      const worst = Math.min(...ups.map((u) => this.eq.get(u)?.capacity ?? 1), 1);
      return (worst - 1) * span * 0.6;
    }
    if (measurement === "temperature") {
      const ups = this.upstream.get(eqId) ?? [];
      const worst = Math.min(...ups.map((u) => this.eq.get(u)?.capacity ?? 1), 1);
      return (1 - worst) * span * 0.35;
    }
    if (measurement === "vibration") {
      const rt = this.eq.get(eqId)!;
      const wear = rt.faults.has("bearing_wear") || rt.faults.has("cavitation") ? 1 : 0;
      return wear * span * 0.5 + (rt.capacity - 1) * span * 0.1;
    }
    if (measurement === "level") {
      const f = flow.get(eqId) ?? 1;
      return (f - 1) * span * 0.7;
    }
    if (measurement === "current" || measurement === "power" || measurement === "rpm") {
      return (this.eq.get(eqId)!.capacity - 1) * span * 0.8;
    }
    return 0;
  }

  private propagateFlow(): Map<string, number> {
    const flow = new Map<string, number>();
    for (const c of this.plant.connections) {
      if (c.kind !== "pipe") continue;
      const src = this.eq.get(c.source);
      const srcCap = src ? src.capacity : 0;
      let pipeCap = !c.enabled || c.status === "disabled" ? 0 : 1;
      if (c.leaking) pipeCap *= 0.55;
      c.flow = Math.round(c.capacity * srcCap * pipeCap * 100) / 100;
      if (c.capacity > 0) {
        const prev = flow.get(c.target) ?? 1;
        flow.set(c.target, Math.min(prev, srcCap * pipeCap));
      }
    }
    return flow;
  }

  private evaluateAlarms(): void {
    const active = new Set<string>();
    for (const [sid, rt] of this.sensors) {
      const m = this.sensorModel.get(sid)!;
      if (rt.quality === "bad" || m.is_detector) continue;
      const v = rt.value;
      let sev: Alarm["severity"] | null = null;
      if (v <= m.critical_min || v >= m.critical_max) sev = "critical";
      else if (v <= m.warning_min || v >= m.warning_max) sev = "warning";
      const aid = `ALM-${sid}`;
      if (sev) {
        if (!this.alarms.has(aid)) {
          this.alarmSeq += 1;
          const alarm: Alarm = {
            id: `${aid}-${this.alarmSeq}`,
            sensor_id: sid,
            tag: m.tag,
            severity: sev,
            message: `${m.tag} ${m.measurement} ${v.toFixed(1)} ${m.unit} outside envelope`,
            at: this.t,
            active: true,
          };
          this.alarms.set(aid, alarm);
          this.emit("alarm.created", { ...alarm });
        }
        active.add(aid);
      }
    }
    for (const aid of [...this.alarms.keys()]) {
      if (!active.has(aid)) {
        this.emit("alarm.cleared", { id: aid, tag: this.alarms.get(aid)!.tag });
        this.alarms.delete(aid);
      }
    }
  }

  // ------------------------------------------------------------- failures

  injectFailure(equipmentId: string, modeId: string): Record<string, unknown> {
    const eq = this.plant.equipment.find((e) => e.id === equipmentId);
    const mode = this.plant.failure_modes.find((m) => m.id === modeId);
    if (!eq || !mode) throw new Error(`unknown equipment ${equipmentId} or mode ${modeId}`);
    const rt = this.eq.get(equipmentId)!;
    const changed: Record<string, unknown> = { equipment_id: equipmentId, mode: modeId, mechanism: mode.mechanism };

    if (mode.mechanism === "sensor") {
      const target = eq.sensors.find((s) => mode.applies_to.includes(s.measurement)) ?? eq.sensors[0];
      if (target) {
        const srt = this.sensors.get(target.id)!;
        srt.failed = true;
        srt.quality = "bad";
        changed.sensor_id = target.id;
        changed.tag = target.tag;
      }
    } else if (mode.mechanism === "drift") {
      const target = eq.sensors.find((s) => mode.applies_to.includes(s.measurement));
      if (target) {
        this.sensors.get(target.id)!.drifting = true;
        changed.sensor_id = target.id;
        changed.tag = target.tag;
      }
    } else if (mode.mechanism === "stop") {
      rt.capacity = 0;
      rt.state = "failed";
    } else if (mode.mechanism === "degrade") {
      rt.capacity = Math.max(0.15, rt.capacity * (1 - mode.magnitude));
      rt.state = "warning";
    } else if (mode.mechanism === "leak") {
      for (const pid of this.pipesOut.get(equipmentId) ?? []) {
        this.pipeById.get(pid)!.leaking = true;
      }
      const det = [...this.sensors.keys()].find((sid) => {
        const m = this.sensorModel.get(sid)!;
        return m.is_detector && this.areaOf(m.equipment_id) === eq.area_id;
      });
      if (det) {
        this.sensors.get(det)!.value = 1;
        changed.detector = this.sensorModel.get(det)!.tag;
      }
    } else if (mode.mechanism === "surge") {
      rt.capacity = Math.min(1.6, rt.capacity * (1 + mode.magnitude));
      rt.state = "warning";
    }

    rt.faults.add(modeId);
    this.emit("fault.injected", changed);
    this.emit("equipment.state_changed", { equipment_id: equipmentId, state: rt.state });
    return changed;
  }

  disableEquipment(equipmentId: string): void {
    const rt = this.eq.get(equipmentId)!;
    rt.capacity = 0;
    rt.state = "disabled";
    this.disabledEquipment.add(equipmentId);
    this.emit("equipment.disabled", { equipment_id: equipmentId });
  }

  removeEquipment(equipmentId: string): string[] {
    const affected = this.downstream.get(equipmentId) ?? [];
    const rt = this.eq.get(equipmentId)!;
    rt.capacity = 0;
    rt.state = "disabled";
    this.disabledEquipment.add(equipmentId);
    for (const c of this.plant.connections) {
      if (c.source === equipmentId || c.target === equipmentId) c.enabled = false;
    }
    this.emit("equipment.removed", { equipment_id: equipmentId, broken_paths: affected });
    return affected;
  }

  // --- sensor out-of-service (session scope) ------------------------------

  /** Whether a sensor is out of service this session, and how. */
  sensorOutOfService(sensorId: string): "disabled" | "removed" | null {
    if (this.removedSensors.has(sensorId)) return "removed";
    if (this.disabledSensors.has(sensorId)) return "disabled";
    return null;
  }

  /** An asset's sensors that still exist — a deleted sensor is genuinely gone. */
  visibleSensors(equipmentId: string) {
    const eq = this.plant.equipment.find((e) => e.id === equipmentId);
    if (!eq) return [];
    return eq.sensors.filter((s) => !this.removedSensors.has(s.id));
  }

  disableSensor(sensorId: string): void {
    const rt = this.sensors.get(sensorId);
    if (!rt) throw new Error(`unknown sensor '${sensorId}'`);
    this.disabledSensors.add(sensorId);
    // An out-of-service transmitter is indistinguishable from a failed one to
    // everything downstream: the value freezes and quality goes bad. That is
    // what the agent pipeline reacts to, so the recovery path it reasons about
    // is the real one and not a UI-only fiction.
    rt.failed = true;
    rt.quality = "bad";
    this.emit("sensor.disabled", {
      sensor_id: sensorId,
      equipment_id: this.sensorOwner.get(sensorId) ?? null,
    });
  }

  removeSensor(sensorId: string): void {
    const rt = this.sensors.get(sensorId);
    if (!rt) throw new Error(`unknown sensor '${sensorId}'`);
    const owner = this.sensorOwner.get(sensorId) ?? null;
    this.removedSensors.add(sensorId);
    this.disabledSensors.delete(sensorId);
    rt.failed = true;
    rt.quality = "bad";
    // Emit the redundancy context now: once the sensor is gone, "what can
    // still measure this point?" is the question the recovery panel answers.
    this.emit("sensor.removed", {
      sensor_id: sensorId,
      equipment_id: owner,
      alternates: this.alternateSensors(sensorId).map((s) => s.id),
    });
  }

  restoreSensor(sensorId: string): void {
    if (this.removedSensors.has(sensorId)) {
      throw new Error(
        `sensor '${sensorId}' was deleted this session; only a plant reset brings it back`,
      );
    }
    if (!this.sensors.has(sensorId)) throw new Error(`unknown sensor '${sensorId}'`);
    this.disabledSensors.delete(sensorId);
    this.repairSensor(sensorId);
    this.emit("sensor.restored", { sensor_id: sensorId });
  }

  /** How many operator changes are live this session (console indicator). */
  sessionChanges(): { disabledSensors: number; removedSensors: number; disabledEquipment: number } {
    return {
      disabledSensors: this.disabledSensors.size,
      removedSensors: this.removedSensors.size,
      disabledEquipment: this.disabledEquipment.size,
    };
  }

  sessionChangeCount(): number {
    const c = this.sessionChanges();
    return c.disabledSensors + c.removedSensors + c.disabledEquipment;
  }

  repairSensor(sensorId: string): void {
    const rt = this.sensors.get(sensorId)!;
    rt.failed = false;
    rt.drifting = false;
    rt.quality = "good";
    rt.value = this.sensorModel.get(sensorId)!.nominal;
  }

  restoreEquipment(equipmentId: string, capacity = 1): void {
    const rt = this.eq.get(equipmentId)!;
    rt.capacity = capacity;
    rt.state = "normal";
    rt.faults.clear();
    for (const c of this.plant.connections) {
      if (c.source === equipmentId || c.target === equipmentId) {
        c.enabled = true;
        c.leaking = false;
      }
    }
    // Reset latched gas/leak detectors in the same area once the leak path is
    // repaired; otherwise verification can never close a `leak` incident.
    // Mirrors backend SimulationEngine.restore_equipment.
    const area = this.areaOf(equipmentId);
    for (const [sid, m] of this.sensorModel) {
      if (m.is_detector && this.areaOf(m.equipment_id) === area) {
        const srt = this.sensors.get(sid)!;
        srt.value = 0;
        srt.quality = "good";
      }
    }
  }

  // ------------------------------------------------------------- topology

  neighbors(equipmentId: string, depth = 2): string[] {
    const seen = new Set([equipmentId]);
    let frontier = [equipmentId];
    const out: string[] = [];
    for (let d = 0; d < depth; d++) {
      const next: string[] = [];
      for (const cur of frontier) {
        for (const nb of [...(this.downstream.get(cur) ?? []), ...(this.upstream.get(cur) ?? [])]) {
          if (!seen.has(nb)) {
            seen.add(nb);
            out.push(nb);
            next.push(nb);
          }
        }
      }
      frontier = next;
    }
    return out;
  }

  /** Explicit REDUNDANCY partners declared in the topology, if any. */
  declaredRedundancy(sensorId: string): string[] {
    return declaredRedundancyIds(this.plant, sensorId);
  }

  /**
   * Instruments that can still read the point `sensorId` was reading.
   *
   * Delegates to the shared pure rule in `recovery.ts` so the engine and the
   * console's recovery panel can never disagree about what a valid fallback is.
   * Sensors that are themselves out of service this session are excluded.
   */
  alternateSensors(sensorId: string) {
    return alternateSensorsFor(this.plant, sensorId, (id) => this.sensorOutOfService(id) !== null).map(
      (a) => a.sensor,
    );
  }

  private areaOf(equipmentId: string): string {
    return this.plant.equipment.find((e) => e.id === equipmentId)?.area_id ?? "";
  }

  // ------------------------------------------------------------- incidents

  createIncident(opts: { title: string; severity: Alarm["severity"]; originEquipment: string; originSensor?: string | null; failureMode?: string | null }): Incident {
    this.incidentSeq += 1;
    const incident: Incident = {
      id: `INC-${1000 + this.incidentSeq}`,
      plant_id: this.plant.id,
      title: opts.title,
      severity: opts.severity,
      status: "detected",
      origin_equipment: opts.originEquipment,
      origin_sensor: opts.originSensor ?? null,
      failure_mode: opts.failureMode ?? null,
      affected: this.neighbors(opts.originEquipment, 2),
      created_at: this.t,
      resolved_at: null,
    };
    this.incidents.set(incident.id, incident);
    this.emit("incident.created", { ...incident });
    return incident;
  }

  /** The deterministic multi-agent pipeline — identical records to backend. */
  runAgentPipeline(incidentId: string): { tasks: AgentTask[]; plan: IncidentPlan } {
    const incident = this.incidents.get(incidentId)!;
    incident.status = "investigating";
    this.emit("incident.updated", { ...incident });

    const tasks: AgentTask[] = [];
    let seq = 0;
    let t = this.t;
    const eq = this.plant.equipment.find((e) => e.id === incident.origin_equipment)!;
    const originSensor = incident.origin_sensor;

    const add = (agent: AgentTask["agent"], title: string, dependsOn: string[] = []): AgentTask => {
      seq += 1;
      t += 1;
      const task: AgentTask = {
        id: `${incident.id}-T${seq}`,
        incident_id: incident.id,
        agent,
        title,
        status: "running",
        started_at: t,
        completed_at: t + 1,
        depends_on: dependsOn,
        tools: [],
        evidence: [],
        result: "",
        sequence: seq,
      };
      tasks.push(task);
      this.emit("agent.task_started", { ...task });
      return task;
    };
    const finish = (task: AgentTask) => {
      task.status = "completed";
      for (const tool of task.tools) this.emit("agent.tool_completed", { task_id: task.id, tool: tool.tool, summary: tool.summary });
      for (const ev of task.evidence) this.emit("agent.evidence_found", { ...ev });
      this.emit("agent.task_completed", { ...task });
    };

    // orchestrator
    const orch = add("orchestrator", "Classify incident and decompose into agent tasks");
    orch.tools.push({ tool: "incident.classify", summary: `${incident.severity} · origin ${eq.tag}`, ok: true });
    orch.evidence.push({ id: `${incident.id}-E0`, source_type: "topology", source_id: eq.id, description: `Blast radius: ${incident.affected.length} linked assets`, confidence: 1 });
    orch.result = `Classified as ${incident.severity} incident on ${eq.tag}; 5 agents tasked.`;
    finish(orch);

    // data analysis
    const da = add("data_analysis", "Validate the failure against related measurements", [orch.id]);
    da.tools.push({ tool: "telemetry.query", summary: `window t-300s..t · ${eq.tag}`, ok: true });
    da.tools.push({ tool: "graph.query", summary: "sensor redundancy + topology walk", ok: true });
    if (originSensor) {
      const alts = this.alternateSensors(originSensor);
      for (const s of alts.slice(0, 4)) {
        const rt = this.sensors.get(s.id)!;
        da.evidence.push({
          id: `${da.id}-E${da.evidence.length + 1}`,
          source_type: "telemetry",
          source_id: s.id,
          description: `${s.tag} = ${rt.value.toFixed(1)} ${s.unit} (${rt.quality})`,
          confidence: rt.quality === "good" ? 0.95 : 0.4,
        });
      }
      const good = alts.filter((a) => this.sensors.get(a.id)!.quality === "good");
      da.result = good.length
        ? `${good.length} alternate measurement(s) consistent — process readable via redundancy.`
        : "No consistent alternate measurement — treat as unreadable process point.";
    } else {
      da.result = "Telemetry pattern matches the injected failure signature.";
    }
    da.tools.push({ tool: "anomaly.detect", summary: da.result, ok: true });
    finish(da);

    // maintenance
    const mt = add("maintenance", "Evaluate failure mode and replacement requirement", [orch.id]);
    mt.tools.push({ tool: "maintenance_history.query", summary: `${eq.tag} · last inspection ${eq.last_inspection}`, ok: true });
    mt.tools.push({ tool: "failure_mode.match", summary: incident.failure_mode ?? "unknown", ok: true });
    mt.evidence.push({ id: `${mt.id}-E1`, source_type: "maintenance", source_id: eq.id, description: `${eq.manufacturer} ${eq.model} · installed ${eq.installed} · inspected ${eq.last_inspection}`, confidence: 1 });
    mt.result = "Component-level fault confirmed; inspection/replacement required.";
    finish(mt);

    // operations
    const op = add("operations", "Evaluate process continuity on degraded instrumentation", [da.id]);
    op.tools.push({ tool: "topology.impact", summary: `${incident.affected.length} assets downstream/upstream`, ok: true });
    for (const aid of incident.affected.slice(0, 4)) {
      const aeq = this.plant.equipment.find((e) => e.id === aid)!;
      const rt = this.eq.get(aid)!;
      op.evidence.push({ id: `${op.id}-E${op.evidence.length + 1}`, source_type: "topology", source_id: aid, description: `${aeq.tag} capacity ${(rt.capacity * 100).toFixed(0)}% · state ${rt.state}`, confidence: 0.9 });
    }
    op.result = originSensor ? "Process can continue under compensating monitoring." : "Production impact under evaluation.";
    finish(op);

    // safety
    const sf = add("safety", "Check safe-operating envelope", [da.id, mt.id]);
    sf.tools.push({ tool: "policy_check", summary: "continued-operation criteria", ok: true });
    const scope = [incident.origin_equipment, ...incident.affected];
    const over = scope.some((eqId) =>
      (this.plant.equipment.find((e) => e.id === eqId)?.sensors ?? []).some((s) => {
        const rt = this.sensors.get(s.id)!;
        return !s.is_detector && rt.quality === "good" && (rt.value >= s.critical_max || rt.value <= s.critical_min);
      }),
    );
    sf.evidence.push({ id: `${sf.id}-E1`, source_type: "policy", source_id: "safe-envelope", description: over ? "CRITICAL envelope violation present" : "No critical envelope violation on readable sensors", confidence: 0.98 });
    sf.result = over ? "Recommend controlled load reduction." : "Continued operation acceptable with monitoring.";
    finish(sf);

    // documentation
    const dc = add("documentation", "Retrieve governing procedures", [orch.id]);
    dc.tools.push({ tool: "retrieve_documents", summary: "instrument maintenance SOP + emergency procedure", ok: true });
    dc.evidence.push({ id: `${dc.id}-E1`, source_type: "documents", source_id: "SOP-14.2", description: "Sensor maintenance + isolation procedure (pages 2–4)", confidence: 0.97 });
    dc.result = "Governing SOPs retrieved and cited.";
    finish(dc);

    // plan
    const planTask = add("orchestrator", "Synthesize response plan", [da.id, mt.id, op.id, sf.id, dc.id]);
    const action: IncidentPlan["action"] = originSensor
      ? { kind: "repair_sensor", target: originSensor }
      : { kind: "restore_equipment", target: incident.origin_equipment };
    const steps = originSensor
      ? [
          `Mark ${this.sensorModel.get(originSensor)!.tag} unavailable (quality=BAD)`,
          "Switch control input to validated alternate measurement",
          "Confirm alternate consistency against flow/vibration correlates",
          "Create sensor replacement recommendation",
          "Continue monitoring; escalate if alternates diverge",
        ]
      : [
          `Stabilize ${eq.tag} and isolate the faulted path`,
          "Confirm downstream pressures/flows return to envelope",
          "Restore capacity in stages with verification at each step",
          "Create maintenance work order with evidence pack",
        ];
    planTask.result = `Plan ready: ${steps.length} steps, approval required before action.`;
    finish(planTask);

    const plan: IncidentPlan = {
      incident_id: incident.id,
      steps,
      requires_approval: true,
      approval_reason: `Action changes plant state (${eq.tag}); evidence pack attached from ${tasks.length - 1} agent tasks.`,
      action,
      verification: [
        "Alternate/primary measurement consistency within 2%",
        "No active critical alarms on affected assets",
        "Downstream flow stable for 10 consecutive ticks",
      ],
    };
    this.tasks.set(incident.id, tasks);
    this.plans.set(incident.id, plan);
    incident.status = "awaiting_approval";
    this.emit("incident.updated", { ...incident });
    this.emit("approval.required", {
      incident_id: incident.id,
      action: plan.action,
      reason: plan.approval_reason,
      steps: plan.steps,
      risk: "medium",
    });
    return { tasks, plan };
  }

  /** Human decision → action → observe → verify → artifact + audit. */
  decide(incidentId: string, approved: boolean, observe: () => void): { status: IncidentStatus; verified: boolean; findings: string[] } {
    const incident = this.incidents.get(incidentId)!;
    const plan = this.plans.get(incidentId)!;
    this.emit(approved ? "approval.granted" : "approval.rejected", { incident_id: incidentId });
    if (!approved) {
      incident.status = "escalated";
      this.emit("incident.updated", { ...incident });
      return { status: incident.status, verified: false, findings: [] };
    }
    incident.status = "acting";
    this.emit("incident.updated", { ...incident });
    if (plan.action.kind === "repair_sensor") this.repairSensor(plan.action.target);
    else if (plan.action.kind === "restore_equipment") this.restoreEquipment(plan.action.target);
    else if (plan.action.kind === "reduce_load") {
      const rt = this.eq.get(plan.action.target)!;
      rt.capacity = Math.max(0.4, rt.capacity * 0.8);
    }
    this.emit("action.completed", { ...plan.action });

    incident.status = "verifying";
    this.emit("verification.started", { incident_id: incidentId });
    // observation window: up to 12 real ticks, early exit when settled
    let ok = false;
    let findings: string[] = [];
    for (let i = 0; i < 12; i++) {
      observe();
      [ok, findings] = this.verify(incident);
      if (ok) break;
    }
    this.emit("verification.completed", { incident_id: incidentId, ok, findings });

    if (ok) {
      incident.status = "resolved";
      incident.resolved_at = this.t;
      const artifact = {
        id: `ART-${incident.id}`,
        kind: "incident_report",
        filename: `incident_${incident.id.toLowerCase()}.pdf`,
        verified: true,
        sources: (this.tasks.get(incident.id) ?? []).length,
        created_at: this.t,
      };
      this.artifacts.push(artifact);
      this.emit("artifact.created", artifact);
      this.emit("incident.resolved", { ...incident });
      this.emit("audit.recorded", { incident_id: incidentId, actor: "operator", action: "incident.resolved" });
    } else {
      incident.status = "investigating";
      this.emit("incident.updated", { ...incident });
    }
    return { status: incident.status, verified: ok, findings };
  }

  verify(incident: Incident): [boolean, string[]] {
    const findings: string[] = [];
    let ok = true;
    const scope = [incident.origin_equipment, ...incident.affected];
    for (const eqId of scope) {
      const eq = this.plant.equipment.find((e) => e.id === eqId);
      if (!eq) continue;
      for (const s of eq.sensors) {
        const rt = this.sensors.get(s.id)!;
        if (rt.quality === "bad" && incident.origin_sensor === s.id) continue;
        if (s.is_detector) {
          // Latched 0/1 detectors: healthy == 0. Only a tripped detector is a
          // finding — the two-sided envelope test failed every untripped
          // gas/leak detector in the blast radius. Mirrors backend verify_plan.
          if (rt.value >= s.critical_max) {
            findings.push(`${s.tag} detector tripped (${rt.value.toFixed(1)} ${s.unit})`);
            ok = false;
          }
          continue;
        }
        if (rt.value >= s.critical_max || rt.value <= s.critical_min) {
          findings.push(`${s.tag} still beyond critical envelope (${rt.value.toFixed(1)} ${s.unit})`);
          ok = false;
        }
      }
    }
    const crit = [...this.alarms.values()].filter((a) => a.severity === "critical");
    if (crit.length) {
      findings.push(`${crit.length} critical alarm(s) active`);
      ok = false;
    }
    if (!findings.length) findings.push("All affected assets inside envelope; no critical alarms.");
    return [ok, findings];
  }

  // ------------------------------------------------------------- snapshots

  snapshot(): SimSnapshot {
    const equipment: SimSnapshot["equipment"] = {};
    for (const [id, r] of this.eq) {
      if (r.state !== "normal" || r.capacity !== 1) {
        equipment[id] = { state: r.state, capacity: r.capacity, faults: [...r.faults] };
      }
    }
    const sensors: SimSnapshot["sensors"] = {};
    for (const [id, r] of this.sensors) {
      // A deleted sensor is absent from telemetry, not merely zeroed — the
      // snapshot is what every live view renders from.
      if (this.removedSensors.has(id)) continue;
      sensors[id] = { value: r.value, quality: r.quality, failed: r.failed };
    }
    return {
      t: this.t,
      equipment,
      sensors,
      alarms: [...this.alarms.values()],
      incidents: [...this.incidents.values()],
    };
  }

  /** Live-read helpers for the renderer (no React state needed per tick). */
  sensorValue(sensorId: string): { value: number; quality: TelemetryQuality } {
    const rt = this.sensors.get(sensorId);
    // Renderers may still hold a stale reference for one frame after a delete;
    // report bad quality rather than throwing mid-paint.
    if (!rt) return { value: 0, quality: "bad" };
    return { value: rt.value, quality: rt.quality };
  }
  equipmentState(equipmentId: string): { state: AssetState; capacity: number } {
    const rt = this.eq.get(equipmentId)!;
    return { state: rt.state, capacity: rt.capacity };
  }
}
