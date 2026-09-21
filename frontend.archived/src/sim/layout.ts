/**
 * Layout.
 *
 * Nothing here is hand-placed. Zones are laid out as a grid of bounded
 * compartments, and the equipment inside each zone is laid out as its own
 * grid. Compartment size is derived from how many units and sensors that zone
 * actually contains, so adding equipment to the seed data reflows the canvas
 * with no coordinate edits.
 *
 * React Flow parent/child is used for the containment: a zone node is emitted
 * before its children and each child carries `parentId`, so a compartment is a
 * real bounded background that the units sit inside rather than a rectangle
 * drawn behind them.
 */
import type { Node } from "reactflow";
import type { Equipment, Plant, Sensor, Zone } from "../types";

export const EQUIPMENT_W = 156;
export const EQUIPMENT_H = 84;
export const SENSOR_W = 140;
export const SENSOR_H = 30;

const ZONE_PAD = 22;
const ZONE_HEADER = 34;
const ZONE_GAP = 56;
const COL_W = EQUIPMENT_W + 24;
const COL_GAP = 18;
const ROW_GAP = 18;
const SENSOR_GAP = 6;

export interface LayoutResult {
  nodes: Node[];
  /** Zone id → its bounding rect in canvas coordinates (for fitView / focus). */
  zones: Record<string, { x: number; y: number; width: number; height: number }>;
}

function sensorsByEquipment(plant: Plant): Map<string, Sensor[]> {
  const m = new Map<string, Sensor[]>();
  for (const s of plant.sensors) {
    const list = m.get(s.equipment_id);
    if (list) list.push(s);
    else m.set(s.equipment_id, [s]);
  }
  return m;
}

function equipmentByZone(plant: Plant): Map<string, Equipment[]> {
  const m = new Map<string, Equipment[]>();
  for (const z of plant.zones) m.set(z.id, []);
  for (const e of plant.equipment) {
    const list = m.get(e.zone_id);
    if (list) list.push(e);
    else m.set(e.zone_id, [e]);
  }
  return m;
}

/** Grid dimensions for `n` items in `cols` columns. */
function grid(n: number, cols: number): { cols: number; rows: number } {
  const c = Math.max(1, Math.min(cols, n || 1));
  return { cols: c, rows: Math.ceil((n || 1) / c) };
}

export function layoutPlant(plant: Plant): LayoutResult {
  const byZone = equipmentByZone(plant);
  const byEquipment = sensorsByEquipment(plant);

  // Zones that hold equipment get a compartment. If nothing is placed yet
  // (builder mode, or a plant whose seeds are empty) we still emit the declared
  // zones, otherwise there is no compartment for a drop to land in and the
  // canvas is a featureless void.
  const populated = plant.zones.filter((z) => (byZone.get(z.id) ?? []).length > 0);
  const activeZones: Zone[] = populated.length > 0 ? populated : plant.zones;
  const zoneCount = Math.max(1, activeZones.length);

  // Zone compartments themselves sit on a grid sized to the plant.
  const zoneCols = Math.max(1, Math.ceil(Math.sqrt(zoneCount)));

  // Pre-compute each zone's internal grid so the compartment can be sized.
  const plan = activeZones.map((zone) => {
    const units = byZone.get(zone.id) ?? [];
    const unitCols = Math.max(1, Math.min(4, Math.ceil(Math.sqrt(units.length || 1))));
    const { rows } = grid(units.length, unitCols);

    // The tallest column in this zone decides the compartment height.
    let tallest = 0;
    const columns: Equipment[][] = Array.from({ length: unitCols }, () => []);
    units.forEach((u, i) => columns[i % unitCols].push(u));
    for (const col of columns) {
      const h =
        col.reduce((acc, u) => {
          const n = (byEquipment.get(u.id) ?? []).length;
          return acc + EQUIPMENT_H + n * (SENSOR_H + SENSOR_GAP) + ROW_GAP;
        }, 0) - ROW_GAP;
      tallest = Math.max(tallest, h);
    }

    const width = ZONE_PAD * 2 + unitCols * COL_W + (unitCols - 1) * COL_GAP;
    const height = ZONE_HEADER + ZONE_PAD * 2 + Math.max(tallest, EQUIPMENT_H);
    return { zone, units, unitCols, rows, width, height };
  });

  // Zone row heights: the tallest compartment in each grid row.
  const rowHeights: number[] = [];
  plan.forEach((p, i) => {
    const r = Math.floor(i / zoneCols);
    rowHeights[r] = Math.max(rowHeights[r] ?? 0, p.height);
  });
  const rowOffsets: number[] = [];
  rowHeights.forEach((_h, r) => {
    rowOffsets[r] = r === 0 ? 0 : rowOffsets[r - 1] + rowHeights[r - 1] + ZONE_GAP;
  });
  // Column widths: the widest compartment per column.
  const colWidths: number[] = [];
  plan.forEach((p, i) => {
    const c = i % zoneCols;
    colWidths[c] = Math.max(colWidths[c] ?? 0, p.width);
  });
  const colOffsets: number[] = [];
  colWidths.forEach((_w, c) => {
    colOffsets[c] = c === 0 ? 0 : colOffsets[c - 1] + colWidths[c - 1] + ZONE_GAP;
  });

  const nodes: Node[] = [];
  const zones: LayoutResult["zones"] = {};

  plan.forEach((p, i) => {
    const col = i % zoneCols;
    const row = Math.floor(i / zoneCols);
    const zx = colOffsets[col];
    const zy = rowOffsets[row];
    zones[p.zone.id] = { x: zx, y: zy, width: p.width, height: p.height };

    // The compartment itself. Non-interactive: it is background structure.
    nodes.push({
      id: `zone:${p.zone.id}`,
      type: "zone",
      position: { x: zx, y: zy },
      data: {
        name: p.zone.name,
        sequence: p.zone.sequence,
        unitCount: p.units.length,
        sensorCount: p.units.reduce((n, u) => n + (byEquipment.get(u.id) ?? []).length, 0),
      },
      draggable: false,
      selectable: false,
      connectable: false,
      style: { width: p.width, height: p.height },
      zIndex: 0,
    });

    p.units.forEach((unit, ui) => {
      const c = ui % p.unitCols;
      const r = Math.floor(ui / p.unitCols);

      // Vertical offset of this unit inside its column = the units above it.
      const above = p.units.filter((_, k) => k % p.unitCols === c && Math.floor(k / p.unitCols) < r);
      const yBefore = above.reduce((acc, u) => {
        const n = (byEquipment.get(u.id) ?? []).length;
        return acc + EQUIPMENT_H + n * (SENSOR_H + SENSOR_GAP) + ROW_GAP;
      }, 0);

      const ux = ZONE_PAD + c * (COL_W + COL_GAP);
      const uy = ZONE_HEADER + ZONE_PAD + yBefore;

      nodes.push({
        id: unit.id,
        type: "equipment",
        position: { x: ux, y: uy },
        parentId: `zone:${p.zone.id}`,
        extent: "parent",
        data: { ...unit, zoneName: p.zone.name },
        zIndex: 2,
      });

      const sensors = byEquipment.get(unit.id) ?? [];
      sensors.forEach((s, si) => {
        nodes.push({
          id: s.id,
          type: "sensor",
          position: {
            x: ux + 8,
            y: uy + EQUIPMENT_H + SENSOR_GAP + si * (SENSOR_H + SENSOR_GAP),
          },
          parentId: `zone:${p.zone.id}`,
          extent: "parent",
          data: { ...s, equipmentTag: unit.tag },
          zIndex: 1,
        });
      });
    });
  });

  return { nodes, zones };
}

/**
 * Position a newly dropped node so it lands inside a zone compartment rather
 * than floating over empty canvas. Picks the zone whose rect contains the drop
 * point, else the nearest one, and returns coordinates relative to that zone.
 *
 * `parentId` is the React Flow **node id** of the compartment (`zone:<id>`),
 * not the bare zone id — a child whose parentId does not match an existing
 * node makes React Flow throw and take the whole canvas down with it.
 */
export function placeInNearestZone(
  dropX: number,
  dropY: number,
  layoutZones: LayoutResult["zones"],
  occupied: { x: number; y: number }[],
): { parentId: string | null; x: number; y: number } {
  const entries = Object.entries(layoutZones);
  if (!entries.length) return { parentId: null, x: dropX, y: dropY };

  let bestId = entries[0][0];
  let bestDist = Infinity;
  for (const [id, z] of entries) {
    const cx = z.x + z.width / 2;
    const cy = z.y + z.height / 2;
    const d = Math.hypot(dropX - cx, dropY - cy);
    if (d < bestDist) {
      bestDist = d;
      bestId = id;
    }
  }
  const z = layoutZones[bestId];
  const x = Math.max(ZONE_PAD, dropX - z.x - EQUIPMENT_W / 2);
  const y = Math.max(ZONE_HEADER + ZONE_PAD, dropY - z.y - EQUIPMENT_H / 2);

  // Nudge down until the slot is free, so drops never stack invisibly.
  let fy = y;
  let guard = 0;
  while (occupied.some((o) => Math.abs(o.x - x) < 12 && Math.abs(o.y - fy) < 12) && guard < 60) {
    fy += EQUIPMENT_H + ROW_GAP;
    guard += 1;
  }
  return { parentId: `zone:${bestId}`, x, y: fy };
}
