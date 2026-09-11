/**
 * Node context menu.
 *
 * Opened by clicking a unit in builder mode. Actions act on the real store:
 * Disable writes `status: "disabled"`, Remove deletes the node *and* its
 * sensors and edges, and each fault type writes an actual change to the unit's
 * status and to the readings of the sensors physically attached to it.
 *
 * Fault types are the four the schema defines — `disabled`, `removed`,
 * `sensor_drift`, `leak` — not invented names, so what the UI sends matches the
 * `fault_events.fault_type` column the orchestrator writes to.
 */
import { useEffect, useRef } from "react";
import { useSim } from "../store/simStore";
import type { FaultType } from "../types";

const FAULTS: { type: FaultType; label: string; hint: string }[] = [
  { type: "disabled", label: "Disable unit", hint: "status → disabled, no telemetry change" },
  { type: "removed", label: "Remove from service", hint: "attached sensors drop to zero" },
  { type: "sensor_drift", label: "Sensor drift", hint: "readings step outside the normal band" },
  { type: "leak", label: "Leak / loss of containment", hint: "readings fall below the normal band" },
];

export function ContextMenu({ onInject }: { onInject: (nodeId: string, fault: FaultType) => void }) {
  const menu = useSim((s) => s.menu);
  const nodes = useSim((s) => s.nodes);
  const close = useSim((s) => s.closeMenu);
  const openDrawer = useSim((s) => s.openDrawer);
  const removeNode = useSim((s) => s.removeNode);
  const duplicateNode = useSim((s) => s.duplicateNode);
  const setStatus = useSim((s) => s.setStatus);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menu) return;
    const onDown = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) close();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [menu, close]);

  if (!menu) return null;
  const node = nodes.find((n) => n.id === menu.nodeId);
  if (!node) return null;

  const data = node.data as { tag?: string; status?: string };
  const isEquipment = node.type === "equipment";

  // Keep the menu inside the viewport.
  const left = Math.min(menu.x, window.innerWidth - 280);
  const top = Math.min(menu.y, window.innerHeight - 380);

  return (
    <div className="ctxmenu" style={{ left, top }} ref={ref} role="menu" aria-label={`Actions for ${data.tag ?? node.id}`}>
      <div className="ctxmenu__head">
        <span className="ctxmenu__tag">{data.tag ?? node.id}</span>
        <span className={`ctxmenu__status ctxmenu__status--${data.status ?? "normal"}`}>
          {data.status ?? "normal"}
        </span>
      </div>

      <button role="menuitem" onClick={() => openDrawer(node.id)}>Info</button>

      {isEquipment && (
        <>
          <button
            role="menuitem"
            onClick={() => {
              setStatus(node.id, "disabled");
              close();
            }}
          >
            Disable
          </button>
          <button
            role="menuitem"
            onClick={() => {
              setStatus(node.id, "normal");
              close();
            }}
          >
            Return to normal
          </button>
        </>
      )}

      <button
        role="menuitem"
        onClick={() => {
          duplicateNode(node.id);
          close();
        }}
      >
        Duplicate
      </button>

      <div className="ctxmenu__sep" />

      {isEquipment && (
        <>
          <div className="ctxmenu__section">Simulate fault</div>
          {FAULTS.map((f) => (
            <button
              key={f.type}
              role="menuitem"
              className="ctxmenu__fault"
              onClick={() => onInject(node.id, f.type)}
            >
              <span>{f.label}</span>
              <em>{f.hint}</em>
            </button>
          ))}
          <div className="ctxmenu__sep" />
        </>
      )}

      <button role="menuitem" className="ctxmenu__danger" onClick={() => removeNode(node.id)}>
        Remove
      </button>
    </div>
  );
}
