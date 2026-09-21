/**
 * The only module in the app allowed to call `fetch`.
 *
 * Every function is typed against the FastAPI backend contracts. Components
 * never call fetch directly — they use these namespaced methods, and whether
 * the data is live or mocked is decided once in `lib/data.ts`.
 */
import type {
  AgentDescriptor,
  ArtifactRecord,
  ChatTurnRequest,
  ChatTurnResult,
  DocumentRecord,
  HealthResponse,
  JobRecord,
  KnowledgeEntityRecord,
  KnowledgeGraphResponse,
  ToolDescriptor,
  WorkflowDefinition,
  WorkspaceHealthRecord,
  WorkspaceRecord,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
  }
}

/**
 * GET de-duplication and a short read cache.
 *
 * Every console page was fetching the same endpoints two to four times per
 * load. Two separate causes, both fixed here rather than at each call site:
 *
 *  1. **Concurrent identical requests.** The shell and the page (and React's
 *     development double-invoke) mount their effects in the same tick, so
 *     `/api/agents`, `/api/approvals`, `/api/jobs` and the plant list were each
 *     requested 2–4 times before the first reply arrived. `inflight` collapses
 *     them onto one promise.
 *  2. **Sequential repeats.** Two components asking for the same list a moment
 *     apart. `cache` serves the second from memory for `READ_TTL_MS`.
 *
 * Three rules keep this honest:
 *
 *  * **Any write clears the cache.** A PATCH that changes a work order's status
 *    must not be followed by a cached read of the old status, so every non-GET
 *    drops the whole cache. Correctness beats the saving.
 *  * **Live endpoints are never cached.** A 4 Hz telemetry snapshot served from
 *    a 3-second cache is a frozen plant. `LIVE_PATHS` opts them out; they still
 *    benefit from concurrent de-duplication, which cannot serve stale data
 *    because the calls are simultaneous by definition.
 *  * **Failures are not cached.** A rejected promise is removed from both maps,
 *    so a transient outage is retried rather than remembered.
 */
const READ_TTL_MS = 3000;

/** Endpoints whose whole purpose is to report the current moment. */
const LIVE_PATHS = ["/snapshot", "/stream", "/tasks"];

const inflight = new Map<string, Promise<unknown>>();
const readCache = new Map<string, { at: number; value: unknown }>();

function readKey(path: string, init?: RequestInit): string | null {
  const method = (init?.method ?? "GET").toUpperCase();
  if (method !== "GET") return null;
  if (init?.body) return null;
  if (LIVE_PATHS.some((p) => path.includes(p))) return null;
  return path;
}

/** Drop cached reads. Called after any write so a mutation is never masked. */
export function invalidateApiCache(): void {
  readCache.clear();
}

/**
 * Fetch through the read cache and de-duplication described above.
 *
 * `run` is the transport for one response kind; the cache stores whatever it
 * resolves to. The key is the path and a path has exactly one kind, so a JSON
 * read and a text read can never be served each other's value.
 */
async function cachedRead<T>(
  path: string,
  init: RequestInit | undefined,
  run: () => Promise<T>,
): Promise<T> {
  const key = readKey(path, init);
  if (key) {
    const hit = readCache.get(key);
    if (hit && Date.now() - hit.at < READ_TTL_MS) return hit.value as T;
    const pending = inflight.get(key);
    if (pending) return pending as Promise<T>;
  }

  const pending = run();

  if (key) {
    inflight.set(key, pending);
    try {
      const value = await pending;
      readCache.set(key, { at: Date.now(), value });
      return value;
    } finally {
      inflight.delete(key);
    }
  }

  if ((init?.method ?? "GET").toUpperCase() !== "GET") invalidateApiCache();
  return pending;
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  return cachedRead(path, init, () => performRequest<T>(path, init));
}

/**
 * GET a non-JSON body — the equipment QR endpoint answers `image/svg+xml`.
 *
 * `performRequest` ends in `res.json()`, which throws on SVG, so text responses
 * need their own transport. They still share the read cache, which matters on
 * the label sheet: it renders one symbol per asset and re-mounting a page must
 * not re-request every one.
 */
async function requestText(path: string, init?: RequestInit): Promise<string> {
  return cachedRead(path, init, () => performFetch(path, init).then((res) => res.text()));
}

async function performRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await performFetch(path, init);
  return (await res.json()) as T;
}

/** One HTTP call carrying the project's headers, credentials and error envelope. */
async function performFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  let res: Response;
  // Multipart bodies must let the browser set Content-Type, because only it
  // knows the boundary it generated. Forcing application/json here silently
  // produces an unparseable body and a 422 from the server.
  const isForm = typeof FormData !== "undefined" && init?.body instanceof FormData;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        ...(isForm ? {} : { "Content-Type": "application/json" }),
        ...authHeaders(),
        ...(init?.headers ?? {}),
      },
      // Never send credentials cross-origin; this is an on-prem LAN app.
      credentials: "same-origin",
    });
  } catch (err) {
    throw new ApiError(0, "offline", `backend unreachable: ${(err as Error).message}`);
  }
  if (!res.ok) {
    let code = "error";
    let message = res.statusText;
    let detail: unknown;
    try {
      const body = await res.json();
      code = body?.error?.code ?? body?.detail?.code ?? code;
      message = body?.error?.message ?? body?.detail?.message ?? body?.detail ?? message;
      detail = body?.error?.detail ?? body?.detail?.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, code, String(message), detail);
  }
  return res;
}

function authHeaders(): Record<string, string> {
  // Resolved by lib/auth.ts; imported lazily to avoid a cycle.
  if (typeof window === "undefined") return {};
  const roles = window.sessionStorage.getItem("p117.roles");
  return roles ? { "X-P117-Roles": roles } : {};
}

// --- console records -------------------------------------------------------
// Shapes mirror the FastAPI responses exactly (camelCase on the wire), so the
// console can render live rows without a translation layer. These replaced the
// hand-written mock records the console used to read from lib/mock/.

/** One live instrument reading as the backend reports it. */
export interface EquipmentSignal {
  signal: string;
  value: number;
  unit: string;
  baseline: number;
  limit: number;
  deltaPercent: number;
  state: string;
}

export interface EquipmentRecord {
  id: string;
  name: string;
  type: string;
  unit: string;
  area: string;
  /**
   * Plan coordinates from the plant dataset, inside the asset's area
   * rectangle. These are the real layout the schematic draws from; the console
   * used to synthesise a position because the API did not expose these.
   */
  x: number;
  y: number;
  /** A word ("medium", "high"), not a number — the earlier annotation was wrong. */
  criticality: string;
  status: string;
  manufacturer: string;
  model: string;
  installedYear: number;
  lastInspection: string;
  nextInspection: string;
  sopId: string | null;
  manualId: string | null;
  tags: string[];
  /** Real instrument readings (objects), not plain strings. */
  keySignals: EquipmentSignal[];
  summary: string;
}

/**
 * A work order with its related records.
 *
 * `GET /api/work-orders/{id}` does not return a bare order — it returns this
 * envelope, and so do POST and PATCH. Declaring them as `WorkOrderRecord` (which
 * is what this file used to do) was a type that did not describe the wire, so
 * the compiler could not catch `consoleData.workOrders.get` mapping the envelope
 * as if it were the order. Every field on the detail page then rendered
 * `undefined`/defaults. The types are the fix; the unwrap is in console.ts.
 */
/* ---------------------------------------------------------------- materials */
/*
 * Wire types for the Industrial Materials layer. These mirror
 * backend/api/src/routes/materials.py exactly. Deliberately no view-model
 * reshaping here: `console.ts` adapts for rendering, and the domain shapes stay
 * visible so a field the backend computes is never silently reinterpreted.
 */

export interface ProvenanceRecord {
  source: string;
  timestamp: string;
  data_status: "ACTUAL" | "IMPORTED" | "MANUAL" | "SYNTHETIC_DEMO";
  note: string;
}

export interface MaterialRecord {
  id: string;
  name: string;
  material_class: "RAW_MATERIAL" | "INTERMEDIATE" | "FINISHED_PRODUCT" | "MAINTENANCE_SPARE";
  unit: string;
  location: string;
  status: string;
  description: string;
  quality_attributes: Record<string, unknown>;
  supplier_id: string | null;
  cost_basis: string;
  source_process_unit: string | null;
  destination_process_unit: string | null;
  provenance: ProvenanceRecord;
  created_at: string;
  updated_at: string;
}

/** A limitation the backend reported instead of a value. Never rendered as a blank. */
export interface LimitationRecord {
  code: string;
  message: string;
  [key: string]: unknown;
}

export interface InventoryStatusRecord {
  material_id: string;
  material?: MaterialRecord;
  location?: string;
  quantity?: number;
  reserved?: number;
  available?: number;
  safety_stock?: number;
  reorder_level?: number;
  threshold?: number | null;
  unit?: string;
  status?: string;
  timestamp?: string;
  days_of_cover?: number | null;
  average_daily_consumption?: number | null;
  source?: string;
  data_status?: string;
  provenance?: ProvenanceRecord;
  calculation_basis?: Record<string, unknown>;
  limitations?: LimitationRecord[];
}

export interface MaterialMovementRecord {
  id: string;
  material_id: string;
  movement_type: "RECEIPT" | "TRANSFER" | "CONSUMPTION" | "PRODUCTION" | "DISPATCH" | "ADJUSTMENT";
  quantity: number;
  unit: string;
  timestamp: string;
  source_location: string;
  destination_location: string;
  reference: string;
  provenance: ProvenanceRecord;
}

export interface ProductionBucketRecord {
  period_start: string;
  period_end: string;
  quantity: number;
}

export interface ProductionSeriesRecord {
  period: string;
  unit?: string;
  product_id?: string | null;
  process_unit_id?: string | null;
  buckets: ProductionBucketRecord[];
  latest?: ProductionBucketRecord & { partial?: boolean };
  previous?: ProductionBucketRecord | null;
  change_percent?: number | null;
  trend?: "INCREASING" | "DECREASING" | "FLAT" | null;
  records?: number;
  source?: string;
  data_status?: string;
  calculation_basis?: Record<string, unknown>;
  limitations?: LimitationRecord[];
}

export interface PricePointRecord {
  date: string;
  price: number;
  data_status?: string;
  source?: string;
}

export interface PriceHistoryRecord {
  item_id: string;
  name?: string | null;
  current?: { price: number; unit: string; observed_on: string };
  baseline?: { price: number; unit: string; observed_on: string };
  change_absolute?: number;
  change_percent?: number;
  movement?: "NORMAL" | "WARNING" | "ABNORMAL";
  window_days?: number;
  thresholds?: { warning_pct: number; abnormal_pct: number };
  series?: PricePointRecord[];
  points?: number;
  source?: string;
  data_status?: string;
  last_updated?: string;
  calculation_basis?: Record<string, unknown>;
  conversion_note?: string | null;
  limitations?: LimitationRecord[];
}

export interface SupplierRecord {
  id: string;
  name: string;
  lead_time_days: number;
  status: string;
  contact: string;
  reference: string;
  provenance: ProvenanceRecord;
}

export interface FinancialEventRecord {
  id: string;
  event_type: string;
  amount: number;
  currency: string;
  occurred_on: string;
  reference: string;
  calculation_status: string;
  basis: Record<string, unknown>;
  provenance: ProvenanceRecord;
}

export interface RequirementLineRecord {
  requirement_id: string;
  item_id: string;
  item_name?: string | null;
  unit: string;
  required_quantity: number;
  available: number | null;
  reserved?: number | null;
  safety_stock: number;
  surplus_after_requirement_and_safety: number | null;
  coverage: "COVERED" | "SHORTFALL" | "UNKNOWN";
  shortfall_quantity: number;
  schedule?: string;
  purpose?: string;
  failure_mode?: string | null;
  mode_match?: boolean;
  inventory_status?: string;
  limitations?: LimitationRecord[];
}

export interface MaterialRequirementRecord {
  equipment_id: string;
  failure_mode?: string | null;
  multiplier?: number;
  overall_coverage: "COVERED" | "SHORTFALL" | "UNKNOWN";
  lines: RequirementLineRecord[];
  limitations?: LimitationRecord[];
}

export interface EquipmentRequirementRecord {
  requirement_id: string;
  item_id: string;
  item_name?: string | null;
  required_quantity: number;
  unit: string;
  schedule: string;
  purpose: string;
  failure_mode: string | null;
  mode_match: boolean;
  inventory: {
    available?: number | null;
    reserved?: number | null;
    safety_stock?: number | null;
    status?: string;
    unit?: string;
    data_status?: string;
  };
  provenance: ProvenanceRecord;
  limitations?: LimitationRecord[];
}

export interface EquipmentRequirementsRecord {
  equipment_id: string;
  failure_mode?: string | null;
  requirements: EquipmentRequirementRecord[];
  limitations?: LimitationRecord[];
}

export interface GraphNodeRecord {
  id: string;
  kind: string;
  label: string;
  [key: string]: unknown;
}

export interface GraphEdgeRecord {
  source: string;
  target: string;
  relation: string;
  provenance?: ProvenanceRecord;
  [key: string]: unknown;
}

export interface MaterialsGraphRecord {
  nodes: GraphNodeRecord[];
  edges: GraphEdgeRecord[];
  counts: { nodes: number; edges: number };
  material_id?: string;
  data_status?: string;
}

export interface RecommendationLineRecord {
  item_id: string;
  item_name?: string | null;
  required_quantity: number;
  unit: string;
  coverage: string;
  available: number | null;
  safety_stock: number;
  surplus_after_requirement_and_safety: number | null;
  shortfall_quantity: number;
  purpose?: string;
  schedule?: string;
  price: {
    current?: { price: number; unit: string; observed_on: string } | null;
    change_percent?: number | null;
    movement?: string | null;
    window_days?: number;
    data_status?: string | null;
    source?: string | null;
    points?: number;
  };
  cost: {
    amount?: number | null;
    currency?: string | null;
    calculation_status?: string | null;
    basis?: Record<string, unknown> | null;
  };
  procurement_required: boolean;
  recommended_order_quantity: number;
  limitations?: LimitationRecord[];
}

export interface RecommendationRecord {
  equipment_id: string;
  failure_mode?: string | null;
  generated_at?: string;
  status: string;
  overall_coverage?: string;
  recommendation: string;
  procurement_required?: boolean;
  estimated_material_cost?: {
    amount: number;
    currency: string;
    calculation_status: string;
    basis: string;
  };
  confidence?: string;
  confidence_basis?: string;
  lines: RecommendationLineRecord[];
  approval?: { required: boolean; reason: string; state: string };
  limitations?: LimitationRecord[];
}

export interface MaterialsDashboardRecord {
  generated_at: string;
  data_status: string;
  counts: { materials: number; by_class: Record<string, number> };
  raw_material_cover: {
    material_id: string;
    name: string | null;
    quantity?: number;
    unit?: string;
    days_of_cover: number | null;
    status?: string;
    limitations?: LimitationRecord[];
  }[];
  finished_product_positions: {
    material_id: string;
    name: string | null;
    quantity?: number;
    reserved?: number;
    available?: number;
    unit?: string;
    location?: string;
    status?: string;
  }[];
  critical_materials: {
    material_id: string;
    name: string;
    material_class: string;
    status?: string;
    available?: number;
    safety_stock?: number;
    unit?: string;
    location?: string;
  }[];
  production: {
    period?: string;
    latest?: { period_start: string; period_end: string; quantity: number; partial?: boolean } | null;
    previous?: { period_start: string; period_end: string; quantity: number } | null;
    change_percent?: number | null;
    trend?: string | null;
    unit?: string;
  };
  inventory_value: {
    amount: number;
    currency: string;
    materials_priced: number;
    calculation_status: string;
    basis: string;
  };
  recent_movements: MaterialMovementRecord[];
  limitations?: LimitationRecord[];
}

export interface MaterialInsightRecord {
  kind: string;
  severity: "CRITICAL" | "WARNING" | "INFO";
  material_id: string | null;
  name: string | null;
  message: string;
  evidence: Record<string, unknown>;
}

export interface MaterialsIntelligenceRecord {
  dashboard: MaterialsDashboardRecord;
  intelligence: {
    generated_at: string;
    insights: MaterialInsightRecord[];
    counts: { critical: number; warning: number; info: number };
  };
  data_status: string;
}

export interface MaterialForecastRecord {
  material_id: string;
  unit?: string;
  available?: number;
  safety_stock?: number;
  samples?: number;
  window_days?: number;
  mean_daily_consumption?: number;
  stdev_daily_consumption?: number;
  coefficient_of_variation?: number;
  projected_depletion_date?: string;
  projected_safety_stock_crossing_date?: string;
  days_to_depletion?: number;
  days_to_safety_stock?: number;
  confidence?: string;
  confidence_basis?: string;
  status?: string;
  limitations?: LimitationRecord[];
}

export interface MaterialDetailEnvelope {
  material: MaterialRecord;
  class_label: string;
  inventory: InventoryStatusRecord;
  movements: MaterialMovementRecord[];
  price_history: PriceHistoryRecord;
  forecast: MaterialForecastRecord;
  supplier: SupplierRecord | null;
  required_by: {
    equipment_id: string;
    requirement_id: string;
    quantity: number;
    unit: string;
    schedule: string;
    purpose: string;
    failure_mode: string | null;
  }[];
  upcoming_requirements: {
    equipment_id: string;
    schedule?: string;
    purpose?: string;
    required_quantity: number;
    available: number | null;
    safety_stock: number;
    coverage: string;
    gap: number;
    unit: string;
  }[];
  graph: MaterialsGraphRecord;
  provenance: ProvenanceRecord;
  data_status: string;
}

export interface MaterialsListEnvelope<T = MaterialRecord> {
  items: T[];
  count: number;
  total?: number;
  limit?: number;
  offset?: number;
  source?: string;
  data_status?: string;
  calculation_basis?: Record<string, unknown>;
}

export interface WorkOrderEnvelope {
  workOrder: WorkOrderRecord;
  persistence?: string;
  source?: string;
}

export interface WorkOrderDetailEnvelope extends WorkOrderEnvelope {
  equipment: EquipmentRecord | null;
  evidenceDocuments: unknown[];
  allowedTransitions: string[];
}

export interface WorkOrderUpdateEnvelope {
  workOrder: WorkOrderRecord;
  allowedTransitions: string[];
  persistence?: string;
}

export interface WorkOrderRecord {
  id: string;
  title: string;
  equipmentId: string | null;
  priority: string;
  status: string;
  type: string;
  assignee: string | null;
  dueDate: string | null;
  createdAt: string;
  createdBy: string;
  description: string;
  evidence: string[];
  origin: string;
  source: string;
}

export interface ApprovalRecord {
  id: string;
  title: string;
  type: string;
  status: string;
  risk: string;
  requestedBy: string;
  requestedAt: string;
  requiredRole: string;
  relatedId: string | null;
  summary: string;
  evidence: string[];
}

/** GET /api/analytics/summary — every figure computed from real rows or
 *  measured by the running process. Nothing here is a decorative constant. */
export interface AnalyticsSummary {
  equipment: {
    total: number;
    byStatus: Record<string, number>;
    critical: string[];
    warning: string[];
  };
  workOrders: {
    total: number;
    byStatus: Record<string, number>;
    open: number;
    highPriorityOpen: number;
  };
  approvals: { total: number; pending: number };
  /** In-process metrics: request counters and per-route latencies. */
  platform: {
    counters: Record<string, number>;
    durations: Record<string, { count: number; mean_ms: number }>;
  };
  computedAt: string;
  sources: Record<string, string>;
}

/** GET /api/analytics/trends. Series are empty until history is persisted;
 *  the endpoint says so rather than inventing points. */
export interface AnalyticsTrends {
  series: Record<string, { t: number; value: number }[]>;
  available: string[];
  source: string;
}

/** The three list endpoints share this envelope. */
interface ListEnvelope<T> {
  items: T[];
  count: number;
  source: string;
}

type QueryValue = string | number | boolean | string[] | undefined | null;

/**
 * GET /api/audit/integrity — the backend verifier's own output.
 *
 * `valid: false` with `broken_id`/`reason` means the chain failed at a named
 * row. `error` means the verifier could not run at all, which is a third state
 * and must not be rendered as either green or red.
 */
export interface AuditIntegrity {
  valid: boolean;
  status: "VALID" | "BROKEN" | "UNVERIFIABLE";
  events: number;
  last_hash: string;
  last_seq: number;
  checked_at: string | null;
  algorithm: string;
  genesis_hash: string;
  broken_id?: string | null;
  broken_seq?: number | null;
  reason?: string | null;
  error?: string | null;
}

/** One row from GET /api/artifacts/signatures. */
export interface SignedArtifactRecord {
  artifact_id: string;
  filename: string;
  type: string;
  sha256: string;
  signature_status: "signed" | "unsigned" | "signature_failed";
  signature_key_id: string | null;
  signed_at: string | null;
  created_at: string | null;
  verification_status: string;
  /** The digest the signature was made with, when the row records one. */
  algorithm?: string | null;
}

/** One line of GET /api/security/sovereignty's status bar. */
export type SovereigntyState = "VERIFIED" | "IMPLEMENTED" | "PARTIAL" | "NOT AVAILABLE";

export interface SovereigntyEntry {
  key: string;
  label: string;
  state: SovereigntyState;
  detail: string;
  evidence: Record<string, unknown>;
}

/** GET /api/security/sovereignty — every value measured on the backend. */
export interface SovereigntyStatus {
  generated_at: string;
  host: Record<string, string>;
  status: SovereigntyEntry[];
  capabilities: SovereigntyEntry[];
}

/** One row of GET /api/security/events. */
export interface SecurityEvent {
  id: string;
  timestamp: string | null;
  action: string;
  outcome: string | null;
  user: string | null;
  resource_type: string | null;
  resource_id: string | null;
  agent: string | null;
  tool: string | null;
  error: string | null;
}

export interface SecurityEvents {
  available: boolean;
  reason?: string;
  namespaces: { namespace: string; count: number }[];
  total: number;
  events: SecurityEvent[];
}

/** One row of POST /api/security/evaluation. */
export interface EvaluationResult {
  id: string;
  name: string;
  expected: string;
  status: "PASS" | "FAIL" | "NOT IMPLEMENTED";
  actual: string;
  detail: string;
}

export interface SecurityEvaluation {
  generated_at: string;
  total: number;
  passed: number;
  not_implemented: number;
  results: EvaluationResult[];
}

/** POST /api/security/artifacts/{id}/verify. */
export interface ArtifactVerification {
  available: boolean;
  reason?: string;
  artifact_id?: string;
  status?: "SIGNATURE VALID" | "INTEGRITY VALID" | "SIGNATURE INVALID" | "UNSIGNED";
  detail?: string;
  sha256?: string | null;
  expected_sha256?: string | null;
  key_id?: string | null;
}

/** GET /api/artifacts/signatures. */
export interface ArtifactSignatures {
  available: boolean;
  algorithm: string;
  key_id: string | null;
  /** True when no signing key is configured, so nothing here can be signed. */
  flagged: boolean;
  totals: { signed: number; unsigned: number; signature_failed: number };
  artifacts: SignedArtifactRecord[];
  scope: string;
}

/** GET /api/artifacts/{id}/signature. */
export interface SignatureVerification {
  artifact_id: string;
  status: "SIGNATURE VALID" | "INTEGRITY VALID" | "SIGNATURE INVALID" | "UNSIGNED";
  detail: string;
  signature_present: boolean;
  sha256: string | null;
  expected_sha256: string | null;
  key_id: string | null;
  signed_at: string | null;
  algorithm: string | null;
  filename?: string | null;
}

/** One `network.connection_attempt` event from the sentinel SSE stream. */
export interface NetworkConnectionAttempt {
  timestamp: string;
  source: string | null;
  destination: string | null;
  port: number | null;
  process: string | null;
  /** null when the attempt happened outside a task context. Never invented. */
  agent: string | null;
  task_id: string | null;
  action: "ALLOW" | "BLOCK";
  reason: string | null;
  local: boolean;
  scheme: string | null;
}

/**
 * GET /api/models — the gateway's real answer.
 *
 * `roles` is the role → model map the router actually resolves. A role the
 * deployment has not assigned arrives as `null` (vision and reranker do on this
 * host) and must stay `null` in the UI: "unassigned" is a measurement, and
 * naming a plausible model for it would be an invention.
 *
 * Declared as a type alias rather than an interface on purpose: an alias of an
 * object type carries an implicit index signature, so the existing callers that
 * take `Record<string, unknown>` keep compiling.
 */
export type ModelsStatus = {
  backend: { name: string | null; providers: string[] };
  models: Record<string, string[]>;
  roles: Record<string, string | null>;
};

/**
 * POST /api/search — the retrieval envelope.
 *
 * `withheld` is the clearance layer's own count of chunks removed because the
 * caller's level was below the chunk's label. It is reported separately from
 * `total` so "nothing matched" and "something matched that you may not see"
 * stay distinguishable — which is the only way the clearance boundary is
 * observable from the console at all.
 */
export type SearchResponse = {
  query: string;
  mode: string;
  total: number;
  withheld: number;
  results: Record<string, unknown>[];
  elapsed_seconds?: number;
};

/**
 * GET /api/auth/me — who the backend thinks the caller is.
 *
 * This deployment is header-authenticated, so `authenticated: false` is the
 * honest answer for an anonymous console session and `authRequired: false`
 * means the API is not gating on identity. Both are surfaced rather than
 * smoothed over.
 */
export interface CallerIdentity {
  user: string;
  roles: string[];
  authenticated: boolean;
  permissions: string[];
  authRequired: boolean;
  defaultRole: string;
  headers?: Record<string, string>;
}

/**
 * POST /api/security/egress-probe — one real egress decision, no socket.
 *
 * The endpoint only accepts RFC 5737 documentation addresses, so it can never
 * be used to make the process attempt real external traffic. `decision` is the
 * decision the policy actually took and `socket_opened` is always false.
 */
export interface EgressProbeResult {
  accepted: boolean;
  reason?: string;
  url: string;
  destination?: string;
  decision?: "ALLOW" | "BLOCK";
  detail?: string;
  recorded?: boolean;
  socket_opened?: boolean;
}

/**
 * Build a query string. Arrays become repeated parameters (`?series=a&series=b`)
 * rather than a single comma-joined value, which is what FastAPI's `list[str]`
 * query parameters expect.
 */
function query(params: Record<string, QueryValue>): string {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value) qs.append(key, item);
    } else {
      qs.append(key, String(value));
    }
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

/** One entry from GET /api/simulation/plants. */
export interface PlantSummary {
  id: string;
  name: string;
  industry: string;
  assets: number;
  sensors: number;
  scenarios: number;
  areas: number;
}

export const api = {
  health: () => request<HealthResponse>("/health"),

  /**
   * The plant datasets the backend serves. Used for identity — the console
   * displayed a hardcoded "Plant Alpha", which is not a plant that exists.
   */
  plants: {
    list: () =>
      request<{ source: string; plants: PlantSummary[] }>("/api/simulation/plants"),
  },

  chat: {
    create: (payload: ChatTurnRequest) =>
      request<ChatTurnResult>("/api/chat", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    streamUrl: () => `${API_BASE}/api/chat/stream`,
  },

  agents: {
    list: () => request<{ agents: AgentDescriptor[] }>("/api/agents"),
    get: (kind: string) => request<AgentDescriptor>(`/api/agents/${kind}`),
  },

  jobs: {
    list: () => request<{ jobs: JobRecord[] }>("/api/jobs"),
    get: (id: string) => request<JobRecord>(`/api/jobs/${id}`),
    create: (payload: { title: string; agent: string; inputs?: Record<string, unknown> }) =>
      request<JobRecord>("/api/jobs", { method: "POST", body: JSON.stringify(payload) }),
    approve: (id: string) =>
      request<JobRecord>(`/api/jobs/${id}/approve`, { method: "POST" }),
    cancel: (id: string) =>
      request<JobRecord>(`/api/jobs/${id}/cancel`, { method: "POST" }),
  },

  workflows: {
    list: () => request<{ workflows: WorkflowDefinition[] }>("/api/workflows"),
    get: (name: string) =>
      request<WorkflowDefinition>(`/api/workflows/${encodeURIComponent(name)}`),
  },

  workspaces: {
    list: () => request<{ total: number; workspaces: WorkspaceRecord[] }>("/api/workspaces"),
    get: (id: string) => request<WorkspaceRecord>(`/api/workspaces/${encodeURIComponent(id)}`),
    create: (payload: { name: string; description?: string }) =>
      request<WorkspaceRecord>("/api/workspaces", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    delete: (id: string) =>
      request<{ deleted: boolean; id: string }>(`/api/workspaces/${encodeURIComponent(id)}`, {
        method: "DELETE",
      }),
    health: (id: string) =>
      request<WorkspaceHealthRecord>(`/api/workspaces/${encodeURIComponent(id)}/health`),
    default: () => request<WorkspaceRecord>("/api/workspaces/default"),
    defaultHealth: () => request<WorkspaceHealthRecord>("/api/workspaces/default/health"),
  },

  documents: {
    list: (params: { workspaceId?: string; status?: string; limit?: number; offset?: number } = {}) =>
      request<{ total: number; limit: number; offset: number; documents: DocumentRecord[] }>(
        `/api/documents${query({ workspace_id: params.workspaceId, status: params.status, limit: params.limit, offset: params.offset })}`,
      ),
    get: (id: string) => request<DocumentRecord>(`/api/documents/${id}`),
    /**
     * Real multipart upload to POST /api/documents/upload. Supports single or multiple files.
     */
    upload: (file: File, workspaceId?: string) => {
      const form = new FormData();
      form.append("files", file);
      const qs = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";
      return request<{ uploaded: number; documents: DocumentRecord[] }>(
        `/api/documents/upload${qs}`,
        { method: "POST", body: form },
      );
    },
    uploadMulti: (files: File[], workspaceId?: string) => {
      const form = new FormData();
      for (const f of files) {
        form.append("files", f);
      }
      const qs = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";
      return request<{ uploaded: number; documents: DocumentRecord[] }>(
        `/api/documents/upload${qs}`,
        { method: "POST", body: form },
      );
    },
    delete: (id: string) =>
      request<{ deleted: boolean; id: string }>(`/api/documents/${id}`, { method: "DELETE" }),
    /**
     * The parsed text of one document, in reading order.
     */
    chunks: (id: string, limit = 200) =>
      request<{
        documentId: string;
        filename: string;
        chunkCount: number;
        chunks: {
          chunk_id: string;
          document_id: string;
          chunk_index: number;
          text: string;
          block_type: string;
          heading_path: string[];
          page: number | null;
          source: string | null;
        }[];
      }>(`/api/documents/${encodeURIComponent(id)}/chunks?limit=${limit}`),
    reindex: (id: string) =>
      request<Record<string, unknown>>(`/api/documents/${id}/reindex`, { method: "POST" }),
    reprocess: (id: string) =>
      request<Record<string, unknown>>(`/api/documents/${id}/reindex`, { method: "POST" }),
    progressUrl: (id: string) => `${API_BASE}/api/documents/${encodeURIComponent(id)}/progress`,
  },

  knowledgeHub: {
    entities: (params: { workspaceId?: string; entityType?: string; search?: string; limit?: number; offset?: number } = {}) =>
      request<{ total: number; workspace_id: string; entities: KnowledgeEntityRecord[] }>(
        `/api/knowledge-hub/entities${query({
          workspace_id: params.workspaceId,
          entity_type: params.entityType,
          search: params.search,
          limit: params.limit,
          offset: params.offset,
        })}`,
      ),
    entity: (id: string) =>
      request<KnowledgeEntityRecord>(`/api/knowledge-hub/entities/${encodeURIComponent(id)}`),
    graph: (workspaceId?: string) =>
      request<KnowledgeGraphResponse>(
        `/api/knowledge-hub/graph${query({ workspace_id: workspaceId })}`,
      ),
    rebuild: (workspaceId?: string) =>
      request<{ queued: boolean; message: string }>("/api/knowledge-hub/rebuild", {
        method: "POST",
        body: JSON.stringify({ workspace_id: workspaceId }),
      }),
  },

  search: {
    query: (payload: {
      query: string;
      top_k?: number;
      mode?: "hybrid" | "vector_only" | "fts_only";
      document_ids?: string[] | null;
    }) => request<SearchResponse>("/api/search", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  },

  artifacts: {
    list: (jobId?: string) =>
      request<{ total: number; artifacts: ArtifactRecord[] }>(
        `/api/artifacts${jobId ? `?job_id=${encodeURIComponent(jobId)}` : ""}`,
      ),
    get: (id: string) => request<ArtifactRecord>(`/api/artifacts/${id}`),
    generate: (payload: { kind: string; content: Record<string, unknown>; filename?: string }) =>
      request<ArtifactRecord>("/api/artifacts/generate", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    /**
     * Signature status of recent artifacts. Real rows from the artifact store:
     * a deployment with nothing signed reports zero, never a green tick.
     */
    signatures: (limit = 25) =>
      request<ArtifactSignatures>("/api/artifacts/signatures?limit=" + limit),
    /** Re-verify one stored artifact against the bytes currently on disk. */
    verifySignature: (id: string) =>
      request<SignatureVerification>(`/api/artifacts/${id}/signature`),
  },

  security: {
    /**
     * The Security Console's status bar. Every entry is resolved from a
     * measurement taken on the backend at call time — the console renders the
     * state it is given and never derives one of its own.
     */
    sovereignty: () => request<SovereigntyStatus>("/api/security/sovereignty"),
    /** Security-relevant audit rows only, plus the namespace counts behind them. */
    events: (limit = 40) => request<SecurityEvents>(`/api/security/events?limit=${limit}`),
    /**
     * Exercise the refusal controls this build actually has. Real calls, real
     * refusals, no audit writes and no external traffic.
     */
    evaluation: () =>
      request<SecurityEvaluation>("/api/security/evaluation", { method: "POST" }),
    /** Re-verify one artifact through the real Ed25519 implementation. */
    verifyArtifact: (id: string) =>
      request<ArtifactVerification>(`/api/security/artifacts/${encodeURIComponent(id)}/verify`, {
        method: "POST",
      }),
    /**
     * Take one real egress decision inside the API process — no socket is
     * opened, and the endpoint refuses anything outside the RFC 5737
     * documentation ranges. The decision it returns is recorded, so it reaches
     * the audit log and every live sentinel subscriber.
     */
    egressProbe: (url: string) =>
      request<EgressProbeResult>("/api/security/egress-probe", {
        method: "POST",
        body: JSON.stringify({ url }),
      }),
  },

  auth: {
    /**
     * The identity the backend resolves for this session. Used to report the
     * caller's real roles and permissions instead of a role the browser picked.
     */
    me: () => request<CallerIdentity>("/api/auth/me"),
  },

  network: {
    /**
     * The Network Sentinel SSE endpoint. Not opened here — the caller owns the
     * `EventSource` so it can close it on unmount. This exists so no component
     * builds a URL by hand.
     */
    streamUrl: () => `${API_BASE}/api/network/stream`,
  },

  tools: {
    list: () => request<{ tools: ToolDescriptor[] }>("/api/tools"),
  },

  models: {
    /** The real role → model map plus what the local gateway serves. */
    status: () => request<ModelsStatus>("/api/models"),
  },

  audit: {
    query: (
      params: { limit?: number; actor?: string; action?: string; excludeActionPrefix?: string } = {},
    ) => {
      // `excludeActionPrefix` is camelCase on the way in and snake_case on the
      // wire; the rest pass through.
      const { excludeActionPrefix, ...rest } = params;
      const qs = new URLSearchParams(
        Object.entries(rest).filter(([, v]) => v != null) as [string, string][],
      );
      if (excludeActionPrefix) qs.set("exclude_action_prefix", excludeActionPrefix);
      return request<{ events: Record<string, unknown>[] }>(`/api/audit?${qs}`);
    },
    /**
     * The tamper-evident hash chain, walked by the backend verifier. The
     * response is the verifier's own output: `valid`, `events`, `last_hash`,
     * and on failure the offending id/sequence and reason.
     */
    integrity: () => request<AuditIntegrity>("/api/audit/integrity"),
  },

  // --- console records (were mock constants in lib/mock/) ------------------

  equipment: {
    list: (params: { area?: string; status?: string; q?: string } = {}) =>
      request<ListEnvelope<EquipmentRecord>>(`/api/equipment${query(params)}`),
    /**
     * The detail endpoint returns an envelope, not the bare record:
     * `{equipment, openWorkOrders, workOrders, documents, history, source}`.
     * This was typed as `EquipmentRecord`, so the adapter read `name`, `model`
     * and `sensors` straight off the envelope and every field on the detail
     * page rendered as "—".
     */
    get: (id: string) =>
      request<{
        equipment: EquipmentRecord;
        openWorkOrders: Record<string, unknown>[];
        workOrders: Record<string, unknown>[];
        documents: Record<string, unknown>[];
        history: Record<string, unknown>[];
        source: string;
      }>(`/api/equipment/${encodeURIComponent(id)}`),
    telemetry: (id: string) =>
      request<Record<string, unknown>>(`/api/equipment/${encodeURIComponent(id)}/telemetry`),
    history: (id: string) =>
      request<{ equipmentId: string; items: Record<string, unknown>[]; count: number; source: string }>(
        `/api/equipment/${encodeURIComponent(id)}/history`,
      ),
    /**
     * The asset's printable QR label, as an SVG document string.
     *
     * The backend renders it (locally, with `segno`) and encodes the namespaced
     * `P117:EQUIP:<tag>` payload, so the console has exactly one QR source of
     * truth and pulls in no JavaScript QR library of its own.
     */
    qrSvg: (id: string) =>
      requestText(`/api/equipment/${encodeURIComponent(id)}/qr.svg`),
  },

  workOrders: {
    list: (params: { status?: string; equipmentId?: string; priority?: string } = {}) =>
      request<ListEnvelope<WorkOrderRecord>>(`/api/work-orders${query(params)}`),
    get: (id: string) =>
      request<WorkOrderDetailEnvelope>(`/api/work-orders/${encodeURIComponent(id)}`),
    transitions: () => request<Record<string, unknown>>("/api/work-orders/meta/transitions"),
    create: (payload: {
      title: string;
      equipmentId?: string | null;
      priority?: string;
      type?: string;
      status?: string;
      assignee?: string | null;
      dueDate?: string | null;
      description?: string;
      evidence?: string[];
      origin?: string;
    }) =>
      request<WorkOrderEnvelope>("/api/work-orders", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    update: (id: string, patch: { status?: string; assignee?: string; note?: string }) =>
      request<WorkOrderUpdateEnvelope>(`/api/work-orders/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      }),
  },

  /**
   * Industrial materials, inventory and business intelligence.
   *
   * Every figure these endpoints return is computed by the backend domain
   * service. The frontend performs no inventory arithmetic, no unit conversion
   * and no cost calculation — it renders what the domain computed, so the web
   * console, the Android client and the agent tools cannot disagree.
   */
  materials: {
    list: (params: { materialClass?: string; search?: string; supplierId?: string; location?: string; limit?: number; offset?: number } = {}) =>
      request<MaterialsListEnvelope>(`/api/materials${query(params)}`),
    get: (id: string) =>
      request<MaterialDetailEnvelope>(`/api/materials/${encodeURIComponent(id)}`),
    inventory: (params: { materialClass?: string; search?: string; limit?: number; offset?: number } = {}) =>
      request<MaterialsListEnvelope<InventoryStatusRecord>>(
        `/api/materials/inventory${query({ material_class: params.materialClass, search: params.search, limit: params.limit, offset: params.offset })}`,
      ),
    inventoryOne: (materialId: string) =>
      request<InventoryStatusRecord>(`/api/materials/inventory/${encodeURIComponent(materialId)}`),
    movements: (params: { materialId?: string; movementType?: string; since?: string; limit?: number; offset?: number } = {}) =>
      request<ListEnvelope<MaterialMovementRecord>>(
        `/api/materials/movements${query({ material_id: params.materialId, movement_type: params.movementType, since: params.since, limit: params.limit, offset: params.offset })}`,
      ),
    production: (params: { period?: string; productId?: string; processUnitId?: string; since?: string; until?: string } = {}) =>
      request<ProductionSeriesRecord>(
        `/api/materials/production${query({ period: params.period, product_id: params.productId, process_unit_id: params.processUnitId, since: params.since, until: params.until })}`,
      ),
    priceHistory: (itemId: string, params: { windowDays?: number; unit?: string; abnormalPct?: number } = {}) =>
      request<PriceHistoryRecord>(
        `/api/materials/price-history/${encodeURIComponent(itemId)}${query({ window_days: params.windowDays, unit: params.unit, abnormal_pct: params.abnormalPct })}`,
      ),
    suppliers: (params: { status?: string } = {}) =>
      request<ListEnvelope<SupplierRecord>>(`/api/materials/suppliers${query(params)}`),
    financialEvents: (params: { eventType?: string; since?: string; limit?: number } = {}) =>
      request<ListEnvelope<FinancialEventRecord>>(
        `/api/materials/financial-events${query({ event_type: params.eventType, since: params.since, limit: params.limit })}`,
      ),
    /**
     * The equipment→material bridge.
     *
     * The wire parameter is `equipment_id`, not `equipmentId`. Sending the
     * camelCase name did not error — the endpoint treats the filter as absent and
     * falls through to its "list every requirement" branch, which returns a
     * different envelope (`{items, count}`) than the caller's type
     * (`{requirements}`). The consumer then read `.requirements` off that and
     * threw. A silently-ignored filter is worse than a rejected one, so the
     * mapping is explicit here.
     */
    equipmentRequirements: (params: { equipmentId?: string; itemId?: string; failureMode?: string } = {}) =>
      request<EquipmentRequirementsRecord>(
        `/api/materials/equipment-requirements${query({
          equipment_id: params.equipmentId,
          item_id: params.itemId,
          failure_mode: params.failureMode,
        })}`,
      ),
    maintenanceRequirements: (equipmentId: string, params: { failureMode?: string; multiplier?: number } = {}) =>
      request<MaterialRequirementRecord>(
        `/api/materials/maintenance-requirements/${encodeURIComponent(equipmentId)}${query({ failure_mode: params.failureMode, multiplier: params.multiplier })}`,
      ),
    intelligence: () => request<MaterialsIntelligenceRecord>("/api/materials/intelligence"),
    graph: () => request<MaterialsGraphRecord>("/api/materials/graph"),
    graphFor: (materialId: string) =>
      request<MaterialsGraphRecord>(`/api/materials/graph/${encodeURIComponent(materialId)}`),
    /**
     * Compose a procurement recommendation for engineer review.
     *
     * POST because it composes a proposal; the endpoint is read-only and places
     * no order. Execution requires an approval decision through the existing
     * approvals flow.
     */
    recommendation: (equipmentId: string, failureMode?: string) =>
      request<RecommendationRecord>(
        `/api/materials/procurement-recommendations${query({ equipment_id: equipmentId, failure_mode: failureMode })}`,
        { method: "POST" },
      ),
  },

  approvals: {
    list: () =>
      request<ListEnvelope<ApprovalRecord> & { pendingCount: number; canDecide: boolean }>(
        "/api/approvals",
      ),
    get: (id: string) => request<ApprovalRecord>(`/api/approvals/${encodeURIComponent(id)}`),
    decide: (id: string, decision: "approved" | "rejected", note = "") =>
      request<ApprovalRecord>(`/api/approvals/${encodeURIComponent(id)}/decision`, {
        method: "POST",
        body: JSON.stringify({ decision, note }),
      }),
  },

  analytics: {
    summary: () => request<AnalyticsSummary>("/api/analytics/summary"),
    trends: (series?: string[]) =>
      request<AnalyticsTrends>(`/api/analytics/trends${query({ series })}`),
  },
};

export type Api = typeof api;
