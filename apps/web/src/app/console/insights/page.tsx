"use client";

/**
 * Insights — question-driven analytics, not a chart dump.
 *
 * Every figure on this page is one of exactly two things:
 *
 *  * computed from real rows — equipment from the plant dataset, work orders
 *    and approvals from the local operations store, or
 *  * measured by the running backend process — request counters and per-route
 *    latencies from its metrics registry.
 *
 * The page it replaces showed hardcoded KPIs (anomalies_7d, MTTR, MTBF, a
 * "verification rate"), four hand-written "AI observations" with invented
 * confidence percentages, and attached fabricated equipment tags to each. None
 * of it came from the plant. Where the backend genuinely has nothing — trend
 * history is not persisted yet — this page says so instead of drawing a line.
 */
import { useEffect, useState } from "react";
import { Panel, Progress, SkeletonRows, StatusDot } from "@/components/ui/primitives";
import { TrendChart } from "@/components/ui/TrendChart";
import { Counter } from "@/components/fx/Counter";
import { Reveal } from "@/components/fx/Reveal";
import { consoleData } from "@/lib/data/console";
import { useRouter } from "next/navigation";
import type { AnalyticsSummary, AnalyticsTrends } from "@/lib/api";

function BigStat({
  label,
  value,
  suffix,
  decimals = 0,
  tone,
  detail,
}: {
  label: string;
  value: number;
  suffix?: string;
  decimals?: number;
  tone?: string;
  detail?: string;
}) {
  return (
    <div className="cs-kpi" style={{ textAlign: "center", padding: "20px 12px" }}>
      <div className="cs-kpi__label" style={{ marginBottom: 9 }}>{label}</div>
      <div
        className="cs-mono"
        style={{ fontSize: 30, fontWeight: 750, color: tone ?? "var(--ink-1)", letterSpacing: "-0.02em" }}
      >
        <Counter value={value} suffix={suffix} decimals={decimals} />
      </div>
      {detail && (
        <div className="cs-mono" style={{ marginTop: 6, fontSize: 9, letterSpacing: "0.14em", color: "var(--ink-3)", textTransform: "uppercase" }}>
          {detail}
        </div>
      )}
    </div>
  );
}

/**
 * The series the backend can produce, each titled by the question it answers.
 * Names match `SERIES` in backend/api/src/routes/analytics.py; a series the
 * backend does not know is not shown.
 */
const SERIES_QUESTIONS: Record<string, { question: string; unit: string; tone: "cyan" | "amber" | "red" }> = {
  vibrationC3: { question: "Is C-3 vibration drifting toward its limit?", unit: "mm/s", tone: "red" },
  workOrdersOpened: { question: "How much maintenance work is opening?", unit: "orders", tone: "amber" },
  workOrdersClosed: { question: "How much maintenance work is closing?", unit: "orders", tone: "cyan" },
  aiTasksCompleted: { question: "How much analysis is the AI workforce completing?", unit: "tasks", tone: "cyan" },
  verificationPassRate: { question: "What share of generated answers pass verification?", unit: "%", tone: "cyan" },
  mttrDays: { question: "How long does a repair actually take?", unit: "days", tone: "amber" },
};

export default function InsightsPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [trends, setTrends] = useState<AnalyticsTrends | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    consoleData.analytics
      .summary()
      .then((s) => { if (alive) setSummary(s); })
      .catch(() => { if (alive) setFailed(true); });
    consoleData.analytics
      .trends()
      .then((t) => { if (alive) setTrends(t); })
      // A trends failure must not blank the page: the counters above are
      // independently sourced and still true.
      .catch(() => { if (alive) setTrends({ series: {}, available: [], source: "" }); });
    return () => { alive = false; };
  }, []);

  if (failed) {
    return (
      <Panel>
        <p style={{ margin: 0, fontSize: 13, color: "var(--ink-2)" }}>
          The analytics endpoint did not answer, so no figures can be reported. This is not a
          zero — it is an unknown, and the page will not dress it up as one.
        </p>
      </Panel>
    );
  }

  const attention = summary ? summary.equipment.critical.length + summary.equipment.warning.length : 0;
  const requests = summary?.platform.counters["http.requests_total"] ?? 0;
  const routes = summary ? Object.keys(summary.platform.durations).length : 0;

  // Charts are drawn only for series the backend actually returned points for.
  const drawn = trends
    ? Object.entries(SERIES_QUESTIONS).filter(([name]) => (trends.series[name]?.length ?? 0) > 0)
    : [];

  return (
    <>
      <div className="cs-pagehead">
        <div>
          <span className="cs-pagehead__kicker">Plant</span>
          <h1>Insights</h1>
        </div>
        <span className="cs-pagehead__meta">every chart answers a question · source noted on each</span>
      </div>

      <div className="cs-kpis" style={{ marginBottom: 22 }}>
        {!summary ? (
          <Panel><SkeletonRows rows={2} /></Panel>
        ) : (
          <>
            <BigStat label="Equipment monitored" value={summary.equipment.total} detail={Object.keys(summary.equipment.byStatus).join(" · ") || "no status data"} />
            <BigStat
              label="Needs attention"
              value={attention}
              tone={attention ? "var(--warn)" : "var(--ok)"}
              detail={`${summary.equipment.critical.length} critical · ${summary.equipment.warning.length} warning`}
            />
            <BigStat label="Open work orders" value={summary.workOrders.open} detail={`${summary.workOrders.total} total`} />
            <BigStat label="High priority open" value={summary.workOrders.highPriorityOpen} tone={summary.workOrders.highPriorityOpen ? "var(--warn)" : undefined} />
            <BigStat label="Approvals pending" value={summary.approvals.pending} tone={summary.approvals.pending ? "var(--warn)" : undefined} detail={`${summary.approvals.total} total`} />
            <BigStat label="API requests served" value={requests} tone="var(--cyan)" detail={`${routes} routes measured`} />
          </>
        )}
      </div>

      {summary && (
        <Reveal>
          <Panel title="Where do these numbers come from?" style={{ marginBottom: 22 }}>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 12 }}>
              {Object.entries(summary.sources).map(([key, value]) => (
                <span key={key} className="cs-chip" style={{ cursor: "default" }}>
                  {key}: <span className="cs-mono" style={{ marginLeft: 6 }}>{value}</span>
                </span>
              ))}
            </div>
            <div style={{ borderTop: "1px solid var(--line)", paddingTop: 4 }}>
              {Object.entries(summary.platform.durations)
                .sort(([, a], [, b]) => b.mean_ms - a.mean_ms)
                .slice(0, 6)
                .map(([route, stat]) => (
                  <div
                    key={route}
                    style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 2px", borderBottom: "1px dashed var(--line)", fontSize: 12.5 }}
                  >
                    <span className="cs-mono" style={{ color: "var(--ink-2)", minWidth: 250 }}>{route}</span>
                    <span className="cs-mono cs-dim" style={{ fontSize: 10 }}>{stat.count} req</span>
                    <span style={{ flex: 1, maxWidth: 160 }}>
                      <Progress value={Math.min(100, (stat.mean_ms / 50) * 100)} tone="cyan" />
                    </span>
                    <span className="cs-mono" style={{ marginLeft: "auto", fontSize: 12 }}>{stat.mean_ms.toFixed(1)} ms mean</span>
                  </div>
                ))}
              {Object.keys(summary.platform.durations).length === 0 && (
                <p className="cs-dim" style={{ margin: 0, fontSize: 12.5, padding: "10px 2px" }}>
                  No route has been exercised since this process started.
                </p>
              )}
            </div>
            <p className="cs-mono" style={{ margin: "12px 0 0", fontSize: 9, letterSpacing: "0.18em", color: "var(--ink-3)", textTransform: "uppercase" }}>
              computed {summary.computedAt}
            </p>
          </Panel>
        </Reveal>
      )}

      {!trends ? (
        <Panel><SkeletonRows rows={6} label="Reading trend series…" /></Panel>
      ) : drawn.length === 0 ? (
        <Panel title="Trend history">
          <p style={{ margin: 0, fontSize: 13, color: "var(--ink-2)", lineHeight: 1.7 }}>
            No trend series has been recorded yet, so there is nothing to plot. The backend
            defines {trends.available.length} series ({trends.available.join(", ")}) and returns
            them empty until a history store exists — this page will not draw a line through
            numbers that were never measured.
          </p>
          <p className="cs-mono" style={{ margin: "12px 0 0", fontSize: 9, letterSpacing: "0.18em", color: "var(--ink-3)", textTransform: "uppercase" }}>
            source: {trends.source || "operations"}
          </p>
        </Panel>
      ) : (
        <div className="cs-grid-2">
          {drawn.map(([name, meta], i) => {
            const points = trends.series[name];
            const latest = points[points.length - 1]?.value;
            const first = points[0]?.value;
            const delta = first != null && latest != null ? latest - first : null;
            return (
              <Reveal key={name} delay={i * 110}>
                <Panel title={meta.question} hud={i === 0}>
                  <TrendChart points={points} unit={meta.unit} tone={meta.tone} live={i === 0} />
                  <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 10, flexWrap: "wrap" }}>
                    <span className="cs-mono cs-dim" style={{ fontSize: 10 }}>
                      {points.length} points
                      {latest != null && ` · latest ${latest} ${meta.unit}`}
                      {delta != null && ` · ${delta >= 0 ? "+" : ""}${delta.toFixed(2)} over window`}
                    </span>
                  </div>
                  <p className="cs-mono" style={{ margin: "12px 0 0", fontSize: 9, letterSpacing: "0.18em", color: "var(--ink-3)", textTransform: "uppercase" }}>
                    source: {trends.source || "operations"}
                  </p>
                </Panel>
              </Reveal>
            );
          })}
        </div>
      )}
    </>
  );
}
