"use client";

/**
 * PlantLowerDeck — the information band beneath the process drawing.
 *
 * Three registers an operator reads together: what is selected, what is moving
 * through the plant, and what just happened. Every cell is backed by live state:
 * the asset strip from the engine's equipment and its own instruments, the
 * stream table from each line's medium, flow, temperature and pressure, and the
 * event log from the SSE stream the page already subscribes to.
 *
 * Nothing here is a summary invented for display. Where a value does not exist
 * — a line with no temperature instrument — the cell says so.
 */

import { StatusDot } from "@/components/ui/primitives";
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

/** The instruments on a line's source asset that share its medium's physics. */
function readingsForAsset(
  eq: EquipmentDef | undefined,
  readings: Record<string, SpatialReading>,
): Partial<Record<SensorDef["measurement"], number>> {
  const out: Partial<Record<SensorDef["measurement"], number>> = {};
  if (!eq) return out;
  for (const s of eq.sensors) {
    const r = readings[s.id];
    if (r && Number.isFinite(r.value) && out[s.measurement] == null) out[s.measurement] = r.value;
  }
  return out;
}

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
}: {
  plant: PlantDef;
  runtime: CanvasRuntime | null;
  readings: Record<string, SpatialReading>;
  selected: EquipmentDef | null;
  events: SimEvent[];
  onSelectEquipment: (eq: EquipmentDef) => void;
  onSelectLine: (lineId: string) => void;
  selectedLineId: string | null;
  /** Disable or restore an instrument. Hits the engine, not the display. */
  onSensorAction?: (sensorId: string, action: "disable" | "restore") => void;
  busySensor?: string | null;
}) {
  const byId = new Map(plant.equipment.map((e) => [e.id, e]));
  const stream = plant.connections.slice(0, 60);
  // Newest first, and only the events that carry a type — a frame with no type
  // is not something that happened.
  const recent = [...events].reverse().filter((e) => e.type).slice(0, 12);

  return (
    <div className="lowerdeck" data-testid="lower-deck">
      {/* SELECTED EQUIPMENT ------------------------------------------------- */}
      <section className="ldcard ldcard--selected" data-testid="selected-equipment">
        <header className="ldcard__head">
          <Icon name="equipment" size={13} />
          <span className="ldcard__title">Selected equipment</span>
        </header>
        {!selected ? (
          <p className="ldcard__empty">
            Select an asset on the process drawing to inspect it here.
          </p>
        ) : (
          <>
            <div className="ldsel">
              <span className={`ldsel__glyph is-${runtime?.states?.[selected.id] ?? selected.state}`}>
                <SimSymbol
                  type={symbolForEquipment(selected.kind, selected.name)}
                  state={(runtime?.states?.[selected.id] ?? selected.state ?? "normal") as SimVisualState}
                  size={46}
                  label={`${selected.tag} — ${selected.name}`}
                />
              </span>
              <div className="ldsel__id">
                <b>{selected.tag}</b>
                <span>{selected.name}</span>
                <span className="ldsel__meta">
                  {selected.kind} · {selected.area_id} · criticality {selected.criticality}
                </span>
              </div>
              <StatusDot state={runtime?.states?.[selected.id] === "normal" ? "ok" : "warning"} />
            </div>
            <dl className="ldsel__kpis">
              {selected.sensors.slice(0, 6).map((s) => {
                const r = readings[s.id];
                const q = runtime?.qualities?.[s.id] ?? "good";
                return (
                  <div key={s.id} className="ldsel__kpi" data-kpi-sensor={s.id}>
                    <dt>{s.tag}</dt>
                    <dd className={q !== "good" ? "is-critical" : undefined}>
                      {r ? `${fmt(r.value)} ${s.unit}` : "—"}
                    </dd>
                    <span className="ldsel__range">
                      {q !== "good" ? "OUT OF SERVICE" : `${s.normal_min}–${s.normal_max} ${s.unit}`}
                    </span>
                    {/* The signal-failure demo starts here. This control was on
                        the old left rail; removing the rail removed the only way
                        to take a transmitter out of service. */}
                    {onSensorAction && (
                      <button
                        type="button"
                        className="ldsel__act"
                        data-sensor-action={q === "bad" ? "restore" : "disable"}
                        data-sensor-id={s.id}
                        disabled={busySensor === s.id}
                        title={
                          q === "bad"
                            ? `Return ${s.tag} to service`
                            : `Take ${s.tag} out of service and engage the agents`
                        }
                        aria-label={
                          q === "bad"
                            ? `Return ${s.tag} to service`
                            : `Take ${s.tag} out of service`
                        }
                        onClick={() => onSensorAction(s.id, q === "bad" ? "restore" : "disable")}
                      >
                        {busySensor === s.id ? "…" : q === "bad" ? "Restore" : "Disable"}
                      </button>
                    )}
                  </div>
                );
              })}
              {selected.sensors.length === 0 && (
                <p className="ldcard__empty">This asset carries no instruments.</p>
              )}
            </dl>
          </>
        )}
      </section>

      {/* PROCESS STREAMS ---------------------------------------------------- */}
      <section className="ldcard ldcard--streams" data-testid="process-streams">
        <header className="ldcard__head">
          <Icon name="pulse" size={13} />
          <span className="ldcard__title">Process streams</span>
          <span className="ldcard__sub">{stream.length} lines · live</span>
        </header>
        <div className="ldscroll">
          <table className="simdata">
            <thead>
              <tr>
                <th>Stream</th>
                <th>Flow m³/h</th>
                <th>Temp °C</th>
                <th>Press bar</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {stream.map((c) => {
                const live = runtime?.pipes?.[c.id];
                const enabled = live ? live.enabled : c.enabled !== false;
                const leaking = Boolean(live ? live.leaking : c.leaking);
                const src = byId.get(c.source);
                const meas = readingsForAsset(src, readings);
                return (
                  <tr
                    key={c.id}
                    data-stream-row={c.id}
                    className={selectedLineId === c.id ? "is-selected" : undefined}
                    onClick={() => onSelectLine(c.id)}
                  >
                    <td>
                      <span className="ldstream__dot" style={{ background: mediumColor(c.medium) }} />
                      {c.medium ?? c.id}
                    </td>
                    <td className={!enabled ? "is-muted" : undefined}>
                      {enabled ? fmt(live?.flow ?? c.flow) : "blocked"}
                    </td>
                    <td className="is-muted">{fmt(meas.temperature)}</td>
                    <td className="is-muted">{fmt(meas.pressure)}</td>
                    <td className={leaking ? "is-warning" : !enabled ? "is-critical" : "is-muted"}>
                      {leaking ? "LEAKING" : !enabled ? "BLOCKED" : (c.status ?? "normal").toUpperCase()}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* RECENT EVENTS ------------------------------------------------------ */}
      <section className="ldcard ldcard--events" data-testid="recent-events">
        <header className="ldcard__head">
          <Icon name="history" size={13} />
          <span className="ldcard__title">Recent events</span>
          <span className="ldcard__sub">{events.length} on the stream</span>
        </header>
        {recent.length === 0 ? (
          <p className="ldcard__empty">
            Nothing has been emitted yet. Events appear as the engine reports them —
            the list is not padded to look busy.
          </p>
        ) : (
          <ol className="ldevents">
            {recent.map((e) => {
              const tone = String(e.type).startsWith("fault") || String(e.type).includes("critical")
                ? "crit"
                : String(e.type).startsWith("alarm") || String(e.type).startsWith("incident")
                  ? "warn"
                  : "ok";
              return (
                <li key={`${e.seq}-${e.type}`} data-event-type={e.type}>
                  <span className={`ldevents__dot is-${tone}`} />
                  <span className="ldevents__seq">#{e.seq}</span>
                  <span className="ldevents__type">{e.type}</span>
                  <span className="ldevents__t">{fmt(e.at, 1)}s</span>
                </li>
              );
            })}
          </ol>
        )}
      </section>
    </div>
  );
}
