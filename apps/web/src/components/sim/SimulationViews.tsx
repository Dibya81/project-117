"use client";

/**
 * SimulationViews — the panel set behind the simulation's secondary navigation.
 *
 * Six panels sharing the reference anatomy (SimPanel): Sensors, Equipment,
 * Control, Scenarios, Incidents and Agent Activity. Each reads the records the
 * platform already holds — the plant definition, the engine's per-line state,
 * the scenario list, the incident store and the orchestrator's task records —
 * and each says plainly when a record set is empty rather than filling space.
 *
 * Control is deliberately a *reading* surface. The plant exposes controller
 * loops and their process variables, and this shows them; it does not offer a
 * setpoint field, because nothing on the backend accepts one and a control that
 * moves without moving the plant is the exact fakery this project forbids.
 */

import { useMemo, useState } from "react";
import { SimPanel, optionsFrom, usePanelFilters } from "@/components/sim/SimPanel";
import { StatusDot, Tag } from "@/components/ui/primitives";
import { ProcessMap, mediumColor } from "@/components/sim/ProcessMap";
import type { ProcessMapSelection } from "@/components/sim/ProcessMap";
import type { SensorRow } from "@/components/sim/SimulationConsole";
import { AgentDispatchBoxes, type ModelRoleMap } from "@/components/sim/AgentDispatchBoxes";
import type { PlantDef, ScenarioDef, SensorDef } from "@/lib/sim/types";
import type { CanvasRuntime, SpatialReading } from "@/components/sim/SchematicCanvas";
import type { Incident, AgentTask, ConnectionDef } from "@/lib/sim/types";

const stateOf = (v: string) => (v === "normal" ? "Normal" : v === "warning" ? "Warning" : v === "critical" || v === "failed" ? "Critical" : "Normal");

function DetailRow({ label, value, tone }: { label: string; value: string; tone?: "warn" | "crit" }) {
  return (
    <div className="simdetail__row">
      <dt>{label}</dt>
      <dd style={tone ? { color: tone === "crit" ? "var(--crit)" : "var(--warn)" } : undefined}>{value}</dd>
    </div>
  );
}

/* ------------------------------------------------------------------ SENSORS */

export function SensorsPanel({
  rows,
  runtime,
  plant,
  onFocus,
}: {
  rows: SensorRow[];
  runtime: CanvasRuntime | null;
  plant: PlantDef;
  onFocus: (sensorId: string) => void;
}) {
  const f = usePanelFilters();
  const [sel, setSel] = useState<string | null>(null);
  const areaOf = useMemo(() => {
    const m = new Map<string, string>();
    for (const e of plant.equipment) for (const s of e.sensors) m.set(s.id, e.area_id);
    return m;
  }, [plant]);

  const filtered = rows.filter((r) =>
    f.match({
      text: `${r.sensor.tag} ${r.equipmentTag} ${r.sensor.measurement}`,
      area: areaOf.get(r.sensor.id),
      type: r.sensor.measurement,
      state: r.state === "normal" ? "Normal" : r.state === "warning" ? "Warning" : "Critical",
    }),
  );
  const selected = rows.find((r) => r.sensor.id === sel) ?? null;

  return (
    <SimPanel
      accent="sensors"
      icon="gauge"
      title="Sensors"
      subtitle="Real-time sensor data and trends"
      testId="panel-sensors"
      filters={[
        { id: "area", label: "Area", options: optionsFrom(plant.equipment.map((e) => e.area_id)), value: f.area, onChange: f.setArea },
        { id: "type", label: "Type", options: optionsFrom(rows.map((r) => r.sensor.measurement)), value: f.type, onChange: f.setType },
        { id: "state", label: "Status", options: ["All", "Normal", "Warning", "Critical"], value: f.state, onChange: f.setState },
      ]}
      search={{ value: f.q, onChange: f.setQ, placeholder: "Search tags, equipment…" }}
      detail={
        selected ? (
          <>
            <span className="simdetail__title">{selected.sensor.tag}</span>
            <span className="simdetail__sub">
              {selected.sensor.measurement} · {selected.equipmentTag}
            </span>
            <div style={{ margin: "10px 0 4px" }}>
              <DetailRow label="Value" value={selected.value == null ? "—" : `${selected.value} ${selected.sensor.unit}`}
                tone={selected.state === "critical" ? "crit" : selected.state === "warning" ? "warn" : undefined} />
              <DetailRow label="Normal range" value={selected.range} />
              <DetailRow label="Warning" value={`${selected.sensor.warning_min}–${selected.sensor.warning_max} ${selected.sensor.unit}`} />
              <DetailRow label="Critical" value={`${selected.sensor.critical_min}–${selected.sensor.critical_max} ${selected.sensor.unit}`} />
              <DetailRow label="Quality" value={selected.quality} />
              <DetailRow label="Sampling" value={`${selected.sensor.sampling_ms} ms`} />
              <DetailRow label="Area" value={areaOf.get(selected.sensor.id) ?? "—"} />
            </div>
          </>
        ) : (
          <p className="simdetail__hint">
            Select an instrument to see its band, quality and sampling. Its location is
            highlighted on the process drawing.
          </p>
        )
      }
    >
      <table className="simdata">
        <thead>
          <tr><th>Sensor</th><th>Equipment</th><th>Value</th><th>Range</th><th>Status</th></tr>
        </thead>
        <tbody>
          {filtered.map((r) => (
            <tr
              key={r.sensor.id}
              data-sensor-row={r.sensor.id}
              className={sel === r.sensor.id ? "is-selected" : undefined}
              onClick={() => {
                setSel(r.sensor.id);
                onFocus(r.sensor.id);
              }}
            >
              <td>{r.sensor.tag}</td>
              <td className="is-muted">{r.equipmentTag}</td>
              <td className={r.state === "critical" ? "is-critical" : r.state === "warning" ? "is-warning" : undefined}>
                {r.value == null ? "—" : `${r.value} ${r.sensor.unit}`}
              </td>
              <td className="is-muted">{r.range}</td>
              <td className={r.quality !== "good" ? "is-critical" : r.state === "warning" ? "is-warning" : "is-muted"}>
                {r.quality === "bad" ? "OUT OF SERVICE" : r.quality === "substituted" ? "SUBSTITUTED" : r.state.toUpperCase()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </SimPanel>
  );
}

/* ---------------------------------------------------------------- EQUIPMENT */

export function EquipmentPanel({
  plant,
  runtime,
  onFocus,
}: {
  plant: PlantDef;
  runtime: CanvasRuntime | null;
  onFocus: (equipmentId: string) => void;
}) {
  const f = usePanelFilters();
  const [sel, setSel] = useState<string | null>(null);
  const filtered = plant.equipment.filter((e) =>
    f.match({
      text: `${e.tag} ${e.name} ${e.kind}`,
      area: e.area_id,
      type: e.kind,
      state: stateOf(runtime?.states?.[e.id] ?? e.state ?? "normal"),
    }),
  );
  const selected = plant.equipment.find((e) => e.id === sel) ?? null;

  return (
    <SimPanel
      accent="equipment"
      icon="equipment"
      title="Equipment"
      subtitle="Equipment details, health and maintenance"
      testId="panel-equipment"
      filters={[
        { id: "area", label: "Area", options: optionsFrom(plant.equipment.map((e) => e.area_id)), value: f.area, onChange: f.setArea },
        { id: "type", label: "Type", options: optionsFrom(plant.equipment.map((e) => e.kind)), value: f.type, onChange: f.setType },
        { id: "state", label: "State", options: ["All", "Normal", "Warning", "Critical"], value: f.state, onChange: f.setState },
      ]}
      search={{ value: f.q, onChange: f.setQ, placeholder: "Search equipment…" }}
      detail={
        selected ? (
          <>
            <span className="simdetail__title">{selected.tag}</span>
            <span className="simdetail__sub">{selected.name}</span>
            <div style={{ margin: "10px 0 4px" }}>
              <DetailRow label="Type" value={selected.kind} />
              <DetailRow label="Area" value={selected.area_id} />
              <DetailRow label="Criticality" value={String(selected.criticality)} />
              <DetailRow label="State" value={stateOf(runtime?.states?.[selected.id] ?? selected.state ?? "normal")} />
              <DetailRow label="Instruments" value={String(selected.sensors.length)} />
              <DetailRow label="Failure modes" value={String(selected.failure_modes.length)} />
              <DetailRow label="Capacity" value={`${Math.round((selected.capacity ?? 1) * 100)}%`} />
            </div>
          </>
        ) : (
          <p className="simdetail__hint">
            Select an asset to see its type, area, health and instrument count. Selecting
            one focuses it on the process drawing.
          </p>
        )
      }
    >
      <table className="simdata">
        <thead>
          <tr><th>Tag</th><th>Name</th><th>Type</th><th>Area</th><th>Instr.</th><th>State</th></tr>
        </thead>
        <tbody>
          {filtered.map((e) => {
            const st = runtime?.states?.[e.id] ?? e.state ?? "normal";
            return (
              <tr
                key={e.id}
                data-equipment-row={e.id}
                className={sel === e.id ? "is-selected" : undefined}
                onClick={() => {
                  setSel(e.id);
                  onFocus(e.id);
                }}
              >
                <td>{e.tag}</td>
                <td className="is-muted">{e.name}</td>
                <td className="is-muted">{e.kind}</td>
                <td className="is-muted">{e.area_id}</td>
                <td className="is-muted">{e.sensors.length}</td>
                <td className={st !== "normal" ? "is-warning" : undefined}>{String(st).toUpperCase()}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </SimPanel>
  );
}

/* ------------------------------------------------------------------ CONTROL */

export function ControlPanel({
  plant,
  runtime,
  readings,
}: {
  plant: PlantDef;
  runtime: CanvasRuntime | null;
  readings: Record<string, SpatialReading>;
}) {
  const f = usePanelFilters();
  const [sel, setSel] = useState<string | null>(null);
  /**
   * The plant's control surface is its instrumented variables: every measured
   * point has a process value and a band. Showing them together is what makes
   * the plant's control state legible. A setpoint field would need an endpoint
   * that does not exist, so there isn't one.
   */
  const rows = useMemo(
    () =>
      plant.equipment.flatMap((e) =>
        e.sensors.map((s) => ({
          id: s.id,
          tag: s.tag,
          measurement: s.measurement,
          unit: s.unit,
          pv: readings[s.id]?.value ?? null,
          sp: s.nominal,
          band: `${s.normal_min}–${s.normal_max}`,
          equipment: e.tag,
          area: e.area_id,
          mode: "AUTO" as const,
        })),
      ),
    [plant, readings],
  );
  const filtered = rows.filter((r) =>
    f.match({ text: `${r.tag} ${r.equipment} ${r.measurement}`, area: r.area, type: r.measurement, state: "Normal" }),
  );
  const selected = rows.find((r) => r.id === sel) ?? null;
  const dev = (r: (typeof rows)[number]) =>
    r.pv == null || !r.sp ? 0 : Math.abs(r.pv - r.sp);

  return (
    <SimPanel
      accent="control"
      icon="cpu"
      title="Control"
      subtitle="Control systems and their process variables"
      testId="panel-control"
      filters={[
        { id: "area", label: "Area", options: optionsFrom(plant.equipment.map((e) => e.area_id)), value: f.area, onChange: f.setArea },
        { id: "type", label: "Loop", options: optionsFrom(rows.map((r) => r.measurement)), value: f.type, onChange: f.setType },
      ]}
      search={{ value: f.q, onChange: f.setQ, placeholder: "Search loops…" }}
      actions={<Tag tone="ok">{rows.length} loops</Tag>}
      detail={
        selected ? (
          <>
            <span className="simdetail__title">{selected.tag}</span>
            <span className="simdetail__sub">
              {selected.measurement} control · {selected.equipment}
            </span>
            <div style={{ margin: "10px 0 4px" }}>
              <DetailRow label="Process var" value={selected.pv == null ? "—" : `${selected.pv} ${selected.unit}`} />
              <DetailRow label="Setpoint" value={`${selected.sp} ${selected.unit}`} />
              <DetailRow label="Band" value={`${selected.band} ${selected.unit}`} />
              <DetailRow label="Deviation" value={dev(selected).toFixed(2)} />
              <DetailRow label="Mode" value={selected.mode} />
              <DetailRow label="Area" value={selected.area} />
            </div>
            <p className="simdetail__hint">
              Read-only. Changing a setpoint would need a write endpoint on the engine;
              there is none, so this panel does not pretend to offer one.
            </p>
          </>
        ) : (
          <p className="simdetail__hint">
            Select a loop to see its process variable against setpoint. Values come from
            the plant&apos;s own instruments.
          </p>
        )
      }
    >
      <table className="simdata">
        <thead>
          <tr><th>Loop</th><th>Mode</th><th>PV</th><th>SP</th><th>Band</th><th>Equipment</th></tr>
        </thead>
        <tbody>
          {filtered.slice(0, 400).map((r) => (
            <tr
              key={r.id}
              data-control-row={r.id}
              className={sel === r.id ? "is-selected" : undefined}
              onClick={() => setSel(r.id)}
            >
              <td>{r.tag}</td>
              <td className="is-muted">{r.mode}</td>
              <td>{r.pv == null ? "—" : `${r.pv} ${r.unit}`}</td>
              <td className="is-muted">{r.sp} {r.unit}</td>
              <td className="is-muted">{r.band}</td>
              <td className="is-muted">{r.equipment}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </SimPanel>
  );
}

/* ---------------------------------------------------------------- SCENARIOS */

export function ScenariosPanel({
  scenarios,
  onRun,
  running,
}: {
  scenarios: ScenarioDef[];
  onRun: (id: string) => void;
  running: string | null;
}) {
  const f = usePanelFilters();
  const [sel, setSel] = useState<string | null>(null);
  const filtered = scenarios.filter((s) =>
    f.match({ text: `${s.id} ${s.name ?? ""} ${s.description ?? ""}`, type: "Scenario", state: "Ready" }),
  );
  const selected = scenarios.find((s) => s.id === sel) ?? null;

  return (
    <SimPanel
      accent="scenarios"
      icon="play"
      title="Scenarios"
      subtitle="Test scenarios and what-if analysis"
      testId="panel-scenarios"
      filters={[{ id: "state", label: "Status", options: ["All", "Ready"], value: f.state, onChange: f.setState }]}
      search={{ value: f.q, onChange: f.setQ, placeholder: "Search scenarios…" }}
      actions={<Tag tone="ai">{scenarios.length} available</Tag>}
      detail={
        selected ? (
          <>
            <span className="simdetail__title">{selected.name ?? selected.id}</span>
            <span className="simdetail__sub">{selected.description ?? "Scenario"}</span>
            <div style={{ margin: "10px 0 4px" }}>
              <DetailRow label="Steps" value={String(selected.steps?.length ?? 0)} />
              <DetailRow label="Duration" value={`${selected.steps?.[selected.steps.length - 1]?.at_s ?? 0} s`} />
            </div>
            <button
              className="cs-btn cs-btn--primary"
              style={{ width: "100%", justifyContent: "center", marginTop: 8 }}
              disabled={running === selected.id}
              data-scenario-run={selected.id}
              onClick={() => onRun(selected.id)}
            >
              {running === selected.id ? "Running…" : "▶ Run scenario"}
            </button>
          </>
        ) : (
          <p className="simdetail__hint">
            Select a scenario to inspect its steps. Running one drives the real engine —
            it is not a playback.
          </p>
        )
      }
    >
      <table className="simdata">
        <thead>
          <tr><th>Scenario</th><th>Type</th><th>Steps</th><th>Status</th></tr>
        </thead>
        <tbody>
          {filtered.map((s) => (
            <tr
              key={s.id}
              data-scenario-row={s.id}
              className={sel === s.id ? "is-selected" : undefined}
              onClick={() => setSel(s.id)}
            >
              <td>{s.name ?? s.id}</td>
              <td className="is-muted">{s.description ? "Fault" : "Scenario"}</td>
              <td className="is-muted">{s.steps?.length ?? 0}</td>
              <td className="is-muted">READY</td>
            </tr>
          ))}
        </tbody>
      </table>
    </SimPanel>
  );
}

/* ---------------------------------------------------------------- INCIDENTS */

export function IncidentsPanel({
  incidents,
  plant,
  onFocus,
}: {
  incidents: Incident[];
  plant: PlantDef;
  onFocus: (equipmentId: string) => void;
}) {
  const f = usePanelFilters();
  const [sel, setSel] = useState<string | null>(null);
  const tagOf = (id: string) => plant.equipment.find((e) => e.id === id)?.tag ?? id;
  const filtered = incidents.filter((i) =>
    f.match({
      text: `${i.id} ${i.title} ${tagOf(i.origin_equipment)} ${i.failure_mode ?? ""}`,
      type: "Incident",
      state: i.severity === "critical" ? "Critical" : "Warning",
    }),
  );
  const selected = incidents.find((i) => i.id === sel) ?? null;

  return (
    <SimPanel
      accent="incidents"
      icon="alert"
      title="Incidents"
      subtitle="Active and historical incidents"
      testId="panel-incidents"
      filters={[{ id: "state", label: "Severity", options: ["All", "Critical", "Warning"], value: f.state, onChange: f.setState }]}
      search={{ value: f.q, onChange: f.setQ, placeholder: "Search incidents…" }}
      actions={<Tag tone={incidents.length ? "warn" : "ok"}>{incidents.length} recorded</Tag>}
      detail={
        selected ? (
          <>
            <span className="simdetail__title">{selected.id}</span>
            <span className="simdetail__sub">{selected.title}</span>
            <div style={{ margin: "10px 0 4px" }}>
              <DetailRow label="Equipment" value={tagOf(selected.origin_equipment)} />
              <DetailRow label="Severity" value={selected.severity.toUpperCase()} tone={selected.severity === "critical" ? "crit" : "warn"} />
              <DetailRow label="Status" value={selected.status.replace(/_/g, " ")} />
              <DetailRow label="Failure mode" value={selected.failure_mode ?? "—"} />
              <DetailRow label="Affected" value={`${selected.affected.length} unit(s)`} />
              <DetailRow label="Sim time" value={`${selected.created_at}s`} />
            </div>
            <button
              className="cs-btn"
              style={{ width: "100%", justifyContent: "center", marginTop: 8 }}
              onClick={() => onFocus(selected.origin_equipment)}
            >
              Focus on drawing →
            </button>
          </>
        ) : (
          <p className="simdetail__hint">
            {incidents.length === 0
              ? "No incident has been raised. The engine records one when it actually detects a fault."
              : "Select an incident to see its equipment, severity and affected units."}
          </p>
        )
      }
    >
      <table className="simdata">
        <thead>
          <tr><th>Time</th><th>Incident</th><th>Equipment</th><th>Fault</th><th>Severity</th><th>Status</th></tr>
        </thead>
        <tbody>
          {filtered.map((i) => (
            <tr
              key={i.id}
              data-incident-row={i.id}
              className={sel === i.id ? "is-selected" : undefined}
              onClick={() => setSel(i.id)}
            >
              <td className="is-muted">{i.created_at}s</td>
              <td>{i.id}</td>
              <td>{tagOf(i.origin_equipment)}</td>
              <td className="is-muted">{i.failure_mode ?? i.title}</td>
              <td className={i.severity === "critical" ? "is-critical" : "is-warning"}>{i.severity.toUpperCase()}</td>
              <td>{i.status.replace(/_/g, " ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </SimPanel>
  );
}

/* ------------------------------------------------------------------- AGENTS */

export function AgentsPanel({
  tasks,
  models,
  now,
}: {
  tasks: AgentTask[];
  models: ModelRoleMap;
  now: number;
}) {
  return (
    <SimPanel
      accent="agents"
      icon="cpu"
      title="AI Activity"
      subtitle="Multi-agent activity and decision making"
      testId="panel-agents"
      actions={<Tag tone={tasks.length ? "ai" : "ok"}>{tasks.length ? "engaged" : "idle"}</Tag>}
    >
      <div style={{ padding: 14 }}>
        {tasks.length === 0 ? (
          <p className="simdetail__hint">
            The workforce is idle. Three agents are dispatched when an incident raises
            work; nothing here animates to fill the space.
          </p>
        ) : (
          <table className="simdata" data-testid="agent-task-table">
            <thead>
              <tr><th>Agent</th><th>Model</th><th>Task</th><th>Status</th><th>Tools</th><th>Evidence</th><th>Started</th></tr>
            </thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.id} data-agent-task={t.agent}>
                  <td>{t.agent}</td>
                  <td className="is-muted">{models[t.agent === "maintenance" || t.agent === "operations" ? "domain" : "reasoning"] ?? "—"}</td>
                  <td className="is-muted">{t.title}</td>
                  <td className={t.status === "completed" ? "is-muted" : t.status === "running" ? "is-warning" : undefined}>
                    {t.status.toUpperCase()}
                  </td>
                  <td className="is-muted">{t.tools.length}</td>
                  <td className="is-muted">{t.evidence.length}</td>
                  <td className="is-muted">{t.started_at == null ? "—" : `${Math.max(0, Math.round(now - t.started_at))}s`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </SimPanel>
  );
}

/* Re-exported so the page can render the drawing from one place. */
export { ProcessMap };
export type { ProcessMapSelection };
export { AgentDispatchBoxes };
export { mediumColor };
export type { ConnectionDef, SensorDef };
