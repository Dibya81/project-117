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
import { simAdapter, asEmbedded } from "@/lib/sim/adapter";
import { useSimulation } from "@/lib/sim/store";
import { useJourney } from "@/lib/journey";
import { useRouter } from "next/navigation";
import { consoleData } from "@/lib/data/console";
import type { EquipmentDef, PlantDef, ScenarioDef, SimSnapshot } from "@/lib/sim/types";
import "@/styles/plant.css";

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
  const { visit } = useJourney();
  const router = useRouter();

  const [plant, setPlant] = useState<PlantDef | null>(null);
  const [scenarios, setScenarios] = useState<ScenarioDef[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<EquipmentDef | null>(null);
  const [hovered, setHovered] = useState<EquipmentDef | null>(null);
  const [areaFocus, setAreaFocus] = useState<string | null>(null);
  const [runtime, setRuntime] = useState<CanvasRuntime | null>(null);
  const [snap, setSnap] = useState<SimSnapshot | null>(null);
  const [busyScenario, setBusyScenario] = useState<string | null>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const sim = useSimulation(plant ? plantId : null);
  const embedded = asEmbedded(simAdapter);

  // load dataset + boot engine
  useEffect(() => {
    let live = true;
    setPlant(null);
    setRuntime(null);
    simAdapter
      .loadPlant(plantId)
      .then(async ({ plant, scenarios }) => {
        if (!live) return;
        setPlant(plant);
        setScenarios(scenarios);
        setRuntime(emptyRuntime(plant));
        await simAdapter.start(plantId);
        visit({ id: plant.id, label: plant.name, kind: "equipment", href: `/console/simulation/plant/${plant.id}` });
      })
      .catch((e) => setLoadError(String(e)));
    return () => {
      live = false;
      timers.current.forEach(clearTimeout);
    };
  }, [plantId, visit]);

  // refresh canvas runtime at the store's 4 Hz cadence
  useEffect(() => {
    if (!plant) return;
    let live = true;
    if (embedded) {
      setRuntime(runtimeFromEngine(plant, embedded.engine(plantId)));
    } else {
      simAdapter.snapshot(plantId).then(s => {
        if (!live) return;
        setSnap(s);
        const base = emptyRuntime(plant);
        for (const [id, st] of Object.entries(s.equipment)) {
          base.states[id] = st.state as any;
        }
        for (const [id, sx] of Object.entries(s.sensors)) {
          base.qualities[id] = sx.quality as any;
        }
        for (const c of plant.connections) {
          base.pipes[c.id] = { leaking: c.leaking, enabled: c.enabled, flow: c.flow };
        }
        setRuntime(base);
      }).catch(() => undefined);
    }
    return () => { live = false; };
  }, [plant, plantId, embedded, sim.tick]);

  const onSelect = useCallback((eq: EquipmentDef) => setSelected(eq), []);
  const onHover = useCallback((eq: EquipmentDef | null) => setHovered(eq), []);

  const inject = (equipmentId: string, modeId: string) => {
    void simAdapter.injectFailure(plantId, equipmentId, modeId);
  };

  const runScenario = (sc: ScenarioDef) => {
    setBusyScenario(sc.id);
    sc.steps.forEach((st) => {
      timers.current.push(
        setTimeout(() => {
          void simAdapter.injectFailure(plantId, st.target, st.mode);
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
    if (!areaFocus) return plant;
    return {
      ...plant,
      equipment: plant.equipment.filter((e) => e.area_id === areaFocus),
      connections: plant.connections.filter((c) => {
        const s = plant.equipment.find((e) => e.id === c.source);
        const t = plant.equipment.find((e) => e.id === c.target);
        return s?.area_id === areaFocus || t?.area_id === areaFocus;
      }),
    };
  }, [plant, areaFocus]);

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

  if (!plant || !runtime || !displayPlant) {
    return (
      <Panel>
        <SkeletonRows rows={8} label="Commissioning plant…" />
      </Panel>
    );
  }

  const selectedRt = selected ? (embedded ? embedded.engine(plantId).equipmentState(selected.id) : snap?.equipment[selected.id]) : null;

  return (
    <>
      {/* TOP BAR */}
      <div className="cs-pagehead pt-pagehead">
        <div>
          <span className="cs-pagehead__kicker">
            Simulation / {plant.industry} · <span className="cs-text-ember">SYNTHETIC DEMONSTRATION PLANT</span>
          </span>
          <h1 style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            {plant.name}
            <Tag tone={sim.activeIncident ? (sim.activeIncident.severity === "critical" ? "crit" : "warn") : "ok"}>
              {sim.activeIncident ? sim.activeIncident.status.replace(/_/g, " ") : "running"}
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
          <Ring value={health} size={44} tone={health > 80 ? "ok" : health > 55 ? "warn" : "crit"} label="simulation health indicator" />
          <Button variant="ghost" onClick={() => void simAdapter.pause(plantId)}>
            <Icon name="pause" size={12} /> Pause
          </Button>
          <Button variant="primary" onClick={() => void simAdapter.start(plantId)}>
            <Icon name="play" size={12} /> Run
          </Button>
        </div>
      </div>

      <div className="pt-layout">
        {/* LEFT — context, areas, scenarios. The rail holds everything the map
            does not need, so the spatial map keeps the whole remaining width. */}
        <div className="pt-rail">
          {selected ? (
            <Panel title={`${selected.tag} — ${selected.name}`} pad>
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

              <p className="cs-mono cs-dim" style={{ margin: "0 0 8px", fontSize: 9, letterSpacing: "0.26em", textTransform: "uppercase" }}>
                Live sensors
              </p>
              {selected.sensors.map((s) => {
                const v = embedded ? embedded.engine(plantId).sensorValue(s.id) : snap?.sensors[s.id];
                const q = v?.quality ?? "good";
                return (
                  <div key={s.id} className="sm-sensorrow">
                    <StatusDot state={q === "bad" ? "critical" : "ok"} pulse={q === "bad"} />
                    <span className="cs-mono">{s.tag}</span>
                    <span className="cs-dim" style={{ fontSize: 10 }}>{s.measurement}</span>
                    <span className="sm-sensorrow__val" style={{ color: q === "bad" ? "var(--red)" : "var(--ink-1)" }}>
                      {q === "bad" ? "BAD QUALITY" : `${v?.value.toFixed(1)} ${s.unit}`}
                    </span>
                  </div>
                );
              })}

              <p className="cs-mono cs-dim" style={{ margin: "14px 0 8px", fontSize: 9, letterSpacing: "0.26em", textTransform: "uppercase" }}>
                Inject failure
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

              <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
                <Button variant="ghost" style={{ flex: 1, justifyContent: "center" }} onClick={() => void simAdapter.disable(plantId, selected.id)}>
                  <Icon name="pause" size={12} /> Disable
                </Button>
                <Button variant="reject" style={{ flex: 1, justifyContent: "center" }} onClick={() => { void simAdapter.remove(plantId, selected.id); setSelected(null); }}>
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
        <section className="pt-mapwrap">
          <div className="pt-maphead">
            <span className="cs-panel__title">Live process map</span>
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
            <SchematicCanvas
              layout="spatial"
              plant={displayPlant}
              runtime={runtime}
              selectedId={selected?.id ?? null}
              affected={sim.activeIncident?.affected ?? []}
              onSelect={onSelect}
              onHover={onHover}
              onBackground={() => setSelected(null)}
              readings={readings}
              anomalyId={anomalyId}
              panelOpen={Boolean(anomalyId)}
            >
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
          </div>
        </section>
      </div>

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
    </>
  );
}
