/** Core domain model for Project 117 — mirrors backend contracts where routes
 * exist; stable frontend contracts where they don't yet. */

export type ISODate = string;

export type HealthState = "ok" | "warning" | "critical" | "unknown";

export type Role = "viewer" | "analyst" | "operator" | "admin";

export type AgentKind =
  | "maintenance"
  | "operations"
  | "documentation"
  | "data_analysis"
  | "safety";

export type JobState =
  | "QUEUED"
  | "PLANNING"
  | "RETRIEVING"
  | "EXECUTING"
  | "VERIFYING"
  | "NEEDS_APPROVAL"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED"
  | "TIMEOUT";

export interface Citation {
  document_id: string;
  filename: string;
  page?: number;
  section?: string;
  chunk_index?: number;
  snippet: string;
}

export interface DocumentRecord {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: "stored" | "indexing" | "indexed" | "failed";
  metadata: Record<string, unknown>;
  created_at: ISODate;
  updated_at: ISODate;
}

export interface AgentDescriptor {
  kind: AgentKind;
  name: string;
  description: string;
  model_role: string;
  tools: string[];
  permissions: string[];
  status: "idle" | "running" | "verifying" | "blocked";
}

export interface ArtifactRecord {
  id: string;
  kind: "pdf" | "docx" | "pptx" | "xlsx";
  filename: string;
  sha256: string;
  verified: boolean;
  job_id?: string | null;
  created_at: ISODate;
}

export interface JobRecord {
  id: string;
  title: string;
  state: JobState;
  agent: AgentKind;
  created_at: ISODate;
  updated_at: ISODate;
}

export interface Equipment {
  id: string;
  name: string;
  /**
   * The real plant dataset's equipment type vocabulary (`GET /api/equipment`
   * `type`). The console originally knew five kinds; the dataset carries more
   * (vessels, furnaces, columns, utilities, motors), so the union mirrors it.
   */
  kind:
    | "pump"
    | "tank"
    | "compressor"
    | "exchanger"
    | "valve"
    | "vessel"
    | "furnace"
    | "utility"
    | "column"
    | "safety"
    | "motor";
  zone: string;
  status: HealthState;
  /**
   * Schematic canvas position. The plant dataset has no geospatial
   * coordinates, so this is a deterministic layout derived from the asset's
   * area group — it places nodes legibly, it does not claim a real location.
   */
  position: [number, number, number];
  sensors: SensorReading[];
  last_inspection?: ISODate;
  insight?: string;
}

export interface SensorReading {
  key: string;
  label: string;
  unit: string;
  value: number;
  warnAbove?: number;
  critAbove?: number;
}

export interface WorkOrder {
  id: string;
  equipment_id: string;
  title: string;
  /** Mirrors the backend's PRIORITIES (work_orders.py). */
  priority: "low" | "medium" | "high" | "critical";
  /** Mirrors WORK_ORDER_TRANSITIONS in backend/storage/operations.py. */
  status: "draft" | "open" | "in_progress" | "on_hold" | "completed" | "cancelled";
  assignee: string;
  evidence: Citation[];
  recommended_action?: string;
  approval?: ApprovalRequest | null;
}

export interface ApprovalRequest {
  id: string;
  action: string;
  risk: "low" | "medium" | "high";
  /**
   * Optional: the operations approval store records `type`/`requiredRole`,
   * not the originating agent kind, so the adapter does not invent one.
   */
  agent?: AgentKind;
  requested_by: string;
  equipment_id?: string;
  reason: string;
  evidence: Citation[];
  created_at: ISODate;
  status: "pending" | "approved" | "rejected";
}

export interface GraphNode {
  id: string;
  label: string;
  type:
    | "equipment"
    | "component"
    | "sensor"
    | "inspection"
    | "anomaly"
    | "specification"
    | "maintenance"
    | "work_order";
}

export interface GraphEdge {
  from: string;
  to: string;
  relation:
    | "installed_in"
    | "has_sensor"
    | "mentions"
    | "has_anomaly"
    | "affects"
    | "serviced_by"
    | "governed_by";
}

/* --------------------------------------------------------------------------
 * API transport contracts — mirror the backend Pydantic schemas
 * (backend/api/src/schemas/*). lib/api.ts is the only consumer; keeping them
 * here lets the mock adapter satisfy the same surface.
 * ------------------------------------------------------------------------ */

/** GET /health */
/**
 * GET /health. Mirrors the FastAPI response: the top-level fields are the
 * operational truth (is the database up, is the model runtime reachable, which
 * models does it actually serve), so the console can report real status rather
 * than assuming.
 */
export interface HealthResponse {
  status: "ok" | "degraded" | "error";
  version?: string;
  environment?: string;
  uptime_seconds?: number;
  uptime_s?: number;
  database?: string;
  uploads_writable?: boolean;
  checks?: Record<string, string>;
  llm?: {
    backend?: string;
    running?: boolean;
    error?: string | null;
    models?: string[];
    providers?: Record<string, { running?: boolean }>;
  };
  services?: Record<string, { configured?: boolean }>;
}

/** POST /api/chat — mirrors ChatRequest. */
export interface ChatTurnRequest {
  message: string;
  session_id?: string | null;
  role?: string | null;
  model?: string | null;
  use_rag?: boolean | null;
  document_ids?: string[] | null;
}

/** POST /api/chat — mirrors ChatResponse. */
export interface ChatTurnResult {
  message: string;
  session_id: string;
  model: string;
  role: string;
  citations: Citation[];
  grounded?: boolean;
  usage?: Record<string, unknown> | null;
}

/** GET /api/tools — a registered, permission-scoped tool. */
export interface ToolDescriptor {
  name: string;
  description: string;
  kind?: "retrieval" | "analysis" | "execution" | "generation" | "policy";
  permissions?: string[];
}

/** GET /api/workflows — a declarative workflow definition. */
export interface WorkflowDefinition {
  name: string;
  description?: string;
  steps: {
    id: string;
    name: string;
    type: string;
    requires_approval?: boolean;
  }[];
}

/** Websocket frame pushed over /api/jobs/ws. */
export interface ServerEvent {
  type:
    | "job.state"
    | "job.step"
    | "tool.call"
    | "verification.result"
    | "telemetry.tick"
    | "alert.created"
    | "approval.requested"
    | "agent.status"
    | (string & {});
  payload?: Record<string, unknown>;
  at?: ISODate;
}
