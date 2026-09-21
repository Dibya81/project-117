/**
 * Simulation store.
 *
 * Holds one plant and its canvas. Everything the pages render comes from here,
 * so the hub, the builder and a prebuilt plant all drive the same code path —
 * only the initial `plant` differs.
 *
 * The store never invents telemetry. Sensor values come from the dataset; the
 * only values it writes are the ones a user explicitly sets in the builder.
 */
import { create } from "zustand";
import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection as RFConnection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
} from "reactflow";
import { emptyPlant } from "../data/service";
import { layoutPlant, placeInNearestZone, type LayoutResult } from "../sim/layout";
import { validateCircuit, type ValidationReport } from "../sim/validate";
import type {
  Connection,
  Equipment,
  EquipmentStatus,
  EquipmentType,
  FaultType,
  Plant,
  Sensor,
  SensorType,
} from "../types";

/** Default engineering bands for a sensor dropped in the builder. */
const SENSOR_DEFAULTS: Record<SensorType, { label: string; unit: string; min: number; max: number }> = {
  PT: { label: "pressure", unit: "bar", min: 0, max: 25 },
  TT: { label: "temperature", unit: "C", min: 0, max: 250 },
  FT: { label: "flow", unit: "m3/h", min: 0, max: 200 },
  LT: { label: "level", unit: "%", min: 0, max: 100 },
  VT: { label: "vibration", unit: "mm/s", min: 0, max: 10 },
};

const EQUIPMENT_DEFAULT_LIFESPAN: Record<EquipmentType, number> = {
  pump: 12, valve: 15, tank: 25, heat_exchanger: 18, compressor: 15,
  compressor_blower: 15, column: 25, reactor: 20, furnace: 20,
  conveyor: 12, motor: 15, caster: 20, mill_stand: 20,
};

const EQUIPMENT_FAILURE_MODES: Record<EquipmentType, string[]> = {
  pump: ["bearing wear", "seal leak", "cavitation"],
  valve: ["actuator fault", "stem sticking", "seat leakage"],
  tank: ["level excursion", "corrosion", "vapour loss"],
  heat_exchanger: ["fouling", "tube leak", "bypass"],
  compressor: ["bearing wear", "surge", "lube oil degradation"],
  compressor_blower: ["bearing wear", "surge", "belt slip"],
  column: ["tray fouling", "flooding", "corrosion at feed nozzle"],
  reactor: ["catalyst deactivation", "hot spot", "pressure excursion"],
  furnace: ["burner fouling", "tube hot spot", "flame failure"],
  conveyor: ["belt misalignment", "drive failure", "blockage"],
  motor: ["winding overheat", "bearing wear", "insulation degradation"],
  caster: ["mould level instability", "strand breakout", "cooling blockage"],
  mill_stand: ["roll wear", "hydraulic fault", "motor overload"],
};

const ISO = (d: Date) => d.toISOString().slice(0, 10);

export interface ContextMenuState {
  nodeId: string;
  x: number;
  y: number;
}

export interface SimState {
  plant: Plant | null;
  nodes: Node[];
  edges: Edge[];
  layoutZones: LayoutResult["zones"];
  loading: boolean;
  error: string | null;

  selectedId: string | null;
  menu: ContextMenuState | null;
  drawerNodeId: string | null;
  validation: ValidationReport | null;

  /** Locally escalated units after a fault injection, keyed by node id. */
  faulted: Record<string, { faultType: FaultType; at: string }>;
  seq: number;

  setPlant: (plant: Plant) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clear: () => void;

  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (conn: RFConnection) => void;

  addEquipment: (type: EquipmentType, x: number, y: number) => void;
  addSensor: (type: SensorType, x: number, y: number) => void;
  removeNode: (id: string) => void;
  duplicateNode: (id: string) => void;
  setStatus: (id: string, status: EquipmentStatus) => void;

  select: (id: string | null) => void;
  openMenu: (nodeId: string, x: number, y: number) => void;
  closeMenu: () => void;
  openDrawer: (id: string | null) => void;

  runValidation: () => void;

  injectFault: (nodeId: string, faultType: FaultType) => { plantId: string; sensors: Sensor[] };
  resetFaults: () => void;
}

function edgesFrom(plant: Plant): Edge[] {
  return plant.connections.map((c) => ({
    id: c.id,
    source: c.source,
    target: c.target,
    type: "flow",
    data: { kind: c.kind },
  }));
}

function toPlant(
  base: Plant,
  nodes: Node[],
  edges: Edge[],
  sensors: Sensor[],
): Plant {
  const equipment: Equipment[] = nodes
    .filter((n) => n.type === "equipment")
    .map((n) => {
      const d = n.data as Equipment;
      return { ...d, zone_id: (n.parentId ?? base.zones[0]?.id ?? "").replace("zone:", "") };
    });

  const connections: Connection[] = edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    kind: (e.data?.kind as "pipe" | "wire") ?? "pipe",
  }));

  return { ...base, equipment, sensors, connections };
}

export const useSim = create<SimState>((set, get) => ({
  plant: null,
  nodes: [],
  edges: [],
  layoutZones: {},
  loading: false,
  error: null,
  selectedId: null,
  menu: null,
  drawerNodeId: null,
  validation: null,
  faulted: {},
  seq: 1,

  setPlant: (plant) => {
    const { nodes, zones } = layoutPlant(plant);
    set({
      plant,
      nodes,
      edges: edgesFrom(plant),
      layoutZones: zones,
      loading: false,
      error: null,
      selectedId: null,
      menu: null,
      drawerNodeId: null,
      validation: null,
      faulted: {},
    });
  },

  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error, loading: false }),

  clear: () => {
    const p = emptyPlant();
    get().setPlant(p);
  },

  onNodesChange: (changes) => {
    const structural = changes.some(
      (c) => c.type === "remove" || c.type === "add" || c.type === "position",
    );
    set({ nodes: applyNodeChanges(changes, get().nodes) });
    if (structural) set({ validation: null });
    const p = get().plant;
    if (p) set({ plant: toPlant(p, get().nodes, get().edges, p.sensors) });
  },

  onEdgesChange: (changes) => {
    set({ edges: applyEdgeChanges(changes, get().edges), validation: null });
    const p = get().plant;
    if (p) set({ plant: toPlant(p, get().nodes, get().edges, p.sensors) });
  },

  onConnect: (conn) => {
    if (!conn.source || !conn.target) return;
    const state = get();
    const source = state.nodes.find((n) => n.id === conn.source);
    const target = state.nodes.find((n) => n.id === conn.target);
    if (!source || !target) return;

    // A sensor feeding equipment is a signal wire; anything else is process.
    const kind: "pipe" | "wire" = source.type === "sensor" ? "wire" : "pipe";
    const edge: Edge = {
      id: `conn-${conn.source}-${conn.target}-${Date.now().toString(36)}`,
      source: conn.source,
      target: conn.target,
      type: "flow",
      data: { kind },
    };
    const edges = addEdge(edge, state.edges);

    // Wiring a sensor onto a unit is what attaches it — that is the assignment.
    let sensors = state.plant?.sensors ?? [];
    if (source.type === "sensor" && target.type === "equipment") {
      const targetId = conn.target;
      sensors = sensors.map((s) => (s.id === conn.source ? { ...s, equipment_id: targetId } : s));
    }

    set({ edges, validation: null });
    const p = state.plant;
    if (p) set({ plant: toPlant(p, get().nodes, edges, sensors) });
  },

  addEquipment: (type, x, y) => {
    const state = get();
    const seq = state.seq;
    const tag = `${type.slice(0, 3).toUpperCase()}-${900 + seq}`;
    const id = `custom-${tag}-${seq}`;
    const unit: Equipment = {
      id,
      tag,
      type,
      zone_id: state.plant?.zones[0]?.id ?? "custom-zone0",
      install_date: ISO(new Date()),
      expected_lifespan_years: EQUIPMENT_DEFAULT_LIFESPAN[type],
      age_years: 0,
      last_inspection: ISO(new Date()),
      status: "normal",
      failure_modes: EQUIPMENT_FAILURE_MODES[type],
    };

    const occupied = state.nodes
      .filter((n) => n.type === "equipment")
      .map((n) => n.position);
    const placed = placeInNearestZone(x, y, state.layoutZones, occupied);

    const node: Node = {
      id,
      type: "equipment",
      position: { x: placed.x, y: placed.y },
      parentId: placed.parentId ?? undefined,
      extent: placed.parentId ? "parent" : undefined,
      data: { ...unit, zoneName: state.plant?.zones[0]?.name ?? "Zone 1" },
      zIndex: 2,
    };

    set({ nodes: [...state.nodes, node], seq: seq + 1, validation: null });
    const p = state.plant;
    if (p) set({ plant: toPlant(p, get().nodes, get().edges, p.sensors) });
  },

  addSensor: (type, x, y) => {
    const state = get();
    const seq = state.seq;
    const def = SENSOR_DEFAULTS[type];
    const tag = `${type}-${900 + seq}`;
    const id = `custom-${tag}-${seq}`;
    const sensor: Sensor = {
      id,
      equipment_id: "",
      tag,
      type,
      label: def.label,
      unit: def.unit,
      normal_min: def.min,
      normal_max: def.max,
      current_value: Number(((def.min + def.max) / 2).toFixed(2)),
    };

    const occupied = state.nodes.filter((n) => n.type === "sensor").map((n) => n.position);
    const placed = placeInNearestZone(x, y, state.layoutZones, occupied);

    const node: Node = {
      id,
      type: "sensor",
      position: { x: placed.x + 8, y: placed.y },
      parentId: placed.parentId ?? undefined,
      extent: placed.parentId ? "parent" : undefined,
      data: { ...sensor, equipmentTag: "unassigned" },
      zIndex: 1,
    };

    set({ nodes: [...state.nodes, node], seq: seq + 1, validation: null });
    const p = state.plant;
    if (p) set({ plant: toPlant(p, get().nodes, get().edges, [...p.sensors, sensor]) });
  },

  removeNode: (id) => {
    const state = get();
    const nodes = state.nodes.filter((n) => n.id !== id && n.parentId !== id);
    const edges = state.edges.filter((e) => e.source !== id && e.target !== id);
    set({ nodes, edges, menu: null, drawerNodeId: null, selectedId: null, validation: null });
    const p = state.plant;
    if (p) {
      set({ plant: toPlant(p, nodes, edges, p.sensors.filter((s) => s.id !== id)) });
    }
  },

  duplicateNode: (id) => {
    const state = get();
    const src = state.nodes.find((n) => n.id === id);
    if (!src || src.type === "zone") return;
    const seq = state.seq;
    const suffix = `-${seq}`;

    if (src.type === "equipment") {
      const d = src.data as Equipment;
      const tag = `${d.tag}${suffix}`;
      const nid = `${d.id}${suffix}`;
      const node: Node = {
        ...src,
        id: nid,
        position: { x: src.position.x, y: src.position.y + 104 },
        data: { ...d, id: nid, tag },
        selected: false,
      };
      set({ nodes: [...state.nodes, node], seq: seq + 1 });
      const p = state.plant;
      if (p) set({ plant: toPlant(p, get().nodes, get().edges, p.sensors) });
      return;
    }

    const d = src.data as Sensor & { equipmentTag?: string };
    const tag = `${d.tag}${suffix}`;
    const nid = `${d.id}${suffix}`;
    const sensor: Sensor = {
      id: nid,
      equipment_id: d.equipment_id,
      tag,
      type: d.type,
      label: d.label,
      unit: d.unit,
      normal_min: d.normal_min,
      normal_max: d.normal_max,
      current_value: d.current_value,
    };
    const node: Node = {
      ...src,
      id: nid,
      position: { x: src.position.x + 12, y: src.position.y + 38 },
      data: { ...sensor, equipmentTag: d.equipmentTag },
      selected: false,
    };
    set({ nodes: [...state.nodes, node], seq: seq + 1 });
    const p = state.plant;
    if (p) set({ plant: toPlant(p, get().nodes, get().edges, [...p.sensors, sensor]) });
  },

  setStatus: (id, status) => {
    const nodes = get().nodes.map((n) =>
      n.id === id ? { ...n, data: { ...n.data, status } } : n,
    );
    set({ nodes });
    const p = get().plant;
    if (p) set({ plant: toPlant(p, nodes, get().edges, p.sensors) });
  },

  select: (id) => set({ selectedId: id, menu: null }),
  openMenu: (nodeId, x, y) => set({ menu: { nodeId, x, y }, selectedId: nodeId }),
  closeMenu: () => set({ menu: null }),
  openDrawer: (id) => set({ drawerNodeId: id, menu: null }),

  runValidation: () => {
    const { nodes, edges } = get();
    set({ validation: validateCircuit(nodes, edges) });
  },

  injectFault: (nodeId, faultType) => {
    const state = get();
    const unit = state.nodes.find((n) => n.id === nodeId);
    if (!unit || unit.type !== "equipment") {
      return { plantId: state.plant?.plant_id ?? "custom", sensors: [] };
    }

    // A fault is a real change to the unit's own record and to the readings of
    // the sensors physically attached to it. Nothing else is touched.
    const status: EquipmentStatus = faultType === "disabled" ? "disabled" : "critical";
    const nodes = state.nodes.map((n) =>
      n.id === nodeId ? { ...n, data: { ...n.data, status } } : n,
    );

    const attached = (state.plant?.sensors ?? []).filter((s) => s.equipment_id === nodeId);
    const shifted = attached.map((s) => {
      const width = Math.abs(s.normal_max - s.normal_min) || 1;
      const drift =
        faultType === "sensor_drift"
          ? width * 0.35
          : faultType === "leak"
            ? -width * 0.4
            : faultType === "removed"
              ? 0
              : width * 0.3;
      const next = faultType === "removed" ? 0 : Number((s.current_value + drift).toFixed(3));
      return { ...s, current_value: next };
    });
    const shiftedById = new Map(shifted.map((s) => [s.id, s]));

    const nodesWithSensors = nodes.map((n) =>
      shiftedById.has(n.id) ? { ...n, data: { ...n.data, ...shiftedById.get(n.id)! } } : n,
    );

    const sensors = (state.plant?.sensors ?? []).map((s) => shiftedById.get(s.id) ?? s);

    set({
      nodes: nodesWithSensors,
      menu: null,
      faulted: { ...state.faulted, [nodeId]: { faultType, at: new Date().toISOString() } },
    });
    const p = state.plant;
    if (p) set({ plant: toPlant(p, nodesWithSensors, state.edges, sensors) });

    // The snapshot sent to the orchestrator is the post-fault state.
    return { plantId: p?.plant_id ?? "custom", sensors };
  },

  resetFaults: () => {
    const state = get();
    const nodes = state.nodes.map((n) => {
      if (state.faulted[n.id]) return { ...n, data: { ...n.data, status: "normal" } };
      return n;
    });
    set({ nodes, faulted: {} });
    const p = state.plant;
    if (p) set({ plant: toPlant(p, nodes, state.edges, p.sensors) });
  },
}));
