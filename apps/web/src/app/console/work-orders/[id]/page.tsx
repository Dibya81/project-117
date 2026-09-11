"use client";

/**
 * Work Order Detail — issue, linked equipment, AI recommendation + evidence,
 * approval status, timeline. AI-generated orders carry provenance.
 */
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button, EmptyState, Panel, SkeletonRows, StatusDot, Tag } from "@/components/ui/primitives";
import { Icon } from "@/components/ui/Icon";
import { consoleData } from "@/lib/data/console";
import { useJourney } from "@/lib/journey";
import { HISTORY } from "@/lib/mock/console";
import type { WorkOrder } from "@/types";

const STATUS_LABEL: Record<WorkOrder["status"], string> = {
  open: "Open",
  assigned: "Assigned",
  in_progress: "In progress",
  pending_approval: "Pending approval",
  done: "Done",
};

const STATUS_TONE: Record<WorkOrder["status"], "warn" | "ai" | "ok"> = {
  open: "warn",
  assigned: "ai",
  in_progress: "ai",
  pending_approval: "warn",
  done: "ok",
};

const PROVENANCE = [
  { id: "observed", label: "Observed" },
  { id: "analyzed", label: "Analyzed" },
  { id: "recommended", label: "Recommended" },
  { id: "drafted", label: "Drafted" },
  { id: "approved", label: "Approved" },
  { id: "executing", label: "Executing" },
  { id: "completed", label: "Completed" },
  { id: "verified", label: "Verified" },
];

/** Where this WO sits on the provenance spine. */
function provenanceIndex(w: WorkOrder): number {
  if (w.status === "done") return 7;
  if (w.status === "in_progress") return 5;
  if (w.status === "assigned") return 4;
  if (w.status === "pending_approval") return 3; // drafted, awaiting decision
  return w.evidence.length > 0 || w.recommended_action ? 2 : 1;
}

export default function WorkOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = decodeURIComponent(params.id);
  const [wo, setWo] = useState<WorkOrder | null | undefined>(undefined);
  const { visit } = useJourney();

  useEffect(() => {
    consoleData.workOrders.get(id).then((w) => {
      setWo(w);
      if (w) visit({ id: w.id, label: w.id, kind: "workorder", href: `/console/work-orders/${w.id}` });
    });
  }, [id, visit]);

  if (wo === undefined) {
    return (
      <Panel>
        <SkeletonRows rows={5} />
      </Panel>
    );
  }

  if (wo === null) {
    return (
      <EmptyState
        title={`Work order “${id}” not found`}
        detail="It may be newly created and not yet committed, or the ID is wrong."
        action={<Button onClick={() => router.push("/console/work-orders")}>Back to work orders</Button>}
      />
    );
  }

  const aiDrafted = wo.assignee.includes("agent") || wo.evidence.length > 0;
  const relatedHistory = HISTORY.filter((h) => h.equipment_id === wo.equipment_id).slice(0, 5);

  return (
    <>
      <div className="cs-pagehead">
        <div>
          <span className="cs-pagehead__kicker">
            <button
              onClick={() => router.push("/console/work-orders")}
              style={{ background: "none", border: 0, color: "inherit", cursor: "pointer", font: "inherit", letterSpacing: "inherit", padding: 0 }}
            >
              Work Orders
            </button>{" "}
            / <span className="cs-mono">{wo.id}</span>
          </span>
          <h1 style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            {wo.title}
            <Tag tone={STATUS_TONE[wo.status]}>{STATUS_LABEL[wo.status]}</Tag>
            {aiDrafted && <Tag tone="ai">AI-drafted</Tag>}
          </h1>
        </div>
        <div className="cs-pagehead__actions" style={{ marginLeft: "auto" }}>
          <Button variant="primary" onClick={() => router.push(`/console/equipment/${wo.equipment_id}`)}>
            <Icon name="equipment" size={13} /> Open {wo.equipment_id}
          </Button>
        </div>
      </div>

      <div className="cs-grid-2" style={{ gridTemplateColumns: "minmax(0, 1.6fr) minmax(300px, 1fr)", alignItems: "start" }}>
        <div className="cs-stack">
          <Panel title="Provenance — how this action came to exist" hud pad={false}>
            <div style={{ display: "flex", padding: "18px 16px", gap: 0, overflowX: "auto" }}>
              {PROVENANCE.map((st, i) => {
                const current = provenanceIndex(wo);
                const done = i < current;
                const live = i === current;
                return (
                  <div key={st.id} style={{ flex: 1, minWidth: 64, display: "flex", flexDirection: "column", alignItems: "center", gap: 7, position: "relative", animation: `p117-fade-up 460ms var(--ease-out) ${i * 80}ms both` }}>
                    {i > 0 && (
                      <span style={{ position: "absolute", top: 5, left: "-50%", width: "100%", height: 1.5, background: done || live ? "var(--cyan)" : "var(--line)", boxShadow: done || live ? "0 0 8px rgba(69,213,255,0.5)" : "none", transition: "all 500ms" }} />
                    )}
                    <span
                      style={{
                        width: 11,
                        height: 11,
                        borderRadius: "50%",
                        border: `1.5px solid ${done || live ? "var(--cyan)" : "var(--ink-3)"}`,
                        background: done ? "var(--cyan)" : live ? "var(--bg-1)" : "transparent",
                        boxShadow: live ? "0 0 12px var(--cyan)" : done ? "0 0 8px rgba(69,213,255,0.6)" : "none",
                        zIndex: 1,
                      }}
                      className={live ? "cs-dot--pulse" : undefined}
                    />
                    <span className="cs-mono" style={{ fontSize: 8, letterSpacing: "0.16em", textTransform: "uppercase", color: done || live ? "var(--ink-1)" : "var(--ink-3)", whiteSpace: "nowrap" }}>
                      {st.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </Panel>
          <Panel title="Details">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, fontSize: 13 }}>
              {(
                [
                  ["Equipment", wo.equipment_id],
                  ["Assignee", wo.assignee],
                  ["Priority", wo.priority.toUpperCase()],
                  ["Status", STATUS_LABEL[wo.status]],
                ] as const
              ).map(([k, v]) => (
                <div key={k}>
                  <div className="cs-mono cs-dim" style={{ fontSize: 9.5, letterSpacing: "0.26em", textTransform: "uppercase", marginBottom: 5 }}>
                    {k}
                  </div>
                  <div className="cs-mono">{v}</div>
                </div>
              ))}
            </div>
          </Panel>

          {wo.recommended_action && (
            <Panel title="AI recommendation" glow hud>
              <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.7 }}>{wo.recommended_action}</p>
              {wo.evidence.length > 0 && (
                <>
                  <p className="cs-mono cs-dim" style={{ margin: "14px 0 9px", fontSize: 9.5, letterSpacing: "0.28em", textTransform: "uppercase" }}>
                    Evidence
                  </p>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {wo.evidence.map((c, i) => (
                      <button
                        key={i}
                        className="cs-row"
                        style={{ border: "1px solid var(--line)", borderRadius: 8, background: "rgba(6,10,16,0.5)", font: "inherit", textAlign: "left" }}
                        onClick={() => router.push(`/console/documents?doc=${c.document_id}`)}
                      >
                        <Icon name="doc" size={14} />
                        <span>
                          <div className="cs-row__title cs-mono" style={{ fontSize: 11.5 }}>
                            {c.filename}
                            {c.page != null && <span className="cs-dim"> · p.{c.page}</span>}
                          </div>
                          <div className="cs-row__sub">{c.snippet}</div>
                        </span>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </Panel>
          )}
        </div>

        <div className="cs-stack">
          {wo.status === "pending_approval" && (
            <Panel title="Approval gate" pad style={{ borderColor: "rgba(255,180,84,0.4)" }}>
              <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                <StatusDot state="warning" pulse />
                <p style={{ margin: 0, fontSize: 12.5, color: "var(--ink-2)", lineHeight: 1.6 }}>
                  This action was proposed by an agent and is waiting for a human decision.
                  Nothing executes until someone approves it.
                </p>
              </div>
              <Button variant="primary" style={{ marginTop: 12, width: "100%", justifyContent: "center" }} onClick={() => router.push("/console/approvals")}>
                <Icon name="check" size={13} /> Review in Approvals
              </Button>
            </Panel>
          )}

          <Panel title="Timeline" pad={false}>
            <div className="cs-timeline" style={{ padding: "18px 18px 4px", marginLeft: 8 }}>
              {relatedHistory.map((h, i) => (
                <div key={h.id} className="cs-tl-item" style={{ animationDelay: `${i * 90}ms` }}>
                  <strong style={{ fontSize: 12.5 }}>{h.title}</strong>
                  <p className="cs-dim" style={{ margin: "3px 0", fontSize: 12 }}>{h.detail}</p>
                  <p className="cs-mono" style={{ margin: 0, fontSize: 10, color: "var(--ink-3)" }}>{h.actor}</p>
                </div>
              ))}
              {relatedHistory.length === 0 && <p className="cs-dim" style={{ fontSize: 12.5, paddingBottom: 14 }}>No linked history.</p>}
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}
