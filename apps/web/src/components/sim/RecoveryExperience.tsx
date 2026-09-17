"use client";

/**
 * RecoveryExperience — the full-screen three-agent incident experience.
 *
 * Everything shown here is read from the backend event stream: the agent tasks
 * (`agent.task_started` / `agent.tool_completed` / `agent.evidence_found` /
 * `agent.task_completed`) and the validated recovery decision
 * (`response.decision`, produced by the three agents over the local model).
 *
 * There is no timeline in this component and no setInterval. A panel advances
 * because an event arrived, and the phase changes because an event arrived:
 *
 *   incident open, no decision        -> analysing
 *   response.decision.available=false -> LOCAL MODEL UNAVAILABLE (no recovery)
 *   response.decision.available=true  -> decision ready
 *   action.started                    -> executing the route the agents chose
 *   verification.completed / resolved -> verified
 *
 * The route shown is `decision.block` / `decision.restore` — real connection
 * ids from the plant graph — never a scripted path.
 */

import { useMemo } from "react";
import { StatusDot, Tag } from "@/components/ui/primitives";
import type { SimEvent } from "@/lib/sim/types";

type AgentId = "diagnostic" | "operations" | "safety";

interface Panel {
  id: AgentId;
  name: string;
  role: string;
  model: string;
  tone: string;
  /** Backend task agents that feed this panel. */
  sources: string[];
}

const PANELS: Panel[] = [
  {
    id: "diagnostic",
    name: "Diagnostic Agent",
    role: "Identify the fault and the affected assets",
    model: "qwen3:1.7b",
    tone: "#6366f1",
    sources: ["data_analysis", "maintenance", "documentation"],
  },
  {
    id: "operations",
    name: "Operations Agent",
    role: "Choose the recovery route over the plant topology",
    model: "llama3.2:3b",
    tone: "#0ea5e9",
    sources: ["operations"],
  },
  {
    id: "safety",
    name: "Safety & Verification Agent",
    role: "Confirm the route is safe before it is executed",
    model: "gemma3:1b",
    tone: "#10b981",
    sources: ["safety"],
  },
];

/**
 * How long the full-screen three-agent experience stays up AFTER the agents
 * have returned their decision (the backend's `response.decision` event).
 *
 * The clock starts on the DECISION — the moment all three agents have answered —
 * and never on the incident start and never on resolution. A recovery keeps
 * running (action, verification) for an arbitrary time after the models reply,
 * so counting from the incident or from `incident.resolved` would show the
 * operator the panel for a duration that has nothing to do with the agents.
 *
 * This is a dismissal delay only: it never simulates agent work. It is applied
 * to a panel whose content the backend has already finished producing.
 */
export const AGENT_PANEL_DISMISS_MS = 20_000;

/**
 * Fallback dismissal for a run that ended with no decision at all — the
 * incident resolved or escalated before any `response.decision` arrived. That
 * run has no three-agent result to read, so the panel returns to the plant
 * after the existing short hold rather than hanging open forever.
 */
export const AGENT_PANEL_NO_DECISION_DISMISS_MS = 2_800;

interface TaskView {
  agent: string;
  title: string;
  status: string;
  tools: { tool: string; summary: string; ok?: boolean }[];
  evidence: { description: string; citation?: string | null; source_type?: string }[];
  result: string;
  runtime?: string;
}

export interface DecisionView {
  incidentId?: string | null;
  available: boolean;
  model: string | null;
  error: string | null;
  diagnosis: string;
  route: string[];
  block: string[];
  restore: string[];
  safety_confirmed: boolean;
  safety_concerns: string[];
  rationale: string;
  /**
   * Per-agent outcome from the backend (`response.decision.agent_status`):
   * completed | rejected | failed | skipped. A panel may only claim success
   * for a role the backend marked `completed` — never from task records.
   */
  agent_status: Record<string, string>;
}

export type RecoveryPhase =
  | "analysing"
  | "decided"
  | "executing"
  | "verified"
  | "escalated"
  | "unavailable"
  | "safety-rejected"
  | "invalid";

function readTasks(events: SimEvent[], incidentId: string): TaskView[] {
  const byId = new Map<string, TaskView>();
  for (const ev of events) {
    if (!ev.type.startsWith("agent.task_") && !ev.type.startsWith("agent.tool_") && !ev.type.startsWith("agent.evidence_")) {
      continue;
    }
    const p = ev.payload as Record<string, unknown>;
    const id = String(p.id ?? p.task_id ?? "");
    if (!id) continue;
    if (ev.type === "agent.task_started" || ev.type === "agent.task_completed") {
      // A task belongs to exactly one incident. Without this filter a second
      // incident would render the first incident's tasks in its panels.
      if (String(p.incident_id ?? "") !== incidentId) continue;
      byId.set(id, {
        agent: String(p.agent ?? ""),
        title: String(p.title ?? ""),
        status: String(p.status ?? "queued"),
        tools: (p.tools as TaskView["tools"]) ?? [],
        evidence: (p.evidence as TaskView["evidence"]) ?? [],
        result: String(p.result ?? ""),
        runtime: p.agent_runtime ? String(p.agent_runtime) : undefined,
      });
    } else {
      const task = byId.get(id);
      if (!task) continue;
      if (ev.type === "agent.tool_completed") {
        task.tools = [...task.tools, {
          tool: String(p.tool ?? ""),
          summary: String(p.summary ?? ""),
          ok: p.ok !== false,
        }];
      } else if (ev.type === "agent.evidence_found") {
        task.evidence = [...task.evidence, {
          description: String(p.description ?? ""),
          citation: (p.citation as string | null) ?? null,
          source_type: p.source_type ? String(p.source_type) : undefined,
        }];
      }
    }
  }
  return [...byId.values()].filter((t) => t.agent);
}

/** The outcome a panel can be in, from the backend or, pre-decision, the DAG. */
export type AgentState =
  | "waiting"
  | "running"
  | "completed"
  | "blocked"
  | "rejected"
  | "failed"
  | "skipped";

/**
 * One panel's state, from that agent's OWN outcome.
 *
 * This previously read the decision as a single boolean: if the decision was
 * available, all three panels said "completed"; if it was not, all three said
 * "unavailable". That is how the console came to show a Diagnostic that had
 * failed sitting next to a Safety agent marked verified — the panels were
 * describing the incident, not the agents. It also let a panel claim success
 * for a role that never ran.
 *
 * The backend records per-role truth in `response.decision.agent_status`
 * (`completed` / `rejected` / `failed` / `skipped`), and only the backend knows
 * whether Safety actually approved the route or declined it. That is the
 * authority here; task records are only a fallback for the window before the
 * decision event arrives.
 *
 * Module scope so the full-screen experience and the docked rail share ONE
 * definition of an agent's outcome rather than re-deriving it.
 */
export function panelState(panel: Panel, decision: DecisionView | null, tasks: TaskView[]): AgentState {
  const reported = decision?.agent_status?.[panel.id];
  if (reported === "completed") return "completed";
  if (reported === "rejected") return "rejected";
  if (reported === "failed") return "failed";
  if (reported === "skipped") return "skipped";

  // No per-agent answer yet: show progress from the task DAG, and never claim
  // a completed decision that has not arrived.
  const mine = tasks.filter((t) => panel.sources.includes(t.agent));
  const running = mine.some((t) => t.status === "running" || t.status === "queued");
  const blocked = mine.some((t) => t.status === "blocked");
  const done = mine.length > 0 && mine.every((t) => t.status === "completed" || t.status === "blocked");
  if (running) return "running";
  if (blocked && done) return "blocked";
  if (done) return "running"; // evidence gathered; the model has not answered yet
  return "waiting";
}

/**
 * Wording per panel per outcome. A distinct label for every state the backend
 * can report, so "the agent declined" and "the agent never ran" never read as
 * the same thing.
 */
export const STATUS_LABEL: Record<string, Record<string, string>> = {
  diagnostic: {
    waiting: "Queued",
    running: "Diagnosing",
    completed: "Fault Diagnosed",
    blocked: "Blocked",
    rejected: "Diagnosis Declined",
    failed: "Diagnosis Failed",
    skipped: "Not Run",
    unavailable: "Unavailable",
  },
  operations: {
    waiting: "Queued",
    running: "Routing",
    completed: "Route Selected",
    blocked: "Blocked",
    rejected: "No Route Accepted",
    failed: "Routing Failed",
    skipped: "Not Run — diagnosis failed",
    unavailable: "Unavailable",
  },
  safety: {
    waiting: "Queued",
    running: "Verifying",
    completed: "Safety Verified",
    blocked: "Blocked",
    rejected: "Safety Declined",
    failed: "Safety Check Failed",
    skipped: "Not Run — no route to check",
    unavailable: "Unavailable",
  },
};

/**
 * The one-line finding each agent produced, in the words the full-screen panel
 * uses. Shared so the docked rail shows exactly the same result text and never
 * invents a summary: a role with no finding reports that honestly.
 */
export function agentFinding(panel: Panel, decision: DecisionView | null, st: AgentState): string {
  if (panel.id === "diagnostic") {
    if (decision?.diagnosis) return decision.diagnosis;
    if (st === "failed" || st === "rejected") {
      return "The diagnostic agent did not return a usable finding. See the failure detail above.";
    }
    return st === "running" ? "Reasoning over the evidence pack…" : "No finding yet.";
  }
  if (panel.id === "operations") {
    if (decision?.rationale) return decision.rationale;
    if (st === "failed" || st === "rejected") return "No route was accepted. The recovery was not planned.";
    if (st === "skipped") return "Not run — there was no valid diagnosis to plan from.";
    return st === "running" ? "Evaluating candidate routes…" : "No route chosen yet.";
  }
  // Safety.
  const answered =
    Boolean(decision?.safety_concerns.length) ||
    Boolean(decision && typeof decision.safety_confirmed === "boolean" && st === "completed");
  if (answered) {
    return decision?.safety_confirmed ? "Route confirmed safe to execute." : "Route NOT confirmed safe.";
  }
  if (st === "skipped") return "Not run — the operations agent produced no route to verify.";
  if (st === "failed" || st === "rejected") {
    return "The safety check did not clear. The route was not executed.";
  }
  return st === "running" ? "Checking the safe-operating envelope…" : "No verification yet.";
}

/** A StatusDot tone per agent outcome — colour always travels with a label. */
function dockDot(st: AgentState): "ok" | "warning" | "critical" | "ai" | "unknown" {
  if (st === "completed") return "ok";
  if (st === "failed" || st === "rejected") return "critical";
  if (st === "blocked" || st === "skipped") return "warning";
  if (st === "running") return "ai";
  return "unknown";
}

export function RecoveryExperience({
  events,
  incident,
  decision,
  plantName,
  onClose,
  onRetry,
}: {
  events: SimEvent[];
  incident: { id: string; title?: string; origin_equipment?: string; severity?: string; status?: string } | null;
  decision: DecisionView | null;
  plantName?: string | null;
  onClose: () => void;
  /** Re-run the three agents for this incident after an unusable decision. */
  onRetry?: () => void;
}) {
  const incidentId = incident?.id ?? "";

  const tasks = useMemo(() => readTasks(events, incidentId), [events, incidentId]);

  const phase: RecoveryPhase = useMemo(() => {
    if (!incident) return "analysing";
    // A failed decision is not one generic state: a Safety refusal, a route
    // the validator rejected and a model that never answered are three
    // different endings and the header names the real one.
    if (decision && !decision.available) {
      const err = decision.error ?? "";
      if (err.startsWith("SAFETY CHECK FAILED")) return "safety-rejected";
      if (err.startsWith("RECOVERY DECISION INVALID")) return "invalid";
      return "unavailable";
    }
    const mine = (type: string) =>
      events.some(
        (e) =>
          e.type === type &&
          String((e.payload as Record<string, unknown>).incident_id ?? (e.payload as Record<string, unknown>).id ?? "") ===
            incidentId,
      );
    if (mine("incident.resolved")) return "verified";
    // Every route the agents could build failed the plant's own verification,
    // so the orchestrator handed the incident to the operator. That is a real
    // ending, not a recovery — the panel says so before it closes.
    if (mine("recovery.escalated")) return "escalated";
    // Scoped to THIS incident: a previous incident's action beats must not make
    // this one look like it is already executing.
    if (mine("action.started") || mine("action.completed")) return "executing";
    if (decision?.available) return "decided";
    return "analysing";
  }, [events, incident, decision, incidentId]);

  const verifiedOk = useMemo(() => {
    const v = [...events].reverse().find(
      (e) =>
        e.type === "verification.completed" &&
        String((e.payload as Record<string, unknown>).incident_id ?? "") === incidentId,
    );
    return v ? Boolean((v.payload as Record<string, unknown>).ok) : null;
  }, [events, incidentId]);

  /** The orchestrator's real escalation, with the findings that caused it. */
  const escalation = useMemo(() => {
    const v = [...events].reverse().find(
      (e) =>
        e.type === "recovery.escalated" &&
        String((e.payload as Record<string, unknown>).incident_id ?? "") === incidentId,
    );
    if (!v) return null;
    const p = v.payload as Record<string, unknown>;
    return {
      message: String(p.message ?? "No verified route — handed to the operator"),
      findings: Array.isArray(p.findings) ? (p.findings as unknown[]).map(String) : [],
      attempts: Number(p.attempts ?? 0),
    };
  }, [events, incidentId]);

  /** The agents the backend reported as failed or rejected, named for the banner. */
  const failingAgents = useMemo(
    () =>
      PANELS.filter((p) => {
        const st = decision?.agent_status?.[p.id];
        return st === "failed" || st === "rejected";
      }),
    [decision],
  );

  if (!incident) return null;

  const origin = String(incident.origin_equipment ?? "—");

  return (
    <div className="rcx" data-testid="recovery-experience" data-phase={phase}>
      <div className="rcx__bar">
        <div className="rcx__title">
          <span className="rcx__kicker">
            {plantName ?? "Plant"} · incident {incident.id}
          </span>
          <b>{incident.title ?? "Sensor fault — agent response"}</b>
        </div>
        <div className="rcx__phase" data-phase={phase}>
          {phase === "analysing" && "Agents analysing…"}
          {phase === "decided" && "Decision ready"}
          {phase === "executing" && "Executing the chosen route…"}
          {phase === "verified" && (verifiedOk === false ? "Verification failed" : "Recovery verified")}
          {phase === "escalated" && "Escalated — no route verified"}
          {phase === "unavailable" && "LOCAL MODEL UNAVAILABLE"}
        </div>
        <button type="button" className="rcx__close" onClick={onClose} aria-label="Close the agent view">
          Return to plant
        </button>
      </div>

      {phase === "escalated" && (
        <div className="rcx__alert" role="status" data-testid="rcx-escalated">
          <b>ESCALATED TO THE OPERATOR</b>
          <span>
            {escalation?.message ?? "No route the agents built cleared verification."}{" "}
            {escalation && escalation.attempts > 1 && (
              <>The three agents were asked {escalation.attempts} times. The plant keeps the
              last route they chose until you change it.</>
            )}
            {escalation && escalation.findings.length > 0 && <> {escalation.findings[0]}</>}
          </span>
        </div>
      )}

      {phase === "unavailable" && (
        <div className="rcx__alert" role="status" data-testid="rcx-unavailable">
          <b>NO RECOVERY PRODUCED</b>
          <span>
            {/* Name the agent(s) that actually failed. "The three agents could not
                produce a decision" was wrong whenever one of them answered and a
                later one was skipped as a result — it blamed all three for one
                agent's failure, and hid which model to look at. */}
            {failingAgents.length > 0 ? (
              <>
                {failingAgents.map((a) => a.name).join(", ")}
                {failingAgents.length === 1 ? " did not return" : " did not return"} a usable
                result, so the recovery stopped before any route was applied and the plant was
                not changed.
              </>
            ) : (
              <>The agents could not produce a usable decision, so no recovery decision was
              produced and the plant was not changed.</>
            )}{" "}
            {decision?.error ?? ""}
          </span>
          {onRetry && (
            <button type="button" className="rcx__retry" onClick={onRetry} data-testid="rcx-retry">
              Re-run the three agents
            </button>
          )}
        </div>
      )}

      <div className="rcx__grid">
        {PANELS.map((panel) => {
          const st = panelState(panel, decision, tasks);
          const mine = tasks.filter((t) => panel.sources.includes(t.agent));
          const label = STATUS_LABEL[panel.id]?.[st] ?? st;
          return (
            <section key={panel.id} className="rcx__panel" data-agent={panel.id} data-status={st}>
              <header style={{ borderTopColor: panel.tone }}>
                <span className="rcx__dot" style={{ background: panel.tone }} />
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <b>{panel.name}</b>
                    <code style={{ fontSize: 10, padding: "1px 5px", borderRadius: 4, background: "rgba(0,0,0,0.06)", color: "var(--ink-2)", fontWeight: 500 }}>
                      {panel.model}
                    </code>
                  </div>
                  <span>{panel.role}</span>
                </div>
                <em className={`rcx__state is-${st}`}>{label}</em>
              </header>

              <div className="rcx__body">
                {/* What it is analysing: the real task titles it was given. */}
                <div className="rcx__block">
                  <span className="rcx__label">Analysing</span>
                  {mine.length === 0 ? (
                    <p className="rcx__muted">Waiting for the orchestrator to dispatch this agent.</p>
                  ) : (
                    <ul>
                      {mine.map((t) => (
                        <li key={t.title}>
                          {t.title}
                          <em className={`rcx__task is-${t.status}`}>{t.status}</em>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {/* Tools actually invoked, from agent.tool_completed. */}
                {mine.some((t) => t.tools.length) && (
                  <div className="rcx__block">
                    <span className="rcx__label">Actions</span>
                    <ul className="rcx__tools">
                      {mine.flatMap((t) => t.tools).slice(0, 6).map((tool, i) => (
                        <li key={`${tool.tool}-${i}`} data-ok={tool.ok === false ? "false" : "true"}>
                          <code>{tool.tool}</code>
                          {tool.summary}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Findings: the decision fields each agent owns. */}
                <div className="rcx__block">
                  <span className="rcx__label">Findings</span>
                  {/*
                    Each panel reports its OWN outcome. Previously Operations and
                    Safety both keyed off `decision.available`, so an Operations
                    failure — or Safety never running because there was no route
                    to check — rendered as the passive "No route chosen yet." on
                    every panel, while the decision banner reported a hard
                    failure. The panel and the banner described different runs.
                  */}
                  {panel.id === "diagnostic" && (
                    decision?.diagnosis
                      ? <p>{decision.diagnosis}</p>
                      : <p className="rcx__muted">{agentFinding(panel, decision, st)}</p>
                  )}
                  {panel.id === "operations" && (
                    decision?.rationale
                      ? <p>{decision.rationale}</p>
                      : <p className="rcx__muted">{agentFinding(panel, decision, st)}</p>
                  )}
                  {panel.id === "safety" && (
                    decision?.safety_concerns.length || (decision && typeof decision.safety_confirmed === "boolean" && st === "completed")
                      ? (
                        <div>
                          <p>
                            {/* Same text the docked rail shows — one definition
                                of what each agent found, in agentFinding(). */}
                            {agentFinding(panel, decision, st)}
                          </p>
                          {decision && decision.safety_concerns.length > 0 && (
                            <ul className="rcx__concerns">
                              {decision.safety_concerns.map((c, i) => <li key={i}>{c}</li>)}
                            </ul>
                          )}
                        </div>
                      )
                      : <p className="rcx__muted">{agentFinding(panel, decision, st)}</p>
                  )}
                </div>

                {/* Evidence: retrieval citations and topology facts. */}
                {mine.some((t) => t.evidence.length) && (
                  <div className="rcx__block">
                    <span className="rcx__label">Evidence</span>
                    <ul className="rcx__evidence">
                      {mine.flatMap((t) => t.evidence).slice(0, 4).map((e, i) => (
                        <li key={i}>
                          {e.description}
                          {e.citation && <code>{e.citation}</code>}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Result: the model's own text, or the route it produced. */}
                <div className="rcx__block rcx__block--result">
                  <span className="rcx__label">Result</span>
                  {panel.id === "operations" && decision?.available ? (
                    <div className="rcx__route">
                      {decision.block.length > 0 && (
                        <div>
                          <span className="rcx__route-tag is-block">shut</span>
                          {decision.block.map((id) => <code key={id}>{id}</code>)}
                        </div>
                      )}
                      {decision.restore.length > 0 && (
                        <div>
                          <span className="rcx__route-tag is-open">open</span>
                          {decision.restore.map((id) => <code key={id}>{id}</code>)}
                        </div>
                      )}
                      {decision.block.length === 0 && decision.restore.length === 0 && (
                        <span className="rcx__muted">The agents chose no route change.</span>
                      )}
                    </div>
                  ) : mine.some((t) => t.result) ? (
                    <p>{mine.map((t) => t.result).filter(Boolean).join(" ")}</p>
                  ) : (
                    <p className="rcx__muted">—</p>
                  )}
                  {mine.some((t) => t.runtime) && (
                    <span className="rcx__runtime">
                      runtime: {[...new Set(mine.map((t) => t.runtime).filter(Boolean))].join(", ")}
                    </span>
                  )}
                </div>
              </div>
            </section>
          );
        })}
      </div>

      <footer className="rcx__foot">
        <span>Origin asset <code>{origin}</code></span>
        {decision?.model && <span>model <code>{decision.model}</code></span>}
        <span>{events.length} events received</span>
      </footer>
    </div>
  );
}

/**
 * The three-agent rail kept after the operator returns to the plant.
 *
 * One compact card per agent — the same three agents, the same real model, the
 * same per-agent outcome and the same finding text as the full-screen
 * experience. Every value is read through the shared helpers above, which take
 * it from the backend's own `response.decision`: the per-role `agent_status` is
 * the authority for success, so the rail cannot mark an agent completed because
 * a task record exists, and a role with no result says so rather than inventing
 * one.
 *
 * It is dismissible, and the plant page remembers the dismissal per incident.
 */
export function RecoveryDock({
  decision,
  events,
  onDismiss,
}: {
  decision: DecisionView;
  events: SimEvent[];
  onDismiss: () => void;
}) {
  const tasks = useMemo(
    () => readTasks(events, decision.incidentId ?? ""),
    [events, decision.incidentId],
  );

  return (
    <aside className="rcx-dock" data-testid="agent-rail" aria-label="Agent responses">
      <header className="rcx-dock__head">
        <span>Agent response</span>
        <Tag tone={decision.available ? "ok" : "crit"}>
          {decision.available ? "decided" : "unavailable"}
        </Tag>
        <button
          type="button"
          className="rcx-dock__close"
          onClick={onDismiss}
          aria-label="Dismiss the agent responses"
          title="Dismiss agent responses"
          data-testid="agent-rail-dismiss"
        >
          ×
        </button>
      </header>

      {!decision.available && (
        // The backend's own error, not a guess: a Safety refusal and a model
        // that never answered are different failures and read differently.
        <p className="rcx-dock__alert">{decision.error ?? "No recovery was produced."}</p>
      )}

      {PANELS.map((panel) => {
        const st = panelState(panel, decision, tasks);
        const label = STATUS_LABEL[panel.id]?.[st] ?? st;
        const base = agentFinding(panel, decision, st);
        // The full panel lists Safety's concerns beneath its sentence; the rail
        // keeps them on the same line rather than dropping real findings.
        const finding =
          panel.id === "safety" && decision.safety_concerns.length > 0
            ? `${base} · ${decision.safety_concerns.join("; ")}`
            : base;
        return (
          <section
            key={panel.id}
            className="rcx-dock__card"
            data-agent={panel.id}
            data-agent-box={panel.id}
            data-status={st}
            data-testid={`agent-rail-${panel.id}`}
            /* A CSS variable, not `borderLeftColor`: the class already sets the
               `border` shorthand, and mixing a longhand inline style with it
               makes React warn about conflicting properties on every rerender. */
            style={{ "--tone": panel.tone } as React.CSSProperties}
          >
            <div className="rcx-dock__top">
              <StatusDot state={dockDot(st)} />
              <b>{panel.name}</b>
              <em className={`rcx__state is-${st}`}>{label}</em>
            </div>
            <code className="rcx-dock__model">{panel.model}</code>
            <p className="rcx-dock__finding" title={finding}>{finding}</p>
          </section>
        );
      })}
    </aside>
  );
}
