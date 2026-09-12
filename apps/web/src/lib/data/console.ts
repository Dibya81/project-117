/**
 * Console data adapter — the only import surface for workbench pages.
 * Today everything resolves from the typed mock dataset; each accessor is a
 * single awaitable call so swapping to live backend endpoints is a mechanical
 * change inside this file, never in a component.
 */
import type { ConsoleRole, HistoryEvent } from "@/types/console";
import type { WorkOrder } from "@/types";
import type { PlantDef, SimEvent } from "@/lib/sim/types";
import {
  AGENTS,
  ALERTS,
  APPROVALS,
  ARTIFACTS,
  AUDIT,
  C3_TASK,
  DOCUMENTS,
  EQUIPMENT,
  GRAPH_EDGES,
  GRAPH_NODES,
  HISTORY,
  LEARNED_RULES,
  MODELS,
  NOTIFICATIONS,
  POSTURE,
  SESSIONS,
  USERS,
  WORK_ORDERS,
} from "@/lib/mock/console";
import { equipmentDetail, INSIGHTS } from "@/lib/mock/console2";
import { ANALYTICS_SUMMARY, JOBS, TOOLS, WORKFLOWS, searchMock } from "@/lib/mock/console3";
import { api } from "@/lib/api";
import { loadLibrary } from "@/lib/documents/library";
import { crosswalkForRegister } from "@/lib/knowledge/canonical";

const ok = <T,>(value: T) => Promise.resolve(value);

/**
 * Work orders raised this session. Genuine in-memory records — they are listed,
 * routed to, and survive navigation within the session (they are not persisted
 * across a reload, and the UI does not claim they are).
 */
const createdWorkOrders: WorkOrder[] = [];

/**
 * Builder-authored plants saved this session. Same contract as
 * `createdWorkOrders`: genuine in-memory records that every consumer of this
 * adapter can see — the Knowledge Graph reads them — and that are gone on
 * reload. The builder's Save message states that plainly.
 */
const savedCustomPlants = new Map<string, PlantDef>();
let customPlantRevision = 0;

/**
 * Simulation milestones promoted into operational history. `agent.task_*`
 * chatter is deliberately excluded: history is organizational memory, not an
 * event log, and mirroring every task would flood it.
 */
const SIM_MILESTONE_TYPES = new Set([
  "incident.created",
  "incident.updated",
  "incident.resolved",
  "approval.required",
  "approval.granted",
  "approval.rejected",
]);
const simHistory: HistoryEvent[] = [];
const recordedSimEvents = new Set<string>();
const resolvedIncidents = new Set<string>();
const simIncidentContext = new Map<
  string,
  { equipment_id?: string; title: string; action?: string; target?: string }
>();
let simHistorySeq = 0;

/** Engine time is simulated seconds; only a real epoch (ms) is used verbatim. */
function eventTimestamp(at: unknown): string {
  return typeof at === "number" && at > 1e12 ? new Date(at).toISOString() : new Date().toISOString();
}

const humanAction = (kind: string | undefined) => (kind ?? "action").replace(/_/g, " ");

/** Map one engine event onto a history entry, or nothing if it is not a milestone. */
function recordSimMilestone(ev: SimEvent): void {
  if (!SIM_MILESTONE_TYPES.has(ev.type)) return;
  const dedup = `${ev.plant_id}:${ev.seq}:${ev.type}`;
  if (recordedSimEvents.has(dedup)) return;
  recordedSimEvents.add(dedup);

  const p = ev.payload as {
    id?: string; incident_id?: string; title?: string; severity?: string;
    status?: string; origin_equipment?: string; origin_sensor?: string | null;
    failure_mode?: string | null; affected?: string[]; reason?: string; risk?: string;
    action?: { kind?: string; target?: string };
  };
  const at = eventTimestamp(ev.at);
  const push = (
    kind: HistoryEvent["kind"], title: string, detail: string, actor: string, equipment_id?: string,
  ) => {
    simHistory.unshift({ id: `sim-h-${++simHistorySeq}`, kind, title, detail, actor, equipment_id, at });
  };

  if (ev.type === "incident.created") {
    const incId = p.id ?? `${ev.plant_id}-${ev.seq}`;
    simIncidentContext.set(incId, { equipment_id: p.origin_equipment, title: p.title ?? incId });
    push(
      "anomaly",
      `Anomaly detected — ${p.title ?? incId}`,
      `${(p.severity ?? "warning").toUpperCase()} incident ${incId} on ${p.origin_equipment ?? "unknown unit"}` +
        `${p.origin_sensor ? ` via ${p.origin_sensor}` : ""}${p.failure_mode ? ` · ${p.failure_mode}` : ""}; ` +
        `${p.affected?.length ?? 0} linked asset(s).`,
      "system",
      p.origin_equipment,
    );
    return;
  }

  if (ev.type === "approval.required") {
    const incId = p.incident_id ?? "";
    const ctx = simIncidentContext.get(incId);
    if (ctx) {
      ctx.action = p.action?.kind;
      ctx.target = p.action?.target;
    }
    push(
      "approval",
      `Approval required — ${incId}`,
      `${humanAction(p.action?.kind)} on ${p.action?.target ?? ctx?.equipment_id ?? "plant"} ` +
        `(risk ${p.risk ?? "unrated"}): ${p.reason ?? "action changes plant state"}`,
      "orchestrator-agent",
      ctx?.equipment_id ?? p.action?.target,
    );
    return;
  }

  if (ev.type === "approval.granted" || ev.type === "approval.rejected") {
    const incId = p.incident_id ?? "";
    const ctx = simIncidentContext.get(incId);
    const approved = ev.type === "approval.granted";
    push(
      "decision",
      `${approved ? "Approval granted" : "Approval rejected"} — ${incId}`,
      approved
        ? `Operator authorized ${humanAction(ctx?.action)} on ${ctx?.target ?? ctx?.equipment_id ?? "the plant"}.`
        : `Operator rejected the proposed response for ${ctx?.title ?? incId}; the incident is escalated for review.`,
      "operator",
      ctx?.equipment_id,
    );
    return;
  }

  // incident.updated / incident.resolved — only a resolved state is a milestone.
  if (p.status !== "resolved") return;
  const incId = p.id ?? `${ev.plant_id}-${ev.seq}`;
  if (resolvedIncidents.has(incId)) return;
  resolvedIncidents.add(incId);
  const ctx = simIncidentContext.get(incId);
  push(
    ctx?.action ? "work_order" : "recommendation",
    `Incident resolved — ${p.title ?? ctx?.title ?? incId}`,
    `Verified back inside the operating envelope after ` +
      `${ctx?.action ? `${humanAction(ctx.action)} on ${ctx.target ?? p.origin_equipment}` : "the response plan verified"}` +
      ` · ${p.affected?.length ?? 0} linked asset(s) checked, simulation t=${typeof ev.at === "number" ? ev.at.toFixed(0) : "?"} s.`,
    "operator",
    p.origin_equipment ?? ctx?.equipment_id,
  );
}

export const consoleData = {
  equipment: {
    list: () => ok(EQUIPMENT),
    /**
     * Resolve an equipment tag to its record.
     *
     * The console names units by their narrative tag (C-3); the simulation
     * register names the same machine differently (C-1071). A URL can arrive
     * with either, so an unknown tag is looked up in the crosswalk and served
     * as its canonical twin — annotated with the mapping rather than silently
     * pretending the two tags are the same string.
     */
    detail: async (id: string) => {
      const direct = equipmentDetail(id);
      if (direct) return direct;
      const entry = crosswalkForRegister(id);
      if (!entry) return null;
      const twin = equipmentDetail(entry.overlay);
      if (!twin) return null;
      return {
        ...twin,
        registerTag: entry.register,
        registerName: entry.registerName,
        mappingConfidence: entry.confidence,
        mappingBasis: entry.basis,
      };
    },
  },
  alerts: {
    list: () => ok(ALERTS),
    active: () => ok(ALERTS.filter((a) => !a.acknowledged)),
  },
  notifications: { list: () => ok(NOTIFICATIONS) },
  // Agents come from the backend registry — the real descriptors the
  // orchestrator dispatches on, not a client-side list.
  //
  // Shape note, because the declared type does not match the wire: the backend
  // returns {capabilities, description, name, requires_rag, tools}, while
  // AgentDescriptor declares {kind, name, description, model_role, tools,
  // permissions, status}. The agent's `name` IS its kind, so it is mapped
  // across. `status` is reported as idle rather than invented: a registry
  // listing genuinely does not know whether an agent is mid-run, and claiming
  // otherwise would be the exact fakery this console exists to avoid.
  agents: {
    list: () =>
      api.agents.list().then((r) =>
        r.agents.map((a) => ({ ...a, kind: a.name as typeof a.kind, status: "idle" as const })),
      ),
  },
  documents: {
    /**
     * The canonical library: register rows joined with the real refinery
     * corpus and the 5-year dossier. See lib/documents/library.ts.
     */
    list: () => loadLibrary(DOCUMENTS).then((r) => r.docs),
    get: (id: string) => loadLibrary(DOCUMENTS).then((r) => r.docs.find((d) => d.id === id) ?? null),
    stats: () => loadLibrary(DOCUMENTS).then((r) => r.stats),
    /** Simulated upload pipeline: stored → indexing → indexed. */
    upload: (filename: string) => {
      const id = `d-${Math.floor(Math.random() * 900 + 100)}`;
      return ok({ id, filename });
    },
  },
  workOrders: {
    // Orders raised during this session are real records in an in-memory store:
    // they appear in the list and resolve on their own detail route. The
    // previous implementation minted an id and dropped it, so "Create work
    // order" looked like it worked and left nothing behind.
    list: () => ok([...createdWorkOrders, ...WORK_ORDERS]),
    get: (id: string) => ok([...createdWorkOrders, ...WORK_ORDERS].find((w) => w.id === id) ?? null),
    create: (input: { title: string; equipment_id: string; priority: string; assignee: string }) => {
      const id = `WO-${8900 + createdWorkOrders.length + 1}`;
      const record: WorkOrder = {
        id,
        equipment_id: input.equipment_id,
        title: input.title,
        priority: (["low", "medium", "high", "urgent"].includes(input.priority)
          ? input.priority
          : "high") as WorkOrder["priority"],
        status: "open",
        assignee: input.assignee,
        evidence: [],
        recommended_action: input.title,
      };
      createdWorkOrders.unshift(record);
      return ok(record);
    },
  },
  approvals: {
    list: () => ok(APPROVALS),
    pending: () => ok(APPROVALS.filter((a) => a.status === "pending")),
    decide: (id: string, decision: "approved" | "rejected") => {
      const found = APPROVALS.find((a) => a.id === id);
      if (found) found.status = decision;
      return ok(found ?? null);
    },
  },
  graph: { get: () => ok({ nodes: GRAPH_NODES, edges: GRAPH_EDGES }) },
  history: {
    list: () => ok([...simHistory, ...HISTORY]),
    rules: () => ok(LEARNED_RULES),
    /**
     * Promote a real simulation milestone into session history. Called by
     * lib/sim/store.ts as engine events arrive; non-milestones are ignored.
     */
    record: (ev: SimEvent) => {
      recordSimMilestone(ev);
    },
  },
  /**
   * Builder-authored topology saved this session. `revision()` bumps on every
   * save so cached consumers (the Knowledge Graph) can invalidate.
   */
  customPlants: {
    list: () => ok([...savedCustomPlants.values()]),
    save: (plant: PlantDef) => {
      savedCustomPlants.set(plant.id, plant);
      customPlantRevision += 1;
      return ok(plant);
    },
    revision: () => customPlantRevision,
  },
  artifacts: { list: () => ok(ARTIFACTS) },
  workspace: {
    sessions: () => ok(SESSIONS),
    demoTask: () => ok(C3_TASK),
  },
  insights: { list: () => ok(INSIGHTS) },
  jobs: {
    list: () => ok(JOBS),
    get: (id: string) => ok(JOBS.find((j) => j.id === id) ?? null),
  },
  tools: { list: () => ok(TOOLS) },
  workflows: { list: () => ok(WORKFLOWS) },
  search: { query: (q: string) => ok(searchMock(q)) },
  analytics: { summary: () => ok(ANALYTICS_SUMMARY) },
  admin: {
    users: () => ok(USERS),
    models: () => ok(MODELS),
    posture: () => ok(POSTURE),
    audit: () => ok(AUDIT),
  },
};

/** Role → nav visibility. Hides (not disables) unauthorized sections. */
export const ROLE_NAV: Record<ConsoleRole, string[]> = {
  operator: ["home", "workspace", "equipment", "work-orders", "simulation"],
  engineer: ["home", "workspace", "documents", "knowledge", "history", "equipment", "work-orders", "insights", "simulation"],
  maintenance: ["home", "workspace", "equipment", "work-orders", "documents", "simulation"],
  safety: ["home", "documents", "history", "approvals", "insights", "simulation"],
  manager: ["home", "workspace", "approvals", "insights", "equipment", "work-orders", "simulation"],
  admin: ["home", "workspace", "documents", "knowledge", "history", "equipment", "work-orders", "insights", "approvals", "admin", "simulation"],
};
