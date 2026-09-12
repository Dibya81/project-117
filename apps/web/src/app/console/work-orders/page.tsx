"use client";

/**
 * Work Orders — status board with filters; create modal (manual or AI-drafted).
 * ?new=1 (from the command palette) opens the create modal directly.
 */
import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button, Panel, SkeletonRows, StatusDot, Tag } from "@/components/ui/primitives";
import { Modal } from "@/components/ui/overlays";
import { Icon } from "@/components/ui/Icon";
import { consoleData } from "@/lib/data/console";
import type { Equipment, WorkOrder } from "@/types";

const COLUMNS: { id: WorkOrder["status"]; label: string; tone: "warn" | "ai" | "ok" | undefined }[] = [
  { id: "on_hold", label: "Pending approval", tone: "warn" },
  { id: "open", label: "Open", tone: undefined },
  { id: "in_progress", label: "In progress", tone: "ai" },
  { id: "completed", label: "Done", tone: "ok" },
];

const PRIORITY_TONE: Record<WorkOrder["priority"], "crit" | "warn" | "ok" | undefined> = {
  critical: "crit",
  high: "warn",
  medium: undefined,
  low: "ok",
};

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

  useEffect(() => {
    consoleData.workOrders.list().then(setOrders);
    consoleData.equipment.list().then(setEquipment);
  }, []);

  useEffect(() => {
    if (params.get("new") === "1") setCreateOpen(true);
  }, [params]);

  const filtered = useMemo(
    () => (orders ?? []).filter((w) => prioFilter === "all" || w.priority === prioFilter),
    [orders, prioFilter],
  );

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

      {!orders ? (
        <Panel><SkeletonRows rows={6} label="Loading action system…" /></Panel>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 14, alignItems: "start" }}>
          {COLUMNS.map((col, ci) => {
            const items = filtered.filter((w) => w.status === col.id);
            return (
              <Panel key={col.id} pad={false} title={`${col.label} · ${items.length}`} style={{ animation: `p117-fade-up 560ms var(--ease-out) ${ci * 90}ms both` }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 9, padding: 12 }}>
                  {items.map((w) => (
                    <button
                      key={w.id}
                      onClick={() => router.push(`/console/work-orders/${w.id}`)}
                      style={{
                        textAlign: "left",
                        font: "inherit",
                        color: "inherit",
                        padding: "12px 13px",
                        border: "1px solid var(--line)",
                        borderRadius: 8,
                        background: "rgba(6,10,16,0.5)",
                        cursor: "pointer",
                        transition: "border-color 160ms, box-shadow 160ms, transform 160ms",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = "var(--line-glow)";
                        e.currentTarget.style.boxShadow = "var(--glow-cyan)";
                        e.currentTarget.style.transform = "translateY(-2px)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = "var(--line)";
                        e.currentTarget.style.boxShadow = "none";
                        e.currentTarget.style.transform = "none";
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 7 }}>
                        <span className="cs-mono cs-text-cyan" style={{ fontSize: 11 }}>{w.id}</span>
                        {w.assignee.includes("agent") && <Tag tone="ai">AI</Tag>}
                        <span style={{ marginLeft: "auto" }}>
                          <Tag tone={PRIORITY_TONE[w.priority]}>{w.priority}</Tag>
                        </span>
                      </div>
                      <div style={{ fontSize: 12.5, lineHeight: 1.5 }}>{w.title}</div>
                      {(w.evidence.length > 0 || w.recommended_action) && (
                        <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                          {w.recommended_action && <Tag tone="ai">AI recommendation</Tag>}
                          {w.evidence.length > 0 && <Tag>{w.evidence.length} evidence</Tag>}
                          {w.evidence.length > 0 && <Tag tone="ok">verified ✓</Tag>}
                        </div>
                      )}
                      <div className="cs-mono cs-dim" style={{ fontSize: 10, marginTop: 8, display: "flex", alignItems: "center", gap: 6 }}>
                        <StatusDot state={col.id === "completed" ? "ok" : col.id === "on_hold" ? "warning" : "ai"} />
                        {w.equipment_id} · {w.assignee}
                      </div>
                    </button>
                  ))}
                  {items.length === 0 && (
                    <p className="cs-dim" style={{ margin: "6px 2px", fontSize: 11.5 }}>—</p>
                  )}
                </div>
              </Panel>
            );
          })}
        </div>
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
