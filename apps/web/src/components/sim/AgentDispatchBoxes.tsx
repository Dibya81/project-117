"use client";

/**
 * AgentDispatchBoxes — three floating panels showing what the responding
 * agents are doing, and what they did.
 *
 * Every line comes from a real `AgentTask` record produced by the simulation
 * pipeline: its status, the tools it actually called, the evidence it actually
 * gathered, and its own result text. Nothing here is a scripted sequence — if
 * the pipeline produced no task, no box appears, and the panel says so.
 *
 * The header is the thing an operator asks first: which model is doing this,
 * and in what role. The model comes from the gateway's role map (e.g.
 * reasoning → llama3:latest), not from a label chosen here.
 *
 * Motion follows lib/motion.ts: a box EMERGES when its task starts and
 * RESOLVES when its task completes.
 */

import { StatusDot, Tag } from "@/components/ui/primitives";
import { Icon, type IconName } from "@/components/ui/Icon";
import { MOTION, prefersReducedMotion } from "@/lib/motion";
import type { AgentTask } from "@/lib/sim/types";

const ROLE: Record<AgentTask["agent"], { label: string; role: string; icon: IconName }> = {
  orchestrator: { label: "Orchestrator", role: "reasoning", icon: "cpu" },
  data_analysis: { label: "Data Analysis", role: "reasoning", icon: "pulse" },
  maintenance: { label: "Maintenance", role: "domain", icon: "wrench" },
  operations: { label: "Operations", role: "domain", icon: "gauge" },
  safety: { label: "Safety", role: "reasoning", icon: "shield" },
  documentation: { label: "Documentation", role: "reasoning", icon: "doc" },
};

export interface ModelRoleMap {
  [role: string]: string | null;
}

/**
 * What the agent is doing right now, in the operator's language.
 *
 * Derived from the task's own status and the tools it has recorded — not from a
 * synthetic "thinking…" line, which would claim activity the pipeline has not
 * reported.
 */
function activityOf(task: AgentTask): string {
  const lastTool = task.tools[task.tools.length - 1];
  switch (task.status) {
    case "queued":
      return task.depends_on.length
        ? `Waiting on ${task.depends_on.length} upstream task${task.depends_on.length === 1 ? "" : "s"}`
        : "Queued";
    case "running":
      if (lastTool) return `Running ${lastTool.tool} — ${lastTool.summary}`;
      return "Working the task";
    case "completed":
      return task.result ? "Completed — see findings below" : "Completed";
    case "blocked":
      return "Blocked — recording why rather than guessing";
    case "failed":
      return "Failed — the task did not complete";
  }
}

function statusTone(task: AgentTask): "ok" | "warning" | "critical" | "unknown" {
  switch (task.status) {
    case "completed":
      return "ok";
    case "running":
      return "warning";
    case "failed":
    case "blocked":
      return "critical";
    default:
      return "unknown";
  }
}

/**
 * The agent's findings, as bullets.
 *
 * `result` is the pipeline's own prose. Where it is absent the box shows the
 * evidence it gathered instead of inventing a conclusion — an agent that has
 * not finished has not concluded anything.
 */
function findingsOf(task: AgentTask): string[] {
  const out: string[] = [];
  if (task.result) {
    out.push(
      ...task.result
        .split(/(?<=\.)\s+/)
        .map((s) => s.trim())
        .filter(Boolean)
        .slice(0, 4),
    );
  }
  if (!out.length && task.evidence.length) {
    out.push(...task.evidence.slice(0, 3).map((e) => `${e.description} (${e.confidence}%)`));
  }
  if (!out.length && task.tools.length) {
    out.push(...task.tools.slice(0, 3).map((t) => `${t.tool}: ${t.summary}`));
  }
  return out;
}

export function AgentDispatchBoxes({
  tasks,
  models,
  max = 3,
}: {
  tasks: AgentTask[];
  models: ModelRoleMap;
  /** How many boxes to float. The request is three. */
  max?: number;
}) {
  const reduced = prefersReducedMotion();
  // The agents that did work, in pipeline order. Orchestrator is included only
  // if it is one of the first three — it always runs, so it would otherwise
  // crowd out the specialists that actually resolve the incident.
  const shown = tasks
    .filter((t) => t.agent !== "orchestrator")
    .slice(0, max);

  // A healthy plant shows nothing here. An empty panel announcing that nothing
  // is happening is noise over the drawing an operator is trying to read, and
  // the page already states that no anomaly is active.
  if (!shown.length) return null;

  return (
    <div className="adb-layer" data-testid="agent-dispatch-boxes" data-count={shown.length}>
      {shown.map((task, i) => {
        const meta = ROLE[task.agent];
        const model = models[meta.role] ?? null;
        const findings = findingsOf(task);
        const anim =
          task.status === "running"
            ? MOTION.handoff
            : task.status === "completed"
              ? MOTION.resolve
              : MOTION.emerge;
        return (
          <article
            key={task.id}
            className="adb-box"
            data-agent={task.agent}
            data-status={task.status}
            data-testid={`agent-box-${task.agent}`}
            style={{
              animation: reduced
                ? undefined
                : `p117-motion-emerge ${anim.duration}ms ${anim.easing} both`,
              animationDelay: reduced ? undefined : `${i * 120}ms`,
            }}
          >
            <header className="adb-box__head">
              <Icon name={meta.icon} size={13} />
              <div style={{ minWidth: 0 }}>
                <div className="adb-box__model" title={model ?? "no model assigned"}>
                  {model ?? "model unassigned"}
                </div>
                <div className="adb-box__role">
                  {meta.label} · {meta.role}
                </div>
              </div>
              <span className="adb-box__status">
                <StatusDot state={statusTone(task)} pulse={task.status === "running"} />
                {task.status.toUpperCase()}
              </span>
            </header>

            <p className="adb-box__activity">{activityOf(task)}</p>

            {findings.length > 0 && (
              <ul className="adb-box__findings">
                {findings.map((f, k) => (
                  <li key={k}>{f}</li>
                ))}
              </ul>
            )}

            <footer className="adb-box__foot">
              {task.tools.length > 0 && <Tag tone="ai">{task.tools.length} tool calls</Tag>}
              {task.evidence.length > 0 && <Tag>{task.evidence.length} evidence</Tag>}
              {task.status === "completed" && <Tag tone="ok">done</Tag>}
            </footer>
          </article>
        );
      })}
    </div>
  );
}
