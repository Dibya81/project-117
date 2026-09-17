"use client";

import { AgentDispatchBoxes } from "@/components/sim/AgentDispatchBoxes";
import { ProcessMap, type ProcessMapSelection } from "@/components/sim/ProcessMap";
import type { AgentTask, EquipmentDef, PlantDef } from "@/lib/sim/types";
import type { CanvasRuntime, SpatialReading } from "@/components/sim/SchematicCanvas";

export interface TopologyRecoveryDecision {
  available: boolean;
  error?: string | null;
  diagnosis?: string;
  route: string[];
  block: string[];
  restore: string[];
  safety_confirmed: boolean;
  safety_concerns?: string[];
  rationale?: string;
}

export function MeridianRefineryCanvas({
  plant,
  runtime,
  readings,
  selected,
  onSelectEquipment,
  failover = null,
  activeIncident = null,
  tasks = [],
  models = {},
  recoveryDecision = null,
  fixedCamera = false,
  editable = false,
  onEquipmentMove,
  connectMode = false,
  connectFromId = null,
  onPortClick,
  selectedLineId = null,
  onSelectLine,
  isolatedLines = [],
  isolatedEquipment = [],
}: {
  plant: PlantDef;
  runtime: CanvasRuntime | null;
  readings: Record<string, SpatialReading>;
  selected: EquipmentDef | null;
  onSelectEquipment: (eq: EquipmentDef) => void;
  failover?: { from: string; to: string } | null;
  activeIncident?: { origin_equipment?: string; affected?: string[]; origin_sensor?: string | null; title?: string; severity?: string } | null;
  tasks?: AgentTask[];
  models?: Record<string, string | null>;
  recoveryDecision?: TopologyRecoveryDecision | null;
  /** Lock the schematic camera (the live refinery). Off in the builder. */
  fixedCamera?: boolean;
  /** Edit mode (the builder): drag units, snap to grid, wire port-to-port. */
  editable?: boolean;
  onEquipmentMove?: (id: string, x: number, y: number) => void;
  connectMode?: boolean;
  connectFromId?: string | null;
  onPortClick?: (equipmentId: string, port: "in" | "out") => void;
  /** The line picked on the drawing. A line is a first-class selection. */
  selectedLineId?: string | null;
  onSelectLine?: (id: string | null) => void;
  /** The fault's own isolation, drawn before any agent has spoken. */
  isolatedLines?: string[];
  isolatedEquipment?: string[];
}) {
  const selection: ProcessMapSelection | null = selectedLineId
    ? { kind: "pipe", id: selectedLineId }
    : selected
      ? { kind: "equipment", id: selected.id }
      : null;
  const highlight = activeIncident
    ? [activeIncident.origin_equipment, ...(activeIncident.affected ?? [])].filter(Boolean) as string[]
    : [];
  const lineCount = plant.connections.length;
  const blocked = recoveryDecision?.available ? recoveryDecision.block.filter((id) => plant.connections.some((c) => c.id === id)) : [];
  const restored = recoveryDecision?.available ? recoveryDecision.restore.filter((id) => plant.connections.some((c) => c.id === id)) : [];

  return (
    <div className="mr-topology-canvas">
      <div className="mr-topology-status" aria-live="polite">
        <span>{lineCount} real topology connections</span>
        {activeIncident?.origin_sensor && <span>Failed sensor: {activeIncident.origin_sensor}</span>}
        {recoveryDecision?.available && recoveryDecision.safety_confirmed && (
          <span>Verified route: {recoveryDecision.route.length} line{recoveryDecision.route.length === 1 ? "" : "s"}</span>
        )}
        {recoveryDecision && !recoveryDecision.available && (
          <span className="is-critical">{recoveryDecision.error ?? "Decision unavailable"}</span>
        )}
      </div>

      {recoveryDecision?.available && recoveryDecision.safety_confirmed && (
        <div className="mr-recovery-strip" data-testid="topology-recovery-strip">
          <span>Decision executed from real connection IDs</span>
          <b>BLOCK {blocked.length ? blocked.join(", ") : "none"}</b>
          <b>RESTORE {restored.length ? restored.join(", ") : "none"}</b>
        </div>
      )}

      <ProcessMap
        plant={plant}
        runtime={runtime}
        readings={readings}
        selection={selection}
        onSelect={(sel) => {
          // A line selection is reported, not swallowed: the Builder's
          // connection inspector edits the line the operator actually clicked.
          if (sel?.kind === "pipe") {
            onSelectLine?.(sel.id);
            return;
          }
          if (sel?.kind === "equipment") {
            const eq = plant.equipment.find((e) => e.id === sel.id);
            if (eq) onSelectEquipment(eq);
            return;
          }
          onSelectLine?.(null);
        }}
        highlight={highlight}
        focusId={activeIncident?.origin_equipment ?? null}
        failover={failover}
        recoveryDecision={recoveryDecision}
        fixedCamera={fixedCamera}
        editable={editable}
        onEquipmentMove={onEquipmentMove}
        connectMode={connectMode}
        connectFromId={connectFromId}
        onPortClick={onPortClick}
        isolatedLines={isolatedLines}
        isolatedEquipment={isolatedEquipment}
      />

      <AgentDispatchBoxes tasks={tasks} models={models} />
    </div>
  );
}
