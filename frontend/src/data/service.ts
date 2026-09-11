/**
 * Data service.
 *
 * One surface, two sources, chosen by env var — never inferred:
 *
 *   VITE_DATA_SOURCE=json     (default) read the exported JSON directly.
 *                             No backend, no database, works offline.
 *   VITE_DATA_SOURCE=backend  GET {VITE_API_BASE}/plants/{id}, which queries
 *                             the SQLite schema in database/schema.sql and
 *                             returns the identical shape.
 *
 * Both paths are normalised through `normalisePlant`, so a plant loaded from
 * either source is indistinguishable to the rest of the app. If the configured
 * source fails the error surfaces — nothing silently falls back to the other
 * one, because a demo that quietly reads stale JSON while claiming to be live
 * is worse than a visible failure.
 */
import {
  DataSourceError,
  type Connection,
  type Equipment,
  type EquipmentStatus,
  type EquipmentType,
  type Plant,
  type PlantManifestEntry,
  type PlantsManifest,
  type Sensor,
  type SensorType,
  type Zone,
} from "../types";

const RAW_SOURCE = import.meta.env.VITE_DATA_SOURCE ?? "json";
export const DATA_SOURCE: "json" | "backend" = RAW_SOURCE === "backend" ? "backend" : "json";
export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

/* ---------------------------------------------------------------- helpers */

const EQUIPMENT_TYPES: EquipmentType[] = [
  "pump", "valve", "tank", "heat_exchanger", "compressor", "compressor_blower",
  "column", "reactor", "furnace", "conveyor", "motor", "caster", "mill_stand",
];
const SENSOR_TYPES: SensorType[] = ["PT", "TT", "FT", "LT", "VT"];
const STATUSES: EquipmentStatus[] = ["normal", "warning", "critical", "disabled"];

function asEquipmentType(v: unknown): EquipmentType {
  return EQUIPMENT_TYPES.includes(v as EquipmentType) ? (v as EquipmentType) : "valve";
}
function asSensorType(v: unknown): SensorType {
  return SENSOR_TYPES.includes(v as SensorType) ? (v as SensorType) : "PT";
}
function asStatus(v: unknown): EquipmentStatus {
  return STATUSES.includes(v as EquipmentStatus) ? (v as EquipmentStatus) : "normal";
}
function num(v: unknown, fallback = 0): number {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : fallback;
}
function str(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

/** Age in years from install_date to now, matching the exporter's `age_years`. */
function ageYears(installDate: string): number {
  const t = Date.parse(installDate);
  if (Number.isNaN(t)) return 0;
  return Math.round(((Date.now() - t) / (365.25 * 24 * 3600 * 1000)) * 10) / 10;
}

/**
 * Accept either the JSON export's `source`/`target` or the SQL column names
 * `source_id`/`target_id`, and either `failure_modes` as an array or the
 * comma-separated string the schema stores.
 */
export function normalisePlant(raw: unknown): Plant {
  const d = (raw ?? {}) as Record<string, unknown>;
  const zonesRaw = Array.isArray(d.zones) ? d.zones : [];
  const equipRaw = Array.isArray(d.equipment) ? d.equipment : [];
  const sensorsRaw = Array.isArray(d.sensors) ? d.sensors : [];
  const connRaw = Array.isArray(d.connections) ? d.connections : [];

  const zones: Zone[] = zonesRaw.map((z, i) => {
    const r = z as Record<string, unknown>;
    return {
      id: str(r.id, `zone-${i}`),
      name: str(r.name, `Zone ${i + 1}`),
      sequence: num(r.sequence, i),
    };
  });

  const equipment: Equipment[] = equipRaw.map((e, i) => {
    const r = e as Record<string, unknown>;
    const install = str(r.install_date, "");
    const fm = r.failure_modes;
    return {
      id: str(r.id, `equipment-${i}`),
      tag: str(r.tag, `EQ-${i}`),
      type: asEquipmentType(r.type),
      zone_id: str(r.zone_id, zones[0]?.id ?? ""),
      install_date: install,
      expected_lifespan_years: num(r.expected_lifespan_years, 10),
      age_years: r.age_years != null ? num(r.age_years) : ageYears(install),
      last_inspection: str(r.last_inspection, ""),
      status: asStatus(r.status),
      failure_modes: Array.isArray(fm)
        ? fm.map((x) => String(x))
        : str(fm, "").split(",").map((s) => s.trim()).filter(Boolean),
    };
  });

  const sensors: Sensor[] = sensorsRaw.map((s, i) => {
    const r = s as Record<string, unknown>;
    return {
      id: str(r.id, `sensor-${i}`),
      equipment_id: str(r.equipment_id, ""),
      tag: str(r.tag, `S-${i}`),
      type: asSensorType(r.type),
      label: str(r.label, ""),
      unit: str(r.unit, ""),
      normal_min: num(r.normal_min),
      normal_max: num(r.normal_max, 100),
      current_value: num(r.current_value),
    };
  });

  const connections: Connection[] = connRaw.map((c, i) => {
    const r = c as Record<string, unknown>;
    return {
      id: str(r.id, `conn-${i}`),
      source: str(r.source ?? r.source_id, ""),
      target: str(r.target ?? r.target_id, ""),
      kind: r.kind === "wire" ? "wire" : "pipe",
    };
  });

  return {
    plant_id: str(d.plant_id, "unknown"),
    plant_name: str(d.plant_name, "Unknown plant"),
    zones: zones.sort((a, b) => a.sequence - b.sequence),
    equipment,
    sensors,
    connections,
  };
}

/* ------------------------------------------------------------------- read */

export async function loadManifest(): Promise<PlantManifestEntry[]> {
  try {
    const res = await fetch("/plants.json");
    if (!res.ok) throw new DataSourceError("/plants.json", `HTTP ${res.status}`);
    const m = (await res.json()) as PlantsManifest;
    return m.plants ?? [];
  } catch (err) {
    throw err instanceof DataSourceError
      ? err
      : new DataSourceError("/plants.json", (err as Error).message);
  }
}

export async function loadPlant(entry: PlantManifestEntry): Promise<Plant> {
  if (DATA_SOURCE === "backend") {
    const url = `${API_BASE}/plants/${encodeURIComponent(entry.id)}`;
    let res: Response;
    try {
      res = await fetch(url);
    } catch (err) {
      throw new DataSourceError(url, (err as Error).message);
    }
    if (!res.ok) throw new DataSourceError(url, `HTTP ${res.status}`);
    return normalisePlant(await res.json());
  }

  if (!entry.data_file) {
    throw new DataSourceError(entry.id, "this plant has no data_file; it is the empty builder");
  }
  let res: Response;
  try {
    res = await fetch(entry.data_file);
  } catch (err) {
    throw new DataSourceError(entry.data_file, (err as Error).message);
  }
  if (!res.ok) throw new DataSourceError(entry.data_file, `HTTP ${res.status}`);
  return normalisePlant(await res.json());
}

/** An empty plant for builder mode. */
export function emptyPlant(): Plant {
  return {
    plant_id: "custom",
    plant_name: "Untitled plant",
    zones: [{ id: "custom-zone0", name: "Zone 1", sequence: 0 }],
    equipment: [],
    sensors: [],
    connections: [],
  };
}
