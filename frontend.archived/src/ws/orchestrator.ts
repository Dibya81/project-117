/**
 * Orchestrator bridge.
 *
 * A raw WebSocket to VITE_ORCHESTRATOR_WS_URL. There is no socket.io and no
 * polling: one socket, one event contract.
 *
 * Connection policy, deliberately strict:
 *   - up to MAX_ATTEMPTS connection attempts with backoff
 *   - if every attempt fails, the app enters MOCK MODE and says so loudly
 *   - in mock mode a scripted trace runs so the UI can be developed offline
 *   - every scripted entry is flagged `synthetic: true` and mocked runs are
 *     labelled in the trace panel, so a fallback is never mistaken for a live
 *     orchestration
 *
 * In live mode the trace advances ONLY on frames that actually arrive. There is
 * no local timer advancing it, and nothing is pre-scripted.
 */
import { create } from "zustand";
import type {
  Artifact,
  FaultInjectedMessage,
  FaultType,
  OrchestratorEvent,
  Sensor,
  TraceEntry,
  TraceStage,
} from "../types";

const WS_URL = import.meta.env.VITE_ORCHESTRATOR_WS_URL ?? "";
const MAX_ATTEMPTS = 3;
const BACKOFF_MS = [700, 1600, 3200];

export type ConnectionStatus = "idle" | "connecting" | "open" | "mock";

interface OrchestratorState {
  status: ConnectionStatus;
  attempts: number;
  lastError: string | null;
  /** Why we are in mock mode, surfaced verbatim in the UI. */
  mockReason: string | null;
  traces: TraceEntry[];
  artifacts: Artifact[];
  jobId: string | null;
  /** Set when an event payload names equipment — the canvas highlights it. */
  activeEquipmentId: string | null;
  connect: () => void;
  disconnect: () => void;
  injectFault: (args: {
    plantId: string;
    equipmentId: string;
    faultType: FaultType;
    sensorSnapshot: Sensor[];
  }) => void;
  reset: () => void;
}

let socket: WebSocket | null = null;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let mockTimers: ReturnType<typeof setTimeout>[] = [];
let entrySeq = 0;

const nextId = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${entrySeq++}`;
const nowIso = () => new Date().toISOString();

function clearMockTimers() {
  mockTimers.forEach(clearTimeout);
  mockTimers = [];
}

/** Map an incoming frame to a trace stage, or reject it. */
function stageFor(ev: OrchestratorEvent): TraceStage | null {
  switch (ev.type) {
    case "job.created":
      return "perceive";
    case "agent.started":
      return "plan";
    case "tool.completed":
      return "act";
    case "verification.completed":
      return "verify";
    case "artifact.created":
      return "complete";
    default:
      return null;
  }
}

export const useOrchestrator = create<OrchestratorState>((set, get) => ({
  status: "idle",
  attempts: 0,
  lastError: null,
  mockReason: null,
  traces: [],
  artifacts: [],
  jobId: null,
  activeEquipmentId: null,

  connect: () => {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
      return;
    }
    if (!WS_URL) {
      set({
        status: "mock",
        mockReason:
          "VITE_ORCHESTRATOR_WS_URL is not set, so there is no orchestrator to connect to.",
        lastError: "VITE_ORCHESTRATOR_WS_URL is not set",
      });
      return;
    }

    const attempt = get().attempts + 1;
    set({ status: "connecting", attempts: attempt, lastError: null });

    let ws: WebSocket;
    try {
      ws = new WebSocket(WS_URL);
    } catch (err) {
      scheduleRetry(set, attempt, (err as Error).message);
      return;
    }
    socket = ws;

    ws.onopen = () => {
      set({ status: "open", attempts: 0, mockReason: null, lastError: null });
    };

    ws.onmessage = (msg) => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(String(msg.data));
      } catch {
        return; // ignore frames we cannot read rather than crashing the panel
      }
      handleEvent(parsed as OrchestratorEvent, set, get);
    };

    ws.onerror = () => {
      set({ lastError: `socket error against ${WS_URL}` });
    };

    ws.onclose = (ev) => {
      socket = null;
      if (get().status === "open") {
        // Drop after a healthy session: report it, retry once more.
        set({ status: "connecting", lastError: `socket closed (${ev.code})` });
      }
      scheduleRetry(set, get().attempts, `socket closed (${ev.code})`);
    };
  },

  disconnect: () => {
    if (retryTimer) clearTimeout(retryTimer);
    retryTimer = null;
    clearMockTimers();
    socket?.close();
    socket = null;
    set({ status: "idle", attempts: 0 });
  },

  injectFault: ({ plantId, equipmentId, faultType, sensorSnapshot }) => {
    const payload: FaultInjectedMessage = {
      type: "fault.injected",
      plant_id: plantId,
      equipment_id: equipmentId,
      fault_type: faultType,
      sensor_snapshot: sensorSnapshot,
    };

    const status = get().status;
    if (status === "open" && socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(payload));
      // The trace is NOT seeded here. It fills only as real frames arrive.
      set({ activeEquipmentId: equipmentId });
      return;
    }

    if (status !== "mock") {
      get().connect();
    }
    // Fallback path — unmistakably synthetic.
    runMockSequence(plantId, equipmentId, faultType, set);
  },

  reset: () => {
    clearMockTimers();
    set({ traces: [], artifacts: [], jobId: null, activeEquipmentId: null });
  },
}));

/* --------------------------------------------------------------- internals */

function scheduleRetry(
  set: (partial: Partial<OrchestratorState>) => void,
  attempt: number,
  reason: string,
) {
  if (retryTimer) clearTimeout(retryTimer);
  if (attempt >= MAX_ATTEMPTS) {
    set({
      status: "mock",
      lastError: reason,
      mockReason: `Could not reach ${WS_URL || "(no URL configured)"} after ${MAX_ATTEMPTS} attempts (${reason}).`,
    });
    return;
  }
  const delay = BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)];
  retryTimer = setTimeout(() => useOrchestrator.getState().connect(), delay);
}

function handleEvent(
  ev: OrchestratorEvent,
  set: (partial: Partial<OrchestratorState>) => void,
  get: () => OrchestratorState,
) {
  const stage = stageFor(ev);
  if (!stage) return;

  const state = get();
  const jobId = "job_id" in ev && ev.job_id ? ev.job_id : state.jobId;

  const base = { job_id: jobId ?? "unassigned", stage, at: nowIso() };
  let entry: TraceEntry | null = null;
  const patch: Partial<OrchestratorState> = {};

  switch (ev.type) {
    case "job.created":
      entry = { id: nextId("t"), ...base, label: "Job created", detail: `Job ${ev.job_id} accepted by the orchestrator.` };
      patch.jobId = ev.job_id;
      if (ev.equipment_id) patch.activeEquipmentId = ev.equipment_id;
      break;

    case "agent.started":
      entry = {
        id: nextId("t"), ...base,
        label: ev.label ?? `${ev.agent} started`,
        detail: ev.detail ?? `Agent ${ev.agent} is working.`,
      };
      break;

    case "tool.completed":
      entry = {
        id: nextId("t"), ...base,
        label: ev.label ?? `${ev.tool} completed`,
        detail: ev.detail ?? `Tool ${ev.tool} returned.`,
        related_equipment_id: ev.related_equipment_id,
      };
      if (ev.related_equipment_id) patch.activeEquipmentId = ev.related_equipment_id;
      break;

    case "verification.completed":
      entry = {
        id: nextId("t"), ...base,
        label: ev.label ?? (ev.passed ? "Verification passed" : "Verification failed"),
        detail: ev.detail ?? (ev.passed ? "All checks passed." : "One or more checks failed."),
        related_equipment_id: ev.related_equipment_id,
      };
      if (ev.related_equipment_id) patch.activeEquipmentId = ev.related_equipment_id;
      break;

    case "artifact.created":
      entry = {
        id: nextId("t"), ...base,
        label: ev.label ?? `Artifact ${ev.filename}`,
        detail: ev.detail ?? "Deliverable written.",
      };
      patch.artifacts = [
        ...state.artifacts,
        { id: ev.artifact_id ?? nextId("art"), job_id: base.job_id, filename: ev.filename, url: ev.url },
      ];
      break;

    default:
      return;
  }

  patch.traces = [...state.traces, entry];
  set(patch);
}

/**
 * Development fallback. Every entry is marked synthetic and the sequence is
 * deliberately generic — it must never look like a real investigation result.
 */
function runMockSequence(
  plantId: string,
  equipmentId: string,
  faultType: FaultType,
  set: (partial: Partial<OrchestratorState>) => void,
) {
  clearMockTimers();
  const jobId = `mock-${Date.now().toString(36)}`;
  const steps: { stage: TraceStage; label: string; detail: string; delay: number }[] = [
    { stage: "perceive", label: "Job created (mock)", detail: `Local placeholder for ${equipmentId} on ${plantId}.`, delay: 0 },
    { stage: "plan", label: "Plan started (mock)", detail: `Fault type "${faultType}". No orchestrator is running — this sequence is generated in the browser.`, delay: 900 },
    { stage: "act", label: "Tool completed (mock)", detail: "Placeholder tool result. Not a real analysis.", delay: 1800 },
    { stage: "verify", label: "Verification pending (mock)", detail: "No verification ran. This entry exists only so the panel can be styled.", delay: 2700 },
    { stage: "complete", label: "Trace ended (mock)", detail: "Connect an orchestrator to replace this sequence with real events.", delay: 3500 },
  ];

  set({ jobId, activeEquipmentId: equipmentId });

  for (const s of steps) {
    mockTimers.push(
      setTimeout(() => {
        const state = useOrchestrator.getState();
        set({
          traces: [
            ...state.traces,
            {
              id: nextId("tm"),
              job_id: jobId,
              stage: s.stage,
              label: s.label,
              detail: s.detail,
              at: nowIso(),
              synthetic: true,
            },
          ],
        });
      }, s.delay),
    );
  }
}
