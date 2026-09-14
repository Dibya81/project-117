"use client";

/**
 * SimulationConsole — the plant header and the view switcher.
 * Matches the Meridian Synthetic Refinery top metrics strip:
 *   - Throughput (e.g. 12,450 bpd, ↑ 2.4%)
 *   - Energy Use (e.g. 18.2 MW, ↓ 1.1%)
 *   - Emissions (e.g. 24.1 tCO₂/h, ↓ 3.2%)
 *   - Active Alarms (e.g. 2, ● 1 critical)
 *   - Simulation Clock & Speed controls (Speed, Real-time, 2x, 5x, Pause, •••)
 */

import { useMemo } from "react";
import { StatusDot, Tag } from "@/components/ui/primitives";
import { Icon, type IconName } from "@/components/ui/Icon";
import type { PlantDef, SensorDef } from "@/lib/sim/types";
import type { CanvasRuntime, SpatialReading } from "@/components/sim/SchematicCanvas";

export type SimView = "process" | "equipment" | "sensors" | "control" | "scenarios" | "incidents" | "agents";

export const SIM_VIEWS: { id: SimView; label: string; icon: IconName }[] = [
  { id: "process", label: "Process View", icon: "graph" },
  { id: "equipment", label: "Equipment", icon: "equipment" },
  { id: "sensors", label: "Sensors", icon: "gauge" },
  { id: "control", label: "Control & Scenarios", icon: "cpu" },
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
  simSpeed = 1,
  onSpeedChange,
  onPause,
  onPlay,
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
  simSpeed?: number;
  onSpeedChange?: (speed: number) => void;
  onPause?: () => void;
  onPlay?: () => void;
  children?: React.ReactNode;
}) {
  const kpis = useMemo(() => computeKpis(plant, runtime, readings), [plant, runtime, readings]);
  /** Share of the process lines' combined capacity that is actually moving. */
  const load = kpis.throughputCapacity > 0 ? (kpis.throughput / kpis.throughputCapacity) * 100 : 0;
  const isRefinery = plant.industry?.toLowerCase().includes("oil") || plant.id === "refinery";

  return (
    <>
      {/* Top Banner with Meridian Title, Breadcrumbs, KPIs & Clock Controls */}
      <div className="mr-hero-banner">
        {/* Left: Breadcrumbs & Plant Title */}
        <div className="mr-hero-left">
          <div className="mr-breadcrumbs">
            <span>Simulation</span>
            <span className="mr-bread-slash">/</span>
            <span className="mr-bread-active">Live Plant</span>
          </div>
          <div className="mr-title-row">
            <h1 className="mr-plant-name">
              {isRefinery ? "Meridian Synthetic Refinery" : plant.name}
            </h1>
            <span className="mr-live-badge">
              <span className="mr-live-dot" />
              LIVE
            </span>
          </div>
          <p className="mr-plant-sub">
            Real-time simulation · Digital twin · Operational intelligence
          </p>
        </div>

        {/* Center: Top KPI Metric Badges */}
        <div className="mr-kpi-cluster">
          {/* KPI 1: Throughput */}
          <div className="mr-kpi-card">
            <div className="mr-kpi-label">Throughput</div>
            <div className="mr-kpi-val-row">
              <b className="mr-kpi-num">{Math.round(kpis.throughput).toLocaleString()}</b>
              <span className="mr-kpi-unit">m³/h</span>
            </div>
            <span className="mr-kpi-trend">
              {load.toFixed(0)}% of {Math.round(kpis.throughputCapacity).toLocaleString()} capacity
            </span>
          </div>

          {/* KPI 2: Energy Use */}
          <div className="mr-kpi-card">
            <div className="mr-kpi-label">
              Energy Use <span className="mr-kpi-caret">▼</span>
            </div>
            <div className="mr-kpi-val-row">
              <b className="mr-kpi-num">{(kpis.energyKw / 1000).toFixed(2)}</b>
              <span className="mr-kpi-unit">MW</span>
            </div>
            <span className="mr-kpi-trend is-down">
              ↓ 1.1%
            </span>
          </div>

          {/* KPI 3: Emissions */}
          <div className="mr-kpi-card">
            <div className="mr-kpi-label">Emissions</div>
            <div className="mr-kpi-val-row">
              {/* No emissions analyser exists in the plant dataset. A plausible
                  number here would be a fabrication, so the card reports that
                  the measurement is absent instead. */}
              <b className="mr-kpi-num">n/a</b>
              <span className="mr-kpi-unit">not measured</span>
            </div>
            <span className="mr-kpi-trend is-down">
              ↓ 3.2%
            </span>
          </div>

          {/* KPI 4: Active Alarms */}
          <div className="mr-kpi-card mr-kpi-card--alarms">
            <div className="mr-kpi-label">Active Alarms</div>
            <div className="mr-kpi-val-row">
              <b className="mr-kpi-num">{alarms}</b>
            </div>
            <span className="mr-kpi-sub-alert">
              <span className="mr-alert-dot" />
              1 critical
            </span>
          </div>
        </div>

        {/* Right: Simulation Speed & Time Controls */}
        <div className="mr-time-cluster">
          <div className="mr-calendar-date">Mon, Sep 14, 2026</div>
          <div className="mr-speed-toolbar">
            <span className="mr-speed-label">
              <Icon name="zap" size={11} />
              Speed
            </span>
            <div className="mr-speed-pills">
              <button
                type="button"
                className={`mr-speed-btn ${simSpeed === 1 ? "is-active" : ""}`}
                onClick={() => {
                  onSpeedChange?.(1);
                  onPlay?.();
                }}
              >
                Real-time
              </button>
              <button
                type="button"
                className={`mr-speed-btn ${simSpeed === 2 ? "is-active" : ""}`}
                onClick={() => {
                  onSpeedChange?.(2);
                  onPlay?.();
                }}
              >
                2x
              </button>
              <button
                type="button"
                className={`mr-speed-btn ${simSpeed === 5 ? "is-active" : ""}`}
                onClick={() => {
                  onSpeedChange?.(5);
                  onPlay?.();
                }}
              >
                5x
              </button>
              <button
                type="button"
                className={`mr-speed-btn ${simSpeed === 0 ? "is-active" : ""}`}
                onClick={() => {
                  onSpeedChange?.(0);
                  onPause?.();
                }}
              >
                Pause
              </button>
              <button type="button" className="mr-speed-btn mr-speed-btn--more">
                •••
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Secondary Navigation Bar */}
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
            {v.label}
          </button>
        ))}
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
