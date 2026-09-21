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

/**
 * GET /api/agents — one registered agent.
 *
 * Mirrors the wire: `{name, description, capabilities, requires_rag, tools}`.
 * It previously declared `model_role` and `permissions`, which the endpoint has
 * never returned. Two consumers read them, and one crashed the Knowledge
 * Universe page with "Cannot read properties of undefined (reading 'join')".
 * A field that exists only in the type is a promise the API does not keep.
 *
 * `kind` and `status` are added by the client adapter, not the wire: an agent's
 * registry name *is* its kind, and the registry does not report load state, so
 * the adapter reports `idle` rather than inventing a running agent.
 */
export interface AgentDescriptor {
  kind: AgentKind;
  name: string;
  description: string;
  /** What this agent is allowed to do, as the registry declares it. */
  capabilities: string[];
  /** True when answers must be grounded in retrieved documents. */
  requires_rag: boolean;
  tools: string[];
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
  /**
   * The real plant tag (`P-1001`) — the identifier printed on the asset and
   * encoded in its QR label. Distinct from `id` (`e-P-1001`); the equipment
   * index resolves either. Absent only when the dataset record carries no tag.
   */
  tag?: string;
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
 * (backend/api/src/schemas/*). lib/api.ts is the only consumer.
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
  /** Measured disk figures for the volume the backend writes to. */
  storage?: {
    available?: boolean;
    path?: string;
    used_gb?: number;
    total_gb?: number;
    free_gb?: number;
  };
  egress?: "denied" | "allowlist";
  /**
   * The process-local record of outbound decisions the egress guard made.
   * `external_allowed` is the figure that matters: destinations off this
   * machine that were actually reached. Loopback traffic to a local model
   * server is counted under `totals.local_*` and is deliberately not promoted
   * into the external figure.
   */
  network?: {
    since?: number;
    scope?: string;
    external_allowed?: number;
    external_blocked?: number;
    totals?: {
      allowed?: number;
      blocked?: number;
      external_allowed?: number;
      external_blocked?: number;
      local_allowed?: number;
      local_blocked?: number;
    };
    blocked_hosts?: string[];
    allowed_hosts?: string[];
    /**
     * The most recent decisions, newest first, exactly as the monitor recorded
     * them. `agent`/`task_id` are null outside a task context and are shown as
     * such rather than inferred.
     */
    recent?: {
      host?: string | null;
      scheme?: string | null;
      decision?: string;
      at?: number;
      reason?: string | null;
      local?: boolean;
      port?: number | null;
      agent?: string | null;
      task_id?: string | null;
    }[];
    /**
     * Live subscribers to the sentinel SSE stream. Deliberately streamed only
     * while a security page is mounted, so this is 0 when none is open.
     */
    sentinel_subscribers?: number;
  };
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

/** Where a retrieved chunk came from inside its source document. */
export interface EvidenceCitation {
  document_id: string;
  chunk_index: number;
  page?: number | null;
  heading_path?: string[];
  block_type?: string;
}

/** One retrieved chunk offered to the model as grounding. */
export interface ChatEvidence {
  chunk_id: string;
  text: string;
  score?: number | null;
  rerank_score?: number | null;
  citation: EvidenceCitation;
  document?: { id: string; filename: string } | null;
}

/**
 * POST /api/chat — mirrors the backend's ChatResponse.
 *
 * This previously declared `{message, role, citations, grounded}` while the
 * route returns `{response, provider, latency_ms, evidence}`. Nothing consumed
 * it, so the drift went unnoticed. It now matches `schemas/chat.py`, and a
 * backend test asserts that schema against a live payload.
 */
export interface ChatTurnResult {
  response: string;
  model: string;
  provider: string;
  latency_ms: number;
  session_id?: string | null;
  usage?: Record<string, number>;
  evidence: ChatEvidence[];
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

export interface WorkspaceRecord {
  id: string;
  name: string;
  description: string | null;
  knowledge_version: string;
  created_at: ISODate;
  updated_at: ISODate;
}

export interface WorkspaceHealthRecord {
  workspace_id: string;
  documents: number;
  indexed: number;
  processing: number;
  failed: number;
  chunks: number;
  entities: number;
  relationships: number;
  last_updated: ISODate | null;
  status: "READY" | "UPDATING" | "DEGRADED" | "FAILED" | "EMPTY";
  knowledge_version: string;
}

export interface KnowledgeEntityRecord {
  id: string;
  name: string;
  type: string;
  aliases: string[];
  relationships_count?: number;
  relationships?: {
    rel: string;
    target: string;
    source_chunk?: string | null;
    confidence?: number | null;
  }[];
  sources?: {
    document_id: string;
    filename: string;
  }[];
  confidence: number;
  created_at: ISODate;
}

export interface KnowledgeGraphResponse {
  workspace_id: string;
  nodes: {
    id: string;
    label: string;
    type: string;
    confidence: number;
    document_ids: string[];
  }[];
  edges: {
    id: string;
    source: string;
    target: string;
    label: string;
    confidence: number;
  }[];
  stats: {
    total_nodes: number;
    total_edges: number;
    by_type: Record<string, number>;
  };
}

