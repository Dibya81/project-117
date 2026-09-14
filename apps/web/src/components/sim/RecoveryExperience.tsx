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
import type { SimEvent } from "@/lib/sim/types";

type AgentId = "diagnostic" | "operations" | "safety";

interface Panel {
  id: AgentId;
  name: string;
  role: string;
  tone: string;
  /** Backend task agents that feed this panel. */
  sources: string[];
}

const PANELS: Panel[] = [
  {
    id: "diagnostic",
    name: "Diagnostic Agent",
    role: "Identify the fault and the affected assets",
    tone: "#6366f1",
    sources: ["data_analysis", "maintenance", "documentation"],
  },
  {
    id: "operations",
    name: "Operations Agent",
    role: "Choose the recovery route over the plant topology",
    tone: "#0ea5e9",
    sources: ["operations"],
  },
  {
    id: "safety",
    name: "Safety & Verification Agent",
    role: "Confirm the route is safe before it is executed",
    tone: "#10b981",
    sources: ["safety"],
  },
];

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
}

export type RecoveryPhase = "analysing" | "decided" | "executing" | "verified" | "unavailable";

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

export function RecoveryExperience({
  events,
  incident,
  decision,
  plantName,
  onClose,
}: {
  events: SimEvent[];
  incident: { id: string; title?: string; origin_equipment?: string; severity?: string; status?: string } | null;
  decision: DecisionView | null;
  plantName?: string | null;
  onClose: () => void;
}) {
  const incidentId = incident?.id ?? "";

  const tasks = useMemo(() => readTasks(events, incidentId), [events, incidentId]);

  const phase: RecoveryPhase = useMemo(() => {
    if (!incident) return "analysing";
    if (decision && !decision.available) return "unavailable";
    const resolved = events.some(
      (e) => e.type === "incident.resolved" && (e.payload as Record<string, unknown>).id === incidentId,
    );
    if (resolved) return "verified";
    if (events.some((e) => e.type === "action.started" || e.type === "action.completed")) return "executing";
    if (decision?.available) return "decided";
    return "analysing";
  }, [events, incident, decision, incidentId]);

  const verifiedOk = useMemo(() => {
    const v = [...events].reverse().find((e) => e.type === "verification.completed");
    return v ? Boolean((v.payload as Record<string, unknown>).ok) : null;
  }, [events]);

  if (!incident) return null;

  const origin = String(incident.origin_equipment ?? "—");

  const panelState = (panel: Panel) => {
    const mine = tasks.filter((t) => panel.sources.includes(t.agent));
    const running = mine.some((t) => t.status === "running" || t.status === "queued");
    const blocked = mine.some((t) => t.status === "blocked");
    const done = mine.length > 0 && mine.every((t) => t.status === "completed" || t.status === "blocked");
    // The decision is the Operations and Safety agent's actual output.
    const decided = decision?.available === true;
    if (panel.id === "operations" && decided) return "completed" as const;
    if (panel.id === "safety" && decided) return "completed" as const;
    if (panel.id === "diagnostic" && decision?.diagnosis) return "completed" as const;
    if (running) return "running" as const;
    if (blocked && done) return "blocked" as const;
    if (done) return "completed" as const;
    return "waiting" as const;
  };

  const statusLabel: Record<string, string> = {
    waiting: "Waiting",
    running: "Working",
    completed: "Complete",
    blocked: "Blocked",
    unavailable: "Unavailable",
  };

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
          {phase === "unavailable" && "LOCAL MODEL UNAVAILABLE"}
        </div>
        <button type="button" className="rcx__close" onClick={onClose} aria-label="Close the agent view">
          Return to plant
        </button>
      </div>

      {phase === "unavailable" && (
        <div className="rcx__alert" role="status" data-testid="rcx-unavailable">
          <b>LOCAL MODEL UNAVAILABLE</b>
          <span>
            The three agents could not reach the local model, so no recovery decision was
            produced and the plant was not changed. {decision?.error ?? ""}
          </span>
        </div>
      )}

      <div className="rcx__grid">
        {PANELS.map((panel) => {
          const st = panelState(panel);
          const mine = tasks.filter((t) => panel.sources.includes(t.agent));
          return (
            <section key={panel.id} className="rcx__panel" data-agent={panel.id} data-status={st}>
              <header style={{ borderTopColor: panel.tone }}>
                <span className="rcx__dot" style={{ background: panel.tone }} />
                <div>
                  <b>{panel.name}</b>
                  <span>{panel.role}</span>
                </div>
                <em className={`rcx__state is-${st}`}>{statusLabel[st]}</em>
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
                  {panel.id === "diagnostic" && (
                    decision?.diagnosis
                      ? <p>{decision.diagnosis}</p>
                      : <p className="rcx__muted">{st === "running" ? "Reasoning over the evidence pack…" : "No finding yet."}</p>
                  )}
                  {panel.id === "operations" && (
                    decision?.available
                      ? <p>{decision.rationale || "Route evaluated against the plant topology."}</p>
                      : <p className="rcx__muted">{st === "running" ? "Evaluating candidate routes…" : "No route chosen yet."}</p>
                  )}
                  {panel.id === "safety" && (
                    decision?.available
                      ? (
                        <div>
                          <p>
                            {decision.safety_confirmed
                              ? "Route confirmed safe to execute."
                              : "Route NOT confirmed safe."}
                          </p>
                          {decision.safety_concerns.length > 0 && (
                            <ul className="rcx__concerns">
                              {decision.safety_concerns.map((c, i) => <li key={i}>{c}</li>)}
                            </ul>
                          )}
                        </div>
                      )
                      : <p className="rcx__muted">{st === "running" ? "Checking the safe-operating envelope…" : "No verification yet."}</p>
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
 * The compact summaries kept after the operator returns to the plant.
 *
 * Same three results as the full view, at panel size — the actual text and the
 * actual route ids the agents produced, so the decision remains on screen while
 * the plant is being operated.
 */
export function RecoverySummary({
  decision,
  events,
}: {
  decision: DecisionView | null;
  events: SimEvent[];
}) {
  const verification = useMemo(() => {
    const v = [...events].reverse().find((e) => e.type === "verification.completed");
    if (!v) return null;
    const p = v.payload as Record<string, unknown>;
    return { ok: p.ok === true, findings: Array.isArray(p.findings) ? (p.findings as unknown[]).map(String) : [] };
  }, [events]);

  if (!decision) return null;

  return (
    <aside className="rcx-sum" data-testid="recovery-summary">
      <header>
        <span>Agent response</span>
        <em className={decision.available ? "is-ok" : "is-crit"}>
          {decision.available ? "decided" : "unavailable"}
        </em>
      </header>

      {!decision.available && (
        <p className="rcx-sum__alert">LOCAL MODEL UNAVAILABLE — no recovery was applied.</p>
      )}

      <div className="rcx-sum__row" data-agent="diagnostic">
        <b>Diagnostic</b>
        <span>{decision.diagnosis || "—"}</span>
      </div>
      <div className="rcx-sum__row" data-agent="operations">
        <b>Operations</b>
        {decision.block.length === 0 && decision.restore.length === 0 ? (
          <span>No route change chosen.</span>
        ) : (
          <span>
            {decision.block.length > 0 && <>shut <code>{decision.block.join(", ")}</code> </>}
            {decision.restore.length > 0 && <>open <code>{decision.restore.join(", ")}</code></>}
          </span>
        )}
      </div>
      <div className="rcx-sum__row" data-agent="safety">
        <b>Safety</b>
        <span>
          {decision.safety_confirmed ? "Route confirmed safe." : "Route not confirmed safe."}
          {decision.safety_concerns.length > 0 && <> · {decision.safety_concerns.join("; ")}</>}
        </span>
      </div>

      {verification && (
        <div className="rcx-sum__verdict" data-ok={verification.ok ? "true" : "false"}>
          {verification.ok ? "Recovery verified" : "Verification failed"}
          {verification.findings.length > 0 && <span>{verification.findings[0]}</span>}
        </div>
      )}
    </aside>
  );
}
