"use client";

/**
 * Home / Command Center — a live industrial environment, not a dashboard.
 * Status strip → intelligence chain (the product spine) → live plant map
 * (hover: telemetry · click: dive into the twin) + reactor/counters →
 * ranked tri-column: Needs Attention | Plant State | AI Activity.
 */
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Panel, StatusDot, Tag, SkeletonRows, timeAgo } from "@/components/ui/primitives";
import { TrendChart } from "@/components/ui/TrendChart";
import { ReactorOrb } from "@/components/fx/ReactorOrb";
import { IntelligenceCore } from "@/components/fx/IntelligenceCore";
import { Counter } from "@/components/fx/Counter";
import { PlantMap } from "@/components/console/PlantMap";
import { IntelligenceChain } from "@/components/console/IntelligenceChain";
import { LogicCoreScene } from "@/components/threeui/ThreeUIScenes";
import { consoleData } from "@/lib/data/console";
import { INSIGHTS } from "@/lib/mock/console2";
import type { Alert } from "@/types/console";
import type { AgentDescriptor, ApprovalRequest, ArtifactRecord, Equipment, JobRecord, WorkOrder } from "@/types";

/** Deterministic 2 Hz drift so telemetry feels alive, not random. */
function useLiveSensor(base: number, seed: number, amplitude = 0.04) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = setInterval(() => setTick((t) => t + 1), 2000);
    return () => clearInterval(id);
  }, []);
  return base + Math.sin(tick * 0.9 + seed * 2.3) * base * amplitude;
}

function LiveSensorValue({ value, seed, unit }: { value: number; seed: number; unit: string }) {
  const v = useLiveSensor(value, seed);
  return (
    <span className="cs-mono" style={{ fontSize: 11, color: "var(--ink-2)" }}>
      {v.toFixed(1)} {unit}
    </span>
  );
}

function HeroStat({ label, value, suffix, tone, onClick }: { label: string; value: number; suffix?: string; tone?: string; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "baseline",
        justifyContent: "space-between",
        gap: 10,
        width: "100%",
        padding: "10px 2px",
        border: "0",
        borderBottom: "1px dashed var(--line)",
        background: "none",
        color: "inherit",
        cursor: onClick ? "pointer" : "default",
        font: "inherit",
        textAlign: "left",
      }}
    >
      <span className="cs-mono cs-dim" style={{ fontSize: 9, letterSpacing: "0.24em", textTransform: "uppercase" }}>
        {label}
      </span>
      <span className="cs-mono" style={{ fontSize: 21, fontWeight: 700, color: tone ?? "var(--ink-1)" }}>
        <Counter value={value} suffix={suffix} />
      </span>
    </button>
  );
}

export default function HomePage() {
  const router = useRouter();
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [equipment, setEquipment] = useState<Equipment[] | null>(null);
  const [workOrders, setWorkOrders] = useState<WorkOrder[] | null>(null);
  const [approvals, setApprovals] = useState<ApprovalRequest[] | null>(null);
  const [agents, setAgents] = useState<AgentDescriptor[] | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactRecord[] | null>(null);
  const [jobs, setJobs] = useState<JobRecord[] | null>(null);

  useEffect(() => {
    consoleData.alerts.active().then(setAlerts);
    consoleData.equipment.list().then(setEquipment);
    consoleData.workOrders.list().then(setWorkOrders);
    consoleData.approvals.pending().then(setApprovals);
    consoleData.agents.list().then(setAgents);
    consoleData.artifacts.list().then(setArtifacts);
    consoleData.jobs.list().then(setJobs);
  }, []);

  const openWOs = useMemo(() => workOrders?.filter((w) => w.status !== "completed") ?? [], [workOrders]);
  const anomalies = INSIGHTS[0];
  const liveJobs = jobs?.filter((j) => ["QUEUED", "PLANNING", "RETRIEVING", "EXECUTING", "VERIFYING"].includes(j.state)) ?? [];
  const critCount = alerts?.filter((a) => a.severity === "critical").length ?? 0;
  const [coreMode, setCoreMode] = useState<"reactor" | "lattice">("lattice");

  return (
    <>
      <div className="cs-pagehead">
        <div>
          <span className="cs-pagehead__kicker">Command Center</span>
          <h1>Plant Alpha — Live</h1>
        </div>
        <span className="cs-pagehead__meta">
          {new Date().toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })} · all systems sovereign
        </span>
      </div>

      {/* status strip */}
      <div className="cs-strip" role="status" aria-label="System status" style={{ marginBottom: 16 }}>
        <span><StatusDot state="ok" pulse /> SYSTEM OK</span>
        <span><StatusDot state="ok" pulse /> MODELS LOCAL</span>
        <span><StatusDot state="ok" /> SANDBOX SECURE</span>
        <span><StatusDot state="ok" /> EGRESS DENIED</span>
        <span className="cs-dim">EXTERNAL CALLS: 0</span>
        <span className="cs-dim" style={{ marginLeft: "auto" }}>
          {liveJobs.length} AGENT TASK{liveJobs.length === 1 ? "" : "S"} RUNNING
        </span>
      </div>

      {/* THE SPINE — information → action, as one living chain */}
      <Panel title="Intelligence chain — sensor to verification" hud style={{ marginBottom: 16 }}>
        <IntelligenceChain />
      </Panel>

      {/* LIVE PLANT + REACTOR */}
      <div className="cs-home cs-home--plant" style={{ marginBottom: 16 }}>
        <Panel
          title="Plant Alpha — live twin"
          hud
          glow
          pad={false}
          actions={<span className="cs-mono cs-dim" style={{ fontSize: 9, letterSpacing: "0.2em" }}>HOVER = TELEMETRY · CLICK = DIVE</span>}
        >
          <div className="cs-scan" style={{ borderRadius: "0 0 10px 10px" }}>
            {!equipment ? <SkeletonRows rows={5} /> : <PlantMap equipment={equipment} />}
          </div>
        </Panel>

        <Panel
          title="Project 117 intelligence core"
          pad={false}
          actions={
            <div style={{ display: "flex", gap: 4 }}>
              <button
                type="button"
                onClick={() => setCoreMode("lattice")}
                className="cs-chip"
                style={{
                  cursor: "pointer",
                  fontSize: 8.5,
                  padding: "1px 6px",
                  borderColor: coreMode === "lattice" ? "var(--cyan)" : undefined,
                  color: coreMode === "lattice" ? "var(--cyan)" : "var(--ink-3)",
                }}
              >
                LATTICE
              </button>
              <button
                type="button"
                onClick={() => setCoreMode("reactor")}
                className="cs-chip"
                style={{
                  cursor: "pointer",
                  fontSize: 8.5,
                  padding: "1px 6px",
                  borderColor: coreMode === "reactor" ? "var(--cyan)" : undefined,
                  color: coreMode === "reactor" ? "var(--cyan)" : "var(--ink-3)",
                }}
              >
                REACTOR
              </button>
            </div>
          }
        >
          <div className="cs-core-visual">
            {coreMode === "reactor" ? <ReactorOrb size="compact" /> : coreMode === "lattice" ? <LogicCoreScene /> : <IntelligenceCore size="compact" />}
          </div>
          <div style={{ padding: "4px 18px 16px", display: "flex", flexDirection: "column" }}>
            <HeroStat label="Active alerts" value={alerts?.length ?? 0} tone={critCount ? "var(--crit)" : "var(--warn)"} onClick={() => router.push("/console/equipment")} />
            <HeroStat label="Pending approvals" value={approvals?.length ?? 0} tone="var(--warn)" onClick={() => router.push("/console/approvals")} />
            <HeroStat label="Open work orders" value={openWOs.length} onClick={() => router.push("/console/work-orders")} />
            <HeroStat label="Agent tasks · 7d" value={47} tone="var(--cyan)" onClick={() => router.push("/console/insights")} />
            <HeroStat label="Verified" value={96} suffix="%" tone="var(--ok)" />
          </div>
        </Panel>
      </div>

      <div className="cs-home">
        {/* NEEDS ATTENTION — ranked by severity */}
        <Panel title="Needs attention" pad={false}>
          {!alerts || !approvals ? (
            <SkeletonRows rows={4} />
          ) : (
            <div className="cs-fade-list">
              {alerts
                .slice()
                .sort((a, b) => (a.severity === "critical" ? -1 : b.severity === "critical" ? 1 : 0))
                .map((a) => (
                  <button
                    key={a.id}
                    className="cs-row"
                    style={{ width: "100%", background: "none", border: "0", textAlign: "left", font: "inherit" }}
                    onClick={() => a.equipment_id && router.push(`/console/equipment/${a.equipment_id}`)}
                  >
                    <StatusDot
                      state={a.severity === "critical" ? "critical" : a.severity === "warning" ? "warning" : "unknown"}
                      pulse={a.severity === "critical"}
                    />
                    <span>
                      <div className="cs-row__title">{a.title}</div>
                      <div className="cs-row__sub">{a.detail}</div>
                    </span>
                    <span className="cs-row__meta">
                      <span className="cs-mono cs-dim" style={{ fontSize: 10 }}>{timeAgo(a.at)}</span>
                    </span>
                  </button>
                ))}
              {approvals.map((a) => (
                <button
                  key={a.id}
                  className="cs-row"
                  style={{ width: "100%", background: "none", border: "0", textAlign: "left", font: "inherit" }}
                  onClick={() => router.push("/console/approvals")}
                >
                  <StatusDot state="ai" />
                  <span>
                    <div className="cs-row__title">{a.action}</div>
                    <div className="cs-row__sub">proposed by {a.requested_by} · risk {a.risk}</div>
                  </span>
                  <span className="cs-row__meta"><Tag tone="warn">Approval</Tag></span>
                </button>
              ))}
            </div>
          )}
        </Panel>

        {/* PLANT STATE */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <Panel title="Plant state — by zone" pad={false}>
            {!equipment ? (
              <SkeletonRows rows={5} />
            ) : (
              <div className="cs-fade-list">
                {equipment.map((e, i) => (
                  <button
                    key={e.id}
                    className="cs-row"
                    style={{ width: "100%", background: "none", border: "0", textAlign: "left", font: "inherit" }}
                    onClick={() => router.push(`/console/equipment/${e.id}`)}
                  >
                    <StatusDot state={e.status} pulse={e.status === "critical"} />
                    <span>
                      <div className="cs-row__title">
                        <span className="cs-mono cs-text-cyan">{e.id}</span> · {e.name}
                      </div>
                      <div className="cs-row__sub">{e.zone}</div>
                    </span>
                    <span className="cs-row__meta">
                      {e.sensors[0] && <LiveSensorValue value={e.sensors[0].value} seed={i} unit={e.sensors[0].unit} />}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </Panel>

          <Panel title="Anomalies — 30 days">
            <TrendChart points={anomalies.points} threshold={anomalies.threshold} unit={anomalies.unit} tone="amber" live />
            <p className="cs-dim" style={{ margin: "8px 0 0", fontSize: 12 }}>{anomalies.summary}</p>
          </Panel>
        </div>

        {/* AI ACTIVITY */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <Panel title="AI activity" pad={false}>
            {!agents || !artifacts ? (
              <SkeletonRows rows={4} />
            ) : (
              <div className="cs-fade-list">
                {agents.slice(0, 3).map((a) => (
                  <div key={a.kind} className="cs-row" style={{ cursor: "default" }}>
                    <StatusDot state={a.status === "idle" ? "ok" : "ai"} pulse={a.status !== "idle"} />
                    <span>
                      <div className="cs-row__title">{a.name}</div>
                      <div className="cs-row__sub">{a.status === "idle" ? "Idle — awaiting task" : a.status}</div>
                    </span>
                  </div>
                ))}
                {artifacts.map((art) => (
                  <button
                    key={art.id}
                    className="cs-row"
                    style={{ width: "100%", background: "none", border: "0", textAlign: "left", font: "inherit" }}
                    onClick={() => router.push("/console/workspace")}
                  >
                    <span>
                      <div className="cs-row__title cs-mono" style={{ fontSize: 12 }}>{art.filename}</div>
                      <div className="cs-row__sub">{timeAgo(art.created_at)}</div>
                    </span>
                    <span className="cs-row__meta">{art.verified && <Tag tone="ok">Verified ✓</Tag>}</span>
                  </button>
                ))}
              </div>
            )}
          </Panel>

          <Panel title="Open work orders" pad={false}>
            <div className="cs-fade-list">
              {openWOs.map((w) => (
                <button
                  key={w.id}
                  className="cs-row"
                  style={{ width: "100%", background: "none", border: "0", textAlign: "left", font: "inherit" }}
                  onClick={() => router.push(`/console/work-orders/${w.id}`)}
                >
                  <span>
                    <div className="cs-row__title">
                      <span className="cs-mono cs-text-cyan">{w.id}</span> · {w.title}
                    </div>
                    <div className="cs-row__sub">{w.equipment_id} · {w.assignee}</div>
                  </span>
                  <span className="cs-row__meta">
                    <Tag tone={w.priority === "critical" ? "crit" : w.priority === "high" ? "warn" : undefined}>{w.priority}</Tag>
                  </span>
                </button>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}
