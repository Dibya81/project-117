"use client";

/**
 * WorkOrderCard / KanbanColumn — the draggable half of the work-order board.
 *
 * Drag physics
 * ------------
 * Cards are framer-motion `drag` elements with `dragSnapToOrigin`. On drop the
 * page resolves which column the pointer landed on, checks it against the
 * backend's own lifecycle map, and only then calls the real mutation
 * (`PATCH /api/work-orders/{id}` through `api.workOrders.update`). Nothing here
 * moves a card between columns on its own — see WorkOrdersPage for the
 * persistence contract.
 *
 * Urgency colour is derived from `WorkOrder["priority"]`, never invented:
 *   critical → red-600 (deepest red, strongest glow)
 *   high     → neon red #ff2d55
 *   medium   → amber-500
 *   low      → cyan-500
 * The left accent bar carries the same colour, so urgency survives a glance at
 * a dense board while the text stays slate (the glass contract's neutral ink).
 */
import { motion, type PanInfo } from "framer-motion";
import { StatusDot, Tag } from "@/components/ui/primitives";
import { Lucide } from "@/components/ui/LucideIcon";
import { SPRING } from "@/lib/ui/motion";
import type { WorkOrder } from "@/types";

type Priority = WorkOrder["priority"];

/**
 * Drag guard.
 *
 * framer-motion fires `click` after a drag gesture on the same node, which
 * would navigate to the detail page every time an operator dropped a card. The
 * flag lives at module scope rather than in a per-card ref because
 * `WorkOrderCard` is remounted into the destination column the instant the write
 * lands, so a per-instance ref would be a fresh `false` and swallow the flag.
 */
const dragGuard = { current: false };

export function markDragged(): void {
  dragGuard.current = true;
}

export function consumeDragged(): boolean {
  const was = dragGuard.current;
  dragGuard.current = false;
  return was;
}

interface PriorityStyle {
  /** Text + chip colour. */
  chip: string;
  /** Accent bar colour (also used for the glow). */
  accent: string;
  glow: string;
  label: string;
}

export const PRIORITY_STYLE: Record<Priority, PriorityStyle> = {
  critical: {
    chip: "bg-red-600/10 text-red-700 ring-red-600/40",
    accent: "#dc2626",
    glow: "0 0 12px rgba(220,38,38,0.55)",
    label: "Critical",
  },
  high: {
    chip: "bg-[#ff2d55]/10 text-[#c81e46] ring-[#ff2d55]/45",
    accent: "#ff2d55",
    glow: "0 0 12px rgba(255,45,85,0.5)",
    label: "High",
  },
  medium: {
    chip: "bg-amber-500/12 text-amber-700 ring-amber-500/45",
    accent: "#f59e0b",
    glow: "0 0 12px rgba(245,158,11,0.45)",
    label: "Medium",
  },
  low: {
    chip: "bg-cyan-500/12 text-cyan-700 ring-cyan-500/45",
    accent: "#0891b2",
    glow: "0 0 12px rgba(8,145,178,0.45)",
    label: "Low",
  },
};

export interface ColumnDef {
  id: WorkOrder["status"];
  label: string;
  /** True for statuses the backend lifecycle treats as terminal. */
  terminal: boolean;
}

/** Pointer position in client (viewport) coordinates, whatever the input device. */
export function pointerClient(
  event: MouseEvent | TouchEvent | PointerEvent,
  info: PanInfo,
): { x: number; y: number } {
  const e = event as MouseEvent & TouchEvent;
  if (typeof e.clientX === "number") return { x: e.clientX, y: e.clientY };
  const touch = e.changedTouches?.[0] ?? e.touches?.[0];
  if (touch) return { x: touch.clientX, y: touch.clientY };
  // `PanInfo.point` is page-relative: compensate for scroll.
  return { x: info.point.x - window.scrollX, y: info.point.y - window.scrollY };
}

export function WorkOrderCard({
  order,
  draggable,
  pending,
  dragging,
  onOpen,
  onDragStart,
  onDrag,
  onDragEnd,
}: {
  order: WorkOrder;
  draggable: boolean;
  /** A status write for this order is in flight. */
  pending: boolean;
  /**
   * This card is the one currently in flight. It is opaque while it is out of
   * its column so the card it passes over does not read through it.
   */
  dragging: boolean;
  onOpen: () => void;
  onDragStart: () => void;
  onDrag: (point: { x: number; y: number }) => void;
  onDragEnd: (point: { x: number; y: number } | null) => void;
}) {
  const prio = PRIORITY_STYLE[order.priority];
  const isAgent = order.assignee.includes("agent");

  return (
    /**
     * `layout` animates the card's own reflow, and the reflow of its siblings
     * when one leaves or joins a column. A shared `layoutId` is deliberately NOT
     * used: the two columns are separate `AnimatePresence` boundaries, so a
     * layoutId held by an exiting card in one column and a mounting card in
     * another makes framer-motion treat them as one lead/follower pair across
     * trees. The move is therefore a layout reflow plus enter/exit, which stays
     * correct and keeps every card in the DOM.
     */
    <motion.div
      layout
      drag={draggable}
      dragSnapToOrigin
      dragElastic={0.14}
      dragMomentum={false}
      whileDrag={{ scale: 1.03, rotate: 1.1, zIndex: 60, cursor: "grabbing" }}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: pending ? 0.55 : 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.96 }}
      transition={SPRING.glide}
      onDragStart={onDragStart}
      onDrag={(_e, info) => onDrag(pointerClient(_e, info))}
      onDragEnd={(e, info) => onDragEnd(pointerClient(e, info))}
      onClick={(e) => {
        // A drag ends with a click on the same element; only a real press opens.
        if (consumeDragged()) {
          e.preventDefault();
          return;
        }
        onOpen();
      }}
      onKeyDown={(e) => e.key === "Enter" && onOpen()}
      role="button"
      tabIndex={0}
      aria-label={`${order.id}: ${order.title}. Priority ${prio.label}. ${draggable ? "Drag to change status." : "Terminal status."}`}
      data-work-order-card={order.id}
      data-work-order-status={order.status}
      data-work-order-priority={order.priority}
      data-work-order-pending={pending ? "true" : "false"}
      data-work-order-dragging={dragging ? "true" : "false"}
      className={`group relative overflow-hidden rounded-xl border p-3 pl-4 text-left transition-colors ${
        dragging
          ? // Opaque and hover-free while in flight: the pointer is over the card
            // for the whole gesture, so a `hover:bg-white/80` utility would win
            // over the base background and let the card underneath read through.
            "border-cyan-500/40 bg-white shadow-[0_18px_40px_rgba(15,23,42,0.18)]"
          : `border-slate-200/60 bg-white/60 shadow-sm backdrop-blur-md ${
              draggable ? "cursor-grab hover:border-slate-300/80 hover:bg-white/80" : "cursor-pointer"
            }`
      }`}
    >
      <span
        aria-hidden="true"
        className="absolute left-0 top-2 bottom-2 w-[3px] rounded-full"
        style={{ background: prio.accent, boxShadow: prio.glow }}
      />

      <div className="mb-1.5 flex items-center gap-2">
        <span className="cs-mono text-[11px] font-semibold text-cyan-700">{order.id}</span>
        {isAgent && <Tag tone="ai">AI</Tag>}
        <span className="ml-auto inline-flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: prio.accent, boxShadow: prio.glow }}
          />
          <span
            className={`rounded-full px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.14em] ring-1 ring-inset ${prio.chip}`}
            data-priority-chip={order.priority}
          >
            {order.priority}
          </span>
        </span>
      </div>

      <div className="text-[12.5px] leading-relaxed text-slate-600">{order.title}</div>

      {(order.evidence.length > 0 || order.recommended_action) && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {order.recommended_action && <Tag tone="ai">AI recommendation</Tag>}
          {order.evidence.length > 0 && <Tag>{order.evidence.length} evidence</Tag>}
          {order.evidence.length > 0 && <Tag tone="ok">verified ✓</Tag>}
        </div>
      )}

      <div className="cs-mono cs-dim mt-2 flex items-center gap-1.5 text-[10px]">
        <StatusDot state={order.status === "completed" ? "ok" : order.status === "on_hold" ? "warning" : "ai"} />
        <span className="min-w-0 truncate">
          {order.equipment_id || "—"} · {order.assignee}
        </span>
        {pending && <span className="ml-auto shrink-0 text-cyan-700">saving…</span>}
        {!pending && draggable && (
          <span className="ml-auto shrink-0 text-slate-400 opacity-0 transition-opacity group-hover:opacity-100">drag ⇄</span>
        )}
        {!pending && !draggable && <span className="ml-auto shrink-0 text-slate-400">terminal</span>}
      </div>
    </motion.div>
  );
}

/**
 * A column of the board. The drop ring is driven by the page's live drop-target
 * resolution, so an operator can see before releasing whether the lifecycle
 * permits the move.
 *
 * `raised` is set on the column a card is currently being dragged out of.
 * WHY it is needed: `backdrop-blur-xl` makes each column its own stacking
 * context, so a card translated out of its column cannot paint above a
 * neighbouring column — the drag ghost slid underneath the next column's 80%
 * white glass and effectively vanished. Lifting the source column's own
 * stacking context while its card is in flight puts the ghost back on top,
 * without touching the glass recipe.
 */
export function KanbanColumn({
  column,
  count,
  dropState,
  raised = false,
  registerRef,
  children,
}: {
  column: ColumnDef;
  count: number;
  dropState: "idle" | "allowed" | "blocked";
  raised?: boolean;
  registerRef: (el: HTMLDivElement | null) => void;
  children: React.ReactNode;
}) {
  const ring =
    dropState === "allowed"
      ? "border-cyan-500/60 shadow-[0_0_0_1px_rgba(8,145,178,0.35),0_10px_30px_rgba(8,145,178,0.16)]"
      : dropState === "blocked"
        ? "border-red-400/60 shadow-[0_0_0_1px_rgba(220,38,38,0.3)]"
        : "border-slate-200/80 shadow-sm";

  return (
    <section
      ref={registerRef}
      data-kanban-column={column.id}
      data-kanban-count={count}
      data-kanban-drop={dropState}
      data-kanban-raised={raised ? "true" : "false"}
      aria-label={`${column.label} column, ${count} work order${count === 1 ? "" : "s"}`}
      className={`relative flex flex-col rounded-2xl border bg-white/80 backdrop-blur-xl transition-[border-color,box-shadow] duration-200 ${ring} ${
        raised ? "z-50" : "z-0"
      }`}
    >
      <header className="flex items-center gap-2 border-b border-slate-200/60 px-3.5 py-2.5">
        <h2 className="cs-mono text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
          {column.label}
        </h2>
        <span
          className="ml-auto rounded-full border border-slate-200/80 bg-white/70 px-2 py-0.5 text-[10px] font-semibold tabular-nums text-slate-500"
          data-kanban-count-badge
        >
          {count}
        </span>
        {column.terminal && (
          <Lucide name="lock" size={11} className="text-slate-300" aria-label="Terminal status" />
        )}
      </header>

      <div className="flex min-h-[92px] flex-col gap-2.5 p-2.5">
        {children}
        {count === 0 && (
          <p className="cs-dim px-1.5 py-3 text-center text-[11px]">
            {dropState === "blocked" ? "— transition not allowed" : "— empty"}
          </p>
        )}
      </div>
    </section>
  );
}
