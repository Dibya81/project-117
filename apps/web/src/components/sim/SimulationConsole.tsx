"use client";

/**
 * SimulationConsole — the plant header and the view switcher.
 *
 * Every figure in the strip is computed from state the engine is already
 * reporting: throughput is the sum of live flow across the process lines,
 * energy is the sum of the plant's own kW instruments, and instrumentation
 * counts sensors the engine says are reading GOOD. Nothing here is a decorative
 * number — where the plant does not measure something (it has no emissions
 * analyser), the figure is absent rather than invented.
 */

import { useMemo } from "react";
import { StatusDot, Tag } from "@/components/ui/primitives";
import { Icon, type IconName } from "@/components/ui/Icon";
import type { PlantDef, SensorDef } from "@/lib/sim/types";
import type { CanvasRuntime, SpatialReading } from "@/components/sim/SchematicCanvas";

export type SimView = "process" | "equipment" | "sensors" | "incidents" | "agents";

export const SIM_VIEWS: { id: SimView; label: string; icon: IconName }[] = [
  { id: "process", label: "Process View", icon: "graph" },
  { id: "equipment", label: "Equipment", icon: "equipment" },
  { id: "sensors", label: "Sensors", icon: "gauge" },
  { id: "incidents", label: "Incidents", icon: "alert" },
  { id: "agents", label: "Agent Activity", icon: "cpu" },
];

export interface PlantKpis {
  throughput: number;
  throughputCapacity: number;
  energyKw: number;
  instrumentsOnline: number;
  instrumentsTotal: number;
}

/** Compute the strip from real engine state. */
export function computeKpis(
  plant: PlantDef,
  runtime: CanvasRuntime | null,
  readings: Record<string, SpatialReading>,
): PlantKpis {
  let throughput = 0;
  let throughputCapacity = 0;
  for (const c of plant.connections) {
    const p = runtime?.pipes?.[c.id];
    const enabled = p ? p.enabled : c.enabled !== false;
    if (!enabled) continue;
    throughput += p?.flow ?? c.flow ?? 0;
    throughputCapacity += c.capacity ?? 0;
  }

  let energyKw = 0;
  let instrumentsTotal = 0;
  let instrumentsOnline = 0;
  for (const e of plant.equipment) {
    for (const s of e.sensors) {
      instrumentsTotal += 1;
      const q = runtime?.qualities?.[s.id] ?? "good";
      if (q === "good") instrumentsOnline += 1;
      if (s.measurement === "power") {
        const r = readings[s.id];
        if (r && Number.isFinite(r.value)) energyKw += r.value;
      }
    }
  }
  return { throughput, throughputCapacity, energyKw, instrumentsOnline, instrumentsTotal };
}

function Kpi({
  label,
  value,
  unit,
  detail,
  tone = "neutral",
}: {
  label: string;
  value: string;
  unit?: string;
  detail?: string;
  tone?: "neutral" | "ok" | "warn" | "crit";
}) {
  const colour =
    tone === "ok" ? "var(--ok)" : tone === "warn" ? "var(--warn)" : tone === "crit" ? "var(--crit)" : "var(--ink-1)";
  return (
    <div className="simkpi" data-tone={tone}>
      <span className="simkpi__label">{label}</span>
      <span className="simkpi__value" style={{ color: colour }}>
        {value}
        {unit && <em>{unit}</em>}
      </span>
      {detail && <span className="simkpi__detail">{detail}</span>}
    </div>
  );
}

export function SimulationConsole({
  plant,
  runtime,
  readings,
  alarms,
  health,
  activeView,
  onView,
  incidentSeverity,
  incidentStatus,
  children,
}: {
  plant: PlantDef;
  runtime: CanvasRuntime | null;
  readings: Record<string, SpatialReading>;
  alarms: number;
  health: number;
  activeView: SimView;
  onView: (v: SimView) => void;
  incidentSeverity?: string | null;
  incidentStatus?: string | null;
  children?: React.ReactNode;
}) {
  const kpis = useMemo(() => computeKpis(plant, runtime, readings), [plant, runtime, readings]);
  const load = kpis.throughputCapacity > 0 ? (kpis.throughput / kpis.throughputCapacity) * 100 : 0;
  const online = kpis.instrumentsTotal > 0 ? (kpis.instrumentsOnline / kpis.instrumentsTotal) * 100 : 0;

  return (
    <>
      {/* The strip answers "is the plant well?" before the reader has to look
          at a single asset. */}
      <div className="simkpis" data-testid="plant-kpis">
        <Kpi
          label="Throughput"
          value={load.toFixed(0)}
          unit="% of line capacity"
          detail={`${kpis.throughput.toFixed(0)} / ${kpis.throughputCapacity.toFixed(0)} m³/h`}
        />
        <Kpi
          label="Energy"
          value={kpis.energyKw.toFixed(0)}
          unit="kW"
          detail={`${plant.equipment.filter((e) => e.sensors.some((s) => s.measurement === "power")).length} metered drives`}
        />
        <Kpi
          label="Instrumentation"
          value={`${kpis.instrumentsOnline}/${kpis.instrumentsTotal}`}
          detail={`${online.toFixed(0)}% reading good`}
          tone={online > 99 ? "ok" : online > 95 ? "warn" : "crit"}
        />
        <Kpi
          label="Active alarms"
          value={String(alarms)}
          tone={alarms > 0 ? "warn" : "ok"}
          detail={alarms > 0 ? "requires attention" : "none raised"}
        />
        <Kpi
          label="Plant health"
          value={health.toFixed(0)}
          unit="%"
          tone={health > 80 ? "ok" : health > 55 ? "warn" : "crit"}
          detail="from asset states and alarms"
        />
        <Kpi
          label="Response"
          value={incidentStatus ? incidentStatus.replace(/_/g, " ") : "idle"}
          tone={incidentStatus ? (incidentSeverity === "critical" ? "crit" : "warn") : "ok"}
          detail={incidentStatus ? "agents engaged" : "no active incident"}
        />
      </div>

      {/* Secondary navigation. Each view renders real records; switching does
          not tear down the simulation, because the engine lives in the store. */}
      <nav className="simnav" role="tablist" aria-label="Simulation views" data-testid="sim-nav">
        {SIM_VIEWS.map((v) => (
          <button
            key={v.id}
            role="tab"
            aria-selected={activeView === v.id}
            className={activeView === v.id ? "is-active" : undefined}
            data-view={v.id}
            onClick={() => onView(v.id)}
          >
            <Icon name={v.icon} size={12} />
            {v.label}
          </button>
        ))}
        <span className="simnav__plant">
          <StatusDot state={alarms > 0 ? "warning" : "ok"} pulse={alarms > 0} />
          {plant.name}
          <Tag tone={incidentStatus ? "warn" : "ok"}>{incidentStatus ? "responding" : "LIVE"}</Tag>
        </span>
      </nav>

      {children}
    </>
  );
}

/** Instrument rows for the Sensors view. Real values, real bands. */
export interface SensorRow {
  sensor: SensorDef;
  equipmentTag: string;
  area: string;
  value: number | null;
  quality: string;
  state: "normal" | "warning" | "critical";
  range: string;
}

export function buildSensorRows(
  plant: PlantDef,
  runtime: CanvasRuntime | null,
  readings: Record<string, SpatialReading>,
): SensorRow[] {
  const byId = new Map(plant.equipment.map((e) => [e.id, e]));
  const rows: SensorRow[] = [];
  for (const e of plant.equipment) {
    for (const s of e.sensors) {
      const r = readings[s.id];
      const q = runtime?.qualities?.[s.id] ?? "good";
      const v = r && Number.isFinite(r.value) ? r.value : null;
      let state: SensorRow["state"] = "normal";
      if (v != null) {
        if ((s.critical_max != null && v >= s.critical_max) || (s.critical_min != null && v <= s.critical_min)) {
          state = "critical";
        } else if ((s.warning_max != null && v >= s.warning_max) || (s.warning_min != null && v <= s.warning_min)) {
          state = "warning";
        }
      }
      rows.push({
        sensor: s,
        equipmentTag: byId.get(e.id)?.tag ?? e.id,
        area: e.area_id,
        value: v,
        quality: q,
        state: q === "bad" ? "critical" : q === "stale" ? "warning" : state,
        range: `${s.normal_min}–${s.normal_max} ${s.unit}`,
      });
    }
  }
  return rows;
}
