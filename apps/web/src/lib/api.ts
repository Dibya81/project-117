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
  ToolDescriptor,
  WorkflowDefinition,
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

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
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
  return (await res.json()) as T;
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

export const api = {
  health: () => request<HealthResponse>("/health"),

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

  documents: {
    list: () => request<{ total: number; documents: DocumentRecord[] }>("/api/documents"),
    get: (id: string) => request<DocumentRecord>(`/api/documents/${id}`),
    /**
     * Real multipart upload to POST /api/documents/upload. The file is read by
     * the server and stored; the response carries the registered rows.
     */
    upload: (file: File) => {
      const form = new FormData();
      form.append("files", file);
      return request<{ uploaded: number; documents: DocumentRecord[] }>(
        "/api/documents/upload",
        { method: "POST", body: form },
      );
    },
    delete: (id: string) =>
      request<{ deleted: boolean; id: string }>(`/api/documents/${id}`, { method: "DELETE" }),
    /**
     * The parsed text of one document, in reading order. This is the only place
     * a document's content exists after parsing — the source file is not
     * re-parsed on read, so anything that displays document text reads it here.
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
  },

  search: {
    query: (payload: {
      query: string;
      top_k?: number;
      mode?: "hybrid" | "vector_only" | "fts_only";
      document_ids?: string[] | null;
    }) => request<Record<string, unknown>>("/api/search", {
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
  },

  tools: {
    list: () => request<{ tools: ToolDescriptor[] }>("/api/tools"),
  },

  models: {
    status: () => request<Record<string, unknown>>("/api/models"),
  },

  audit: {
    query: (params: { limit?: number; actor?: string; action?: string } = {}) => {
      const qs = new URLSearchParams(
        Object.entries(params).filter(([, v]) => v != null) as [string, string][],
      );
      return request<{ events: Record<string, unknown>[] }>(`/api/audit?${qs}`);
    },
  },

  // --- console records (were mock constants in lib/mock/) ------------------

  equipment: {
    list: (params: { area?: string; status?: string; q?: string } = {}) =>
      request<ListEnvelope<EquipmentRecord>>(`/api/equipment${query(params)}`),
    get: (id: string) => request<EquipmentRecord>(`/api/equipment/${encodeURIComponent(id)}`),
    telemetry: (id: string) =>
      request<Record<string, unknown>>(`/api/equipment/${encodeURIComponent(id)}/telemetry`),
    history: (id: string) =>
      request<Record<string, unknown>>(`/api/equipment/${encodeURIComponent(id)}/history`),
  },

  workOrders: {
    list: (params: { status?: string; equipmentId?: string; priority?: string } = {}) =>
      request<ListEnvelope<WorkOrderRecord>>(`/api/work-orders${query(params)}`),
    get: (id: string) => request<WorkOrderRecord>(`/api/work-orders/${encodeURIComponent(id)}`),
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
      request<WorkOrderRecord>("/api/work-orders", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    update: (id: string, patch: { status?: string; assignee?: string; note?: string }) =>
      request<WorkOrderRecord>(`/api/work-orders/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      }),
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
