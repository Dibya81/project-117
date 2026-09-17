"use client";

/**
 * PlantLowerDeck — the information band beneath the process drawing.
 * Matches the Meridian Synthetic Refinery 3-card design:
 *   Card 1: Selected Equipment (FCC Unit C-201 3D model, metadata, tabs, sparklines)
 *   Card 2: Process Streams (tabular real-time metrics with status dots)
 *   Card 3: Recent Events (timestamped events with severity dots)
 */

import { useState } from "react";
import Image from "next/image";
import { StatusDot, Tag } from "@/components/ui/primitives";
import { Icon } from "@/components/ui/Icon";
import { SimSymbol, symbolForEquipment, type SimVisualState } from "@/lib/sim/symbols";
import { mediumColor } from "@/components/sim/ProcessMap";
import type { ConnectionDef, EquipmentDef, PlantDef, SensorDef, SimEvent } from "@/lib/sim/types";
import type { CanvasRuntime, SpatialReading } from "@/components/sim/SchematicCanvas";

function fmt(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return "—";
  const a = Math.abs(v);
  if (a >= 1000) return v.toFixed(0);
  return v.toFixed(a >= 100 ? 0 : digits);
}

// Mini SVG Sparkline generator
function MiniSparkline({
  color = "#06b6d4",
  trend = "up",
}: {
  color?: string;
  trend?: "up" | "down" | "flat";
}) {
  const points =
    trend === "up"
      ? "0,14 10,12 20,15 30,10 40,11 50,6 60,8 70,4 80,5 90,2"
      : trend === "down"
        ? "0,4 10,6 20,3 30,9 40,8 50,12 60,11 70,14 80,13 90,16"
        : "0,10 10,9 20,11 30,10 40,9 50,11 60,10 70,9 80,10 90,10";

  return (
    <svg width="46" height="18" viewBox="0 0 90 20" fill="none" className="ld-sparkline">
      <polyline points={points} stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const DEFAULT_STREAMS = [
  { stream: "Crude Feed", flow: "412.3", temp: "32.4", press: "1.2", status: "ok", color: "#06b6d4" },
  { stream: "Naphtha", flow: "85.6", temp: "128.4", press: "2.1", status: "ok", color: "#f97316" },
  { stream: "Kerosene", flow: "62.1", temp: "210.3", press: "1.8", status: "ok", color: "#3b82f6" },
  { stream: "Diesel", flow: "118.7", temp: "265.1", press: "2.4", status: "ok", color: "#eab308" },
  { stream: "VGO", flow: "96.4", temp: "340.2", press: "1.6", status: "ok", color: "#a855f7" },
  { stream: "Residue", flow: "49.8", temp: "380.5", press: "1.1", status: "ok", color: "#64748b" },
];

const MOCK_EVENTS = [
  { time: "10:24", text: "Sensor P-101-A flow normalised", type: "ok", id: "ev-1" },
  { time: "10:18", text: "Temperature spike at C-201", type: "crit", id: "ev-2" },
  { time: "10:15", text: "Agent Diagnostic analysis completed", type: "ai", id: "ev-3" },
  { time: "10:12", text: "Work order WO-2024-1187 created", type: "warn", id: "ev-4" },
  { time: "10:08", text: "Maintenance inspection uploaded", type: "ok", id: "ev-5" },
  { time: "10:03", text: "Simulation scenario started", type: "info", id: "ev-6" },
];

export function PlantLowerDeck({
  plant,
  runtime,
  readings,
  selected,
  events,
  onSelectEquipment,
  onSelectLine,
  selectedLineId,
  onSensorAction,
  busySensor,
  onInjectFault,
  busyFault = null,
}: {
  plant: PlantDef;
  runtime: CanvasRuntime | null;
  readings: Record<string, SpatialReading>;
  selected: EquipmentDef | null;
  events: SimEvent[];
  onSelectEquipment: (eq: EquipmentDef) => void;
  onSelectLine: (lineId: string) => void;
  selectedLineId: string | null;
  onSensorAction?: (sensorId: string, action: "disable" | "restore") => void;
  busySensor?: string | null;
  /** Inject an equipment failure mode. `modeId` comes from the asset's own list. */
  onInjectFault?: (equipmentId: string, modeId: string) => void;
  busyFault?: string | null;
}) {
  const [activeTab, setActiveTab] = useState<"live" | "trends" | "maintenance" | "related">("live");

  // The selected asset is exactly the asset the operator selected. There is no
  // default: inventing one (the old code substituted a hardcoded "FCC Unit
  // C-201" with made-up sensors and failure modes) both showed a plant asset
  // that does not exist and let the console POST a fault at equipment the
  // backend has never heard of, which is a 404 with no agent response.
  const displaySelected = selected;

  const isFCC = Boolean(
    displaySelected &&
      (displaySelected.tag.includes("C-201") ||
        displaySelected.id.includes("C-201") ||
        displaySelected.name.toLowerCase().includes("fcc")),
  );

  return (
    <div className="mr-lowerdeck" data-testid="lower-deck">
      {/* 1. SELECTED EQUIPMENT CARD */}
      <section className="mr-deck-card mr-deck-card--selected" data-testid="selected-equipment">
        <header className="mr-card-head">
          <span className="mr-card-title">Selected Equipment</span>
        </header>

        {!displaySelected ? (
          <div className="mr-sel-empty" data-testid="no-asset-selected">
            <Icon name="equipment" size={22} />
            <b>No asset selected</b>
            <p>
              Pick a unit on the drawing to inspect its live instruments, take one out
              of service, or inject a failure.
            </p>
          </div>
        ) : (
        <div className="mr-sel-layout">
          {/* Left Column: 3D Visual & Core Details */}
          <div className="mr-sel-profile">
            <div className="mr-sel-visual">
              {isFCC ? (
                <div className="mr-sel-3d-frame">
                  <Image
                    src="/assets/refinery/fcc_unit_c201.jpg"
                    alt="FCC Unit C-201 3D Model"
                    width={110}
                    height={150}
                    className="mr-sel-3d-img"
                  />
                </div>
              ) : (
                <div className="mr-sel-glyph-frame">
                  <SimSymbol
                    type={symbolForEquipment(displaySelected.kind, displaySelected.name)}
                    state={(runtime?.states?.[displaySelected.id] ?? displaySelected.state ?? "normal") as SimVisualState}
                    size={72}
                    label={`${displaySelected.tag} — ${displaySelected.name}`}
                  />
                </div>
              )}
            </div>

            <div className="mr-sel-meta">
              <div className="mr-sel-title-row">
                <h3 className="mr-sel-name">{displaySelected.name}</h3>
                <span className="mr-sel-running-tag">
                  <span className="mr-running-dot" />
                  Running
                </span>
              </div>

              <div className="mr-sel-kv-grid">
                <div className="mr-sel-kv">
                  <span className="mr-kv-label">Type</span>
                  <span className="mr-kv-val">
                    {isFCC ? "Fluid Catalytic Cracking Unit" : displaySelected.kind}
                  </span>
                </div>
                <div className="mr-sel-kv">
                  <span className="mr-kv-label">Area</span>
                  <span className="mr-kv-val">{displaySelected.area_id}</span>
                </div>
                <div className="mr-sel-kv">
                  <span className="mr-kv-label">Capacity</span>
                  <span className="mr-kv-val">
                    {displaySelected.capacity ? `${displaySelected.capacity.toLocaleString()} bpd` : "18,000 bpd"}
                  </span>
                </div>
                <div className="mr-sel-kv">
                  <span className="mr-kv-label">Criticality</span>
                  <span className="mr-kv-val mr-kv-val--high">
                    <span className="mr-crit-dot" />
                    High
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Multi-tab Telemetry & Trends */}
          <div className="mr-sel-telemetry">
            <div className="mr-sel-tabs" role="tablist">
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === "live"}
                className={`mr-tab-btn ${activeTab === "live" ? "is-active" : ""}`}
                onClick={() => setActiveTab("live")}
              >
                Live Data
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === "trends"}
                className={`mr-tab-btn ${activeTab === "trends" ? "is-active" : ""}`}
                onClick={() => setActiveTab("trends")}
              >
                Trends
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === "maintenance"}
                className={`mr-tab-btn ${activeTab === "maintenance" ? "is-active" : ""}`}
                onClick={() => setActiveTab("maintenance")}
              >
                Maintenance
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === "related"}
                className={`mr-tab-btn ${activeTab === "related" ? "is-active" : ""}`}
                onClick={() => setActiveTab("related")}
              >
                Related
              </button>
            </div>

            {/* The instruments on THIS asset, with their real readings and the
                action that starts the Project 117 demo. The panel previously
                showed a fixed telemetry grid with values baked in and no way to
                take a point out of service, so the fault/agent sequence could
                not be started from the drawing at all. */}
            {displaySelected.sensors.length > 0 && (
              <div className="mr-sensorctl" data-testid="selected-sensors">
                <div className="mr-sensorctl__head">
                  <span>Instrumentation</span>
                  <span className="mr-sensorctl__count">
                    {displaySelected.sensors.length} point
                    {displaySelected.sensors.length === 1 ? "" : "s"}
                  </span>
                </div>
                {displaySelected.sensors.map((sensor) => {
                  const r = readings[sensor.id];
                  const q = runtime?.qualities?.[sensor.id] ?? "good";
                  const out = q === "bad";
                  return (
                    <div
                      key={sensor.id}
                      className={`mr-sensorctl__row${out ? " is-out" : ""}`}
                      data-sensor-row={sensor.id}
                    >
                      <span className={`mr-sensorctl__dot is-${out ? "crit" : "ok"}`} />
                      <span className="mr-sensorctl__tag">{sensor.tag}</span>
                      <span className="mr-sensorctl__meas">{sensor.measurement}</span>
                      <span className="mr-sensorctl__val">
                        {out
                          ? "OUT OF SERVICE"
                          : r
                            ? `${r.value} ${sensor.unit}`
                            : "—"}
                      </span>
                      <button
                        type="button"
                        className="mr-sensorctl__btn"
                        data-sensor-action={out ? "restore" : "disable"}
                        data-sensor-id={sensor.id}
                        disabled={!onSensorAction || busySensor === sensor.id}
                        title={
                          out
                            ? `Return ${sensor.tag} to service`
                            : `Take ${sensor.tag} out of service and engage the agents`
                        }
                        aria-label={
                          out
                            ? `Return ${sensor.tag} to service`
                            : `Take ${sensor.tag} out of service`
                        }
                        onClick={() =>
                          onSensorAction?.(sensor.id, out ? "restore" : "disable")
                        }
                      >
                        {busySensor === sensor.id ? "…" : out ? "Restore" : "Disable"}
                      </button>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Equipment failure modes. These lived only in the left rail, so
                when the rail was hidden to give the plant the width they became
                unreachable — the fault could not be injected at all. They belong
                with the asset that owns them. */}
            {onInjectFault && displaySelected.failure_modes.length > 0 && (
              <div className="mr-sensorctl" data-testid="selected-faults">
                <div className="mr-sensorctl__head">
                  <span>Inject failure</span>
                  <span className="mr-sensorctl__count">
                    {displaySelected.failure_modes.length} mode
                    {displaySelected.failure_modes.length === 1 ? "" : "s"}
                  </span>
                </div>
                <div className="mr-faults">
                  {displaySelected.failure_modes.map((fm) => (
                    <button
                      key={fm}
                      type="button"
                      className="sm-scenario"
                      data-fault-mode={fm}
                      data-equipment={displaySelected.id}
                      disabled={busyFault !== null}
                      onClick={() => onInjectFault(displaySelected.id, fm)}
                    >
                      {fm.replace(/_/g, " ")}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="mr-telemetry-grid">
              {/* Telemetry Item 1: Temperature */}
              <div className="mr-telem-card">
                <span className="mr-telem-label">Temperature</span>
                <div className="mr-telem-data">
                  <b className="mr-telem-val">520.4 °C</b>
                  <MiniSparkline color="#10b981" trend="up" />
                </div>
              </div>

              {/* Telemetry Item 2: Pressure */}
              <div className="mr-telem-card">
                <span className="mr-telem-label">Pressure</span>
                <div className="mr-telem-data">
                  <b className="mr-telem-val">1.8 bar</b>
                  <MiniSparkline color="#06b6d4" trend="flat" />
                </div>
              </div>

              {/* Telemetry Item 3: Flow In */}
              <div className="mr-telem-card">
                <span className="mr-telem-label">Flow In</span>
                <div className="mr-telem-data">
                  <b className="mr-telem-val">245.2 m³/h</b>
                  <MiniSparkline color="#3b82f6" trend="up" />
                </div>
              </div>

              {/* Telemetry Item 4: Flow Out */}
              <div className="mr-telem-card">
                <span className="mr-telem-label">Flow Out</span>
                <div className="mr-telem-data">
                  <b className="mr-telem-val">238.6 m³/h</b>
                  <MiniSparkline color="#3b82f6" trend="flat" />
                </div>
              </div>

              {/* Telemetry Item 5: Vibration */}
              <div className="mr-telem-card">
                <span className="mr-telem-label">Vibration</span>
                <div className="mr-telem-data">
                  <b className="mr-telem-val">0.12 mm/s</b>
                  <MiniSparkline color="#06b6d4" trend="down" />
                </div>
              </div>

              {/* Telemetry Item 6: Status */}
              <div className="mr-telem-card">
                <span className="mr-telem-label">Status</span>
                <div className="mr-telem-data">
                  <span className="mr-telem-status-tag">
                    <StatusDot state="ok" />
                    Normal
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
        )}
      </section>

      {/* 2. PROCESS STREAMS CARD */}
      <section className="mr-deck-card mr-deck-card--streams" data-testid="process-streams">
        <header className="mr-card-head">
          <span className="mr-card-title">Process Streams</span>
        </header>

        <div className="mr-streams-table-wrap">
          <table className="mr-streams-table">
            <thead>
              <tr>
                <th>Stream</th>
                <th>Flow (m³/h)</th>
                <th>Temperature</th>
                <th>Pressure</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {/* Every process line in the plant, with the engine's own flow and
                  the readings of the asset that feeds it. This table used to be
                  a fixed constant, so it showed the same four numbers whatever
                  the plant was doing. */}
              {plant.connections.map((c) => {
                const live = runtime?.pipes?.[c.id];
                const enabled = live ? live.enabled : c.enabled !== false;
                const leaking = Boolean(live ? live.leaking : c.leaking);
                const src = plant.equipment.find((e) => e.id === c.source);
                const meas: Record<string, number> = {};
                for (const sensor of src?.sensors ?? []) {
                  const r = readings[sensor.id];
                  if (r && Number.isFinite(r.value) && meas[sensor.measurement] == null) {
                    meas[sensor.measurement] = r.value;
                  }
                }
                const tone = leaking ? "warn" : enabled ? "ok" : "crit";
                return (
                  <tr
                    key={c.id}
                    data-stream-row={c.id}
                    className={selectedLineId === c.id ? "is-selected" : undefined}
                    style={{ cursor: "pointer" }}
                    onClick={() => onSelectLine(c.id)}
                  >
                    <td>
                      <span className="mr-stream-dot" style={{ background: mediumColor(c.medium) }} />
                      <span className="mr-stream-name">{c.medium ?? c.id}</span>
                    </td>
                    <td className="mr-mono">{enabled ? (live?.flow ?? c.flow ?? 0).toFixed(1) : "blocked"}</td>
                    <td className="mr-mono">{meas.temperature != null ? `${meas.temperature.toFixed(1)} °C` : "—"}</td>
                    <td className="mr-mono">{meas.pressure != null ? `${meas.pressure.toFixed(2)} bar` : "—"}</td>
                    <td>
                      <span className={`mr-stream-status-dot is-${tone}`} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* 3. RECENT EVENTS CARD */}
      <section className="mr-deck-card mr-deck-card--events" data-testid="recent-events">
        <header className="mr-card-head">
          <span className="mr-card-title">Recent Events</span>
          <button type="button" className="mr-card-link">
            View All →
          </button>
        </header>

        <div className="mr-events-feed">
          {MOCK_EVENTS.map((ev) => (
            <div key={ev.id} className="mr-event-row">
              <span className="mr-event-time">{ev.time}</span>
              <span
                className={`mr-event-badge mr-event-badge--${ev.type}`}
                title={ev.type}
              />
              <span className="mr-event-desc">{ev.text}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
