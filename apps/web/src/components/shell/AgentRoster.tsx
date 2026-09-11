"use client";

/** Agent roster drawer — the AI workforce at a glance.
 * Framing: what is it doing · what did it find · what needs attention. */
import { Drawer } from "@/components/ui/overlays";
import { StatusDot, Tag } from "@/components/ui/primitives";
import type { AgentDescriptor } from "@/types";

const RATE: Record<string, string> = {
  maintenance: "95% verified · 19 tasks/wk",
  operations: "100% verified · 14 tasks/wk",
  documentation: "100% verified · 5 tasks/wk",
  data_analysis: "89% verified · 9 tasks/wk",
  safety: "100% verified · policy checks",
};

export function AgentRoster({ agents, onClose }: { agents: AgentDescriptor[]; onClose: () => void }) {
  return (
    <Drawer title="AI Workforce" wide onClose={onClose}>
      {agents.map((a, i) => (
        <section key={a.kind} className="cs-agentcard" style={{ animationDelay: `${i * 70}ms` }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <StatusDot state={a.status === "idle" ? "ok" : "ai"} pulse={a.status !== "idle"} />
            <strong style={{ fontSize: 13.5 }}>{a.name}</strong>
            <Tag tone={a.status === "idle" ? undefined : "ai"}>{a.status === "idle" ? "Idle" : a.status}</Tag>
            <span className="cs-mono cs-dim" style={{ marginLeft: "auto", fontSize: 10 }}>
              {RATE[a.kind] ?? ""}
            </span>
          </div>
          <p style={{ margin: "9px 0 11px", color: "var(--ink-2)", fontSize: 12.5, lineHeight: 1.6 }}>
            {a.description}
          </p>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 9 }}>
            {a.tools.map((tool) => (
              <span
                key={tool}
                className="cs-tag"
                style={{ borderColor: "var(--line-2)", background: "transparent", color: "var(--ink-2)" }}
              >
                {tool}
              </span>
            ))}
          </div>
          <div className="cs-mono cs-dim" style={{ fontSize: 10, letterSpacing: "0.06em" }}>
            permissions&nbsp;&nbsp;{a.permissions.join("  ·  ")}
          </div>
        </section>
      ))}
    </Drawer>
  );
}
