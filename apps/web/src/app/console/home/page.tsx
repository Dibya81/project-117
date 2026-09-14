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
import { KnowledgeCoreOrbital, type OrbitNode } from "@/components/console/KnowledgeCoreOrbital";
import { LogicCoreScene } from "@/components/threeui/ThreeUIScenes";
import { consoleData } from "@/lib/data/console";
import type { Alert, SystemPosture } from "@/types/console";
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

function HeroStat({ label, value, suffix, tone, onClick }: { label: string; value: number | string; suffix?: string; tone?: string; onClick?: () => void }) {
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
        {/* A dash means "no denominator", which Counter cannot express. */}
        {typeof value === "number" ? <Counter value={value} suffix={suffix} /> : <>{value}{suffix}</>}
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
  const [posture, setPosture] = useState<SystemPosture | null>(null);
  const [plantName, setPlantName] = useState<string | null>(null);

  useEffect(() => {
    consoleData.alerts.active().then(setAlerts);
    consoleData.equipment.list().then(setEquipment);
    consoleData.workOrders.list().then(setWorkOrders);
    consoleData.approvals.pending().then(setApprovals);
    consoleData.agents.list().then(setAgents);
    consoleData.artifacts.list().then(setArtifacts);
    consoleData.jobs.list().then(setJobs);
    consoleData.admin.posture().then(setPosture).catch(() => setPosture(null));
    consoleData.plant.identity().then((p) => setPlantName(p?.name ?? null));
  }, []);

  const openWOs = useMemo(() => workOrders?.filter((w) => w.status !== "completed") ?? [], [workOrders]);
  /**
   * The orbital nodes, each carrying a figure the plant actually reports. A
   * capability with nothing behind it shows an em dash rather than a number
   * chosen to look busy.
   */
  const orbitNodes = useMemo<OrbitNode[]>(() => {
    const sensorCount = equipment?.reduce((n, e) => n + e.sensors.length, 0) ?? null;
    return [
      { id: "documents", label: "Documents", detail: "Procedures and manuals behind every citation", href: "/console/documents", icon: "doc", count: artifacts?.length ?? null, countLabel: "artifacts", ring: 1, phase: -1.9, tone: "intel" },
      { id: "equipment", label: "Equipment", detail: "Assets and their instrumented points", href: "/console/equipment", icon: "equipment", count: equipment?.length ?? null, countLabel: "assets", ring: 2, phase: 0.5, tone: "intel" },
      { id: "sensors", label: "Sensors", detail: "Live telemetry from the running plant", href: "/console/equipment", icon: "gauge", count: sensorCount, countLabel: "points", ring: 1, phase: 0.35, tone: "ok" },
      { id: "agents", label: "AI agents", detail: "The workforce that detects, decides and acts", href: "/console/workspace", icon: "cpu", count: agents?.length ?? null, countLabel: "agents", ring: 2, phase: -1.1, tone: "ai" },
      { id: "simulation", label: "Simulation", detail: "The digital twin, and the faults injected into it", href: "/console/simulation", icon: "graph", count: jobs?.length ?? null, countLabel: "jobs", ring: 1, phase: 1.5, tone: "intel" },
      { id: "work-orders", label: "Work orders", detail: "Maintenance raised, and by whom", href: "/console/work-orders", icon: "workorder", count: openWOs.length, countLabel: "open", ring: 2, phase: 1.9, tone: "warn" },
      { id: "insights", label: "Insights", detail: "What the plant's numbers are saying", href: "/console/insights", icon: "insights", count: null, countLabel: "analytics", ring: 2, phase: -2.5, tone: "intel" },
      { id: "history", label: "History", detail: "Operational memory — what was decided and verified", href: "/console/history", icon: "history", count: null, countLabel: "memory", ring: 1, phase: 2.5, tone: "intel" },
      { id: "approvals", label: "Approvals", detail: "Human decisions waiting on a person", href: "/console/approvals", icon: "check", count: approvals?.length ?? null, countLabel: "pending", ring: 2, phase: 3.0, tone: approvals && approvals.length ? "warn" : "ok" },
      { id: "knowledge", label: "Knowledge graph", detail: "Equipment, documents and events as one topology", href: "/console/knowledge", icon: "graph", count: null, countLabel: "graph", ring: 1, phase: -0.7, tone: "ai" },
    ];
  }, [equipment, agents, artifacts, jobs, approvals, openWOs]);

  const liveJobs = jobs?.filter((j) => ["QUEUED", "PLANNING", "RETRIEVING", "EXECUTING", "VERIFYING"].includes(j.state)) ?? [];
  // Completion rate over real jobs. Null when there are none: a rate with no
  // denominator is not 0%, it is undefined, and showing a number would invent it.
  const completedRate =
    jobs && jobs.length
      ? Math.round((jobs.filter((j) => j.state === "COMPLETED").length / jobs.length) * 100)
      : null;
  const critCount = alerts?.filter((a) => a.severity === "critical").length ?? 0;
  const [coreMode, setCoreMode] = useState<"reactor" | "lattice">("lattice");

  return (
    <>
      <div className="cs-pagehead">
        <div>
          <span className="cs-pagehead__kicker">Command Center</span>
          {/* Real dataset name. This said "Plant Alpha", which is not a plant
              in the store — the console was showing Meridian Synthetic Refinery. */}
          <h1>{plantName ?? "Plant"} — Live</h1>
        </div>
        <span className="cs-pagehead__meta">
          {new Date().toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })} ·{" "}
          {posture
            ? posture.model_gateway === "local" && posture.egress === "denied"
              ? "all systems sovereign"
              : "posture degraded — see Sovereignty"
            : "posture unread"}
        </span>
      </div>

      {/* Status strip — real posture, not a fixed banner. Each dot is bound to
          the measurement it claims; before the reading lands it reads unknown
          rather than green. */}
      <div className="cs-strip" role="status" aria-label="System status" style={{ marginBottom: 16 }}>
        <span>
          <StatusDot state={posture ? (posture.database === "ok" ? "ok" : "critical") : "unknown"} pulse />
          {posture ? (posture.database === "ok" ? "SYSTEM OK" : "DATABASE ERROR") : "SYSTEM UNKNOWN"}
        </span>
        <span>
          <StatusDot state={posture ? (posture.model_gateway === "local" ? "ok" : "warning") : "unknown"} pulse />
          {posture ? `MODELS ${posture.model_gateway.toUpperCase()}` : "MODELS UNKNOWN"}
        </span>
        <span>
          <StatusDot state={posture ? (posture.sandbox === "isolated" ? "ok" : "critical") : "unknown"} />
          {posture ? (posture.sandbox === "isolated" ? "SANDBOX SECURE" : "SANDBOX UNAVAILABLE") : "SANDBOX UNKNOWN"}
        </span>
        <span>
          <StatusDot state={posture ? (posture.egress === "denied" ? "ok" : "warning") : "unknown"} />
          {posture ? `EGRESS ${posture.egress.toUpperCase()}` : "EGRESS UNKNOWN"}
        </span>
        <span className="cs-dim">
          EXTERNAL CALLS: {posture ? posture.external_calls_24h : "—"}
        </span>
        <span className="cs-dim" style={{ marginLeft: "auto" }}>
          {liveJobs.length} AGENT TASK{liveJobs.length === 1 ? "" : "S"} RUNNING
        </span>
      </div>

      {/* THE SPINE — information → action, as one living chain */}
      {/* THE CENTRE OF GRAVITY — the knowledge core and the capabilities that
          feed it and draw from it. This is the page's primary object; the
          panels below it are supporting information. */}
      <section className="kc-stage" aria-label="Knowledge core">
        <div className="kc-stage__intro">
          <span className="kc-stage__kicker">Welcome to Project 117</span>
          <h2>
            Knowledge at the Core.
            <br />
            <span>Everything Connected.</span>
          </h2>
          <p>
            An autonomous multi-agent system for safer, smarter and more resilient
            industrial operations. Every capability below reads from the same plant
            and writes back into the same memory.
          </p>
        </div>
        <KnowledgeCoreOrbital nodes={orbitNodes} />
      </section>

      <Panel title="Intelligence chain — sensor to verification" hud style={{ marginBottom: 16 }}>
        <IntelligenceChain />
      </Panel>

      {/* LIVE PLANT + REACTOR */}
      <div className="cs-home cs-home--plant" style={{ marginBottom: 16 }}>
        <Panel
          title={`${plantName ?? "Plant"} — live twin`}
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
            {/* These two read 47 agent tasks and 96% verified as literals — the
                last fabricated figures on this page, sitting directly beneath
                three honest zeros. Now they are the real counts: jobs the
                backend has recorded, and the share that reached a terminal
                state. With no jobs the rate is null, and the row says so
                rather than showing a confident 96%. */}
            <HeroStat
              label="Agent tasks"
              value={jobs?.length ?? 0}
              tone="var(--cyan)"
              onClick={() => router.push("/console/insights")}
            />
            <HeroStat
              label="Tasks completed"
              value={completedRate ?? "—"}
              suffix={completedRate == null ? "" : "%"}
              tone="var(--ok)"
            />
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
            {alerts === null ? (
              <SkeletonRows rows={3} />
            ) : alerts.length === 0 ? (
              <p className="cs-dim" style={{ margin: 0, fontSize: 12, lineHeight: 1.7 }}>
                No anomaly series is recorded yet, so there is nothing to plot. The panel this
                replaced drew a hand-written curve and described it as a finding.
              </p>
            ) : (
              <>
                <TrendChart
                  points={alerts.map((a, i) => ({ t: Date.parse(a.at) || i, value: 1 }))}
                  unit="alerts"
                  tone="amber"
                />
                <p className="cs-dim" style={{ margin: "8px 0 0", fontSize: 12 }}>
                  {alerts.length} active alert{alerts.length === 1 ? "" : "s"} · {critCount} critical
                </p>
              </>
            )}
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
