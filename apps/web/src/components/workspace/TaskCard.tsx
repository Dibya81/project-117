"use client";

/**
 * TaskCard — the heart of the AI Workspace.
 * Request → live stepper → context → result with cited claims → artifact →
 * verification. No chain-of-thought: only safe operational status + evidence.
 */
import { useRouter } from "next/navigation";
import type { CSSProperties } from "react";
import { StatusDot, Tag, Button } from "@/components/ui/primitives";
import { VerificationSummary } from "./VerificationSummary";
import { ArtifactCard } from "./ArtifactPreview";
import { Typewriter } from "@/components/fx/Typewriter";
import type { WorkspaceTask, TaskStep } from "@/types/console";

const STEPS: { id: TaskStep; label: string }[] = [
  { id: "request", label: "Request" },
  { id: "retrieving", label: "Retrieving" },
  { id: "analyzing", label: "Analyzing" },
  { id: "executing", label: "Executing" },
  { id: "verifying", label: "Verifying" },
  { id: "complete", label: "Complete" },
];

function Stepper({ current }: { current: TaskStep }) {
  const activeIdx = current === "failed" ? -1 : STEPS.findIndex((s) => s.id === current);
  return (
    <div className="cs-stepper" role="status" aria-label={`Task status: ${current}`}>
      {STEPS.map((s, i) => (
        <span
          key={s.id}
          className={`cs-step${i < activeIdx ? " is-done" : ""}${i === activeIdx ? " is-live" : ""}`}
        >
          <i aria-hidden="true" />
          {s.label}
        </span>
      ))}
    </div>
  );
}

const KICKER: CSSProperties = {
  margin: "0 0 9px",
  fontFamily: "var(--font-mono)",
  fontSize: 9.5,
  letterSpacing: "0.3em",
  textTransform: "uppercase",
  color: "var(--ink-3)",
};

export function TaskCard({
  task,
  onReviewApproval,
  streamResult = false,
}: {
  task: WorkspaceTask;
  onReviewApproval?: (id: string) => void;
  streamResult?: boolean;
}) {
  const router = useRouter();
  const running = task.step !== "complete" && task.step !== "failed";

  return (
    <article className="cs-task cs-scan" aria-label={`Task: ${task.request}`}>
      <header className="cs-task__head">
        <StatusDot state={task.step === "complete" ? "ok" : task.step === "failed" ? "critical" : "ai"} pulse={running} />
        <strong style={{ fontSize: 13.5 }}>{task.request}</strong>
        <span className="cs-mono cs-dim" style={{ marginLeft: "auto", fontSize: 10, whiteSpace: "nowrap" }}>
          {task.job_id} · {task.agent} agent
        </span>
      </header>

      <div className="cs-task__body">
        <Stepper current={task.step} />

        {task.context.length > 0 && (
          <div>
            <p style={KICKER}>Context</p>
            <div className="cs-chips">
              {task.context.map((c, i) => (
                <button
                  key={i}
                  className="cs-chip"
                  onClick={() => router.push(`/console/documents?doc=${c.document_id}`)}
                  title={c.snippet}
                >
                  {c.filename}
                  {c.page != null && <span className="cs-dim">p.{c.page}</span>}
                </button>
              ))}
            </div>
          </div>
        )}

        {task.result && (
          <div>
            <p style={KICKER}>Result</p>
            <p style={{ margin: 0, lineHeight: 1.7, color: "var(--ink-1)", fontSize: 13.5 }}>
              {streamResult ? <Typewriter text={task.result} /> : task.result}
            </p>
            {task.claims && (
              <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
                {task.claims.map((claim, i) => (
                  <div key={i} className="cs-claim" style={{ animationDelay: `${i * 130}ms` }}>
                    <StatusDot state={claim.verified ? "ok" : "warning"} />
                    <span style={{ color: "var(--ink-2)", flex: 1 }}>{claim.text}</span>
                    <span className="cs-chips">
                      {claim.citations.map((c, j) => (
                        <button
                          key={j}
                          className="cs-chip"
                          onClick={() => router.push(`/console/documents?doc=${c.document_id}`)}
                          title={c.snippet}
                        >
                          {c.filename}
                          {c.page != null && ` p.${c.page}`}
                        </button>
                      ))}
                      {!claim.verified && <Tag tone="warn">Unverified</Tag>}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {task.step === "complete" && task.structured && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {(
              [
                ["Executive answer", task.structured.executive, "var(--cyan)"],
                ["Primary finding", task.structured.finding, "var(--ink-1)"],
                ["Recommended action", task.structured.action, "var(--warn)"],
                ["Risk", task.structured.risk, "var(--warn)"],
                ["Next action", task.structured.next, "var(--ok)"],
              ] as const
            ).map(([label, text, color], i) => (
              <div
                key={label}
                style={{
                  borderLeft: `2px solid ${color}`,
                  padding: "8px 14px",
                  background: "rgba(6,10,16,0.45)",
                  borderRadius: "0 8px 8px 0",
                  animation: `p117-fade-up 520ms var(--ease-out) ${i * 110}ms both`,
                }}
              >
                <div className="cs-mono" style={{ fontSize: 8.5, letterSpacing: "0.3em", textTransform: "uppercase", color, marginBottom: 4 }}>
                  {label}
                </div>
                <div style={{ fontSize: 12.5, lineHeight: 1.65, color: "var(--ink-1)" }}>{text}</div>
              </div>
            ))}
            <div style={{ animation: "p117-fade-up 520ms var(--ease-out) 550ms both" }}>
              <div className="cs-mono" style={{ fontSize: 8.5, letterSpacing: "0.3em", textTransform: "uppercase", color: "var(--ink-3)", marginBottom: 7 }}>
                Contributing factors
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {task.structured.factors.map((f, i) => (
                  <div key={i} style={{ display: "flex", gap: 9, fontSize: 12.5, color: "var(--ink-2)", animation: `p117-fade-up 480ms var(--ease-out) ${600 + i * 90}ms both` }}>
                    <span className="cs-text-cyan cs-mono" style={{ fontSize: 10 }}>{String(i + 1).padStart(2, "0")}</span>
                    {f}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {task.artifacts.length > 0 && (
          <div>
            <p style={KICKER}>Artifacts</p>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {task.artifacts.map((a) => (
                <ArtifactCard key={a.id} artifact={a} />
              ))}
            </div>
          </div>
        )}

        {task.checks.length > 0 && task.step === "complete" && (
          <div>
            <p style={KICKER}>Verification</p>
            <VerificationSummary checks={task.checks} />
          </div>
        )}

        {task.needs_approval && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              border: "1px solid rgba(255,180,84,0.4)",
              borderRadius: 8,
              padding: "11px 15px",
              background: "var(--warn-soft)",
              animation: "p117-fade-up 500ms var(--ease-out) both",
            }}
          >
            <StatusDot state="warning" pulse />
            <span style={{ fontSize: 12.5 }}>
              Waiting for approval — <b>{task.needs_approval.action}</b>
            </span>
            <Button
              variant="primary"
              style={{ marginLeft: "auto" }}
              onClick={() => onReviewApproval?.(task.needs_approval!.approval_id)}
            >
              Review
            </Button>
          </div>
        )}
      </div>
    </article>
  );
}
