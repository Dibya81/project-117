"use client";

/**
 * Plant twin screen — the primary demonstration environment.
 * TOP: identity · sim clock · health · alarms · workforce. CENTER: sweeping
 * left-to-right spatial process map (live telemetry pills, anomaly pulses and
 * an animated agent investigation link). LEFT: areas + scenarios. RIGHT:
 * equipment / plant context. BOTTOM: event spine.
 *
 * Every pixel of state comes from the engine via events — nothing here
 * invents telemetry. The spatial map's stages are the plant's own areas and
 * its pills are the plant's own sensors read from the live snapshot.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Button, EmptyState, Panel, Ring, SkeletonRows, StatusDot, Tag } from "@/components/ui/primitives";
import { Icon } from "@/components/ui/Icon";
import {
  SchematicCanvas,
  emptyRuntime,
  runtimeFromEngine,
  type CanvasRuntime,
  type SpatialReading,
} from "@/components/sim/SchematicCanvas";
import { AgentCommandCenter } from "@/components/sim/AgentCommandCenter";
import { AssessmentPanel } from "@/components/sim/AssessmentPanel";
import { AgentResponseConsole } from "@/components/sim/AgentResponseConsole";
import { AgentDispatchBoxes } from "@/components/sim/AgentDispatchBoxes";
import {
  RecoveryExperience,
  RecoveryDock,
  AGENT_PANEL_DISMISS_MS,
  AGENT_PANEL_NO_DECISION_DISMISS_MS,
  type DecisionView,
} from "@/components/sim/RecoveryExperience";
import { ProcessMap, type ProcessMapSelection } from "@/components/sim/ProcessMap";
import { MeridianRefineryView } from "@/components/sim/MeridianRefineryView";
import { EquipmentRenderer, normalizeEquipmentAsset, preferredAssetSize } from "@/components/equipment";
import { SimulationConsole, buildSensorRows, type SimView } from "@/components/sim/SimulationConsole";
import { PlantLowerDeck } from "@/components/sim/PlantLowerDeck";
import {
  SensorsPanel,
  EquipmentPanel,
  ControlPanel,
  ScenariosPanel,
  IncidentsPanel,
  AgentsPanel,
} from "@/components/sim/SimulationViews";
import { SensorRecoveryPanel, type RecoveryFocus } from "@/components/sim/SensorRecoveryPanel";
import { simAdapter, asEmbedded } from "@/lib/sim/adapter";
import { useSimulation } from "@/lib/sim/store";
import { reduceResponseJobs } from "@/lib/sim/response";
import { useJourney } from "@/lib/journey";
import { useRouter } from "next/navigation";
import { consoleData } from "@/lib/data/console";
import { api } from "@/lib/api";
import { recoveryCircuit } from "@/lib/sim/recovery";
import type { AgentTask, EquipmentDef, PlantDef, ScenarioDef, SensorDef, SimSnapshot } from "@/lib/sim/types";
import "@/styles/plant.css";

/**
 * One reset per plant for the lifetime of this page load.
 *
 * Stores the PROMISE, not a boolean. React 18 StrictMode invokes effects twice
 * in development, and a boolean flag set *before* the request finished let the
 * second invocation skip the reset and read the plant definition while the
 * first reset was still in flight — which is exactly how a deleted sensor came
 * back still missing after a reload. Awaiting the shared promise removes the
 * race, so the definition is only ever read once the plant is pristine.
 *
 * A full browser reload re-evaluates this module, so the map starts empty and
 * the plant is reset — which is what makes operator changes temporary. A
 * client-side navigation keeps the module alive, so work in progress survives
 * moving between console pages; only a reload discards it.
 */
const plantReset = new Map<string, Promise<void>>();

function PlantEquipmentAsset({ equipment, status, selected = true }: { equipment: EquipmentDef; status?: string; selected?: boolean }) {
  const asset = normalizeEquipmentAsset(equipment.kind, equipment.name, equipment.tag);
  const preferred = preferredAssetSize[asset];
  const scale = Math.min(210 / preferred.w, 160 / preferred.h);
  const box = {
    x: (236 - preferred.w * scale) / 2,
    y: (178 - preferred.h * scale) / 2 + 4,
    w: preferred.w * scale,
    h: preferred.h * scale,
  };
  return (
    <svg className="pt-selected-asset" viewBox="0 0 236 196" role="img" aria-label={`${equipment.tag} ${equipment.name}`}>
      <EquipmentRenderer asset={asset} kind={equipment.kind} name={equipment.name} id={equipment.tag} status={status ?? equipment.state ?? "healthy"} selected={selected} box={box} />
    </svg>
  );
}

function ensurePlantIsFresh(plantId: string): Promise<void> {
  const inFlight = plantReset.get(plantId);
  if (inFlight) return inFlight;
  const started = simAdapter.resetPlant(plantId).catch(() => undefined);
  plantReset.set(plantId, started);
  return started;
}


/** §38 SIMULATION HEALTH INDICATOR — documented heuristic, not a validated model. */
function plantHealth(plant: PlantDef, runtime: CanvasRuntime, alarmCount: number): number {
  const faulted = Object.values(runtime.states).filter((s) => s === "failed" || s === "critical").length;
  const warned = Object.values(runtime.states).filter((s) => s === "warning").length;
  const h = 100 - faulted * 18 - warned * 6 - alarmCount * 2.5;
  return Math.max(0, Math.min(100, Math.round(h)));
}

function fmtClock(t: number): string {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `T+${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function eventDetail(ev: { type: string; payload: Record<string, unknown> }): string {
  const p = ev.payload;
  if (ev.type === "fault.injected") return `${p.tag ?? p.equipment_id} · ${String(p.mode).replace(/_/g, " ")}`;
  if (ev.type === "incident.created") return String(p.title ?? "incident");
  if (ev.type === "agent.task_started" || ev.type === "agent.task_completed") return String(p.title ?? p.agent ?? "");
  if (ev.type === "agent.evidence_found") return String(p.description ?? "");
  if (ev.type === "alarm.created") return String(p.message ?? "alarm");
  if (ev.type === "approval.required") return "response plan awaiting human decision";
  if (ev.type === "artifact.created") return String(p.filename ?? "artifact");
  if (ev.type === "verification.completed") return p.ok ? "all gates passed" : "failed — orchestrator continues";
  return ev.type;
}

const EVENT_TONE: Record<string, string> = {
  "incident.created": "var(--red)",
  "fault.injected": "var(--amber)",
  "alarm.created": "var(--amber)",
  "approval.required": "var(--amber)",
  "approval.granted": "var(--green)",
  "verification.completed": "var(--green)",
  "incident.resolved": "var(--green)",
  "artifact.created": "var(--violet)",
};

export default function PlantTwinPage() {
  const params = useParams<{ id: string }>();
  const plantId = decodeURIComponent(params.id);
  /**
   * The oil refinery is the live control-room view: one locked camera on the
   * whole circuit, no zoom, no pan. Other plants (and the builder) keep the
   * navigable canvas.
   */
  const liveFixedCamera = plantId === "refinery";
  const { visit } = useJourney();
  const router = useRouter();

  const [plant, setPlant] = useState<PlantDef | null>(null);
  const [scenarios, setScenarios] = useState<ScenarioDef[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<EquipmentDef | null>(null);
  const [hovered, setHovered] = useState<EquipmentDef | null>(null);
  const [areaFocus, setAreaFocus] = useState<string | null>(null);
  const [runtime, setRuntime] = useState<CanvasRuntime | null>(null);
  /**
   * Role → model, from the gateway. The dispatch boxes name the model that is
   * actually serving each role rather than labelling an agent generically.
   */
  const [modelRoles, setModelRoles] = useState<Record<string, string | null>>({});
  /**
   * View mode of the plant.
   * `overview` is the Meridian flagship visual digital twin;
   * `3d` is the 3D isometric cutaway;
   * `pipeline` is the vector P&ID;
   * `schematic` is the swept stage view.
   */
  const [viewMode, setViewMode] = useState<"overview" | "3d" | "pipeline" | "schematic">("overview");
  const [pipeSel, setPipeSel] = useState<ProcessMapSelection | null>(null);
  const [activeView, setActiveView] = useState<SimView>("process");
  /** The line an action is currently in flight for, and any error it returned. */
  const [busyLine, setBusyLine] = useState<string | null>(null);
  const [lineError, setLineError] = useState<string | null>(null);
  const [busySensor, setBusySensor] = useState<string | null>(null);

  const [snap, setSnap] = useState<SimSnapshot | null>(null);
  const [busyScenario, setBusyScenario] = useState<string | null>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  // Session-only sensor state. Deliberately NOT persisted anywhere: the plant
  // definition is never mutated, so a reload re-reads the committed dataset and
  // the plant returns to normal. This overlay is what every view filters
  // through, so "removed" means the same thing on the map, in this list, and in
  // the recovery panel.
  const [sensorState, setSensorState] = useState<Record<string, "disabled" | "removed">>({});
  const [recovery, setRecovery] = useState<RecoveryFocus | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  /** Unit-level disable/remove, counted so the session chip tells the truth. */
  const [equipmentChanges, setEquipmentChanges] = useState(0);

  // Agent Response Console: opened by a real fault injection, bucketed by the
  // incident id the backend returned (never guessed from event shape).
  const [consoleOpen, setConsoleOpen] = useState(false);
  const [consoleJobId, setConsoleJobId] = useState<string | null>(null);
  const [focusEquipmentId, setFocusEquipmentId] = useState<string | null>(null);

  const sim = useSimulation(plant ? plantId : null);
  const embedded = asEmbedded(simAdapter);

  /**
   * Test/dev override for the no-response timeout (ms). Defaults to 20s; a
   * `?stepTimeout=` query param only shortens it so the stalled-step state can
   * be exercised without waiting. It never lengthens or invents state.
   */
  const stepTimeoutMs = useMemo(() => {
    if (typeof window === "undefined") return 20_000;
    const raw = new URLSearchParams(window.location.search).get("stepTimeout");
    const parsed = raw ? Number(raw) : NaN;
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 20_000;
  }, []);

  /** Every concurrent response job, bucketed by the event's own job id. */
  const responseJobs = useMemo(() => reduceResponseJobs(sim.events), [sim.events]);
  const activeResponseJob = useMemo(() => {
    if (!responseJobs.length) return null;
    return responseJobs.find((j) => j.jobId === consoleJobId) ?? responseJobs[responseJobs.length - 1];
  }, [responseJobs, consoleJobId]);
  const predictedIds = useMemo(
    () => activeResponseJob?.prediction.map((p) => p.equipmentId) ?? [],
    [activeResponseJob],
  );

  const decisionFromEvent = useCallback((ev: (typeof sim.events)[number]): DecisionView => {
    const p = ev.payload as Record<string, unknown>;
    const list = (k: string) => (Array.isArray(p[k]) ? (p[k] as unknown[]).map(String) : []);
    return {
      incidentId: p.incident_id ? String(p.incident_id) : p.job_id ? String(p.job_id) : null,
      available: p.available === true,
      model: p.model ? String(p.model) : null,
      error: p.error ? String(p.error) : null,
      diagnosis: String(p.diagnosis ?? ""),
      route: list("route"),
      block: list("block"),
      restore: list("restore"),
      safety_confirmed: p.safety_confirmed === true,
      safety_concerns: list("safety_concerns"),
      rationale: String(p.rationale ?? ""),
      // Per-agent outcome as the backend recorded it. The type requires this,
      // the payload has always carried it, and it was simply not mapped — so a
      // panel could not tell a role that completed from one that never ran.
      agent_status:
        p.agent_status && typeof p.agent_status === "object"
          ? Object.fromEntries(
              Object.entries(p.agent_status as Record<string, unknown>).map(([k, v]) => [k, String(v)]),
            )
          : {},
    };
  }, []);

  const [openIncidentId, setOpenIncidentId] = useState<string | null>(null);
  /**
   * Incidents whose docked agent rail the operator has dismissed. Keyed by
   * incident id so a new incident's rail still appears, while a rail the
   * operator closed stays closed for the run it belonged to.
   */
  const [dismissedDocks, setDismissedDocks] = useState<Set<string>>(new Set());
  /**
   * The incident the plant itself is concerned with: the newest one the stream
   * has produced. Every top-level overlay and every compact summary is keyed to
   * it, so a finished incident's route can never bleed into the next incident.
   */
  const currentIncident = useMemo(
    () => (sim.incidents.length ? sim.incidents[sim.incidents.length - 1] : null),
    [sim.incidents],
  );
  // The stream replays from seq 0, so on load `sim.incidents` already contains
  // every past incident. Only incidents that appear *after* the first render
  // should take over the screen — otherwise opening the page pops the panel for
  // an incident that finished before the operator arrived. An incident that is
  // still running when the operator arrives does take over, because it is not.
  const seenIncidentIds = useRef<Set<string> | null>(null);

  /**
   * Whether the fault's isolation has actually been painted.
   *
   * The panel opens on `agent.started`, which the backend emits a few
   * milliseconds after `incident.created` — both can land in one SSE flush, so
   * React would commit the isolation and the panels in the same frame and the
   * operator would never see which chamber failed before the AI took the screen.
   *
   * This is a **paint barrier, not a delay**: `requestAnimationFrame` fires when
   * the browser is about to paint, so it guarantees the isolated section is on
   * screen. No duration is invented and nothing waits on a clock.
   */
  const [isolationPainted, setIsolationPainted] = useState(false);

  /**
   * Incidents whose agents have actually been dispatched.
   *
   * The three-agent panel opens on `agent.started`, NOT when the incident row
   * appears and NOT when the disable request returns. The order the operator
   * must see is: the sensor goes out of service, the affected chamber isolates
   * and its flow stops, and only then does the AI take the screen. Opening on
   * the incident opened the panels in the same frame as the fault, so the
   * drawing's isolation was never visible — the agents appeared to be reacting
   * to a plant that had not changed yet.
   */
  const startedIncidents = useMemo(() => {
    const ids = new Set<string>();
    for (const e of sim.events) {
      if (e.type !== "agent.started") continue;
      const p = e.payload as Record<string, unknown>;
      const id = String(p.incident_id ?? p.job_id ?? "");
      if (id) ids.add(id);
    }
    return ids;
  }, [sim.events]);

  useEffect(() => {
    const seen = seenIncidentIds.current;
    if (seen === null) {
      seenIncidentIds.current = new Set(sim.incidents.map((i) => i.id));
      // A page opened while an incident is already running still shows it, but
      // only once its agents exist — otherwise the panel would describe a run
      // that has not started.
      const running = [...sim.incidents]
        .reverse()
        .find((i) => i.status !== "resolved" && i.status !== "escalated" && startedIncidents.has(i.id));
      if (running) setOpenIncidentId(running.id);
      return;
    }
    const fresh = sim.incidents.filter((i) => !seen.has(i.id) && startedIncidents.has(i.id));
    if (!fresh.length) return;
    // Do not cover the plant until the failure itself is on screen.
    if (!isolationPainted) return;
    for (const i of fresh) seen.add(i.id);
    // A new sensor failure starts its own recovery. If a burst carries more
    // than one, the newest is the one the operator must deal with.
    setOpenIncidentId(fresh[fresh.length - 1].id);
  }, [sim.incidents, startedIncidents, isolationPainted]);
  const recoveryIncident = useMemo(
    () => sim.incidents.find((i) => i.id === openIncidentId) ?? null,
    [sim.incidents, openIncidentId],
  );

  /**
   * The validated recovery decision for one incident, read straight from the
   * `response.decision` event emitted for that incident id. It never falls back
   * to another incident's decision: a decision belongs to exactly the incident
   * that produced it, so incident B cannot inherit incident A's route.
   */
  const decisionForIncident = useCallback(
    (incidentId: string | null): DecisionView | null => {
      if (!incidentId) return null;
      const ev = [...sim.events].reverse().find((e) => {
        if (e.type !== "response.decision") return false;
        const p = e.payload as Record<string, unknown>;
        return String(p.incident_id ?? p.job_id ?? "") === incidentId;
      });
      return ev ? decisionFromEvent(ev) : null;
    },
    [sim.events, decisionFromEvent],
  );

  /** The decision the full-screen three-agent experience is showing. */
  const openDecision = useMemo(
    () => decisionForIncident(openIncidentId),
    [decisionForIncident, openIncidentId],
  );

  /**
   * The decision the PLANT reflects: the current incident's own decision.
   *
   * The topology overlay, the wiring state and the three compact summaries all
   * read this, so the plant and the summaries always describe the same real
   * incident — the latest one — and never a mixture of two.
   */
  const plantDecision = useMemo(
    () => decisionForIncident(currentIncident?.id ?? null),
    [decisionForIncident, currentIncident?.id],
  );

  /**
   * The plant's own state, as the operator reads it. `recovered` is a fact about
   * the last incident — it resolved and its verified decision is what the
   * drawing is showing — not a timer's opinion.
   */
  const recovered =
    !sim.activeIncident &&
    currentIncident?.status === "resolved" &&
    plantDecision?.available === true &&
    plantDecision.safety_confirmed === true;
  const plantState = sim.activeIncident ? "responding" : recovered ? "recovered" : "running";

  /**
   * The canvas runtime with the failover and verified topology overlays
   * applied. Both overlays are copied from backend events and decision ids:
   * no local path or connection id is invented here.
   */
  /**
   * The ISOLATION the plant is showing, taken from the backend's own
   * `sensor.disabled` event.
   *
   * This is what makes the fault visible *before* any agent speaks. The event
   * carries the origin asset and the exact set of assets the lost measurement
   * touched (`affected`), so the drawing can isolate precisely those and stop
   * their flow — no more, no less. Nothing here is inferred from a timer or a
   * placeholder: if the backend did not say an asset is affected, it is not
   * drawn as affected.
   *
   * It is cleared when the incident it belongs to ends, at which point the
   * verified decision owns the drawing.
   */
  const isolation = useMemo(() => {
    const incident = currentIncident;
    if (!incident || incident.status === "resolved" || incident.status === "escalated") return null;
    // The incident record itself carries the origin asset and the exact blast
    // radius the engine computed. Reading it here rather than from the
    // `sensor.disabled` event is deliberate: that event names only the sensor,
    // and it does not exist at all for an injected fault or a blocked line —
    // this way every incident isolates the right section.
    const equipmentIds = new Set<string>();
    if (incident.origin_equipment) equipmentIds.add(incident.origin_equipment);
    for (const id of incident.affected ?? []) equipmentIds.add(id);
    if (!equipmentIds.size) return null;
    // Every line that touches an isolated asset is out of service, because a
    // chamber with a stopped process cannot be feeding or drawing through it.
    const connectionIds = (plant?.connections ?? [])
      .filter((c) => equipmentIds.has(c.source) || equipmentIds.has(c.target))
      .map((c) => c.id);
    return { incidentId: incident.id, equipmentIds: [...equipmentIds], connectionIds };
  }, [currentIncident, plant?.connections]);

  useEffect(() => {
    if (!isolation) {
      setIsolationPainted(false);
      return;
    }
    const raf = requestAnimationFrame(() => setIsolationPainted(true));
    return () => cancelAnimationFrame(raf);
  }, [isolation]);

  const displayRuntime = useMemo(() => {
    if (!runtime) return runtime;
    const sensorId = activeResponseJob?.failover?.relatedSensorId;
    const next: CanvasRuntime = {
      ...runtime,
      // `states` must be copied too: the isolation below writes into it, and
      // writing through the shared reference would corrupt the runtime the
      // store polls.
      states: { ...runtime.states },
      qualities: { ...runtime.qualities },
      pipes: Object.fromEntries(Object.entries(runtime.pipes).map(([id, pipe]) => [id, { ...pipe }])),
    };
    // Immediate isolation, applied before any decision exists.
    if (isolation) {
      for (const id of isolation.equipmentIds) next.states[id] = "failed" as CanvasRuntime["states"][string];
      for (const id of isolation.connectionIds) {
        if (!next.pipes[id]) continue;
        next.pipes[id] = { ...next.pipes[id], enabled: false, flow: 0, leaking: false };
      }
    }
    if (sensorId && runtime.qualities[sensorId]) {
      next.qualities[sensorId] = "substituted" as const;
    }
    if (plantDecision?.available && plantDecision.safety_confirmed) {
      // The decision's own block/restore sets are what the drawing follows once
      // the agents have spoken. Note the restore loop below only opens lines the
      // decision named; a line isolated by the fault and NOT named in `restore`
      // stays shut, which is the honest reading of the route.
      const known = new Set(plant?.connections.map((c) => c.id) ?? []);
      for (const id of plantDecision.block) {
        if (!known.has(id) || !next.pipes[id]) continue;
        next.pipes[id] = { ...next.pipes[id], enabled: false, flow: 0 };
      }
      for (const id of plantDecision.restore) {
        if (!known.has(id) || !next.pipes[id]) continue;
        const base = plant?.connections.find((c) => c.id === id);
        next.pipes[id] = { ...next.pipes[id], enabled: true, leaking: false, flow: Math.max(next.pipes[id].flow ?? 0, base?.flow ?? 0, 8) };
      }
    }
    return next;
  }, [runtime, activeResponseJob, plantDecision, plant?.connections, isolation]);

  /**
   * The three-agent view opens on a new incident and stays up after it resolves
   * so the outcome is readable.
   *
   * Keyed on the incident id rather than `sim.activeIncident`: a fast incident
   * can open and close between two store polls, and watching the "active" flag
   * meant the view never appeared at all. `sim.incidents` keeps every incident
   * the log has seen, including resolved ones, so the panel still has an
   * incident to render once it is over.
   */
  /**
   * Return to the plant once the agents have answered.
   *
   * The countdown starts on the DECISION — the backend's `response.decision`
   * event for this incident, which is the real "all three agents have returned"
   * signal. It is NOT started by a frontend timer and it is NOT started by the
   * incident's start or its resolution: a recovery executes and verifies long
   * after the models reply, so those would hold the panel for a duration that
   * has nothing to do with the agents.
   *
   * The clock is triggered by the decision event ARRIVING, not by it being
   * usable. A run where Operations could not find a valid route
   * (`available === false`, "ROUTING FAILED") has still finished — all three
   * agents have answered — and the operator needs the plant back, with the three
   * results docked on the right. Holding a failed run open forever also meant the
   * panel never closed on the common validator-rejected path.
   *
   * The flag is a primitive, not the incident object: `sim.incidents` is rebuilt
   * on every store publish, and depending on the incident object would restart
   * the countdown on each poll so it could never elapse. The effect re-runs only
   * when the decision first arrives, or the open incident changes.
   */
  const openDecisionArrived = openDecision !== null;
  const openIncidentStatus = recoveryIncident?.status ?? null;

  // The clock starts here, on `response.decision` — usable or not. Once it has
  // arrived this effect does not re-run while the same incident stays open, so
  // the 20 s is a single uninterrupted countdown. Switching incident clears it,
  // so a countdown that belonged to one incident can never close another.
  useEffect(() => {
    if (!openIncidentId || !openDecisionArrived) return;
    const t = setTimeout(() => setOpenIncidentId(null), AGENT_PANEL_DISMISS_MS);
    return () => clearTimeout(t);
  }, [openIncidentId, openDecisionArrived]);

  // A run that ended (resolved / escalated) with NO decision at all has nothing
  // for the panel to show. Fall back to a short hold and return to the plant
  // rather than hanging open forever. (The countdown above covers every case
  // where a decision did arrive.)
  useEffect(() => {
    if (!openIncidentId || openDecisionArrived) return;
    if (openIncidentStatus !== "resolved" && openIncidentStatus !== "escalated") return;
    const t = setTimeout(() => setOpenIncidentId(null), AGENT_PANEL_NO_DECISION_DISMISS_MS);
    return () => clearTimeout(t);
  }, [openIncidentId, openDecisionArrived, openIncidentStatus]);

  /**
   * Forget rail dismissals when a fresh runtime boots.
   *
   * The engine's incident ids are a per-runtime counter (`INC-1001`,
   * `INC-1002`, …), so a reset restarts them. Without this, dismissing the rail
   * for `INC-1001`, resetting the plant and raising a new first incident would
   * leave the new run's rail suppressed because it happens to share the old id.
   */
  const bootSeq = useRef<number | null>(null);
  useEffect(() => {
    const boot = [...sim.events].reverse().find((e) => e.type === "simulation.started");
    if (!boot || bootSeq.current === boot.seq) return;
    bootSeq.current = boot.seq;
    setDismissedDocks(new Set());
  }, [sim.events]);

  /**
   * Run the agents' decision once the evidence pack is in.
   *
   * The backend computes the RecoveryDecision on approval, so the console
   * grants it as soon as the orchestrator has dispatched the tasks — otherwise
   * the demo would stall on a button and the agents would never reach the
   * model. Guarded per incident so it fires exactly once.
   */
  const decidedRef = useRef<Set<string>>(new Set());
  /** How many times a decision request has been retried for an incident. */
  const decideAttempts = useRef<Map<string, number>>(new Map());

  /**
   * Re-run the three agents for an incident whose decision was unusable.
   *
   * The local model sometimes returns a route the validator rejects (or JSON it
   * cannot parse). The plant is left untouched, which is correct — but the
   * incident would otherwise sit open with no way forward. This asks the same
   * three agents again; nothing is fabricated and the decision is still the
   * model's.
   */
  const retryDecision = useCallback(
    (incidentId: string) => {
      decidedRef.current.delete(incidentId);
      decideAttempts.current.set(incidentId, 0);
      void simAdapter.decide(plantId, incidentId, true).catch(() => undefined);
    },
    [plantId],
  );
  useEffect(() => {
    const inc = sim.activeIncident;
    if (!inc || sim.tasks.length === 0) return;
    if (decidedRef.current.has(inc.id)) return;
    if (sim.events.some((e) => {
      if (e.type !== "response.decision") return false;
      const p = e.payload as Record<string, unknown>;
      return String(p.incident_id ?? p.job_id ?? "") === inc.id;
    })) return;
    decidedRef.current.add(inc.id);
    // A rejected decision request (e.g. a 5xx) must not strand the incident in
    // awaiting_approval with no console feedback. Retry a bounded number of
    // times, then leave it to the operator.
    void simAdapter.decide(plantId, inc.id, true).catch(() => {
      const attempts = (decideAttempts.current.get(inc.id) ?? 0) + 1;
      decideAttempts.current.set(inc.id, attempts);
      if (attempts < 3) decidedRef.current.delete(inc.id);
    });
  }, [sim.activeIncident, sim.tasks.length, sim.events, plantId]);

  // load dataset + boot engine
  useEffect(() => {
    let live = true;
    setPlant(null);
    setRuntime(null);
    setSensorState({});
    setEquipmentChanges(0);
    setRecovery(null);
    (async () => {
      // Reset BEFORE reading the definition, never after.
      //
      // In live mode the snapshot carries the plant definition itself, and
      // taking a sensor out of service mutates that definition in the running
      // engine. Reading first cached the mutated plant, so a deleted sensor
      // stayed missing after a reload even though the backend was already
      // restored. The ordering — and awaiting the shared reset promise — is the
      // fix; see `ensurePlantIsFresh`.
      await ensurePlantIsFresh(plantId);
      const { plant, scenarios } = await simAdapter.loadPlant(plantId);
      if (!live) return;
      setPlant(plant);
      setScenarios(scenarios);
      setRuntime(emptyRuntime(plant));
      await simAdapter.start(plantId);
      visit({ id: plant.id, label: plant.name, kind: "equipment", href: `/console/simulation/plant/${plant.id}` });
    })().catch((e) => setLoadError(String(e)));
    return () => {
      live = false;
      timers.current.forEach(clearTimeout);
    };
  }, [plantId, visit]);

  /**
   * Role → model for the dispatch boxes, from the gateway. Read once: the
   * mapping changes when an operator reassigns a role, not per tick.
   */
  useEffect(() => {
    let alive = true;
    api.models
      .status()
      .then((r: Record<string, unknown>) => {
        if (alive) setModelRoles((r.roles as Record<string, string | null>) ?? {});
      })
      .catch(() => {
        /* no role map: the boxes say "model unassigned" rather than name one */
      });
    return () => {
      alive = false;
    };
  }, []);

  /**
   * The engine's own tick, not the store's refresh cadence.
   *
   * `sim.tick` bumps at the store's 4 Hz projection rate, but the engine only
   * advances `sim.t` once per simulation tick (1 Hz by default). Depending on
   * `sim.tick` therefore fetched the plant state four times per engine tick and
   * three of those four replies were byte-identical — 507 KB/s of traffic, 90%
   * of it the static plant definition, for data that could not have changed.
   *
   * Depending on the engine's clock fetches exactly when the state can differ.
   */
  const engineTick = Math.floor(sim.t);
  useEffect(() => {
    if (!plant) return;
    let live = true;
    if (embedded) {
      setRuntime(runtimeFromEngine(plant, embedded.engine(plantId)));
    } else {
      // `frame`, not `snapshot`: the definition is already in `plant`, so only
      // the changing state is fetched (~26 KB rather than ~127 KB).
      simAdapter.frame(plantId).then(s => {
        if (!live) return;
        setSnap(s);
        const base = emptyRuntime(plant);
        for (const [id, st] of Object.entries(s.equipment)) {
          base.states[id] = st.state as any;
        }
        for (const [id, sx] of Object.entries(s.sensors)) {
          base.qualities[id] = sx.quality as any;
        }
        // The engine's live line state, not the static definition — the
        // definition never carries a running rate, so reading it here left
        // every line animating at zero flow.
        const pipeState = s.connections;
        for (const c of plant.connections) {
          const l = pipeState?.[c.id];
          base.pipes[c.id] = l
            ? { leaking: l.leaking, enabled: l.enabled, flow: l.flow }
            : { leaking: c.leaking, enabled: c.enabled, flow: c.flow };
        }
        setRuntime(base);
      }).catch(() => undefined);
    }
    return () => { live = false; };
  }, [plant, plantId, embedded, engineTick]);

  const onSelect = useCallback((eq: EquipmentDef) => setSelected(eq), []);
  const onHover = useCallback((eq: EquipmentDef | null) => setHovered(eq), []);

  const inject = async (equipmentId: string, modeId: string) => {
    // The backend returns the incident id — that is the job id every response
    // event is bucketed under, so the console never has to guess which run it
    // is watching.
    const incidentId = await simAdapter
      .injectFailure(plantId, equipmentId, modeId)
      .catch(() => null);
    setConsoleOpen(true);
    if (incidentId) setConsoleJobId(incidentId);
    setFocusEquipmentId(equipmentId);
  };

  /** Whether a sensor is out of service this session, and how. */
  const sensorOut = useCallback(
    (id: string): "disabled" | "removed" | null => sensorState[id] ?? null,
    [sensorState],
  );

  /** Sensors of an asset that still exist — a deleted sensor is genuinely gone. */
  const visibleSensors = useCallback(
    (eq: EquipmentDef) => eq.sensors.filter((s) => sensorOut(s.id) !== "removed"),
    [sensorOut],
  );

  const sessionChangeCount = Object.keys(sensorState).length + equipmentChanges;

  /**
   * Take a sensor out of service or delete it, then open the recovery panel on
   * the circuit that lost the measurement.
   *
   * The agents are engaged for real: the adapters raise an incident carrying
   * this sensor id, which is what makes the engine's redundancy reasoning run
   * against the point that was actually lost. The panel renders those tasks.
   */
  const actOnSensor = async (
    eq: EquipmentDef,
    sensor: SensorDef,
    action: "disable" | "remove",
  ) => {
    setActionError(null);
    // 1. Update sensor visual state immediately — no waiting
    setSensorState((m) => ({ ...m, [sensor.id]: action === "disable" ? "disabled" : "removed" }));

    // 2. Computed against the CURRENT overlay so a sensor already out of service
    // cannot be offered as its own fallback.
    const circuit = plant
      ? recoveryCircuit(plant, sensor.id, (id) => Boolean(sensorState[id]))
      : null;

    // 3. Set recovery panel immediately so UI responds instantly
    setRecovery({
      sensorId: sensor.id,
      sensorTag: sensor.tag,
      measurement: sensor.measurement,
      unit: sensor.unit,
      equipmentTag: eq.tag,
      action,
      circuit,
      tasks: [],
      planSteps: [],
    });

    try {
      const res =
        action === "disable"
          ? await simAdapter.disableSensor(plantId, sensor.id)
          : await simAdapter.removeSensor(plantId, sensor.id);

      // The full-screen three-agent experience is NOT opened here. The backend
      // has only just begun dispatching; opening now would cover the plant with
      // agent panels before the operator has seen which chamber isolated. It
      // opens from the `agent.started` event instead (see the effect above).
      // The isolation overlay needs nothing from this response either — it is
      // derived from the `sensor.disabled` event the backend emitted.
      void res;
    } catch (e) {
      setActionError(`${action === "disable" ? "Disable" : "Delete"} failed: ${String(e)}`);
    }
  };

  const restoreSensor = async (sensorId: string) => {
    setActionError(null);
    try {
      await simAdapter.restoreSensor(plantId, sensorId);
      setSensorState((m) => {
        const next = { ...m };
        delete next[sensorId];
        return next;
      });
      setRecovery(null);
    } catch (e) {
      setActionError(`Return to service failed: ${String(e)}`);
    }
  };

  /** Discard every change made this session and rebuild from the definition. */
  const resetPlant = async () => {
    setActionError(null);
    try {
      await simAdapter.resetPlant(plantId);
      setSensorState({});
      setEquipmentChanges(0);
      setRecovery(null);
      setSelected(null);
    } catch (e) {
      setActionError(`Reset failed: ${String(e)}`);
    }
  };

  const runScenario = (sc: ScenarioDef) => {
    setBusyScenario(sc.id);
    sc.steps.forEach((st) => {
      timers.current.push(
        setTimeout(() => {
          void simAdapter.injectFailure(plantId, st.target, st.mode).then((incidentId) => {
            setConsoleOpen(true);
            if (incidentId) setConsoleJobId(incidentId);
            setFocusEquipmentId(st.target);
          });
          if (st === sc.steps[sc.steps.length - 1]) setBusyScenario(null);
        }, Math.max(0, st.at_s) * 1000),
      );
    });
  };

  const health = useMemo(
    () => (plant && runtime ? plantHealth(plant, runtime, sim.alarms) : 100),
    [plant, runtime, sim.alarms],
  );

  /** The map may be narrowed to a single process area. */
  const displayPlant = useMemo(() => {
    if (!plant) return null;
    // Deleted sensors are stripped from the definition the canvas renders, so
    // they are genuinely gone from the schematic rather than merely hidden from
    // one list.
    const strip = (e: EquipmentDef): EquipmentDef => ({
      ...e,
      sensors: e.sensors.filter((s) => sensorOut(s.id) !== "removed"),
    });
    const inArea = areaFocus ? plant.equipment.filter((e) => e.area_id === areaFocus) : plant.equipment;
    if (!areaFocus) return { ...plant, equipment: inArea.map(strip) };
    return {
      ...plant,
      equipment: inArea.map(strip),
      connections: plant.connections.filter((c) => {
        const s = plant.equipment.find((e) => e.id === c.source);
        const t = plant.equipment.find((e) => e.id === c.target);
        return s?.area_id === areaFocus || t?.area_id === areaFocus;
      }),
    };
  }, [plant, areaFocus, sensorOut]);

  /** sensorId → live reading, straight from the snapshot / engine. */
  const readings = useMemo(() => {
    const out: Record<string, SpatialReading> = {};
    if (!plant) return out;
    if (embedded) {
      const eng = embedded.engine(plantId);
      for (const e of plant.equipment) {
        for (const s of e.sensors) {
          const v = eng.sensorValue(s.id);
          out[s.id] = { value: v.value, quality: v.quality };
        }
      }
    } else if (snap) {
      for (const [id, s] of Object.entries(snap.sensors)) {
        out[id] = { value: s.value, quality: s.quality };
      }
    }
    return out;
  }, [plant, plantId, embedded, snap]);
  /** Instrument rows for the Sensors view, from the same readings the map uses. */
  const sensorRows = useMemo(
    () => (plant ? buildSensorRows(plant, displayRuntime ?? null, readings) : []),
    [plant, displayRuntime, readings],
  );


  /**
   * The unit the agent investigation is about: the incident's origin/affected
   * asset when one is live, otherwise the first unit the engine has flagged.
   */
  const anomalyId = useMemo(() => {
    if (!plant || !runtime) return null;
    const inc = sim.activeIncident;
    if (inc) {
      const ids = [inc.origin_equipment, ...(inc.affected ?? [])];
      const hit = ids.find((id) => id && plant.equipment.some((e) => e.id === id));
      if (hit) return hit;
    }
    const bad = plant.equipment.find((e) => {
      const st = runtime.states[e.id];
      return st === "warning" || st === "critical" || st === "failed";
    });
    return bad?.id ?? null;
  }, [plant, runtime, sim.activeIncident]);

  const anomalyUnit = useMemo(
    () => (plant && anomalyId ? plant.equipment.find((e) => e.id === anomalyId) ?? null : null),
    [plant, anomalyId],
  );


  /**
   * Raise a work order from the live incident. This writes a real record into
   * the console data adapter, so it appears on /console/work-orders and
   * resolves on its own detail route — it is not a toast.
   */
  const createWorkOrder = async (incident: NonNullable<typeof sim.activeIncident>) => {
    const unit = plant?.equipment.find((e) => e.id === incident.origin_equipment);
    const rec = await consoleData.workOrders.create({
      title: `Investigate ${unit?.tag ?? incident.origin_equipment} — ${incident.title}`,
      equipment_id: incident.origin_equipment,
      priority: incident.severity === "critical" ? "urgent" : "high",
      assignee: "maintenance-agent",
    });
    router.push(`/console/work-orders/${rec.id}`);
  };

  if (loadError) {
    return <EmptyState title="Plant failed to load" detail={loadError} action={<Button onClick={() => location.reload()}>Retry</Button>} />;
  }

  if (!plant || !runtime || !displayPlant || !displayRuntime) {
    return (
      <Panel>
        <SkeletonRows rows={8} label="Commissioning plant…" />
      </Panel>
    );
  }

  const selectedRt = selected ? (embedded ? embedded.engine(plantId).equipmentState(selected.id) : snap?.equipment[selected.id]) : null;

  return (
    <div className={`pt-page${consoleOpen ? " pt-page--console-open" : ""}`}>
      {/* The three-agent experience takes the whole screen while an incident is
          open. Every panel is fed by the backend event stream; closing it just
          returns to the plant, the incident keeps running either way. */}
      {recoveryIncident && (
        <RecoveryExperience
          events={sim.events}
          incident={recoveryIncident}
          decision={openDecision}
          plantName={plant.name}
          onClose={() => setOpenIncidentId(null)}
          onRetry={() => retryDecision(recoveryIncident.id)}
        />
      )}

      {/* After the full view closes, the three agents' results stay docked on
          the right as one compact card per agent, so the operator keeps the
          outcome in view while watching the plant. Dismissible per incident. */}
      {!recoveryIncident &&
        plantDecision &&
        !(plantDecision.incidentId && dismissedDocks.has(plantDecision.incidentId)) && (
          <RecoveryDock
            decision={plantDecision}
            events={sim.events}
            onDismiss={() => {
              const id = plantDecision.incidentId;
              if (!id) return;
              setDismissedDocks((prev) => new Set(prev).add(id));
            }}
          />
        )}

      {/* TOP BAR */}
      <div className="cs-pagehead pt-pagehead" data-plant-state={plantState}>
        <div>
          <span className="cs-pagehead__kicker">
            Simulation / {plant.industry} · <span className="cs-text-ember">SYNTHETIC DEMONSTRATION PLANT</span>
          </span>
          <h1 style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            {plant.name}
            <Tag tone={sim.activeIncident ? (sim.activeIncident.severity === "critical" ? "crit" : "warn") : "ok"}>
              {sim.activeIncident ? sim.activeIncident.status.replace(/_/g, " ") : recovered ? "recovered" : "running"}
            </Tag>
          </h1>
        </div>
        <div className="cs-pagehead__actions" style={{ marginLeft: "auto", alignItems: "center" }}>
          <span className="cs-mono cs-dim" style={{ fontSize: 11 }}>{fmtClock(sim.t)}</span>
          <span className="cs-mono" style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 7 }}>
            <StatusDot state={sim.alarms > 0 ? "warning" : "ok"} pulse={sim.alarms > 0} />
            {sim.alarms} alarm{sim.alarms === 1 ? "" : "s"}
          </span>
          <span className="cs-mono" style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 7 }}>
            <StatusDot state="ai" pulse={Boolean(sim.activeIncident)} />
            {sim.activeIncident ? "agents engaged" : "agents idle"}
          </span>
          {sessionChangeCount > 0 && (
            <button
              className="sm-sessionchip"
              onClick={() => void resetPlant()}
              title="Every change here is temporary — reset now, or reload the page to restore the plant."
            >
              <Icon name="refresh" size={10} />
              {sessionChangeCount} change{sessionChangeCount === 1 ? "" : "s"} · reset
            </button>
          )}
          <Ring value={health} size={44} tone={health > 80 ? "ok" : health > 55 ? "warn" : "crit"} label="simulation health indicator" />
          <Button variant="ghost" onClick={() => void simAdapter.pause(plantId)}>
            <Icon name="pause" size={12} /> Pause
          </Button>
          <Button variant="primary" onClick={() => void simAdapter.start(plantId)}>
            <Icon name="play" size={12} /> Run
          </Button>
        </div>
      </div>

      {/* The console and the record panels span the full page width. They used
          to sit inside the two-column layout, which squeezed the tab row into a
          236px cell and clipped the panels at a fixed height. */}
      <SimulationConsole
        plant={plant}
        runtime={displayRuntime ?? runtime}
        readings={readings}
        alarms={sim.alarms}
        health={health}
        activeView={activeView}
        onView={setActiveView}
        incidentSeverity={sim.activeIncident?.severity ?? null}
        incidentStatus={sim.activeIncident?.status ?? null}
      />

      {activeView === "process" && (
      <div className="pt-layout">
        {/* LEFT — context, areas, scenarios. The rail holds everything the map
            does not need, so the spatial map keeps the whole remaining width. */}
        <div className="pt-rail">
          {selected ? (
            <Panel title={`${selected.tag} — ${selected.name}`} pad>
              <PlantEquipmentAsset equipment={selected} status={selectedRt?.state ?? selected.state ?? "normal"} />
              <div style={{ display: "flex", flexDirection: "column", gap: 0, marginBottom: 12 }}>
                <div className="sm-kv"><span className="cs-dim">Type</span><b>{selected.kind}</b></div>
                <div className="sm-kv"><span className="cs-dim">State</span>
                  <b style={{ color: selectedRt && selectedRt.state !== "normal" ? "var(--amber)" : "var(--green)" }}>
                    {selectedRt?.state ?? "normal"} · {(100 * (selectedRt?.capacity ?? 1)).toFixed(0)}% capacity
                  </b>
                </div>
                <div className="sm-kv"><span className="cs-dim">Manufacturer</span><b>{selected.manufacturer} {selected.model}</b></div>
                <div className="sm-kv"><span className="cs-dim">Installed</span><b className="cs-mono">{selected.installed}</b></div>
                <div className="sm-kv"><span className="cs-dim">Last inspection</span><b className="cs-mono">{selected.last_inspection}</b></div>
                <div className="sm-kv"><span className="cs-dim">Criticality</span><b>{"●".repeat(selected.criticality)}{"○".repeat(3 - selected.criticality)}</b></div>
              </div>

              <p className="cs-dim" style={{ margin: "0 0 10px", fontSize: 10.5, lineHeight: 1.5 }}>
                Take a sensor <b>out of service</b> — or inject a failure below — to raise a real
                incident and engage the Diagnostic, Operations and Safety agents.
              </p>

              <p className="cs-mono cs-dim" style={{ margin: "0 0 8px", fontSize: 9, letterSpacing: "0.26em", textTransform: "uppercase" }}>
                Live sensors · {visibleSensors(selected).length}
              </p>
              {visibleSensors(selected).map((s) => {
                const out = sensorOut(s.id);
                const v = out ? undefined : embedded ? embedded.engine(plantId).sensorValue(s.id) : snap?.sensors[s.id];
                const q = out === "disabled" ? "bad" : v?.quality ?? "good";
                return (
                  <div key={s.id} className={`sm-sensorrow${out ? " is-down" : ""}`}>
                    <StatusDot state={q === "bad" ? "critical" : "ok"} pulse={q === "bad"} />
                    <span className="cs-mono">{s.tag}</span>
                    <span className="cs-dim" style={{ fontSize: 10 }}>{s.measurement}</span>
                    {out === "disabled" ? (
                      <span className="sm-sensorrow__flag">out of service</span>
                    ) : (
                      <span className="sm-sensorrow__val" style={{ color: q === "bad" ? "var(--red)" : "var(--ink-1)" }}>
                        {q === "bad" ? "BAD QUALITY" : `${v?.value.toFixed(1)} ${s.unit}`}
                      </span>
                    )}
                    <span className="sm-sensorrow__acts">
                      {out === "disabled" ? (
                        <button
                          className="sm-sensorbtn"
                          title={`Return ${s.tag} to service`}
                          aria-label={`Return ${s.tag} to service`}
                          onClick={() => void restoreSensor(s.id)}
                        >
                          <Icon name="play" size={10} />
                        </button>
                      ) : (
                        <>
                          <button
                            className="sm-sensorbtn"
                            title={`Take ${s.tag} out of service and engage the agents`}
                            aria-label={`Take ${s.tag} out of service`}
                            onClick={() => void actOnSensor(selected, s, "disable")}
                          >
                            <Icon name="pause" size={10} />
                          </button>
                          <button
                            className="sm-sensorbtn sm-sensorbtn--danger"
                            title={`Delete ${s.tag}`}
                            aria-label={`Delete ${s.tag}`}
                            onClick={() => void actOnSensor(selected, s, "remove")}
                          >
                            <Icon name="x" size={10} />
                          </button>
                        </>
                      )}
                    </span>
                  </div>
                );
              })}
              {visibleSensors(selected).length < selected.sensors.length && (
                <p className="cs-mono cs-dim" style={{ fontSize: 9.5, margin: "7px 0 0", letterSpacing: "0.1em" }}>
                  {selected.sensors.length - visibleSensors(selected).length} sensor(s) deleted this
                  session — reset the plant to restore them.
                </p>
              )}

              <p className="cs-mono cs-dim" style={{ margin: "14px 0 8px", fontSize: 9, letterSpacing: "0.26em", textTransform: "uppercase" }}>
                Inject failure · engages agents
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                {selected.failure_modes.map((fm) => {
                  const mode = plant.failure_modes.find((m) => m.id === fm);
                  return (
                    <button key={fm} className="sm-scenario" onClick={() => inject(selected.id, fm)} title={mode?.description}>
                      <Icon name="alert" size={12} /> {mode?.name ?? fm}
                    </button>
                  );
                })}
              </div>

              <p className="cs-mono cs-dim" style={{ margin: "14px 0 6px", fontSize: 8.5, letterSpacing: "0.2em", textTransform: "uppercase" }}>
                Plant state · no agent response
              </p>
              <div style={{ display: "flex", gap: 8 }}>
                <Button
                  variant="ghost"
                  style={{ flex: 1, justifyContent: "center" }}
                  onClick={() => {
                    // Plant-state action only. A disabled unit is not something
                    // the agents can auto-recover (the action policy requires
                    // manual intervention), so this deliberately does not raise
                    // an incident — the hint above the controls says which
                    // actions do.
                    void simAdapter.disable(plantId, selected.id);
                    setEquipmentChanges((n) => n + 1);
                  }}
                >
                  <Icon name="pause" size={12} /> Disable unit
                </Button>
                <Button
                  variant="reject"
                  style={{ flex: 1, justifyContent: "center" }}
                  onClick={() => {
                    void simAdapter.remove(plantId, selected.id);
                    setEquipmentChanges((n) => n + 1);
                    setSelected(null);
                  }}
                >
                  <Icon name="x" size={12} /> Remove
                </Button>
              </div>
            </Panel>
          ) : (
            <Panel title="Plant context" pad>
              <p style={{ margin: 0, fontSize: 12.5, color: "var(--ink-2)", lineHeight: 1.65 }}>
                Select any asset on the map to inspect its live sensors, metadata and
                failure modes — or run a scenario from the left panel. When an incident
                occurs, the <b>Agent Investigation</b> panel slides in over the map and
                links straight to the affected unit.
              </p>
              <div className="cs-chips" style={{ marginTop: 14 }}>
                <span className="cs-chip" style={{ cursor: "default" }}>{plant.equipment.length} equipment</span>
                <span className="cs-chip" style={{ cursor: "default" }}>{plant.equipment.reduce((n, e) => n + e.sensors.length, 0)} sensors</span>
                <span className="cs-chip" style={{ cursor: "default" }}>{plant.connections.length} connections</span>
              </div>
              <p className="cs-mono cs-dim" style={{ fontSize: 9.5, marginTop: 16, letterSpacing: "0.14em" }}>
                TRANSPORT: {simAdapter.transport.toUpperCase()} · SEED 117 · TICK 1s
              </p>
            </Panel>
          )}

          <Panel title="Process areas" pad={false}>
            <button className={`sm-area${areaFocus === null ? " is-active" : ""}`} onClick={() => setAreaFocus(null)}>
              <Icon name="layers" size={13} /> Whole plant
              <span className="sm-area__count">{plant.equipment.length}</span>
            </button>
            {plant.areas.map((a) => {
              const count = plant.equipment.filter((e) => e.area_id === a.id).length;
              return (
                <button key={a.id} className={`sm-area${areaFocus === a.id ? " is-active" : ""}`} onClick={() => setAreaFocus(a.id === areaFocus ? null : a.id)}>
                  <Icon name="equipment" size={13} /> {a.name}
                  <span className="sm-area__count">{count}</span>
                </button>
              );
            })}
          </Panel>

          <Panel title="Scenarios" pad>
            <p className="cs-dim" style={{ margin: "0 0 10px", fontSize: 11, lineHeight: 1.5 }}>
              Deterministic fault scripts — same engine, real propagation.
            </p>
            {scenarios.map((sc) => (
              <button key={sc.id} className="sm-scenario" onClick={() => runScenario(sc)} disabled={busyScenario !== null} title={sc.description}>
                <Icon name="zap" size={12} />
                {sc.name}
              </button>
            ))}
          </Panel>
        </div>

        {/* CENTER — the sweeping spatial process map */}

        {activeView === "process" && (
        <section className="pt-mapwrap">
          <div className="pt-maphead">
            <span className="cs-panel__title">Live process map</span>
            <div className="pt-viewtoggle" role="tablist" aria-label="Map view">
              {plantId === "refinery" && (
                <>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={viewMode === "overview"}
                    className={viewMode === "overview" ? "is-active" : undefined}
                    onClick={() => setViewMode("overview")}
                  >
                    Overview
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={viewMode === "3d"}
                    className={viewMode === "3d" ? "is-active" : undefined}
                    onClick={() => setViewMode("3d")}
                  >
                    3D View
                  </button>
                </>
              )}
              <button
                type="button"
                role="tab"
                aria-selected={viewMode === "pipeline"}
                className={viewMode === "pipeline" ? "is-active" : undefined}
                onClick={() => setViewMode("pipeline")}
              >
                P&amp;ID
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={viewMode === "schematic"}
                className={viewMode === "schematic" ? "is-active" : undefined}
                onClick={() => setViewMode("schematic")}
              >
                Areas
              </button>
            </div>
            {/* Process areas as a compact strip. They used to occupy a
                236px column, which took a third of the width from the plant
                for a list that is really a filter. */}
            <div className="pt-areastrip" role="tablist" aria-label="Process areas">
              <button
                type="button"
                role="tab"
                aria-selected={areaFocus === null}
                className={areaFocus === null ? "is-active" : undefined}
                onClick={() => setAreaFocus(null)}
              >
                Whole plant <em>{plant.equipment.length}</em>
              </button>
              {plant.areas.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  role="tab"
                  aria-selected={areaFocus === a.id}
                  className={areaFocus === a.id ? "is-active" : undefined}
                  data-area-chip={a.id}
                  onClick={() => setAreaFocus(areaFocus === a.id ? null : a.id)}
                >
                  {a.name}
                </button>
              ))}
            </div>

            <div className="pt-legend">
              <span><i className="is-ok" /> normal</span>
              <span><i className="is-warn" /> warning</span>
              <span><i className="is-crit" /> critical</span>
            </div>
            <div className="pt-maphead__stats">
              <span className="cs-mono cs-dim" style={{ fontSize: 9, letterSpacing: "0.16em" }}>
                {displayPlant.equipment.length} UNITS · {displayPlant.connections.length} LINKS · 4 HZ
              </span>
            </div>
          </div>
          <div className="pt-mapbody">
            {viewMode === "overview" || viewMode === "3d" ? (
              <>
              <MeridianRefineryView
                plant={displayPlant}
                runtime={displayRuntime}
                readings={readings}
                selected={selected}
                onSelectEquipment={onSelect}
                viewMode={viewMode === "3d" ? "3d" : "overview"}
                onViewModeChange={(m) => {
                  if (m === "pid") setViewMode("pipeline");
                  else setViewMode(m as "overview" | "3d");
                }}
                failover={
                  activeResponseJob?.failover
                    ? {
                        from: activeResponseJob.failover.fromEquipmentId,
                        to: activeResponseJob.failover.relatedEquipmentId,
                      }
                    : null
                }
                activeIncident={sim.activeIncident}
                tasks={sim.tasks}
                models={modelRoles}
                recoveryDecision={plantDecision}
                isolatedLines={isolation?.connectionIds ?? []}
                isolatedEquipment={isolation?.equipmentIds ?? []}
                fixedCamera={liveFixedCamera}
              />
              {/* The three agent panels float over every drawing. They were only
                  mounted on the P&ID branch, so disabling a transmitter in the
                  default overview raised a real incident and the agents really
                  ran — but nothing appeared on screen to say so. */}
              <AgentDispatchBoxes tasks={sim.tasks} models={modelRoles} />
              </>
            ) : viewMode === "pipeline" ? (
              <>
              <ProcessMap
                plant={displayPlant}
                runtime={displayRuntime}
                readings={readings}
                /* One selection across the whole page: a line picked on the
                   drawing, or an asset picked from a list, both land here. */
                selection={pipeSel ?? (selected ? { kind: "equipment", id: selected.id } : null)}
                onSelect={(sel) => {
                  setPipeSel(sel);
                  if (sel?.kind === "equipment") {
                    const eq = displayPlant.equipment.find((e) => e.id === sel.id);
                    if (eq) onSelect(eq);
                  } else if (sel === null) {
                    setSelected(null);
                  }
                }}
                highlight={sim.activeIncident ? [sim.activeIncident.origin_equipment, ...(sim.activeIncident.affected ?? [])].filter(Boolean) as string[] : []}
                isolateArea={areaFocus}
                focusId={focusEquipmentId}
                busyLine={busyLine}
                lineError={lineError}
                onLineAction={async (lineId, action) => {
                  setBusyLine(lineId);
                  setLineError(null);
                  try {
                    if (action === "block") await simAdapter.blockLine(plantId, lineId);
                    else if (action === "restore") await simAdapter.restoreLine(plantId, lineId);
                    else await simAdapter.leakLine(plantId, lineId, action === "leak");
                  } catch (e) {
                    setLineError(e instanceof Error ? e.message : String(e));
                  } finally {
                    setBusyLine(null);
                  }
                }}
                failover={
                  activeResponseJob?.failover
                    ? {
                        from: activeResponseJob.failover.fromEquipmentId,
                        to: activeResponseJob.failover.relatedEquipmentId,
                      }
                    : null
                }
                recoveryDecision={plantDecision}
                isolatedLines={isolation?.connectionIds ?? []}
                isolatedEquipment={isolation?.equipmentIds ?? []}
                fixedCamera={liveFixedCamera}
              />
              {/* The three agent panels float over whichever drawing is shown,
                  so the P&ID is not a lesser view. */}
              <AgentDispatchBoxes tasks={sim.tasks} models={modelRoles} />
              </>
            ) : (
            <>
            <SchematicCanvas
              layout="spatial"
              plant={displayPlant}
              runtime={displayRuntime}
              selectedId={selected?.id ?? null}
              affected={sim.activeIncident?.affected ?? []}
              onSelect={onSelect}
              onHover={onHover}
              onBackground={() => setSelected(null)}
              readings={readings}
              anomalyId={anomalyId}
              panelOpen={Boolean(anomalyId)}
              failover={
                activeResponseJob?.failover
                  ? {
                      from: activeResponseJob.failover.fromEquipmentId,
                      to: activeResponseJob.failover.relatedEquipmentId,
                    }
                  : null
              }
              predictedIds={predictedIds}
              focusId={focusEquipmentId}
            >
              {/* Three floating panels: which model is working, in what role,
                  what it is doing and what it found. Rendered only when the
                  pipeline has actually raised tasks. */}
              <AgentDispatchBoxes tasks={sim.tasks} models={modelRoles} />
              <div className="pt-invhead">
                <span className="pt-invhead__kicker">
                  {sim.activeIncident ? "Agent investigation · live" : "Anomaly detected"}
                </span>
                <span className="pt-invhead__unit">
                  {anomalyUnit ? `${anomalyUnit.tag} — ${anomalyUnit.name}` : "Plant telemetry"}
                </span>
                <span className="pt-invhead__sub">
                  {anomalyUnit ? `${anomalyUnit.kind} · ${anomalyUnit.area_id}` : "monitoring"}
                </span>
              </div>
              {sim.activeIncident ? (
                <>
                  <AgentCommandCenter
                    incident={sim.activeIncident}
                    tasks={sim.tasks}
                    plan={sim.plan}
                    now={sim.t}
                    onDecide={(approved) => void simAdapter.decide(plantId, sim.activeIncident!.id, approved)}
                  />
                  {/* Root cause and prediction appear once the agents have
                      actually produced tasks — never on a timer. */}
                  {snap && sim.tasks.length > 0 && (
                    <AssessmentPanel
                      plant={plant}
                      snapshot={snap}
                      incident={sim.activeIncident}
                      tasks={sim.tasks}
                      onCreateWorkOrder={() => void createWorkOrder(sim.activeIncident!)}
                      onViewEvidence={() => router.push("/console/history")}
                    />
                  )}
                </>
              ) : anomalyUnit ? (
                <>
                  <p className="pt-idle" style={{ marginBottom: 10 }}>
                    Live readings outside their configured band on this unit. The agent
                    pipeline opens here as soon as an incident is raised.
                  </p>
                  {anomalyUnit.sensors.map((s) => {
                    const r = readings[s.id];
                    const bad = r?.quality === "bad";
                    return (
                      <div key={s.id} className="sm-sensorrow">
                        <StatusDot state={bad ? "critical" : "ok"} pulse={bad} />
                        <span className="cs-mono">{s.tag}</span>
                        <span className="cs-dim" style={{ fontSize: 10 }}>{s.measurement}</span>
                        <span className="sm-sensorrow__val" style={{ color: bad ? "var(--red)" : "var(--ink-1)" }}>
                          {bad ? "BAD QUALITY" : r ? `${r.value.toFixed(2)} ${s.unit}` : "—"}
                        </span>
                      </div>
                    );
                  })}
                </>
              ) : (
                <p className="pt-idle">
                  No active anomaly. Telemetry is inside its configured bands across all
                  {` ${displayPlant.equipment.length} `}units — the map stays unobstructed
                  until a unit needs investigation.
                </p>
              )}
            </SchematicCanvas>
            {hovered && (
              <div className="pt-hover">
                <div className="pt-hover__tag">{hovered.tag}</div>
                <div className="pt-hover__name">{hovered.name}</div>
                <div className="pt-hover__meta">
                  {hovered.sensors.length} sensors · {hovered.failure_modes.length} failure modes
                </div>
              </div>
            )}
            </>
            )}
          </div>
        </section>
        )}
      </div>
      )}

          {activeView === "sensors" && (
            <SensorsPanel
              rows={sensorRows}
              runtime={displayRuntime ?? null}
              plant={plant}
              onFocus={(sensorId) => {
                const eq = plant.equipment.find((e) => e.sensors.some((x) => x.id === sensorId));
                if (eq) {
                  onSelect(eq);
                  setFocusEquipmentId(eq.id);
                  setActiveView("process");
                }
              }}
            />
          )}

          {activeView === "equipment" && (
            <EquipmentPanel
              plant={plant}
              runtime={displayRuntime ?? null}
              onFocus={(id) => {
                const eq = plant.equipment.find((e) => e.id === id);
                if (eq) {
                  onSelect(eq);
                  setFocusEquipmentId(id);
                  setActiveView("process");
                }
              }}
            />
          )}

          {/* One tab, both panels. The navigation label is "Control &
              Scenarios"; a single control panel left the scenario list
              unreachable, so the scenarios the engine can actually run are
              shown beside the loops they act on. */}
          {activeView === "control" && (
            <div className="simtwo">
              <ControlPanel plant={plant} runtime={displayRuntime ?? null} readings={readings} />
              <ScenariosPanel
                scenarios={scenarios}
                running={busyScenario}
                onRun={(id) => {
                  const sc = scenarios.find((x) => x.id === id);
                  if (sc) runScenario(sc);
                }}
              />
            </div>
          )}

          {activeView === "scenarios" && (
            <ScenariosPanel
              scenarios={scenarios}
              running={busyScenario}
              onRun={(id) => {
                const sc = scenarios.find((x) => x.id === id);
                if (sc) runScenario(sc);
              }}
            />
          )}

          {activeView === "incidents" && (
            <IncidentsPanel
              incidents={sim.incidents}
              plant={plant}
              onFocus={(id) => {
                const eq = plant.equipment.find((e) => e.id === id);
                if (eq) {
                  onSelect(eq);
                  setFocusEquipmentId(id);
                  setActiveView("process");
                }
              }}
            />
          )}

          {activeView === "agents" && <AgentsPanel tasks={sim.tasks} models={modelRoles} now={sim.t} />}

      {/* LOWER DECK — selected asset, live streams, recent events */}
      <PlantLowerDeck
        plant={plant}
        runtime={displayRuntime ?? null}
        readings={readings}
        selected={selected}
        events={sim.events}
        onSelectEquipment={onSelect}
        onSelectLine={(id) => setPipeSel({ kind: "pipe", id })}
        selectedLineId={pipeSel?.kind === "pipe" ? pipeSel.id : null}
        busySensor={busySensor}
        busyFault={busyScenario}
        onInjectFault={(equipmentId, modeId) => void inject(equipmentId, modeId)}
        onSensorAction={(sensorId, action) => {
          const eq = plant.equipment.find((e) => e.sensors.some((x) => x.id === sensorId));
          const sensor = eq?.sensors.find((x) => x.id === sensorId);
          if (!eq || !sensor) return;
          setBusySensor(sensorId);
          const run =
            action === "disable" ? actOnSensor(eq, sensor, "disable") : restoreSensor(sensorId);
          void run.finally(() => setBusySensor(null));
        }}
      />

      {/* BOTTOM — event spine */}
      <div className="pt-spine">
        <div className="pt-spine__head">
          <span className="cs-panel__title">Event spine</span>
          <span className="cs-mono cs-dim" style={{ fontSize: 9, letterSpacing: "0.18em" }}>
            {sim.events.length} EVENTS · LIVE
          </span>
        </div>
        <div className="sm-events">
          {[...sim.events].reverse().slice(0, 40).map((ev) => (
            <div key={ev.seq} className="sm-event">
              <span className="sm-event__t">#{ev.seq} · {fmtClock(ev.at)}</span>
              <span className="sm-event__type" style={{ color: EVENT_TONE[ev.type] ?? "var(--blue)" }}>
                {ev.type}
              </span>
              <span className="sm-event__detail" title={eventDetail(ev)}>{eventDetail(ev)}</span>
            </div>
          ))}
          {sim.events.length === 0 && (
            <p className="cs-dim cs-mono" style={{ fontSize: 10, alignSelf: "center", padding: "0 12px", letterSpacing: "0.2em" }}>
              LISTENING — EVENTS APPEAR AS THE ENGINE EMITS THEM
            </p>
          )}
        </div>
      </div>

      {/* AGENT RECOVERY — opens when a sensor is lost, anchored right so the
          circuit stays visible behind it. */}
      {actionError && (
        <div className="sm-rec__empty" style={{ position: "fixed", right: 14, bottom: 14, zIndex: 61, maxWidth: 380 }}>
          {actionError}
        </div>
      )}
      {/* AGENT RECOVERY — the legacy right-side popup. It is only shown when
          neither the full-screen experience nor a decision summary is on
          screen, so it can never cover the three persistent summaries that
          item 8 requires. Once a verified decision exists, the summary is the
          record. */}
      {!recoveryIncident && !plantDecision && (
        <SensorRecoveryPanel
          focus={recovery}
          onClose={() => setRecovery(null)}
          onRestore={() => recovery && void restoreSensor(recovery.sensorId)}
          onReset={() => void resetPlant()}
        />
      )}

      {/* AGENT RESPONSE CONSOLE — docks right, canvas stays live on the left.
          Everything it shows comes from the response.* events on the same SSE
          subscription the store already owns. */}
      <AgentResponseConsole
        open={consoleOpen}
        events={sim.events}
        stream={sim.stream}
        plantId={plantId}
        activeJobId={activeResponseJob?.jobId ?? null}
        onSelectJob={(jobId) => setConsoleJobId(jobId)}
        onClose={() => setConsoleOpen(false)}
        onFocusEquipment={(equipmentId) => setFocusEquipmentId(equipmentId)}
        stepTimeoutMs={stepTimeoutMs}
      />
    </div>
  );
}
