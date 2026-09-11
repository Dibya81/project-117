/**
 * Circuit validation.
 *
 * Real graph traversal, not a checklist. "Validate circuit" runs an
 * undirected BFS over the current canvas to find connected components, then
 * checks the structural rules the schema implies:
 *
 *   - a signal wire must terminate on equipment, never on another sensor
 *   - a unit with no connections at all is an orphan
 *   - a plant with more than one component is split (each extra component is
 *     reported with its members so the gap is findable, not just counted)
 *
 * The report is deterministic and ordered, so the same canvas always produces
 * the same report.
 */
import type { Edge, Node } from "reactflow";
import type { EquipmentType } from "../types";

export type IssueLevel = "error" | "warning";

export interface Issue {
  level: IssueLevel;
  code: "orphan" | "sensor_to_sensor" | "wire_target" | "split_plant" | "self_loop";
  message: string;
  nodeIds: string[];
}

export interface ValidationReport {
  ok: boolean;
  issues: Issue[];
  components: string[][];
  nodeCount: number;
  edgeCount: number;
}

function adjacency(nodeIds: string[], edges: Edge[]): Map<string, Set<string>> {
  const adj = new Map<string, Set<string>>();
  for (const id of nodeIds) adj.set(id, new Set());
  for (const e of edges) {
    if (!adj.has(e.source) || !adj.has(e.target)) continue;
    adj.get(e.source)!.add(e.target);
    adj.get(e.target)!.add(e.source);
  }
  return adj;
}

/** Breadth-first connected components over the undirected edge set. */
export function connectedComponents(nodeIds: string[], edges: Edge[]): string[][] {
  const adj = adjacency(nodeIds, edges);
  const seen = new Set<string>();
  const out: string[][] = [];
  for (const start of nodeIds) {
    if (seen.has(start)) continue;
    const queue = [start];
    const comp: string[] = [];
    seen.add(start);
    while (queue.length) {
      const id = queue.shift()!;
      comp.push(id);
      for (const next of adj.get(id) ?? []) {
        if (!seen.has(next)) {
          seen.add(next);
          queue.push(next);
        }
      }
    }
    out.push(comp);
  }
  return out;
}

/** Depth-first reachability from one node — used for the "is anything wired" probe. */
export function reachableFrom(start: string, edges: Edge[]): Set<string> {
  const adj = adjacency([start, ...edges.flatMap((e) => [e.source, e.target])], edges);
  const seen = new Set<string>([start]);
  const stack = [start];
  while (stack.length) {
    const id = stack.pop()!;
    for (const next of adj.get(id) ?? []) {
      if (!seen.has(next)) {
        seen.add(next);
        stack.push(next);
      }
    }
  }
  return seen;
}

export function validateCircuit(nodes: Node[], edges: Edge[]): ValidationReport {
  const issues: Issue[] = [];
  const ids = nodes.map((n) => n.id);
  const idSet = new Set(ids);
  const byId = new Map(nodes.map((n) => [n.id, n]));

  const isSensor = (id: string) => byId.get(id)?.type === "sensor";
  const isEquipment = (id: string) => byId.get(id)?.type === "equipment";

  // --- structural edge rules -------------------------------------------------
  for (const e of edges) {
    if (!idSet.has(e.source) || !idSet.has(e.target)) continue;

    if (e.source === e.target) {
      issues.push({
        level: "error",
        code: "self_loop",
        message: `${label(byId, e.source)} is connected to itself.`,
        nodeIds: [e.source],
      });
      continue;
    }
    if (isSensor(e.source) && isSensor(e.target)) {
      issues.push({
        level: "error",
        code: "sensor_to_sensor",
        message: `Signal wire ${label(byId, e.source)} → ${label(byId, e.target)} joins two sensors. Sensors wire into equipment, not into each other.`,
        nodeIds: [e.source, e.target],
      });
    }
    if (e.data?.kind === "wire" && !isEquipment(e.source) && !isEquipment(e.target)) {
      issues.push({
        level: "error",
        code: "wire_target",
        message: `Signal wire ${label(byId, e.source)} → ${label(byId, e.target)} terminates on no equipment.`,
        nodeIds: [e.source, e.target],
      });
    }
  }

  // --- connectivity ----------------------------------------------------------
  const components = connectedComponents(ids, edges);
  const connected = adjacency(ids, edges);

  for (const id of ids) {
    // A compartment is structure, not plant.
    if (byId.get(id)?.type === "zone") continue;
    if ((connected.get(id)?.size ?? 0) === 0) {
      issues.push({
        level: "warning",
        code: "orphan",
        message: `${label(byId, id)} has no connections — it is inert until wired into the process.`,
        nodeIds: [id],
      });
    }
  }

  const realComponents = components.filter((c) =>
    c.some((id) => byId.get(id)?.type !== "zone"),
  );
  if (realComponents.length > 1) {
    const sizes = realComponents.map((c) => c.length).sort((a, b) => b - a);
    issues.push({
      level: "warning",
      code: "split_plant",
      message: `The canvas has ${realComponents.length} disconnected groups (${sizes.join(", ")} nodes). A fault cannot propagate between them.`,
      nodeIds: realComponents.slice(1).flat(),
    });
  }

  const order: Record<IssueLevel, number> = { error: 0, warning: 1 };
  issues.sort((a, b) => order[a.level] - order[b.level] || a.code.localeCompare(b.code));

  return {
    ok: !issues.some((i) => i.level === "error"),
    issues,
    components: realComponents,
    nodeCount: nodes.filter((n) => n.type !== "zone").length,
    edgeCount: edges.length,
  };
}

function label(byId: Map<string, Node>, id: string): string {
  const n = byId.get(id);
  const d = (n?.data ?? {}) as { tag?: string; label?: string };
  return d.tag ?? d.label ?? id;
}

/* ------------------------------------------------------------ live wiring */

const SENSOR_TYPES = new Set(["PT", "TT", "FT", "LT", "VT"]);

export interface ConnectionAttempt {
  /** React Flow hands these over as nullable while a wire is being dragged. */
  source: string | null;
  target: string | null;
  sourceType?: string;
  targetType?: string;
}

/**
 * Rule applied while dragging a wire. React Flow calls this on every hover, so
 * it only answers "may these two join" — the fuller report comes from
 * `validateCircuit`.
 */
export function isValidConnection(
  attempt: ConnectionAttempt,
  nodes: Node[],
  existing: Edge[],
): boolean {
  const { source, target, sourceType, targetType } = attempt;
  if (!source || !target || source === target) return false;

  const byId = new Map(nodes.map((n) => [n.id, n]));
  const s = byId.get(source);
  const t = byId.get(target);
  if (!s || !t) return false;
  if (s.type === "zone" || t.type === "zone") return false;

  // Sensors are sources of signal only: a sensor may never be the target.
  if (targetType === "sensor" || t.type === "sensor") return false;
  // Equipment does not feed a sensor.
  if (sourceType === "equipment" && t.type === "sensor") return false;
  // Sensor → equipment is the only sensor edge shape allowed.
  if (s.type === "sensor") return t.type === "equipment";

  if (existing.some((e) => e.source === source && e.target === target)) return false;
  return true;
}

export const SENSOR_TYPE_SET = SENSOR_TYPES;

export const EQUIPMENT_LABEL: Record<EquipmentType, string> = {
  pump: "Pump",
  valve: "Valve",
  tank: "Tank",
  heat_exchanger: "Heat exchanger",
  compressor: "Compressor",
  compressor_blower: "Compressor / blower",
  column: "Column",
  reactor: "Reactor",
  furnace: "Furnace",
  conveyor: "Conveyor",
  motor: "Motor",
  caster: "Caster",
  mill_stand: "Mill stand",
};
