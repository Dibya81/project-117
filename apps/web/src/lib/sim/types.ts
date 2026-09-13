/**
 * Simulation contracts — 1:1 mirror of backend/simulation/models.py.
 * The SSE wire format is these shapes as JSON. Nothing here invents data:
 * live mode streams backend events; embedded mode runs the same deterministic
 * engine semantics client-side (see engine.ts — clearly labeled).
 */

export type EquipmentKind =
  | "pump" | "valve" | "tank" | "vessel" | "column" | "exchanger"
  | "furnace" | "compressor" | "motor" | "conveyor" | "safety" | "utility";

export type Measurement =
  | "pressure" | "temperature" | "flow" | "level" | "vibration" | "rpm"
  | "current" | "power" | "gas" | "leak" | "position" | "speed";

export type AssetState =
  | "normal" | "warning" | "critical" | "failed" | "disabled"
  | "investigating" | "acting" | "verifying" | "verified";

export type TelemetryQuality = "good" | "bad" | "stale" | "substituted";

export interface SensorDef {
  id: string;
  tag: string;
  equipment_id: string;
  measurement: Measurement;
  unit: string;
  nominal: number;
  normal_min: number;
  normal_max: number;
  warning_min: number;
  warning_max: number;
  critical_min: number;
  critical_max: number;
  sampling_ms: number;
  noise: number;
  drift_rate: number;
  is_detector: boolean;
}

export interface EquipmentDef {
  id: string;
  tag: string;
  name: string;
  kind: EquipmentKind;
  area_id: string;
  x: number;
  y: number;
  criticality: number;
  capacity: number;
  state: AssetState;
  sensors: SensorDef[];
  failure_modes: string[];
  manufacturer: string;
  model: string;
  installed: string;
  last_inspection: string;
}

export type ConnectionKind = "pipe" | "signal" | "control" | "power";

/**
 * What a connection MEANS, as opposed to how it is drawn.
 *
 * `kind` is the physical carrier (a pipe vs a wire); `relation` is the semantic
 * relationship the agents reason over. `kind` alone cannot express "this
 * instrument is a redundant backup for that one", which is exactly what the
 * failover logic needs, so relations are carried explicitly.
 *
 * Optional and additive: a connection without a `relation` falls back to the
 * default implied by its `kind` (see `relationOf` in ./relations).
 */
export type RelationType =
  | "SENSOR_OF"
  | "TELEMETRY_FROM"
  | "MATERIAL_FLOW"
  | "CONTROL_SIGNAL"
  | "POWER_DEPENDENCY"
  | "SAFETY_INTERLOCK"
  | "PROCESS_DEPENDENCY"
  | "REDUNDANCY"
  | "MONITORS"
  | "FEEDS"
  | "OUTPUT_TO";

export interface ConnectionDef {
  id: string;
  kind: ConnectionKind;
  /** Semantic relationship. Absent on legacy data; derive with `relationOf`. */
  relation?: RelationType;
  source: string;
  target: string;
  medium: string;
  capacity: number;
  flow: number;
  status: AssetState;
  leaking: boolean;
  enabled: boolean;
}

export interface PlantArea {
  id: string;
  name: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface FailureModeDef {
  id: string;
  name: string;
  applies_to: string[];
  mechanism: "sensor" | "drift" | "degrade" | "stop" | "leak" | "surge";
  magnitude: number;
  description: string;
}

export interface PlantDef {
  id: string;
  name: string;
  industry: string;
  areas: PlantArea[];
  equipment: EquipmentDef[];
  connections: ConnectionDef[];
  failure_modes: FailureModeDef[];
}

export interface ScenarioStep {
  at_s: number;
  action: string;
  target: string;
  mode: string;
}

export interface ScenarioDef {
  id: string;
  name: string;
  description: string;
  steps: ScenarioStep[];
}

export interface Alarm {
  id: string;
  sensor_id: string;
  tag: string;
  severity: "warning" | "critical";
  message: string;
  at: number;
  active: boolean;
}

export type IncidentStatus =
  | "detected" | "investigating" | "plan_ready" | "awaiting_approval"
  | "acting" | "verifying" | "resolved" | "escalated";

export interface Incident {
  id: string;
  plant_id: string;
  title: string;
  severity: "warning" | "critical";
  status: IncidentStatus;
  origin_equipment: string;
  origin_sensor: string | null;
  failure_mode: string | null;
  affected: string[];
  created_at: number;
  resolved_at: number | null;
}

export interface SimEvent {
  seq: number;
  plant_id: string;
  type: string;
  payload: Record<string, unknown>;
  at: number;
}

export interface ToolCall {
  tool: string;
  summary: string;
  ok: boolean;
}

export interface AgentEvidence {
  id: string;
  source_type: "telemetry" | "graph" | "documents" | "maintenance" | "policy" | "topology";
  source_id: string;
  description: string;
  confidence: number;
}

export type AgentTaskStatus = "queued" | "running" | "completed" | "failed" | "blocked";

export interface AgentTask {
  id: string;
  incident_id: string;
  agent: "orchestrator" | "data_analysis" | "maintenance" | "operations" | "safety" | "documentation";
  title: string;
  status: AgentTaskStatus;
  started_at: number | null;
  completed_at: number | null;
  depends_on: string[];
  tools: ToolCall[];
  evidence: AgentEvidence[];
  result: string;
  sequence: number;
}

export interface IncidentPlan {
  incident_id: string;
  steps: string[];
  requires_approval: boolean;
  approval_reason: string;
  action: { kind: "repair_sensor" | "restore_equipment" | "reduce_load"; target: string };
  verification: string[];
}

export interface SimSnapshot {
  t: number;
  equipment: Record<string, { state: AssetState; capacity: number; faults: string[] }>;
  sensors: Record<string, { value: number; quality: TelemetryQuality; failed: boolean }>;
  /**
   * Live pipe state. The engine computes each line's flow every tick, so a
   * process diagram that reads only the definition animates at zero forever.
   */
  connections?: Record<string, { flow: number; enabled: boolean; leaking: boolean; status: string }>;
  alarms: Alarm[];
  incidents: Incident[];
}

export interface PlantListItem {
  id: string;
  name: string;
  industry: string;
  assets: number;
  sensors: number;
  scenarios: number;
  areas: number;
  origin?: string;
}

/* ---------------------------------------------- post-incident assessment */

export interface RootCauseEvidence {
  id: string;
  /** Where the evidence came from: failure mode, telemetry, topology, … */
  source: string;
  detail: string;
  /** Which hypothesis this evidence moves. */
  supports: "instrument" | "process" | "maintenance";
}

export interface RootCauseHypothesis {
  id: string;
  label: string;
  /** 0–1. Capped below 1.0 — this is an assessment, never a proof. */
  confidence: number;
  rationale: string;
}

export interface RootCauseAssessment {
  available: boolean;
  reason?: string;
  incidentId?: string;
  equipmentTag?: string;
  sensorTag?: string;
  hypotheses: RootCauseHypothesis[];
  evidence: RootCauseEvidence[];
  caveat?: string;
}

export interface NextFailureCandidate {
  equipmentId: string;
  tag: string;
  name: string;
  /** 0–1 ranked risk. */
  risk: number;
  reasons: string[];
  horizon: string;
}

export interface NextFailurePrediction {
  available: boolean;
  reason?: string;
  incidentId?: string;
  candidates: NextFailureCandidate[];
  caveat?: string;
}
