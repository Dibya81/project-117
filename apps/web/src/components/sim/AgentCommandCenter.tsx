"use client";

/**
 * AgentCommandCenter — the incident response surface.
 * Three levels in one panel: executive header → agent cards (expandable to
 * tools + evidence + result) → plan → approval → verification → resolution.
 * Plus the real task-dependency DAG. Everything is derived from actual
 * pipeline records; no status is decorative.
 */
import { useEffect, useMemo, useState } from "react";
import { Button, StatusDot, Tag } from "@/components/ui/primitives";
import { Icon, type IconName } from "@/components/ui/Icon";
import type { AgentTask, Incident, IncidentPlan } from "@/lib/sim/types";

const AGENT_ICON: Record<string, IconName> = {
  orchestrator: "cpu",
  data_analysis: "pulse",
  maintenance: "wrench",
  operations: "gauge",
  safety: "shield",
  documentation: "doc",
};

const AGENT_LABEL: Record<string, string> = {
  orchestrator: "Orchestrator",
  data_analysis: "Data Analysis Agent",
  maintenance: "Maintenance Agent",
  operations: "Operations Agent",
  safety: "Safety Agent",
  documentation: "Documentation Agent",
};

function elapsed(since: number, now: number): string {
  const s = Math.max(0, Math.round(now - since));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function TaskDag({ tasks }: { tasks: AgentTask[] }) {
  /** Layered DAG: depth = longest dependency chain. */
  const { nodes, edges } = useMemo(() => {
    const depth = new Map<string, number>();
    const byId = new Map(tasks.map((t) => [t.id, t]));
    const depthOf = (id: string, seen: Set<string>): number => {
      if (depth.has(id)) return depth.get(id)!;
      if (seen.has(id)) return 0;
      seen.add(id);
      const t = byId.get(id);
      const d = !t || t.depends_on.length === 0 ? 0 : 1 + Math.max(...t.depends_on.map((p) => depthOf(p, seen)));
      depth.set(id, d);
      return d;
    };
    tasks.forEach((t) => depthOf(t.id, new Set()));
    const layers = new Map<number, AgentTask[]>();
    tasks.forEach((t) => {
      const d = depth.get(t.id) ?? 0;
      if (!layers.has(d)) layers.set(d, []);
      layers.get(d)!.push(t);
    });
    const pos = new Map<string, { x: number; y: number }>();
    const maxD = Math.max(0, ...depth.values());
    layers.forEach((layer, d) => {
      layer.forEach((t, i) => {
        pos.set(t.id, {
          x: 40 + (maxD === 0 ? 0 : (d / maxD) * 220),
          y: 22 + i * (200 / Math.max(1, layer.length)) + 10,
        });
      });
    });
    const edges = tasks.flatMap((t) =>
      t.depends_on.map((p) => ({ from: pos.get(p)!, to: pos.get(t.id)!, done: t.status === "completed" })).filter((e) => e.from && e.to),
    );
    return { nodes: [...pos.entries()].map(([id, p]) => ({ id, ...p, task: byId.get(id)! })), edges };
  }, [tasks]);

  return (
    <div className="sm-dag">
      <p className="cs-mono cs-dim" style={{ margin: "0 0 8px", fontSize: 9, letterSpacing: "0.28em", textTransform: "uppercase" }}>
        Task dependencies
      </p>
      <svg viewBox="0 0 300 230" role="img" aria-label="Agent task dependency graph">
        {edges.map((e, i) => (
          <line
            key={i}
            x1={e.from.x}
            y1={e.from.y}
            x2={e.to.x}
            y2={e.to.y}
            stroke={e.done ? "#10b981" : "rgba(15,23,42,0.18)"}
            strokeWidth="1.2"
            strokeDasharray="4 4"
            className="cs-graph__edge"
          />
        ))}
        {nodes.map((n) => {
          const done = n.task.status === "completed";
          const run = n.task.status === "running";
          return (
            <g key={n.id} transform={`translate(${n.x}, ${n.y})`}>
              <circle r="8" fill="#ffffff" stroke={done ? "#10b981" : run ? "#2563eb" : "#94a3b8"} strokeWidth={done || run ? 1.8 : 1} />
              <circle r="2.4" fill={done ? "#10b981" : run ? "#2563eb" : "#94a3b8"} />
              <text x="12" y="3.5" fontSize="7" fill={done || run ? "#0f172a" : "#64748b"} fontFamily="ui-monospace, monospace">
                {(AGENT_LABEL[n.task.agent] ?? n.task.agent).replace(" Agent", "")}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function AgentCommandCenter({
  incident,
  tasks,
  plan,
  now,
  onDecide,
}: {
  incident: Incident;
  tasks: AgentTask[];
  plan: IncidentPlan | null;
  now: number;
  onDecide: (approved: boolean) => void;
}) {
  const [openTask, setOpenTask] = useState<string | null>(null);
  const [, force] = useState(0);

  // elapsed clock
  useEffect(() => {
    if (incident.status === "resolved") return;
    const id = setInterval(() => force((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [incident.status]);

  const waitingApproval = incident.status === "awaiting_approval";
  const ordered = [...tasks].sort((a, b) => a.sequence - b.sequence);

  return (
    <div>
      {/* executive header */}
      <div className={`sm-incident-head${incident.severity === "critical" ? " sm-incident-head--crit" : ""}`}>
        <div className="cs-mono" style={{ fontSize: 9, letterSpacing: "0.3em", color: "var(--warn)", textTransform: "uppercase", marginBottom: 6 }}>
          AI Workforce — {incident.id}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}>
          <strong style={{ fontSize: 13.5 }}>{incident.title}</strong>
        </div>
        <div style={{ display: "flex", gap: 12, marginTop: 9, flexWrap: "wrap" }}>
          <Tag tone={incident.severity === "critical" ? "crit" : "warn"}>{incident.severity}</Tag>
          <Tag tone="ai">{incident.status.replace(/_/g, " ")}</Tag>
          <span className="cs-mono cs-dim" style={{ fontSize: 10, alignSelf: "center" }}>
            elapsed {elapsed(incident.created_at, now)}
          </span>
        </div>
      </div>

      {/* agents */}
      <p className="cs-mono cs-dim" style={{ margin: "0 0 9px", fontSize: 9, letterSpacing: "0.28em", textTransform: "uppercase" }}>
        Agents · {ordered.filter((t) => t.status === "completed").length}/{ordered.length} complete
      </p>
      {ordered.map((t, i) => {
        const open = openTask === t.id;
        return (
          <div
            key={t.id}
            className={`sm-agent${open ? " is-open" : ""}`}
            style={{ animationDelay: `${i * 80}ms` }}
            onClick={() => setOpenTask(open ? null : t.id)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && setOpenTask(open ? null : t.id)}
          >
            <div className="sm-agent__name">
              <Icon name={AGENT_ICON[t.agent] ?? "cpu"} size={13} />
              {AGENT_LABEL[t.agent] ?? t.agent}
              <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
                <StatusDot state={t.status === "completed" ? "ok" : t.status === "running" ? "ai" : "unknown"} pulse={t.status === "running"} />
                <span className="cs-mono cs-dim" style={{ fontSize: 8.5, letterSpacing: "0.14em", textTransform: "uppercase" }}>
                  {t.status}
                </span>
              </span>
            </div>
            <div className="sm-agent__task">{t.title}</div>
            {t.result && t.status === "completed" && <div className="sm-agent__result">✓ {t.result}</div>}

            {open && (
              <div className="sm-agent__detail">
                {t.depends_on.length > 0 && (
                  <p className="cs-mono cs-dim" style={{ fontSize: 9, margin: "0 0 7px", letterSpacing: "0.14em" }}>
                    DEPENDS ON: {t.depends_on.join(", ")}
                  </p>
                )}
                {t.tools.length > 0 && (
                  <>
                    <p className="cs-mono cs-dim" style={{ fontSize: 8.5, margin: "0 0 6px", letterSpacing: "0.22em" }}>TOOLS</p>
                    {t.tools.map((tool, j) => (
                      <div key={j} className="cs-mono" style={{ fontSize: 10, color: "var(--ink-2)", marginBottom: 4 }}>
                        <span className="cs-text-cyan">{tool.tool}</span> — {tool.summary}
                      </div>
                    ))}
                  </>
                )}
                {t.evidence.length > 0 && (
                  <>
                    <p className="cs-mono cs-dim" style={{ fontSize: 8.5, margin: "8px 0 6px", letterSpacing: "0.22em" }}>EVIDENCE</p>
                    {t.evidence.map((ev) => (
                      <div key={ev.id} className="sm-evidence">
                        <span className="cs-mono cs-text-cyan" style={{ fontSize: 8.5, textTransform: "uppercase", flex: "0 0 auto" }}>
                          {ev.source_type}
                        </span>
                        <span style={{ flex: 1 }}>{ev.description}</span>
                        <span className="cs-mono cs-dim" style={{ fontSize: 9 }}>{Math.round(ev.confidence * 100)}%</span>
                      </div>
                    ))}
                  </>
                )}
                <p className="cs-mono cs-dim" style={{ fontSize: 8.5, margin: "8px 0 0", letterSpacing: "0.14em" }}>
                  STARTED {t.started_at?.toFixed(0)}s · COMPLETED {t.completed_at?.toFixed(0)}s · SEQ {t.sequence}
                </p>
              </div>
            )}
          </div>
        );
      })}

      {/* DAG */}
      {ordered.length > 0 && <TaskDag tasks={ordered} />}

      {/* plan + approval */}
      {plan && waitingApproval && (
        <div className="sm-plan" style={{ marginTop: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <StatusDot state="warning" pulse />
            <strong style={{ fontSize: 12.5 }}>Action request — approval required</strong>
          </div>
          <p style={{ margin: "8px 0 0", fontSize: 11.5, color: "var(--ink-2)", lineHeight: 1.55 }}>{plan.approval_reason}</p>
          <ol>
            {plan.steps.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
          <div className="cs-mono cs-dim" style={{ fontSize: 9, marginTop: 10, letterSpacing: "0.14em" }}>
            VERIFY: {plan.verification.length} gates
          </div>
          <div style={{ display: "flex", gap: 9, marginTop: 12 }}>
            <Button variant="approve" style={{ flex: 1, justifyContent: "center" }} onClick={() => onDecide(true)}>
              <Icon name="check" size={13} /> Approve
            </Button>
            <Button variant="reject" style={{ flex: 1, justifyContent: "center" }} onClick={() => onDecide(false)}>
              <Icon name="x" size={13} /> Reject
            </Button>
          </div>
        </div>
      )}

      {incident.status === "resolved" && (
        <div className="sm-plan" style={{ borderColor: "rgba(61,220,151,0.4)", background: "var(--ok-soft)", marginTop: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <StatusDot state="ok" />
            <strong style={{ fontSize: 12.5, color: "var(--ok)" }}>Incident resolved — verified</strong>
          </div>
          <div style={{ margin: "8px 0 6px", display: "flex", alignItems: "center", gap: 6 }}>
            <Tag tone="ok">Incident Report Ready</Tag>
            <span className="cs-mono cs-dim" style={{ fontSize: 9.5 }}>
              incident_{incident.id.toLowerCase()}.pdf
            </span>
          </div>
          <p className="cs-mono cs-dim" style={{ fontSize: 10, margin: "0 0 10px" }}>
            audit recorded · {elapsed(incident.created_at, incident.resolved_at ?? now)} total response time
          </p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <a
              href={`/api/simulation/plants/${incident.plant_id ?? "plant-refinery-01"}/incidents/${incident.id}/report.pdf`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn--ghost"
              style={{ display: "inline-flex", alignItems: "center", gap: 6, textDecoration: "none", fontSize: 11, padding: "6px 12px" }}
            >
              <Icon name="eye" size={12} /> View Report
            </a>
            <a
              href={`/api/simulation/plants/${incident.plant_id ?? "plant-refinery-01"}/incidents/${incident.id}/report.pdf`}
              download={`incident_${incident.id.toLowerCase()}.pdf`}
              className="btn btn--primary"
              style={{ display: "inline-flex", alignItems: "center", gap: 6, textDecoration: "none", fontSize: 11, padding: "6px 12px" }}
            >
              <Icon name="doc" size={12} /> Download PDF
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
