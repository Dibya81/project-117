/**
 * Data contracts.
 *
 * These mirror `project-117-simulation/database/schema.sql` exactly, plus the
 * two derived fields the JSON export carries (`age_years`, and the `source` /
 * `target` naming on connections, which the SQL calls `source_id` /
 * `target_id`). The data service normalises both spellings so nothing
 * downstream has to care which one it was handed.
 */

export type EquipmentType =
  | "pump"
  | "valve"
  | "tank"
  | "heat_exchanger"
  | "compressor"
  | "compressor_blower"
  | "column"
  | "reactor"
  | "furnace"
  | "conveyor"
  | "motor"
  | "caster"
  | "mill_stand";

export type EquipmentStatus = "normal" | "warning" | "critical" | "disabled";

export type SensorType = "PT" | "TT" | "FT" | "LT" | "VT";

export type ConnectionKind = "pipe" | "wire";

export interface Zone {
  id: string;
  name: string;
  sequence: number;
}

export interface Equipment {
  id: string;
  tag: string;
  type: EquipmentType;
  zone_id: string;
  install_date: string;
  expected_lifespan_years: number;
  /** Derived on export; recomputed from install_date when absent. */
  age_years: number;
  last_inspection: string;
  status: EquipmentStatus;
  failure_modes: string[];
}

export interface Sensor {
  id: string;
  equipment_id: string;
  tag: string;
  type: SensorType;
  label: string;
  unit: string;
  normal_min: number;
  normal_max: number;
  current_value: number;
}

export interface Connection {
  id: string;
  source: string;
  target: string;
  kind: ConnectionKind;
}

export interface Plant {
  plant_id: string;
  plant_name: string;
  zones: Zone[];
  equipment: Equipment[];
  sensors: Sensor[];
  connections: Connection[];
}

export interface PlantManifestEntry {
  id: string;
  name: string;
  subtitle: string;
  description: string;
  /** null for the builder, which starts from an empty canvas. */
  data_file: string | null;
  builtin: boolean;
}

export interface PlantsManifest {
  plants: PlantManifestEntry[];
}

/* ---------------------------------------------------------------- runtime */

export type FaultType = "disabled" | "removed" | "sensor_drift" | "leak";

/** `fault.injected` — frontend → orchestrator. */
export interface FaultInjectedMessage {
  type: "fault.injected";
  plant_id: string;
  equipment_id: string;
  fault_type: FaultType;
  sensor_snapshot: Sensor[];
}

/** Every message the orchestrator may send back. */
export type OrchestratorEvent =
  | { type: "job.created"; job_id: string; plant_id?: string; equipment_id?: string; at?: string }
  | { type: "agent.started"; job_id: string; agent: string; label?: string; detail?: string; at?: string }
  | {
      type: "tool.completed";
      job_id: string;
      agent?: string;
      tool: string;
      label?: string;
      detail?: string;
      related_equipment_id?: string;
      at?: string;
    }
  | {
      type: "verification.completed";
      job_id: string;
      passed: boolean;
      label?: string;
      detail?: string;
      related_equipment_id?: string;
      at?: string;
    }
  | {
      type: "artifact.created";
      job_id: string;
      artifact_id?: string;
      filename: string;
      url: string;
      label?: string;
      detail?: string;
      at?: string;
    }
  | { type: "unknown"; raw: unknown };

export type TraceStage = "perceive" | "plan" | "act" | "verify" | "complete" | "recover";

export interface TraceEntry {
  id: string;
  job_id: string;
  stage: TraceStage;
  label: string;
  detail?: string;
  related_equipment_id?: string;
  at: string;
  /** True when this entry came from the local fallback, not a live socket. */
  synthetic?: boolean;
}

export interface Artifact {
  id: string;
  job_id: string;
  filename: string;
  url: string;
}

/* ------------------------------------------------------------------ errors */

export class DataSourceError extends Error {
  readonly source: string;
  constructor(source: string, detail: string) {
    super(`${source}: ${detail}`);
    this.name = "DataSourceError";
    this.source = source;
  }
}
