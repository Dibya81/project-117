/**
 * Info drawer.
 *
 * Reads straight off the node's `data` object — no second lookup, no refetch.
 * For equipment that is the row from `equipment` in the plant JSON (tag, type,
 * zone, install_date, expected_lifespan_years, age_years, last_inspection,
 * status, failure_modes). For a sensor it is the `sensors` row plus its
 * threshold band. A sensor's owning unit is resolved through the connections,
 * so the drawer reports the attachment the graph actually has.
 */
import { useSim } from "../store/simStore";
import type { Equipment, Sensor } from "../types";
import { SENSOR_LABEL, formatBand, formatValue, lifeUsed, sensorLevel } from "../sim/thresholds";
import { EQUIPMENT_LABEL } from "../sim/validate";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="drawer__row">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

export function InfoDrawer() {
  const id = useSim((s) => s.drawerNodeId);
  const nodes = useSim((s) => s.nodes);
  const edges = useSim((s) => s.edges);
  const plant = useSim((s) => s.plant);
  const close = useSim((s) => s.openDrawer);
  const faulted = useSim((s) => s.faulted);

  if (!id) return null;
  const node = nodes.find((n) => n.id === id);
  if (!node) return null;

  const zoneName = (nodeId: string) => {
    const n = nodes.find((x) => x.id === nodeId);
    const parent = n?.parentId;
    const zoneId = parent?.replace("zone:", "");
    return plant?.zones.find((z) => z.id === zoneId)?.name ?? "—";
  };

  const isEquipment = node.type === "equipment";
  const fault = faulted[id];

  return (
    <aside className="drawer" aria-label="Node information">
      <header className="drawer__head">
        <div>
          <span className="drawer__kicker">{isEquipment ? "Equipment" : "Sensor"}</span>
          <h2>{(node.data as { tag?: string }).tag ?? node.id}</h2>
        </div>
        <button className="drawer__close" onClick={() => close(null)} aria-label="Close">
          ×
        </button>
      </header>

      <dl className="drawer__body">
        {isEquipment ? (
          <>
            <Row label="Tag">{(node.data as Equipment).tag}</Row>
            <Row label="Type">{EQUIPMENT_LABEL[(node.data as Equipment).type] ?? (node.data as Equipment).type}</Row>
            <Row label="Zone">{zoneName(node.id)}</Row>
            <Row label="Install date">{(node.data as Equipment).install_date || "—"}</Row>
            <Row label="Expected life">{(node.data as Equipment).expected_lifespan_years} years</Row>
            <Row label="Age">
              {(node.data as Equipment).age_years.toFixed(1)} years
              <span className="drawer__bar" aria-hidden="true">
                <i
                  style={{
                    width: `${Math.round(
                      lifeUsed(
                        (node.data as Equipment).age_years,
                        (node.data as Equipment).expected_lifespan_years,
                      ) * 100,
                    )}%`,
                  }}
                />
              </span>
            </Row>
            <Row label="Last inspection">{(node.data as Equipment).last_inspection || "—"}</Row>
            <Row label="Status">
              <span className={`pill pill--${(node.data as Equipment).status}`}>
                {(node.data as Equipment).status}
              </span>
              {/* The seed derives equipment status from age vs expected life, and
                  generates every sensor reading inside its normal band. Those are
                  two different axes, so say which one a status came from instead
                  of letting "critical" read as an alarm. */}
              {!fault && (node.data as Equipment).status !== "normal" && (
                <span className="drawer__basis">
                  from age — {(node.data as Equipment).age_years.toFixed(1)}y of{" "}
                  {(node.data as Equipment).expected_lifespan_years}y expected life
                </span>
              )}
              {fault && <span className="drawer__basis">from injected fault</span>}
            </Row>
            <Row label="Failure modes">
              <span className="drawer__modes">
                {(node.data as Equipment).failure_modes.length
                  ? (node.data as Equipment).failure_modes.map((m) => <span key={m}>{m}</span>)
                  : "none recorded"}
              </span>
            </Row>
            <Row label="Attached sensors">
              {plant?.sensors.filter((s) => s.equipment_id === node.id).length ?? 0}
            </Row>
            {fault && (
              <Row label="Fault">
                <span className="pill pill--critical">{fault.faultType}</span>
                <span className="drawer__at">{new Date(fault.at).toLocaleTimeString()}</span>
              </Row>
            )}
          </>
        ) : (
          <>
            <Row label="Tag">{(node.data as Sensor).tag}</Row>
            <Row label="Measurement">{SENSOR_LABEL[(node.data as Sensor).type] ?? (node.data as Sensor).type}</Row>
            <Row label="Zone">{zoneName(node.id)}</Row>
            <Row label="Attached to">
              {(() => {
                const attached = (node.data as Sensor).equipment_id;
                if (attached) {
                  const owner = nodes.find((n) => n.id === attached);
                  return (owner?.data as { tag?: string })?.tag ?? attached;
                }
                const wire = edges.find((e) => e.source === node.id && e.target.startsWith(""));
                const target = wire ? nodes.find((n) => n.id === wire.target) : undefined;
                return (target?.data as { tag?: string })?.tag ?? "unassigned";
              })()}
            </Row>
            <Row label="Normal band">{formatBand(node.data as Sensor)}</Row>
            <Row label="Current">{formatValue(node.data as Sensor)}</Row>
            <Row label="Reading">
              <span className={`pill pill--${sensorLevel(node.data as Sensor)}`}>
                {sensorLevel(node.data as Sensor)}
              </span>
            </Row>
          </>
        )}
      </dl>
    </aside>
  );
}
