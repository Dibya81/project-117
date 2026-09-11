"use client";

/**
 * Approvals — the human-in-the-loop queue.
 * Pending AI-proposed actions with risk, reason and evidence; decisions are
 * instant, animated, and reversible-looking (mock adapter persists in-memory).
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button, EmptyState, Panel, Progress, SkeletonRows, StatusDot, Tag, timeAgo } from "@/components/ui/primitives";
import { Icon } from "@/components/ui/Icon";
import { consoleData } from "@/lib/data/console";
import type { ApprovalRequest } from "@/types";

const RISK_SCORE = { low: 28, medium: 58, high: 88 } as const;
const RISK_TONE = { low: "ok", medium: "warn", high: "crit" } as const;

const AUTH_STEPS = ["Policy check", "Authorized", "Audit recorded"] as const;

function ApprovalCard({ approval, onDecide, index }: { approval: ApprovalRequest; onDecide: (id: string, d: "approved" | "rejected") => void; index: number }) {
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);
  const [phase, setPhase] = useState<"idle" | "authorizing" | "rejecting">("idle");
  const [authStep, setAuthStep] = useState(-1);
  const [reason, setReason] = useState("");
  const pending = approval.status === "pending";

  const authorize = () => {
    setPhase("authorizing");
    AUTH_STEPS.forEach((_, i) => {
      setTimeout(() => setAuthStep(i), 300 + i * 620);
    });
    setTimeout(() => onDecide(approval.id, "approved"), 300 + AUTH_STEPS.length * 620);
  };

  return (
    <article
      className={`cs-panel${pending ? "" : ""}`}
      style={{
        animation: `p117-fade-up 560ms var(--ease-out) ${index * 100}ms both`,
        borderColor: pending ? "rgba(255,180,84,0.28)" : "var(--line)",
        opacity: pending ? 1 : 0.72,
      }}
    >
      <div className="cs-panel__body" style={{ display: "flex", flexDirection: "column", gap: 13 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
          <StatusDot state={pending ? "warning" : approval.status === "approved" ? "ok" : "critical"} pulse={pending} />
          <div style={{ flex: 1 }}>
            <strong style={{ fontSize: 14, lineHeight: 1.5 }}>{approval.action}</strong>
            <div className="cs-mono cs-dim" style={{ fontSize: 10, marginTop: 5, letterSpacing: "0.08em" }}>
              {approval.id} · proposed by {approval.requested_by} · {timeAgo(approval.created_at)}
            </div>
          </div>
          <Tag tone={pending ? "warn" : approval.status === "approved" ? "ok" : "crit"}>
            {approval.status.toUpperCase()}
          </Tag>
        </div>

        <div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10.5, marginBottom: 6 }}>
            <span className="cs-mono cs-dim" style={{ letterSpacing: "0.24em", textTransform: "uppercase" }}>Risk</span>
            <span className={`cs-mono cs-text-${RISK_TONE[approval.risk]}`} style={{ letterSpacing: "0.14em", textTransform: "uppercase" }}>
              {approval.risk}
            </span>
          </div>
          <Progress value={RISK_SCORE[approval.risk]} tone={RISK_TONE[approval.risk]} />
        </div>

        <p style={{ margin: 0, fontSize: 12.5, color: "var(--ink-2)", lineHeight: 1.65 }}>{approval.reason}</p>

        {approval.evidence.length > 0 && (
          <div>
            <button
              onClick={() => setExpanded((v) => !v)}
              className="cs-mono"
              style={{ background: "none", border: 0, color: "var(--cyan)", cursor: "pointer", fontSize: 10, letterSpacing: "0.22em", textTransform: "uppercase", padding: 0 }}
            >
              {expanded ? "▾ Hide evidence" : `▸ Evidence (${approval.evidence.length})`}
            </button>
            {expanded && (
              <div style={{ display: "flex", flexDirection: "column", gap: 7, marginTop: 10 }}>
                {approval.evidence.map((c, i) => (
                  <button
                    key={i}
                    className="cs-row"
                    style={{ border: "1px solid var(--line)", borderRadius: 8, background: "rgba(6,10,16,0.5)", font: "inherit", textAlign: "left" }}
                    onClick={() => router.push(`/console/documents?doc=${c.document_id}`)}
                  >
                    <Icon name="doc" size={13} />
                    <span>
                      <div className="cs-row__title cs-mono" style={{ fontSize: 11.5 }}>
                        {c.filename}{c.page != null && <span className="cs-dim"> · p.{c.page}</span>}
                      </div>
                      <div className="cs-row__sub">{c.snippet}</div>
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {pending && phase === "idle" && (
          <div style={{ display: "flex", gap: 10, borderTop: "1px solid var(--line)", paddingTop: 13 }}>
            <Button variant="approve" style={{ flex: 1, justifyContent: "center" }} onClick={authorize}>
              <Icon name="check" size={13} /> Approve
            </Button>
            <Button variant="reject" style={{ flex: 1, justifyContent: "center" }} onClick={() => setPhase("rejecting")}>
              <Icon name="x" size={13} /> Reject
            </Button>
            {approval.equipment_id && (
              <Button variant="ghost" onClick={() => router.push(`/console/equipment/${approval.equipment_id}`)}>
                <Icon name="eye" size={13} /> Context
              </Button>
            )}
          </div>
        )}

        {/* Authorization sequence — approval visibly unlocks execution */}
        {pending && phase === "authorizing" && (
          <div style={{ borderTop: "1px solid var(--line)", paddingTop: 13, display: "flex", flexDirection: "column", gap: 8 }}>
            {AUTH_STEPS.map((st, i) => (
              <div key={st} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12, opacity: i <= authStep ? 1 : 0.35, transition: "opacity 300ms" }}>
                <StatusDot state={i < authStep ? "ok" : i === authStep ? "ai" : "unknown"} pulse={i === authStep} />
                <span className="cs-mono" style={{ letterSpacing: "0.2em", textTransform: "uppercase", fontSize: 10 }}>{st}</span>
                {i < authStep && <span className="cs-mono cs-text-ok" style={{ marginLeft: "auto", fontSize: 10 }}>PASS ✓</span>}
              </div>
            ))}
          </div>
        )}

        {/* Reject with reason */}
        {pending && phase === "rejecting" && (
          <div style={{ borderTop: "1px solid var(--line)", paddingTop: 13, animation: "p117-fade-up 300ms var(--ease-out) both" }}>
            <div className="cs-field">
              <label htmlFor={`rej-${approval.id}`}>Reason (recorded in the audit ledger)</label>
              <textarea
                id={`rej-${approval.id}`}
                className="cs-textarea"
                rows={2}
                placeholder="Why is this action not authorized?"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                autoFocus
              />
            </div>
            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <Button variant="ghost" onClick={() => setPhase("idle")}>Back</Button>
              <Button variant="reject" onClick={() => onDecide(approval.id, "rejected")} disabled={!reason.trim()}>
                <Icon name="x" size={13} /> Confirm rejection
              </Button>
            </div>
          </div>
        )}
      </div>
    </article>
  );
}

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalRequest[] | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  useEffect(() => {
    consoleData.approvals.list().then(setApprovals);
  }, []);

  const decide = async (id: string, decision: "approved" | "rejected") => {
    await consoleData.approvals.decide(id, decision);
    setApprovals((cur) => cur?.map((a) => (a.id === id ? { ...a, status: decision } : a)) ?? null);
    setFlash(`${id} ${decision === "approved" ? "approved — action committed to the ledger" : "rejected — agent notified"}`);
    setTimeout(() => setFlash(null), 3600);
  };

  const pending = approvals?.filter((a) => a.status === "pending") ?? [];
  const decided = approvals?.filter((a) => a.status !== "pending") ?? [];

  return (
    <>
      <div className="cs-pagehead">
        <div>
          <span className="cs-pagehead__kicker">Control</span>
          <h1>Approvals</h1>
        </div>
        <span className="cs-pagehead__meta">
          {pending.length} pending · agents propose, humans decide
        </span>
      </div>

      {flash && (
        <div className="cs-strip" role="status" style={{ marginBottom: 16, borderColor: "rgba(61,220,151,0.4)", animation: "p117-fade-up 400ms var(--ease-out) both" }}>
          <span><StatusDot state="ok" pulse /> {flash}</span>
        </div>
      )}

      {!approvals ? (
        <Panel><SkeletonRows rows={4} label="Loading governance queue…" /></Panel>
      ) : approvals.length === 0 ? (
        <EmptyState title="Queue clear" detail="No AI-proposed actions are waiting for review." />
      ) : (
        <div className="cs-grid-2" style={{ alignItems: "start" }}>
          <div className="cs-stack">
            <p className="cs-mono cs-dim" style={{ margin: 0, fontSize: 10, letterSpacing: "0.3em", textTransform: "uppercase" }}>
              Pending · {pending.length}
            </p>
            {pending.map((a, i) => (
              <ApprovalCard key={a.id} approval={a} index={i} onDecide={decide} />
            ))}
            {pending.length === 0 && (
              <EmptyState title="Nothing pending" detail="New agent proposals will land here with evidence attached." />
            )}
          </div>
          <div className="cs-stack">
            <p className="cs-mono cs-dim" style={{ margin: 0, fontSize: 10, letterSpacing: "0.3em", textTransform: "uppercase" }}>
              Decided · {decided.length}
            </p>
            {decided.map((a, i) => (
              <ApprovalCard key={a.id} approval={a} index={i + pending.length} onDecide={decide} />
            ))}
          </div>
        </div>
      )}
    </>
  );
}
