/** Console domain types — workbench contracts.
 * Mirror backend routes where they exist; stable frontend contracts otherwise.
 * The data adapter in lib/data/console.ts is the only place that knows which. */

import type { ArtifactRecord, Citation, HealthState, JobState } from "./index";

export type ConsoleRole =
  | "operator"
  | "engineer"
  | "maintenance"
  | "safety"
  | "manager"
  | "admin";

export interface Alert {
  id: string;
  severity: "critical" | "warning" | "info";
  equipment_id?: string;
  title: string;
  detail: string;
  at: string;
  acknowledged: boolean;
}

export interface NotificationItem {
  id: string;
  category: "critical" | "attention" | "ai" | "system";
  title: string;
  detail?: string;
  at: string;
  href?: string;
}

export interface HistoryEvent {
  id: string;
  kind:
    | "anomaly"
    | "inspection"
    | "decision"
    | "maintenance"
    | "recommendation"
    | "approval"
    | "work_order";
  title: string;
  detail: string;
  equipment_id?: string;
  actor: string;
  at: string;
}

export interface LearnedRule {
  id: string;
  rule: string;
  set_by: string;
  at: string;
  status: "verified" | "pending";
  /** Memory provenance — where the rule came from and how much it's used. */
  origin?: string;
  evidence_count?: number;
  confidence?: number;
  used_count?: number;
}

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  role: ConsoleRole;
  last_active: string;
}

export interface AuditEvent {
  id: string;
  at: string;
  actor: string;
  action: string;
  tool?: string;
  model?: string;
  job_id?: string;
  approval_id?: string;
}

export interface ModelStatus {
  role: string;
  model: string;
  status: "loaded" | "available" | "unavailable";
  latency_ms?: number;
}

export interface SystemPosture {
  model_gateway: "local" | "degraded" | "offline";
  sandbox: "isolated" | "unavailable";
  egress: "denied" | "allowlisted";
  external_calls_24h: number;
  database: "ok" | "error";
  storage_used_gb: number;
  storage_total_gb: number;
  version: string;
}

export type TaskStep =
  | "request"
  | "retrieving"
  | "analyzing"
  | "executing"
  | "verifying"
  | "complete"
  | "failed";

/** The investigation answer, structured the way operators read. */
export interface StructuredAnswer {
  executive: string;
  finding: string;
  factors: string[];
  action: string;
  risk: string;
  next: string;
}

export interface WorkspaceTask {
  id: string;
  job_id: string;
  request: string;
  agent: string;
  step: TaskStep;
  context: Citation[];
  trace: { label: string; detail?: string; duration_ms?: number; done: boolean }[];
  result?: string;
  claims?: { text: string; citations: Citation[]; verified: boolean }[];
  artifacts: ArtifactRecord[];
  checks: { name: string; status: "verified" | "pending" | "failed"; detail?: string }[];
  needs_approval?: { approval_id: string; action: string } | null;
  structured?: StructuredAnswer;
}

export interface WorkspaceSession {
  id: string;
  title: string;
  at: string;
  task_count: number;
}

export interface EquipmentTelemetrySeries {
  key: string;
  label: string;
  unit: string;
  warnAbove?: number;
  critAbove?: number;
  points: { t: number; value: number }[];
}

export interface EquipmentDetailData {
  id: string;
  name: string;
  kind: string;
  zone: string;
  status: HealthState;
  kpis: { label: string; value: string; state?: HealthState }[];
  insight?: string;
  /**
   * Current instrument readings, straight from the plant dataset's
   * `keySignals`. Present even when `telemetry` is empty — the dataset carries
   * a nominal value per signal but no persisted time series.
   */
  readings?: { key: string; label: string; unit: string; value: number; warnAbove?: number; critAbove?: number }[];
  telemetry: EquipmentTelemetrySeries[];
  maintenance: { id: string; title: string; at: string; by: string }[];
  documents: { id: string; filename: string; kind: string }[];
  history: HistoryEvent[];
  related: { id: string; name: string; relation: string }[];
  open_work_orders: string[];
  /**
   * Set when this page was opened under a register tag (C-1071) rather than the
   * console unit's own tag (C-3). The console and the simulation register are
   * two vocabularies for the same physical machine; the crosswalk in
   * lib/knowledge/canonical.ts declares which is which, and the page says so
   * instead of silently rewriting the URL.
   */
  registerTag?: string;
  registerName?: string;
  mappingConfidence?: "exact" | "twin" | "partial";
  mappingBasis?: string;
}

export interface InsightSeries {
  id: string;
  question: string;
  summary: string;
  unit: string;
  points: { t: number; value: number }[];
  threshold?: number;
  table?: { label: string; value: string; state?: HealthState }[];
}

export type { JobState };
