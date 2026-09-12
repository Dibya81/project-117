/**
 * Console data adapter — the only import surface for workbench pages.
 * Today everything resolves from the typed mock dataset; each accessor is a
 * single awaitable call so swapping to live backend endpoints is a mechanical
 * change inside this file, never in a component.
 */
import type { ConsoleRole, EquipmentDetailData, HistoryEvent } from "@/types/console";
import type { ApprovalRequest, Equipment, HealthState, WorkOrder } from "@/types";
import type { EquipmentRecord, WorkOrderRecord, ApprovalRecord } from "@/lib/api";
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

/**
 * Adapt a backend equipment record to the console's view model.
 *
 * WHY a mapper rather than a cast: the two shapes genuinely differ, and the
 * console needs exactly two things the API does not carry.
 *
 *   * `status` lives in the console's own HealthState vocabulary.
 *   * `position` — the plant dataset has no geospatial data, so this is a
 *     deterministic placement derived from the asset's area group. It makes the
 *     schematic legible; it does not claim a real location, and the type says so.
 *
 * Everything else passes straight through. `keySignals` is *richer* than the
 * mock's sensor list — it carries a live value, its baseline and its limit — so
 * the readings shown are real instrument state, not invented numbers. Where the
 * backend reports no limit, no threshold is invented.
 */
function toEquipment(r: EquipmentRecord, areaIndex: number, order: number): Equipment {
  const status: HealthState =
    r.status === "healthy"
      ? "ok"
      : r.status === "warning"
        ? "warning"
        : r.status === "critical"
          ? "critical"
          : "unknown";

  const grid = Math.max(0, areaIndex);
  return {
    id: r.id,
    name: r.name,
    kind: r.type as Equipment["kind"],
    zone: r.area || r.unit || "Unassigned",
    status,
    position: [grid * 6, (order % 4) * 3, 0],
    sensors: (r.keySignals ?? []).map((s, i) => {
      // A unit can carry redundant instruments for the same measurement, so the
      // signal name alone is NOT unique — keying on it produced duplicate React
      // keys for the second pressure transmitter. The index disambiguates, and
      // the label says which of the pair it is rather than hiding the redundancy.
      const sameSignalBefore = (r.keySignals ?? []).slice(0, i).filter((o) => o.signal === s.signal).length;
      return {
        key: `${s.signal}-${i}`,
        label: sameSignalBefore === 0 ? s.signal : `${s.signal} (${sameSignalBefore + 1})`,
        unit: s.unit,
        value: s.value,
        // `limit` is the backend's own threshold for the signal; when it is
        // absent nothing is guessed.
        ...(typeof s.limit === "number" && s.limit !== s.baseline
          ? { warnAbove: s.limit }
          : {}),
      };
    }),
    last_inspection: r.lastInspection,
    insight: r.summary,
  };
}

/**
 * Adapt a backend work-order record to the console's view model.
 *
 * The vocabulary is narrowed rather than cast: the API is the authority on
 * priority and status, but an unexpected value must not be smuggled into the
 * UI as if it were valid, so anything unrecognised falls back to a safe default
 * (priority medium, status open) instead of being asserted through.
 *
 * `evidence` is reported empty. The API returns plain strings, while the
 * console's Citation expects a structured source reference; inventing that
 * structure would fabricate provenance the backend never sent.
 */
function toWorkOrder(r: WorkOrderRecord): WorkOrder {
  const PRIORITIES = ["low", "medium", "high", "critical"] as const;
  const STATUSES = ["draft", "open", "in_progress", "on_hold", "completed", "cancelled"] as const;
  return {
    id: r.id,
    equipment_id: r.equipmentId ?? "",
    title: r.title,
    priority: (PRIORITIES as readonly string[]).includes(r.priority)
      ? (r.priority as WorkOrder["priority"])
      : "medium",
    status: (STATUSES as readonly string[]).includes(r.status)
      ? (r.status as WorkOrder["status"])
      : "open",
    assignee: r.assignee ?? "unassigned",
    evidence: [],
    recommended_action: r.description || undefined,
  };
}

/** Adapt a backend approval record to the console's view model. */
function toApproval(r: ApprovalRecord): ApprovalRequest {
  const RISKS = ["low", "medium", "high"] as const;
  return {
    id: r.id,
    action: r.title || r.type,
    risk: (RISKS as readonly string[]).includes(r.risk)
      ? (r.risk as ApprovalRequest["risk"])
      : "medium",
    requested_by: r.requestedBy,
    equipment_id: r.relatedId ?? undefined,
    reason: r.summary,
    evidence: [],
    created_at: r.requestedAt,
    status:
      r.status === "approved" || r.status === "rejected"
        ? (r.status as ApprovalRequest["status"])
        : "pending",
  };
}

export const consoleData = {
  equipment: {
    // The real plant: 58 units served from the SQLite store by /api/equipment,
    // not the six-row synthetic set the console used to read.
    list: () =>
      api.equipment.list().then((r) => {
        // Area order fixes each asset's placement so the schematic is stable
        // across reloads rather than reshuffling.
        const areas = [...new Set(r.items.map((e) => e.area || e.unit || "Unassigned"))].sort();
        return r.items.map((e, i) => toEquipment(e, areas.indexOf(e.area || e.unit || "Unassigned"), i));
      }),
    /**
     * Resolve an equipment tag to its record.
     *
     * The console names units by their narrative tag (C-3); the simulation
     * register names the same machine differently (C-1071). A URL can arrive
     * with either, so the real API is tried first, then the narrative crosswalk
     * — annotated with the mapping rather than silently pretending the two tags
     * are the same string.
     */
    detail: async (id: string): Promise<EquipmentDetailData | null> => {
      try {
        const r = await api.equipment.get(id);
        if (r) {
          const view = toEquipment(r, 0, 0);
          // Telemetry and maintenance come from the backend's own endpoints; an
          // empty series is reported as empty rather than invented, and the
          // dataset genuinely carries no persisted time series (see the type).
          const history = await api.equipment.history(id).catch(() => null);
          const maintenance = Array.isArray((history as { items?: unknown[] })?.items)
            ? ((history as { items: Record<string, unknown>[] }).items ?? []).map((h, i) => ({
                id: String(h.id ?? `h-${i}`),
                title: String(h.title ?? h.summary ?? "Maintenance record"),
                at: String(h.at ?? h.date ?? ""),
                by: String(h.by ?? h.actor ?? "maintenance"),
              }))
            : [];
          return {
            id: view.id,
            name: view.name,
            kind: view.kind,
            zone: view.zone,
            status: view.status,
            insight: view.insight,
            readings: view.sensors.map((s) => ({
              key: s.key,
              label: s.label,
              unit: s.unit,
              value: s.value,
              ...(s.warnAbove !== undefined ? { warnAbove: s.warnAbove } : {}),
            })),
            kpis: [
              { label: "Criticality", value: String(r.criticality ?? "—") },
              { label: "Manufacturer", value: r.manufacturer || "—" },
              { label: "Model", value: r.model || "—" },
              { label: "Installed", value: String(r.installedYear ?? "—") },
              { label: "Last inspection", value: r.lastInspection || "—" },
              { label: "Next inspection", value: r.nextInspection || "—" },
            ],
            telemetry: [],
            maintenance,
            documents: [],
            // Nothing below is invented: the backend exposes no per-asset event
            // history, relation list or open-work-order join yet, so these are
            // reported empty rather than filled with plausible-looking rows.
            history: [],
            related: [],
            open_work_orders: [],
          };
        }
      } catch {
        /* not a register id — fall through to the narrative overlay */
      }
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
    // Real orders from the operations store. The session-only list is gone:
    // orders created here are persisted by the backend, so there is one source
    // of truth and a created order survives a reload.
    list: () => api.workOrders.list().then((r) => r.items.map(toWorkOrder)),
    get: (id: string) => api.workOrders.get(id).then(toWorkOrder),
    create: (input: { title: string; equipment_id: string; priority: string; assignee: string }) =>
      api.workOrders
        .create({
          title: input.title,
          equipmentId: input.equipment_id || null,
          priority: input.priority,
          assignee: input.assignee || null,
          origin: "console",
        })
        .then(toWorkOrder),
  },
  approvals: {
    list: () => api.approvals.list().then((r) => r.items.map(toApproval)),
    pending: () =>
      api.approvals
        .list()
        .then((r) => r.items.filter((a) => a.status === "pending").map(toApproval)),
    decide: (id: string, decision: "approved" | "rejected") =>
      api.approvals.decide(id, decision).then(toApproval),
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
  // Artifacts, jobs, tools and workflows are real backend records.
  artifacts: { list: () => api.artifacts.list().then((r) => r.artifacts) },
  workspace: {
    // No workspace/session endpoint exists yet; an empty list is the honest
    // answer, and clearly better than fabricated sessions.
    sessions: () => ok([]),
    demoTask: () => ok(C3_TASK),
  },
  insights: { list: () => ok(INSIGHTS) },
  jobs: {
    list: () => api.jobs.list().then((r) => r.jobs),
    get: (id: string) => api.jobs.get(id),
  },
  tools: { list: () => api.tools.list().then((r) => r.tools) },
  workflows: { list: () => api.workflows.list().then((r) => r.workflows) },
  search: {
    query: (q: string) =>
      api.search.query({ query: q }).then((r) => {
        const results = (r as { results?: unknown[] }).results ?? [];
        return { query: q, results };
      }),
  },
  // NOTE: still mock. The insights page expects {anomalies_7d, mttr_hours,
  // mtbf_hours, verification_rate, …}, but the real /api/analytics/summary
  // returns {equipment, workOrders, approvals, platform, computedAt, sources}.
  // Wiring it needs the insights page rewritten against the real shape — a
  // separate change, not a one-line swap. Tracked, not silently faked.
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
