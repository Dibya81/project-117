"use client";

/**
 * Insights — question-driven analytics, not a chart dump.
 * Every section is titled by the question it answers and cites its source.
 */
import { useEffect, useState } from "react";
import { Panel, SkeletonRows, StatusDot } from "@/components/ui/primitives";
import { TrendChart } from "@/components/ui/TrendChart";
import { Counter } from "@/components/fx/Counter";
import { Reveal } from "@/components/fx/Reveal";
import { consoleData } from "@/lib/data/console";
import { useRouter } from "next/navigation";
import { Progress } from "@/components/ui/primitives";
import type { InsightSeries } from "@/types/console";
import type { ANALYTICS_SUMMARY } from "@/lib/mock/console3";

type Summary = typeof ANALYTICS_SUMMARY;

function BigStat({ label, value, suffix, decimals = 0, tone }: { label: string; value: number; suffix?: string; decimals?: number; tone?: string }) {
  return (
    <div
      className="cs-kpi"
      style={{ textAlign: "center", padding: "20px 12px" }}
    >
      <div className="cs-kpi__label" style={{ marginBottom: 9 }}>{label}</div>
      <div className="cs-mono" style={{ fontSize: 30, fontWeight: 750, color: tone ?? "var(--ink-1)", letterSpacing: "-0.02em" }}>
        <Counter value={value} suffix={suffix} decimals={decimals} />
      </div>
    </div>
  );
}

const AI_NOTES: Record<string, { confidence: number; affected: string[] }> = {
  anomalies: { confidence: 92, affected: ["C-3", "V-2210", "P-1042"] },
  effort: { confidence: 88, affected: ["C-3", "P-1042"] },
  degrading: { confidence: 95, affected: ["C-3", "P-1042", "V-2210"] },
  workforce: { confidence: 97, affected: [] },
};

export default function InsightsPage() {
  const router = useRouter();
  const [insights, setInsights] = useState<InsightSeries[] | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);

  useEffect(() => {
    consoleData.insights.list().then(setInsights);
    consoleData.analytics.summary().then(setSummary);
  }, []);

  return (
    <>
      <div className="cs-pagehead">
        <div>
          <span className="cs-pagehead__kicker">Plant</span>
          <h1>Insights</h1>
        </div>
        <span className="cs-pagehead__meta">every chart answers a question · source noted on each</span>
      </div>

      {/* headline counters */}
      <div className="cs-kpis" style={{ marginBottom: 22 }}>
        {!summary ? (
          <Panel><SkeletonRows rows={2} /></Panel>
        ) : (
          <>
            <BigStat label="Anomalies · 7d" value={summary.anomalies_7d} tone="var(--warn)" />
            <BigStat label="Open work orders" value={summary.work_orders_open} />
            <BigStat label="MTTR" value={summary.mttr_hours} suffix=" h" decimals={1} tone="var(--cyan)" />
            <BigStat label="MTBF" value={summary.mtbf_hours} suffix=" h" tone="var(--ok)" />
            <BigStat label="Agent tasks · 7d" value={summary.agent_tasks_7d} tone="var(--cyan)" />
            <BigStat label="Verification rate" value={summary.verification_rate} suffix="%" tone="var(--ok)" />
          </>
        )}
      </div>

      {!insights ? (
        <Panel><SkeletonRows rows={6} label="Converging data sources…" /></Panel>
      ) : (
        <div className="cs-grid-2">
          {insights.map((ins, i) => (
            <Reveal key={ins.id} delay={i * 110}>
              <Panel title={ins.question} hud={i === 0}>
                <TrendChart
                  points={ins.points}
                  threshold={ins.threshold}
                  unit={ins.unit}
                  tone={ins.id === "degrading" ? "red" : ins.id === "anomalies" ? "amber" : "cyan"}
                  live={i === 0}
                />
                <div
                  style={{
                    marginTop: 12,
                    padding: "11px 14px",
                    borderLeft: "2px solid var(--cyan)",
                    background: "rgba(69,213,255,0.05)",
                    borderRadius: "0 8px 8px 0",
                  }}
                >
                  <div className="cs-mono cs-text-cyan" style={{ fontSize: 8.5, letterSpacing: "0.3em", textTransform: "uppercase", marginBottom: 5 }}>
                    AI observation
                  </div>
                  <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.6, color: "var(--ink-1)" }}>{ins.summary}</p>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 10, flexWrap: "wrap" }}>
                    <span style={{ display: "flex", alignItems: "center", gap: 8, flex: "0 0 150px" }}>
                      <Progress value={AI_NOTES[ins.id]?.confidence ?? 90} tone="cyan" />
                    </span>
                    <span className="cs-mono cs-dim" style={{ fontSize: 9.5 }}>
                      confidence {AI_NOTES[ins.id]?.confidence ?? 90}%
                    </span>
                    {(AI_NOTES[ins.id]?.affected ?? []).map((eq) => (
                      <button key={eq} className="cs-chip" onClick={() => router.push(`/console/equipment/${eq}`)}>
                        {eq}
                      </button>
                    ))}
                  </div>
                </div>
                {ins.table && (
                  <div style={{ marginTop: 14, borderTop: "1px solid var(--line)", paddingTop: 4 }}>
                    {ins.table.map((row) => (
                      <div
                        key={row.label}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 10,
                          padding: "8px 2px",
                          borderBottom: "1px dashed var(--line)",
                          fontSize: 12.5,
                        }}
                      >
                        {row.state && <StatusDot state={row.state} />}
                        <span style={{ color: "var(--ink-2)" }}>{row.label}</span>
                        <span className="cs-mono" style={{ marginLeft: "auto", fontSize: 12 }}>{row.value}</span>
                      </div>
                    ))}
                  </div>
                )}
                <p className="cs-mono" style={{ margin: "12px 0 0", fontSize: 9, letterSpacing: "0.18em", color: "var(--ink-3)", textTransform: "uppercase" }}>
                  source: telemetry store · work orders · job ledger
                </p>
              </Panel>
            </Reveal>
          ))}
        </div>
      )}
    </>
  );
}
