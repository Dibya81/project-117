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
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
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
    delete: (id: string) =>
      request<{ deleted: boolean; id: string }>(`/api/documents/${id}`, { method: "DELETE" }),
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
};

export type Api = typeof api;
