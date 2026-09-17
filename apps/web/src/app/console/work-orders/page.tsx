"use client";

/**
 * Work Orders — Kanban board, one column per real status.
 * ?new=1 (from the command palette) opens the create modal directly.
 *
 * ------------------------------------------------ persistence contract (read me)
 *
 * Dragging a card between columns is a REAL status change, not a local-only
 * move. The chain is:
 *
 *   drop → `api.workOrders.update(id, { status })`   (PATCH /api/work-orders/{id})
 *        → `consoleData.workOrders.list()`           (re-read the store)
 *
 * The write goes to the operations SQLite store, which validates the move
 * against `WORK_ORDER_TRANSITIONS` and audits it as `work_order.updated`. Two
 * consequences the UI is explicit about rather than hiding:
 *
 *   1. The lifecycle is enforced by the server, so the board fetches the
 *      backend's own map from `GET /api/work-orders/meta/transitions` and marks
 *      a column "blocked" while a card that cannot legally go there is dragged
 *      over it. If that fetch fails the board allows the gesture and lets the
 *      server adjudicate instead of guessing the rules.
 *   2. The move is optimistic (the card lands immediately) but reverted with the
 *      server's own message if the write is rejected, so the board never shows a
 *      status the store does not have. Cards in a terminal status (`completed`,
 *      `cancelled`) are not draggable at all, because no transition exists out
 *      of them.
 *
 * WHY the page calls `api.workOrders.update` directly instead of going through
 * `consoleData`: the adapter exposes `list`, `get` and `create` only — it has no
 * status mutation, and this file is not allowed to change the adapter. Reads
 * still go through `consoleData`; only this one real backend mutation is called
 * directly.
 */
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button, Panel, SkeletonRows, Tag } from "@/components/ui/primitives";
import { Modal } from "@/components/ui/overlays";
import { Icon } from "@/components/ui/Icon";
import { Lucide } from "@/components/ui/LucideIcon";
import {
  KanbanColumn,
  WorkOrderCard,
  markDragged,
  type ColumnDef,
} from "@/components/console/WorkOrderKanban";
import { consoleData } from "@/lib/data/console";
import { ApiError, api } from "@/lib/api";
import { AnimatePresence } from "framer-motion";
import type { Equipment, WorkOrder } from "@/types";

/**
 * The board's columns are the `WorkOrder["status"]` union verbatim — the same
 * six states the operations store and `WORK_ORDER_TRANSITIONS` use. `terminal`
 * mirrors the two statuses the lifecycle gives no way out of.
 */
const COLUMNS: ColumnDef[] = [
  { id: "draft", label: "Draft", terminal: false },
  { id: "open", label: "Open", terminal: false },
  { id: "in_progress", label: "In progress", terminal: false },
  { id: "on_hold", label: "Pending approval", terminal: false },
  { id: "completed", label: "Done", terminal: true },
  { id: "cancelled", label: "Cancelled", terminal: true },
];

const LABEL: Record<WorkOrder["status"], string> = COLUMNS.reduce(
  (acc, c) => ({ ...acc, [c.id]: c.label }),
  {} as Record<WorkOrder["status"], string>,
);

/**
 * Unwrap `GET /api/work-orders/meta/transitions`.
 *
 * `api.workOrders.transitions()` is typed `Record<string, unknown>` because the
 * endpoint answers with an envelope (`{transitions, priorities, types}`) rather
 * than the bare map. The envelope is read field by field here instead of being
 * asserted through, so a changed wire shape degrades to "unknown lifecycle"
 * (drag allowed, server adjudicates) rather than to a wrong rule.
 */
function readTransitions(
  raw: Record<string, unknown>,
): Record<string, WorkOrder["status"][]> | null {
  const rawMap = (raw as { transitions?: unknown }).transitions;
  if (!rawMap || typeof rawMap !== "object") return null;
  const out: Record<string, WorkOrder["status"][]> = {};
  for (const [status, next] of Object.entries(rawMap as Record<string, unknown>)) {
    if (Array.isArray(next)) {
      out[status] = next.filter((n): n is WorkOrder["status"] => typeof n === "string");
    }
  }
  return out;
}

function CreateModal({ equipment, onClose, onCreated }: { equipment: Equipment[]; onClose: () => void; onCreated: (id: string) => void }) {
  const [title, setTitle] = useState("");
  const [equipmentId, setEquipmentId] = useState(equipment[0]?.id ?? "");
  const [priority, setPriority] = useState("medium");
  const [assignee, setAssignee] = useState("");

  const submit = async () => {
    if (!title.trim()) return;
    const res = await consoleData.workOrders.create({ title: title.trim(), equipment_id: equipmentId, priority, assignee: assignee || "unassigned" });
    onCreated(res.id);
  };

  return (
    <Modal title="New work order" onClose={onClose}>
      <div className="cs-field">
        <label htmlFor="wo-title">Title</label>
        <input id="wo-title" className="cs-input" placeholder="e.g. Inspect C-3 bearing assembly" value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
      </div>
      <div className="cs-field">
        <label htmlFor="wo-eq">Equipment</label>
        <select id="wo-eq" className="cs-select" value={equipmentId} onChange={(e) => setEquipmentId(e.target.value)}>
          {equipment.map((e) => (
            <option key={e.id} value={e.id}>
              {e.id} — {e.name}
            </option>
          ))}
        </select>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div className="cs-field">
          <label htmlFor="wo-prio">Priority</label>
          <select id="wo-prio" className="cs-select" value={priority} onChange={(e) => setPriority(e.target.value)}>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </div>
        <div className="cs-field">
          <label htmlFor="wo-assignee">Assignee</label>
          <input id="wo-assignee" className="cs-input" placeholder="unassigned" value={assignee} onChange={(e) => setAssignee(e.target.value)} />
        </div>
      </div>
      <p className="cs-dim" style={{ fontSize: 11.5, margin: "2px 0 16px" }}>
        If created by an agent, this work order would pause for approval first — policy-gated actions
        never execute themselves.
      </p>
      <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button variant="primary" onClick={submit} disabled={!title.trim()}>
          <Icon name="plus" size={13} /> Create
        </Button>
      </div>
    </Modal>
  );
}

function WorkOrdersInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [orders, setOrders] = useState<WorkOrder[] | null>(null);
  const [equipment, setEquipment] = useState<Equipment[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [prioFilter, setPrioFilter] = useState("all");
  /**
   * Backend lifecycle map. `null` means "not known" — which is different from a
   * status that maps to an empty list (a terminal state the store will not move
   * out of). Conflating the two is what would let a terminal card be dragged.
   */
  const [transitions, setTransitions] = useState<Record<string, WorkOrder["status"][]> | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const [dropStatus, setDropStatus] = useState<WorkOrder["status"] | null>(null);
  const [dropAllowed, setDropAllowed] = useState(true);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "error" | "info"; text: string } | null>(null);

  const columnRefs = useRef(new Map<WorkOrder["status"], HTMLDivElement>());

  useEffect(() => {
    consoleData.workOrders.list().then(setOrders);
    consoleData.equipment.list().then(setEquipment);
    api.workOrders
      .transitions()
      .then(readTransitions)
      .then(setTransitions)
      .catch(() => setTransitions(null));
  }, []);

  useEffect(() => {
    if (params.get("new") === "1") setCreateOpen(true);
  }, [params]);

  const filtered = useMemo(
    () => (orders ?? []).filter((w) => prioFilter === "all" || w.priority === prioFilter),
    [orders, prioFilter],
  );

  const byStatus = useMemo(() => {
    const map = new Map<WorkOrder["status"], WorkOrder[]>();
    for (const col of COLUMNS) map.set(col.id, []);
    for (const w of filtered) map.get(w.status)?.push(w);
    return map;
  }, [filtered]);

  /** Which column is under this viewport point, if any. */
  const columnAt = useCallback((x: number, y: number): WorkOrder["status"] | null => {
    for (const [status, el] of columnRefs.current) {
      const r = el.getBoundingClientRect();
      if (x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) return status;
    }
    return null;
  }, []);

  /**
   * A move is allowed only when the backend's own map says so. While the map is
   * still unknown (fetch in flight, or it failed) the gesture is permitted and
   * the server is left to reject it — better than blocking a legal move on a
   * guess. Once the map is known, a status with no outgoing transitions is
   * correctly reported as terminal.
   */
  const isAllowed = useCallback(
    (from: WorkOrder["status"], to: WorkOrder["status"]) => {
      if (transitions === null) return true;
      if (from === to) return true;
      return (transitions[from] ?? []).includes(to);
    },
    [transitions],
  );

  const handleDrag = useCallback(
    (order: WorkOrder, point: { x: number; y: number }) => {
      const status = columnAt(point.x, point.y);
      setDropStatus(status);
      if (status) setDropAllowed(isAllowed(order.status, status));
    },
    [columnAt, isAllowed],
  );

  const moveTo = useCallback(async (order: WorkOrder, target: WorkOrder["status"]) => {
    const from = order.status;
    setNotice(null);
    setPendingId(order.id);
    setOrders((prev) => prev?.map((o) => (o.id === order.id ? { ...o, status: target } : o)) ?? prev);
    try {
      await api.workOrders.update(order.id, { status: target });
      /*
       * Re-read from the store rather than trusting the optimistic guess, so the
       * board shows the status the operations store actually holds.
       *
       * WHY a full `list()` and not `consoleData.workOrders.get(id)`:
       * `GET /api/work-orders/{id}` answers with an envelope
       * (`{workOrder, equipment, evidenceDocuments, allowedTransitions, source}`)
       * while `api.workOrders.get` is typed as the bare record and
       * `consoleData.workOrders.get` runs `toWorkOrder` straight over whatever
       * comes back — so it maps the envelope, and every field on the result
       * (`id`, `status`, `priority`, …) is `undefined`. That is a pre-existing
       * adapter bug in files this change does not own; feeding its output back
       * into the board is what silently deleted a card from the DOM (React saw a
       * `WorkOrderCard` with `key === undefined`). `list()` maps correctly, so the
       * refresh goes through it.
       */
      const fresh = await consoleData.workOrders.list();
      setOrders(fresh);
    } catch (err) {
      setOrders((prev) => prev?.map((o) => (o.id === order.id ? { ...o, status: from } : o)) ?? prev);
      const message = err instanceof ApiError ? err.message : (err as Error).message;
      setNotice({ tone: "error", text: `${order.id} stayed in ${LABEL[from]} — ${message}` });
    } finally {
      setPendingId(null);
    }
  }, []);

  const handleDragEnd = useCallback(
    (order: WorkOrder, point: { x: number; y: number } | null) => {
      const target = point ? columnAt(point.x, point.y) : null;
      setDragId(null);
      setDropStatus(null);
      setDropAllowed(true);
      if (!target || target === order.status) return;
      if (!isAllowed(order.status, target)) {
        const allowed = transitions?.[order.status] ?? [];
        setNotice({
          tone: "info",
          text: `${LABEL[order.status]} → ${LABEL[target]} is not an allowed transition. Allowed from ${LABEL[order.status]}: ${
            allowed.length ? allowed.map((a) => LABEL[a]).join(", ") : "none — terminal state"
          }.`,
        });
        return;
      }
      void moveTo(order, target);
    },
    [columnAt, isAllowed, moveTo, transitions],
  );

  const registerColumn = useCallback(
    (status: WorkOrder["status"]) => (el: HTMLDivElement | null) => {
      if (el) columnRefs.current.set(status, el);
      else columnRefs.current.delete(status);
    },
    [],
  );

  const total = filtered.length;

  return (
    <>
      <div className="cs-pagehead">
        <div>
          <span className="cs-pagehead__kicker">Plant</span>
          <h1>Work Orders</h1>
        </div>
        <div className="cs-pagehead__actions" style={{ marginLeft: "auto" }}>
          <select className="cs-select" style={{ width: 140 }} value={prioFilter} onChange={(e) => setPrioFilter(e.target.value)} aria-label="Filter by priority">
            <option value="all">All priorities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <Button variant="primary" onClick={() => setCreateOpen(true)}>
            <Icon name="plus" size={13} /> New work order
          </Button>
        </div>
      </div>

      {notice && (
        <div
          role={notice.tone === "error" ? "alert" : "status"}
          data-kanban-notice={notice.tone}
          className={`mb-3.5 flex items-start gap-2.5 rounded-xl border px-3.5 py-2.5 text-[12px] backdrop-blur-md ${
            notice.tone === "error"
              ? "border-red-300/70 bg-red-50/70 text-red-700"
              : "border-slate-200/80 bg-white/70 text-slate-600"
          }`}
        >
          <Lucide name={notice.tone === "error" ? "alert" : "lock"} size={14} className="mt-0.5 shrink-0" />
          <span className="flex-1">{notice.text}</span>
          <button type="button" onClick={() => setNotice(null)} aria-label="Dismiss" className="text-slate-400 hover:text-slate-600">
            <Lucide name="x" size={13} />
          </button>
        </div>
      )}

      {!orders ? (
        <Panel><SkeletonRows rows={6} label="Loading action system…" /></Panel>
      ) : (
        <>
          <p className="cs-dim mb-3 text-[11px]" data-kanban-hint>
            {total} order{total === 1 ? "" : "s"}
            {prioFilter !== "all" ? ` · ${prioFilter} priority` : ""} · drag a card to a column to change its
            status (persisted to the operations store)
          </p>
          <div className="grid grid-cols-1 items-start gap-3.5 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
            {COLUMNS.map((col) => {
              const items = byStatus.get(col.id) ?? [];
              return (
                <KanbanColumn
                  key={col.id}
                  column={col}
                  count={items.length}
                  registerRef={registerColumn(col.id)}
                  raised={dragId !== null && items.some((w) => w.id === dragId)}
                  dropState={
                    dropStatus !== col.id || dragId === null
                      ? "idle"
                      : dropAllowed
                        ? "allowed"
                        : "blocked"
                  }
                >
                  {/*
                    `mode="popLayout"` is deliberately NOT used. It wraps each
                    child in framer-motion's PopChild, which measures the child
                    through a ref — a function component cannot be given a ref, so
                    React logs "Function components cannot be given refs" on every
                    render. Default (sync) presence still animates enter and exit.
                  */}
                  <AnimatePresence initial={false}>
                    {items.map((w) => (
                      <WorkOrderCard
                        key={w.id}
                        order={w}
                        draggable={!col.terminal}
                        pending={pendingId === w.id}
                        dragging={dragId === w.id}
                        onOpen={() => router.push(`/console/work-orders/${w.id}`)}
                        onDragStart={() => {
                          markDragged();
                          setDragId(w.id);
                          setNotice(null);
                        }}
                        onDrag={(point) => handleDrag(w, point)}
                        onDragEnd={(point) => handleDragEnd(w, point)}
                      />
                    ))}
                  </AnimatePresence>
                </KanbanColumn>
              );
            })}
          </div>
        </>
      )}

      {createOpen && (
        <CreateModal
          equipment={equipment}
          onClose={() => setCreateOpen(false)}
          onCreated={(id) => {
            setCreateOpen(false);
            router.push(`/console/work-orders/${id}`);
          }}
        />
      )}
    </>
  );
}

export default function WorkOrdersPage() {
  return (
    <Suspense fallback={<Panel><SkeletonRows rows={6} /></Panel>}>
      <WorkOrdersInner />
    </Suspense>
  );
}
