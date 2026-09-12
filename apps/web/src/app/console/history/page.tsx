"use client";

/**
 * Operational History — organizational memory, not an activity log.
 * Events grouped by OBSERVED / DECIDED / ACTED / VERIFIED; the timeline spine
 * draws itself; Learned Rules carry origin, evidence, confidence and usage.
 */
import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { useRouter } from "next/navigation";
import { Panel, Progress, SkeletonRows, Tag, timeAgo } from "@/components/ui/primitives";
import { Icon } from "@/components/ui/Icon";
import { consoleData } from "@/lib/data/console";
import type { HistoryEvent, LearnedRule } from "@/types/console";

const KIND_STYLE: Record<HistoryEvent["kind"], { color: string; label: string }> = {
  anomaly: { color: "var(--crit)", label: "Observed" },
  inspection: { color: "var(--ember)", label: "Observed" },
  decision: { color: "#b79cff", label: "Decided" },
  approval: { color: "var(--warn)", label: "Decided" },
  maintenance: { color: "var(--ok)", label: "Acted" },
  work_order: { color: "var(--ink-2)", label: "Acted" },
  recommendation: { color: "var(--cyan)", label: "Verified" },
  // A real domain event that is none of the named stages. Previously these fell
  // into `recommendation` and were rendered as "Verified", which is how a raw
  // HTTP request ended up wearing a verification badge.
  event: { color: "var(--ink-2)", label: "Recorded" },
};

const CATEGORY_ORDER = ["Observed", "Decided", "Acted", "Verified", "Recorded"];

export default function HistoryPage() {
  const router = useRouter();
  const [events, setEvents] = useState<HistoryEvent[] | null>(null);
  const [rules, setRules] = useState<LearnedRule[] | null>(null);
  const [catFilter, setCatFilter] = useState<string>("all");
  /** Event id from ?event= — the Knowledge Universe deep link. */
  const [focusEvent, setFocusEvent] = useState<string | null>(null);

  useEffect(() => {
    consoleData.history.list().then(setEvents);
    consoleData.history.rules().then(setRules);
    setFocusEvent(new URLSearchParams(window.location.search).get("event"));
  }, []);

  // Once the deep-linked event is rendered, bring it into view.
  useEffect(() => {
    if (!focusEvent || !events) return;
    document.getElementById(`hist-${focusEvent}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focusEvent, events]);

  const filtered = useMemo(
    () => (events ?? []).filter((e) => catFilter === "all" || KIND_STYLE[e.kind].label === catFilter),
    [events, catFilter],
  );

  return (
    <>
      <div className="cs-pagehead">
        <div>
          <span className="cs-pagehead__kicker">Knowledge</span>
          <h1>Organizational Memory</h1>
        </div>
        <span className="cs-pagehead__meta">observed → decided → acted → verified → learned</span>
      </div>

      <div className="cs-grid-2" style={{ gridTemplateColumns: "minmax(0, 1.6fr) minmax(320px, 1fr)", alignItems: "start" }}>
        <Panel
          title="Timeline"
          pad={false}
          actions={
            <select className="cs-select" style={{ width: 150, padding: "6px 11px" }} value={catFilter} onChange={(e) => setCatFilter(e.target.value)} aria-label="Filter by category">
              <option value="all">All memory</option>
              {CATEGORY_ORDER.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          }
        >
          {!events ? (
            <>
              <div className="cs-loading"><i /> Reconstructing memory…</div>
              <SkeletonRows rows={6} />
            </>
          ) : (
            <div className="cs-timeline" style={{ padding: "20px 20px 4px", marginLeft: 10 }}>
              {filtered.map((e, i) => {
                const s = KIND_STYLE[e.kind];
                return (
                  <div
                    key={e.id}
                    id={`hist-${e.id}`}
                    className="cs-tl-item"
                    style={{
                      "--tl-c": s.color,
                      animationDelay: `${i * 90}ms`,
                      ...(focusEvent === e.id
                        ? { outline: "1px solid rgba(69,213,255,0.55)", outlineOffset: 4, borderRadius: 6 }
                        : null),
                    } as CSSProperties}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}>
                      <strong style={{ fontSize: 13.5 }}>{e.title}</strong>
                      <span
                        className="cs-tag"
                        style={{ borderColor: `color-mix(in srgb, ${s.color} 40%, transparent)`, color: s.color, background: `color-mix(in srgb, ${s.color} 9%, transparent)` }}
                      >
                        {s.label}
                      </span>
                      <span className="cs-mono cs-dim" style={{ marginLeft: "auto", fontSize: 10 }}>{timeAgo(e.at)}</span>
                    </div>
                    <p className="cs-dim" style={{ margin: "4px 0 2px", fontSize: 12.5 }}>{e.detail}</p>
                    <p className="cs-mono" style={{ margin: 0, fontSize: 10, color: "var(--ink-3)" }}>
                      by {e.actor}
                      {e.equipment_id && (
                        <button
                          onClick={() => router.push(`/console/equipment/${e.equipment_id}`)}
                          style={{ background: "none", border: 0, color: "var(--cyan)", cursor: "pointer", font: "inherit", marginLeft: 8 }}
                        >
                          → {e.equipment_id}
                        </button>
                      )}
                    </p>
                  </div>
                );
              })}
              {filtered.length === 0 && (
                <p className="cs-dim" style={{ paddingBottom: 20 }}>
                  No {catFilter.toLowerCase()} memory yet — it forms as the plant and the agents operate.
                </p>
              )}
            </div>
          )}
        </Panel>

        <Panel title="Learned rules — what the plant taught us" hud>
          {!rules ? (
            <SkeletonRows rows={4} />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <p className="cs-dim" style={{ margin: 0, fontSize: 12.5, lineHeight: 1.6 }}>
                Rules your team taught the system. Agents cite them as evidence; safety checks enforce them.
              </p>
              {rules.map((r, i) => (
                <div key={r.id} className="cs-agentcard" style={{ marginBottom: 0, animationDelay: `${i * 100}ms`, borderColor: "rgba(183,156,255,0.22)" }}>
                  <div style={{ display: "flex", gap: 9, alignItems: "flex-start", marginBottom: 10 }}>
                    <Icon name="zap" size={13} />
                    <div style={{ flex: 1 }}>
                      <div className="cs-mono" style={{ fontSize: 8.5, letterSpacing: "0.3em", color: "var(--violet)", textTransform: "uppercase", marginBottom: 5 }}>
                        Learned rule #{r.id.replace("r-", "").padStart(3, "0")}
                      </div>
                      <div style={{ fontSize: 12.5, lineHeight: 1.55, color: "var(--ink-1)" }}>{r.rule}</div>
                    </div>
                    <Tag tone={r.status === "verified" ? "ok" : "warn"}>{r.status}</Tag>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 10.5 }}>
                    <div>
                      <span className="cs-dim cs-mono" style={{ fontSize: 8.5, letterSpacing: "0.2em", textTransform: "uppercase" }}>Origin</span>
                      <div style={{ color: "var(--ink-2)", marginTop: 2 }}>{r.origin ?? r.set_by}</div>
                    </div>
                    <div>
                      <span className="cs-dim cs-mono" style={{ fontSize: 8.5, letterSpacing: "0.2em", textTransform: "uppercase" }}>Used</span>
                      <div className="cs-mono" style={{ color: "var(--ink-2)", marginTop: 2 }}>{r.used_count ?? 0}× by agents</div>
                    </div>
                  </div>
                  {r.confidence != null && (
                    <div style={{ marginTop: 10 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, marginBottom: 5 }}>
                        <span className="cs-mono cs-dim" style={{ letterSpacing: "0.2em", textTransform: "uppercase" }}>Confidence</span>
                        <span className="cs-mono" style={{ color: "var(--violet)" }}>{r.confidence}%</span>
                      </div>
                      <Progress value={r.confidence} tone="cyan" />
                    </div>
                  )}
                  <div className="cs-mono cs-dim" style={{ fontSize: 9.5, marginTop: 9 }}>
                    {r.evidence_count != null && `${r.evidence_count} supporting evidence points · `}set {r.at} · {r.set_by}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
