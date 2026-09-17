/**
 * Console data adapter — the only import surface for workbench pages.
 * Today everything resolves from the typed mock dataset; each accessor is a
 * single awaitable call so swapping to live backend endpoints is a mechanical
 * change inside this file, never in a component.
 */
import type {
  AdminUser,
  Alert,
  AuditEvent,
  ConsoleRole,
  EquipmentDetailData,
  HistoryEvent,
  LearnedRule,
  ModelStatus,
  NotificationItem,
  SystemPosture,
} from "@/types/console";
import type { ApprovalRequest, Equipment, HealthState, WorkOrder } from "@/types";
import type { EquipmentRecord, WorkOrderRecord, ApprovalRecord } from "@/lib/api";
import type { PlantDef, SimEvent } from "@/lib/sim/types";
// Only the mock symbols still in use are imported. Every other name here was
// dead: `AGENTS`, `EQUIPMENT`, `WORK_ORDERS`, `JOBS`, `TOOLS`, `WORKFLOWS`,
// `searchMock` and friends had been replaced by real API calls but their
// imports were left behind, which made the module look far more mock-backed
// than it is. The three below are the genuine remainder.
import { api } from "@/lib/api";
import type {
  EquipmentRequirementsRecord,
  InventoryStatusRecord,
  LimitationRecord,
  MaterialDetailEnvelope,
  MaterialForecastRecord,
  MaterialInsightRecord,
  MaterialRecord,
  MaterialRequirementRecord,
  MaterialsDashboardRecord,
  MaterialsGraphRecord,
  PriceHistoryRecord,
  ProductionSeriesRecord,
  RecommendationRecord,
} from "@/lib/api";

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
function toEquipment(r: EquipmentRecord): Equipment {
  const status: HealthState =
    r.status === "healthy"
      ? "ok"
      : r.status === "warning"
        ? "warning"
        : r.status === "critical"
          ? "critical"
          : "unknown";

  // The plan coordinate from the dataset, not a synthesised grid slot.
  //
  // This previously read `[areaIndex * 6, (order % 4) * 3, 0]`, whose third
  // component is always zero — and PlantMap draws the second axis from index 2.
  // Every asset therefore collapsed onto one horizontal line with overlapping
  // labels, in a panel two-thirds empty. The dataset has always carried x and
  // y inside each area rectangle; the API just was not serving them.
  //
  // Convention: plan x -> index 0 (screen x), plan y -> index 2 (depth), with
  // elevation at index 1, which is what the consumers read.
  const x = Number.isFinite(r.x) ? r.x : 0;
  const y = Number.isFinite(r.y) ? r.y : 0;
  return {
    id: r.id,
    name: r.name,
    kind: r.type as Equipment["kind"],
    zone: r.area || r.unit || "Unassigned",
    status,
    position: [x, 0, y],
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
    // The real plant tag (`P-1001`), which is what a QR label encodes and what
    // the backend resolves. It is packed last in the API's `tags` array; the id
    // (`e-P-1001`) is a different string, so the label must carry this one.
    ...(r.tags?.length ? { tag: r.tags[r.tags.length - 1] } : {}),
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

/**
 * Map one audit row onto an operational-history entry.
 *
 * The audit log is the real, durable record of everything the platform did, so
 * history is derived from it rather than from a curated mock timeline. The
 * action prefix decides the category; anything unrecognised is reported as a
 * recommendation rather than being forced into a category it does not belong to.
 */
/**
 * True for the audit middleware's own request log.
 *
 * Every inbound HTTP request is audited as `http.<method>`. Those rows are a
 * transport record, useful in the Admin audit ledger and useless as plant
 * history — they were 76% of the operational-history feed, so the page titled
 * "organizational memory, not an activity log" was rendering exactly that, one
 * `/api/simulation/plants/refinery/reset` at a time.
 */
/** The action namespace the API middleware writes for every request. */
const TRANSPORT_ACTION_PREFIX = "http.";

function isTransportAudit(action: string): boolean {
  return action.startsWith(TRANSPORT_ACTION_PREFIX);
}

/**
 * Map an audit action to a memory stage, without guessing.
 *
 * This previously fell through to `recommendation` for anything unrecognised,
 * and the history page renders `recommendation` as "Verified" — so a raw HTTP
 * request carried a green verification badge. Only the verification domain maps
 * to `recommendation` now; anything real but unstaged is `event`.
 */
function historyKind(action: string): HistoryEvent["kind"] {
  if (action.startsWith("approval.")) return "approval";
  if (action.startsWith("work_order.")) return "work_order";
  if (action.startsWith("incident.") || action.startsWith("alarm.") || action.startsWith("fault.")) {
    return "anomaly";
  }
  if (action.startsWith("verification.") || action.startsWith("artifact.")) return "recommendation";
  if (action.startsWith("simulation.") || action.startsWith("plant.")) return "maintenance";
  return "event";
}

function toHistoryEvent(e: Record<string, unknown>): HistoryEvent {
  const action = String(e.action ?? "");
  const kind = historyKind(action);
  return {
    id: String(e.id ?? ""),
    kind,
    title: action || "audit event",
    detail: [e.resource_type, e.resource_id, e.outcome].filter(Boolean).join(" · "),
    actor: String(e.user ?? "system"),
    equipment_id: typeof e.resource_id === "string" && e.resource_id.includes("-") ? e.resource_id : undefined,
    at: String(e.timestamp ?? ""),
  };
}

export const consoleData = {
  /**
   * The plant the console is showing. The default is the refinery, which is
   * what every data surface reads; if the list is unavailable the name is null
   * and callers say "unknown" rather than falling back to an invented label.
   */
  plant: {
    identity: async (): Promise<{ id: string; name: string } | null> => {
      const r = await api.plants.list().catch(() => null);
      const first = r?.plants?.[0];
      return first ? { id: first.id, name: first.name } : null;
    },
  },
  equipment: {
    // The real plant: 58 units served from the SQLite store by /api/equipment,
    // not the six-row synthetic set the console used to read.
    list: () => api.equipment.list().then((r) => r.items.map((e) => toEquipment(e))),
    /**
     * The asset's printable QR label as inline-ready SVG.
     *
     * One source of truth: the backend renders it and encodes the namespaced
     * `P117:EQUIP:<tag>` payload, so the console ships no QR library and cannot
     * drift from what the scanner resolves. A failed render resolves to `null`
     * so the label panel can say so instead of showing a broken image.
     */
    qrSvg: (id: string): Promise<string | null> => api.equipment.qrSvg(id).catch(() => null),
    /**
     * Every asset's label for the printable sheet, in one call.
     *
     * The symbols are fetched in parallel; the backend caches each tag's SVG
     * and the read cache de-duplicates a re-mount. One failed symbol is reported
     * as `null` for that row only — the rest of the sheet still prints.
     *
     * `tag` and `zone` come from the raw record, not the view model: the label
     * must print the real plant tag (`P-1001`), not the asset id (`e-P-1001`).
     */
    labelSheet: async (): Promise<
      { id: string; tag: string; name: string; zone: string; svg: string | null }[]
    > => {
      const { items } = await api.equipment.list();
      return Promise.all(
        items.map(async (r) => ({
          id: r.id,
          tag: r.tags?.[r.tags.length - 1] ?? r.id,
          name: r.name,
          zone: r.area || r.unit || "",
          svg: await api.equipment.qrSvg(r.id).catch(() => null),
        })),
      );
    },
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
        const envelope = await api.equipment.get(id);
        // Unwrap the envelope. Passing it straight to toEquipment meant `r.name`,
        // `r.model` and `r.keySignals` were all undefined, so the detail page
        // rendered "UNKNOWN" and "—" for a real, fully-populated asset.
        const r = envelope.equipment;
        if (r) {
          const view = toEquipment(r);
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
            ...(view.tag ? { tag: view.tag } : {}),
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
        /* Not a real register id. */
      }
      // No fallback to a narrative detail record. The previous version resolved
      // unknown ids — including the fictional tags from the retired demo data —
      // to a hand-written detail page, so /console/equipment/C-3 rendered a
      // convincing machine that does not exist in the plant dataset. A missing
      // asset now reports as missing.
      return null;
    },
  },
  // No alerting or notification endpoint exists. An empty list is the honest
  // answer — a fabricated alert feed would be worse than none, because an
  // operator cannot tell a real alarm from a decorative one. The list is typed
  // explicitly: an untyped `[]` narrows to never[] and breaks every consumer
  // that reads a field off an alert.
  alerts: {
    list: (): Promise<Alert[]> => ok([]),
    active: (): Promise<Alert[]> => ok([]),
  },
  notifications: { list: (): Promise<NotificationItem[]> => ok([]) },
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
    // The wire carries {name, description, capabilities, requires_rag, tools}.
    // `kind` is the registry name (they are the same string) and `status` is
    // reported idle because a registry listing genuinely does not know whether
    // an agent is mid-run — claiming otherwise is the fakery this console exists
    // to avoid.
    list: () =>
      api.agents.list().then((r) =>
        r.agents.map((a) => ({ ...a, kind: a.name as typeof a.kind, status: "idle" as const })),
      ),
  },
  // The real library: whatever the backend has actually stored and indexed.
  //
  // This used to join seven hand-written register rows with a JSON artifact
  // generated from data/knowledge/**, which no longer exists — so the page
  // listed documents that were not in the plant and omitted the ones that were.
  documents: {
    list: () => api.documents.list().then((r) => r.documents),
    get: (id: string) => api.documents.get(id),
    stats: async () => {
      const rows = await api.documents.list().then((r) => r.documents);
      const chunks = rows.reduce((sum, d) => {
        const ing = (d.metadata as { ingestion?: { chunk_count?: number } })?.ingestion;
        return sum + (ing?.chunk_count ?? 0);
      }, 0);
      return { total: rows.length, indexed: rows.filter((d) => d.status === "indexed").length, chunks };
    },
    /** Real multipart upload; the row is registered by the server. */
    upload: (file: File) => api.documents.upload(file),
    reindex: (id: string) => api.documents.reindex(id),
    remove: (id: string) => api.documents.delete(id),
  },
  workOrders: {
    // Real orders from the operations store. The session-only list is gone:
    // orders created here are persisted by the backend, so there is one source
    // of truth and a created order survives a reload.
    list: () => api.workOrders.list().then((r) => r.items.map(toWorkOrder)),
    // `GET /api/work-orders/{id}` returns `{ workOrder, equipment, … }`, not a
    // bare order. Mapping the envelope as if it were the record produced an
    // object with every field `undefined` — the detail page showed no title,
    // "PRIORITY MEDIUM" and "ASSIGNEE unassigned" for a real high-priority order.
    get: (id: string) => api.workOrders.get(id).then((r) => toWorkOrder(r.workOrder)),
    create: (input: { title: string; equipment_id: string; priority: string; assignee: string }) =>
      api.workOrders
        .create({
          title: input.title,
          equipmentId: input.equipment_id || null,
          priority: input.priority,
          assignee: input.assignee || null,
          origin: "console",
        })
        // POST returns the same envelope as GET — unwrap it, or a newly created
        // order is a record with every field `undefined`.
        .then((r) => toWorkOrder(r.workOrder)),
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
  // The knowledge graph builds itself from the plant definition and the console
  // records (lib/knowledge/plant.ts); this adapter's graph section was a mock
  // leftover that nothing rendered. Empty rather than a second, stale topology.
  /**
   * Industrial materials, inventory and business intelligence.
   *
   * Deliberately thin. Every number the backend computed is passed through
   * unchanged — no re-derivation, no unit conversion, no rounding — because a
   * second implementation of "available stock" in the browser is exactly how a
   * console comes to disagree with the engine it is reporting on. The adapter
   * exists only so pages have one import surface, and so a limitation the
   * backend reported survives the trip to the component that must display it.
   */
  materials: {
    /** Materials Overview: dashboard counters, raw-material cover, critical list. */
    overview: async (): Promise<{
      dashboard: MaterialsDashboardRecord;
      insights: MaterialInsightRecord[];
      insightCounts: { critical: number; warning: number; info: number };
      dataStatus: string;
    } | null> => {
      try {
        const r = await api.materials.intelligence();
        return {
          dashboard: r.dashboard,
          insights: r.intelligence.insights,
          insightCounts: r.intelligence.counts,
          dataStatus: r.data_status,
        };
      } catch {
        // The materials layer is additive. A deployment without it must degrade
        // to an explicit empty state, not to invented figures.
        return null;
      }
    },
    list: (params: { materialClass?: string; search?: string; limit?: number; offset?: number } = {}) =>
      api.materials.list(params).then((r) => ({ items: r.items, total: r.total ?? r.count })),
    detail: (id: string): Promise<MaterialDetailEnvelope> => api.materials.get(id),
    inventory: (params: { materialClass?: string; search?: string; limit?: number } = {}) =>
      api.materials.inventory(params),
    movements: (params: { materialId?: string; movementType?: string; limit?: number } = {}) =>
      api.materials.movements(params).then((r) => r.items),
    production: (params: { period?: string; productId?: string } = {}): Promise<ProductionSeriesRecord> =>
      api.materials.production(params),
    priceHistory: (itemId: string, windowDays = 30): Promise<PriceHistoryRecord> =>
      api.materials.priceHistory(itemId, { windowDays }),
    suppliers: () => api.materials.suppliers().then((r) => r.items),
    financialEvents: (limit = 50) => api.materials.financialEvents({ limit }).then((r) => r.items),
    /** Spares an asset requires, with the live inventory position for each. */
    requirementsFor: (equipmentId: string, failureMode?: string): Promise<EquipmentRequirementsRecord> =>
      api.materials.equipmentRequirements({ equipmentId, failureMode }),
    /** Required vs available vs safety stock, with the backend's coverage verdict. */
    maintenanceRequirement: (equipmentId: string, failureMode?: string): Promise<MaterialRequirementRecord> =>
      api.materials.maintenanceRequirements(equipmentId, { failureMode }),
    /** The composed recommendation. Read-only: it proposes, it does not order. */
    recommendation: (equipmentId: string, failureMode?: string): Promise<RecommendationRecord> =>
      api.materials.recommendation(equipmentId, failureMode),
    /** One material's subgraph — scoped, not the whole industrial graph. */
    graphFor: (materialId: string): Promise<MaterialsGraphRecord> => api.materials.graphFor(materialId),
    graph: (): Promise<MaterialsGraphRecord> => api.materials.graph(),
    forecast: async (materialId: string): Promise<MaterialForecastRecord | null> => {
      try {
        const detail = await api.materials.get(materialId);
        return detail.forecast;
      } catch {
        return null;
      }
    },
  },

  graph: { get: () => ok({ nodes: [], edges: [] }) },
  history: {
    /**
     * Real audit rows, newest first, in front of the milestones this session
     * witnessed. The audit log is the durable record; the session list carries
     * simulation events that have not been persisted yet.
     *
     * The request log is filtered out: `http.*` rows are the middleware
     * recording that a URL was called, which is not something that happened to
     * the plant. Keeping them meant the newest 200 audit rows were 76%
     * transport noise, and they buried the domain events they were mixed with.
     */
    /**
     * @param limit How many audit rows to read. Defaults to what a summary
     *   surface needs. The endpoint returns every row type — the request log is
     *   roughly three quarters of them and is discarded just below — so asking
     *   for 500 cost 201 KB to display five lines on the home page and a few
     *   dozen on the knowledge graph. The full-history page asks for the larger
     *   window it actually renders.
     */
    list: async (limit = 120) => {
      const audited = await api.audit
        // The request log is excluded AT THE SOURCE, not here. Filtering after
        // the fact meant `limit` counted rows that were then thrown away: the
        // newest 120 audit rows are *entirely* `http.*` transport entries, so the
        // register filtered down to nothing and the page reported "no memory yet"
        // while the plant was running. Excluding server-side makes `limit` mean
        // "this many rows the caller can use", and removes ~three quarters of the
        // payload at the same time.
        .query({ limit, excludeActionPrefix: TRANSPORT_ACTION_PREFIX })
        .then((r) =>
          (r.events ?? [])
            .filter((e) => !isTransportAudit(String(e.action ?? "")))
            .map(toHistoryEvent),
        )
        .catch(() => [] as HistoryEvent[]);
      return [...simHistory, ...audited];
    },
    // No learned-rule store exists yet; an empty list beats invented rules.
    rules: (): Promise<LearnedRule[]> => ok([]),
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
  },
  // The insights page reads analytics directly. The mock series that used to
  // live behind insights.list() is gone: its "AI observation" cards and
  // confidence percentages were hand-written constants presented as findings.
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
  // Real analytics. Every figure is computed from the plant dataset, the
  // operations store, or measured by the running process — see
  // backend/api/src/routes/analytics.py. Series are empty until trend history
  // is persisted, and the page says so rather than drawing invented points.
  analytics: {
    summary: () => api.analytics.summary(),
    trends: (series?: string[]) => api.analytics.trends(series),
  },
  admin: {
    // No identity store exists yet — an empty roster beats inventing users.
    users: (): Promise<AdminUser[]> => ok([]),
    // Real model roles from the gateway. `status` reflects whether the role is
    // CONFIGURED, which is what the endpoint actually knows; it does not claim
    // a model is loaded, because nothing here reports load state.
    models: () =>
      api.models.status().then((r) => {
        const roles = (r as { roles?: Record<string, string | null> }).roles ?? {};
        return Object.entries(roles).map<ModelStatus>(([role, model]) => ({
          role,
          model: model ?? "—",
          status: model ? "available" : "unavailable",
        }));
      }),
    // Real posture. Every field is a measurement the backend actually makes:
    // /health reports model-backend reachability, sandbox configuration, the
    // egress policy, disk usage, and the egress guard's own record of every
    // outbound decision. Nothing here is assumed, and a value the backend
    // cannot measure reads as 0 rather than as a plausible guess.
    posture: async (): Promise<SystemPosture> => {
      const health = await api.health();
      const network = health.network;
      const llm = health.llm;
      return {
        // "local" means the on-prem backend answered. A configured-but-silent
        // backend is degraded; no backend at all is offline. These are three
        // genuinely different states and the operator sees which one they are in.
        model_gateway: llm?.running ? "local" : llm?.backend ? "degraded" : "offline",
        sandbox: health.services?.opensandbox?.configured ? "isolated" : "unavailable",
        egress: health.egress === "allowlist" ? "allowlisted" : "denied",
        // Counted by the egress guard transport on the only path outbound HTTP
        // can take. It deliberately excludes loopback, so a busy conversation
        // with the local model server does not read as external traffic.
        external_calls_24h: network?.external_allowed ?? 0,
        egress_blocked_24h: network?.external_blocked ?? 0,
        database: health.database === "ok" ? "ok" : "error",
        storage_used_gb: health.storage?.used_gb ?? 0,
        storage_total_gb: health.storage?.total_gb ?? 0,
        version: health.version ?? "",
      };
    },
    // Real audit rows: the durable record of everything the platform did.
    audit: () =>
      api.audit
        .query({ limit: 200 })
        .then((r) =>
          (r.events ?? []).map<AuditEvent>((e) => ({
            id: String(e.id ?? ""),
            at: String(e.timestamp ?? ""),
            actor: String(e.user ?? "system"),
            action: String(e.action ?? ""),
            // Outcome, resource and error are the columns that make this an
            // audit record rather than a list of verbs.
            ...(e.resource_type ? { resource_type: String(e.resource_type) } : {}),
            ...(e.resource_id ? { resource_id: String(e.resource_id) } : {}),
            ...(e.outcome ? { outcome: String(e.outcome) } : {}),
            ...(e.agent ? { agent: String(e.agent) } : {}),
            ...(e.tool ? { tool: String(e.tool) } : {}),
            ...(e.model ? { model: String(e.model) } : {}),
            ...(e.approval ? { approval: String(e.approval) } : {}),
            ...(e.error ? { error: String(e.error) } : {}),
          })),
        ),
  },
};

/** Role → nav visibility. Hides (not disables) unauthorized sections. */
/**
 * Which navigation ids each role may see.
 *
 * The materials layer is additive and role-appropriate rather than universal: an
 * operator needs the spares shelf and the overview, a safety officer needs the
 * register and the price movement that signals a supply problem, and everyone
 * with plant responsibility needs the materials register itself.
 *
 * The security pair (`sovereignty`, `confidentiality`) is the exception: it is
 * present for every role. Hiding the posture from the people who run the plant
 * meant nobody except an admin could see whether egress was being refused or
 * whether the sandbox was actually up — which is the one reading a security
 * surface exists to give. The pages themselves are read-only measurements, so
 * there is no privileged action to withhold here.
 */
export const ROLE_NAV: Record<ConsoleRole, string[]> = {
  operator: ["home", "workspace", "equipment", "work-orders", "simulation", "sovereignty", "confidentiality", "mat-overview", "mat-spares"],
  engineer: [
    "home", "workspace", "documents", "knowledge", "history", "equipment", "work-orders", "insights", "simulation", "sovereignty", "confidentiality",
    "mat-overview", "mat-materials", "mat-inventory", "mat-production", "mat-prices", "mat-spares", "mat-suppliers",
  ],
  maintenance: ["home", "workspace", "equipment", "work-orders", "documents", "simulation", "sovereignty", "confidentiality", "mat-overview", "mat-spares", "mat-inventory"],
  safety: ["home", "documents", "history", "approvals", "insights", "simulation", "sovereignty", "confidentiality", "mat-overview", "mat-prices", "mat-suppliers"],
  manager: [
    "home", "workspace", "approvals", "insights", "equipment", "work-orders", "simulation", "sovereignty", "confidentiality",
    "mat-overview", "mat-inventory", "mat-production", "mat-prices", "mat-suppliers",
  ],
  admin: [
    "home", "workspace", "documents", "knowledge", "history", "equipment", "work-orders",
    "insights", "approvals", "admin", "sovereignty", "confidentiality", "simulation",
    "mat-overview", "mat-materials", "mat-inventory", "mat-production", "mat-prices", "mat-spares", "mat-suppliers",
  ],
};
