/**
 * Connection semantics.
 *
 * A connection has two independent axes:
 *
 *   kind      the physical carrier — pipe | signal | control | power.
 *             Drives rendering (thickness, dash) and, for `pipe`, whether the
 *             edge participates in process topology.
 *
 *   relation  what the link MEANS — SENSOR_OF, REDUNDANCY, MATERIAL_FLOW, …
 *             This is what the agents reason over. `kind` cannot express
 *             "this instrument is the approved backup for that one", which is
 *             precisely what failover needs.
 *
 * `relationOf` derives a relation for legacy data that only carries `kind`, so
 * nothing has to be migrated and every consumer works on both.
 */
import type { ConnectionDef, ConnectionKind, RelationType } from "./types";

export interface RelationMeta {
  id: RelationType;
  label: string;
  /** Where this relation may legitimately start. */
  from: ("equipment" | "sensor")[];
  /** Where it may legitimately end. */
  to: ("equipment" | "sensor")[];
  /** Shown in the connect dialog to explain the choice. */
  hint: string;
}

export const RELATIONS: RelationMeta[] = [
  {
    id: "SENSOR_OF",
    label: "Sensor of",
    from: ["sensor"],
    to: ["equipment"],
    hint: "This instrument measures that unit. The usual sensor wiring.",
  },
  {
    id: "TELEMETRY_FROM",
    label: "Telemetry from",
    from: ["equipment"],
    to: ["sensor"],
    hint: "The unit publishes telemetry through that instrument.",
  },
  {
    id: "MATERIAL_FLOW",
    label: "Material flow",
    from: ["equipment"],
    to: ["equipment"],
    hint: "Process stream from one unit to the next.",
  },
  {
    id: "FEEDS",
    label: "Feeds",
    from: ["equipment"],
    to: ["equipment"],
    hint: "Upstream supply into a downstream unit.",
  },
  {
    id: "OUTPUT_TO",
    label: "Output to",
    from: ["equipment"],
    to: ["equipment"],
    hint: "Product leaves this unit for the next stage.",
  },
  {
    id: "CONTROL_SIGNAL",
    label: "Control signal",
    from: ["equipment", "sensor"],
    to: ["equipment"],
    hint: "A command path: the target acts on this signal.",
  },
  {
    id: "POWER_DEPENDENCY",
    label: "Power dependency",
    from: ["equipment", "sensor"],
    to: ["equipment"],
    hint: "The target cannot run without the source.",
  },
  {
    id: "SAFETY_INTERLOCK",
    label: "Safety interlock",
    from: ["equipment", "sensor"],
    to: ["equipment"],
    hint: "A trip path — the source can force the target safe.",
  },
  {
    id: "PROCESS_DEPENDENCY",
    label: "Process dependency",
    from: ["equipment"],
    to: ["equipment"],
    hint: "The target depends on the source for correct operation.",
  },
  {
    id: "REDUNDANCY",
    label: "Redundancy",
    from: ["sensor", "equipment"],
    to: ["sensor", "equipment"],
    hint: "A backup. Failover will prefer a valid redundant partner.",
  },
  {
    id: "MONITORS",
    label: "Monitors",
    from: ["sensor"],
    to: ["equipment"],
    hint: "The instrument watches that unit but does not measure it directly.",
  },
];

export const RELATION_BY_ID: Record<RelationType, RelationMeta> = Object.fromEntries(
  RELATIONS.map((r) => [r.id, r]),
) as Record<RelationType, RelationMeta>;

/** Default relation implied by the physical carrier. */
const KIND_DEFAULT: Record<ConnectionKind, RelationType> = {
  pipe: "MATERIAL_FLOW",
  signal: "SENSOR_OF",
  control: "CONTROL_SIGNAL",
  power: "POWER_DEPENDENCY",
};

/** The relation of a connection, falling back to its `kind` for legacy data. */
export function relationOf(c: Pick<ConnectionDef, "kind" | "relation">): RelationType {
  return c.relation ?? KIND_DEFAULT[c.kind] ?? "MATERIAL_FLOW";
}

/** The carrier implied by a relation, for when a user picks a relation first. */
export function kindForRelation(r: RelationType): ConnectionKind {
  switch (r) {
    case "SENSOR_OF":
    case "TELEMETRY_FROM":
    case "MONITORS":
      return "signal";
    case "CONTROL_SIGNAL":
    case "SAFETY_INTERLOCK":
      return "control";
    case "POWER_DEPENDENCY":
      return "power";
    default:
      return "pipe";
  }
}

/** True when this relation should carry process flow and shape the topology. */
export function isProcessRelation(r: RelationType): boolean {
  return (
    r === "MATERIAL_FLOW" ||
    r === "FEEDS" ||
    r === "OUTPUT_TO" ||
    r === "PROCESS_DEPENDENCY"
  );
}

/**
 * Relations offered for a given endpoint pair, so the UI never presents a
 * choice that the topology would reject.
 */
export function validRelations(
  from: "equipment" | "sensor",
  to: "equipment" | "sensor",
): RelationMeta[] {
  return RELATIONS.filter((r) => r.from.includes(from) && r.to.includes(to));
}

export const RELATION_TONE: Record<RelationType, string> = {
  SENSOR_OF: "#2563eb",
  TELEMETRY_FROM: "#2563eb",
  MATERIAL_FLOW: "#0f766e",
  FEEDS: "#0f766e",
  OUTPUT_TO: "#0f766e",
  CONTROL_SIGNAL: "#7c3aed",
  POWER_DEPENDENCY: "#b45309",
  SAFETY_INTERLOCK: "#dc2626",
  PROCESS_DEPENDENCY: "#475569",
  REDUNDANCY: "#10b981",
  MONITORS: "#0891b2",
};
