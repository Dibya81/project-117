"use client";

/**
 * Home / Command Center — a live industrial environment, not a dashboard.
 * Status strip → intelligence chain (the product spine) → live plant map
 * (hover: telemetry · click: dive into the twin) + reactor/counters →
 * ranked tri-column: Needs Attention | Plant State | AI Activity.
 */
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Tag, timeAgo } from "@/components/ui/primitives";
import { KnowledgeCore3D, type Satellite } from "@/components/console/KnowledgeCore3D";
import { consoleData } from "@/lib/data/console";
import type { Alert, SystemPosture } from "@/types/console";
import type { AgentDescriptor, ApprovalRequest, ArtifactRecord, Equipment, JobRecord, WorkOrder } from "@/types";

/** Deterministic 2 Hz drift so telemetry feels alive, not random. */
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
  /** The nine systems the reference puts in orbit, each with its live figure. */
  const satellites = useMemo<Satellite[]>(() => {
    const sensorCount = equipment?.reduce((n, e) => n + e.sensors.length, 0) ?? null;
    return [
      { id: "simulation", label: "Simulation", descriptor: "Test Scenarios", detail: "The digital twin and the faults injected into it", href: "/console/simulation", count: jobs?.length ?? null, countLabel: "jobs", ring: 0, phase: 0.0, tone: "#3b82f6", icon: "play" },
      { id: "operations", label: "Operations", descriptor: "Live Plant Overview", detail: "The running plant, area by area", href: "/console/equipment", count: equipment?.length ?? null, countLabel: "assets", ring: 1, phase: 0.79, tone: "#0ea5e9", icon: "pulse" },
      { id: "documents", label: "Documents", descriptor: "Procedures & Manuals", detail: "The procedures behind every citation", href: "/console/documents", count: artifacts?.length ?? null, countLabel: "artifacts", ring: 1, phase: 2.36, tone: "#6366f1", icon: "doc" },
      { id: "equipment", label: "Equipment", descriptor: "Monitors & Sensors", detail: "Assets and their instrumented points", href: "/console/equipment", count: sensorCount, countLabel: "points", ring: 0, phase: 1.57, tone: "#0891b2", icon: "wrench" },
      { id: "agents", label: "AI Agents", descriptor: "Detect • Decide • Act", detail: "The workforce that detects, decides and acts", href: "/console/workspace", count: agents?.length ?? null, countLabel: "agents", ring: 0, phase: 3.14, tone: "#7c3aed", icon: "cpu" },
      { id: "work-orders", label: "Work Orders", descriptor: "Execute & Track", detail: "Maintenance raised, and by whom", href: "/console/work-orders", count: openWOs.length, countLabel: "open", ring: 1, phase: 3.93, tone: "#f59e0b", icon: "workorder" },
      { id: "insights", label: "Insights", descriptor: "Predict & Optimize", detail: "What the plant's numbers are saying", href: "/console/insights", count: null, countLabel: "analytics", ring: 0, phase: 4.71, tone: "#2563eb", icon: "insights" },
      { id: "history", label: "History", descriptor: "Operational Memory", detail: "Decided, acted, verified, remembered", href: "/console/history", count: null, countLabel: "memory", ring: 1, phase: 5.50, tone: "#64748b", icon: "history" },
    ];
  }, [equipment, agents, artifacts, jobs, openWOs]);

  const sensorTotal = equipment?.reduce((n, e) => n + e.sensors.length, 0) ?? 0;
  /** Health from the equipment the backend reports, not a decorative score. */
  const health = useMemo(() => {
    if (!equipment?.length) return 100;
    const ok = equipment.filter((e) => e.status === "ok").length;
    return (ok / equipment.length) * 100;
  }, [equipment]);
  const sim = { alarms: alerts?.length ?? 0 };
  const [reduceMotion, setReduceMotion] = useState(false);
  useEffect(() => {
    setReduceMotion(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }, []);

  /** The most recent things that actually happened, from the audit-backed feed. */
  const [recent, setRecent] = useState<{ id: string; text: string; when: string; tone: string }[]>([]);
  useEffect(() => {
    let alive = true;
    consoleData.history
      .list()
      .then((ev) => {
        if (!alive) return;
        setRecent(
          ev.slice(0, 5).map((e) => ({
            id: e.id,
            text: e.title.replace(/\./g, " ").replace(/_/g, " "),
            when: e.at ? timeAgo(e.at) : "",
            tone:
              e.kind === "anomaly" ? "crit" : e.kind === "recommendation" ? "ai" : "ok",
          })),
        );
      })
      .catch(() => {
        /* no history: the panel says so rather than inventing events */
      });
    return () => {
      alive = false;
    };
  }, []);

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
          <span className="cs-pagehead__kicker">Welcome to Project 117</span>
          <h1 style={{ maxWidth: 640 }}>
            Knowledge at the Core.
            <br />
            <span style={{ color: "var(--blue)" }}>Everything Connected.</span>
          </h1>
        </div>
        <div className="cs-pagehead__actions" style={{ marginLeft: "auto", display: "flex", gap: 10, alignItems: "center" }}>
          <button className="cs-btn cs-btn--primary" onClick={() => router.push("/console/simulation")}>
            Run simulation →
          </button>
        </div>
      </div>

      <p className="home-lede">
        An autonomous multi-agent system for safer, smarter, and more resilient
        industrial operations. {plantName ?? "The plant"}&apos;s documents, equipment, history
        and agent memory in one place — and every capability reading from it.
      </p>

      {/* MAIN — the core and the systems orbiting it, with the two operational
          panels the reference places to the right. */}
      <div className="home-main">
        <KnowledgeCore3D
          satellites={satellites}
          reduced={reduceMotion}
          onOpenCore={() => router.push("/console/knowledge")}
        />

        <aside className="home-side">
          <section className="home-card" data-testid="plant-status">
            <header>
              <span>Plant status</span>
              <Tag tone={critCount ? "crit" : "ok"}>{critCount ? `${critCount} critical` : "Live"}</Tag>
            </header>
            <div className="home-stat">
              <b>{(equipment?.length ?? 0).toLocaleString()}</b>
              <span>Equipment</span>
            </div>
            <div className="home-stat">
              <b>{sensorTotal.toLocaleString()}</b>
              <span>Sensors</span>
            </div>
            <div className="home-stat">
              <b>{agents?.length ?? 0}</b>
              <span>Active agents</span>
            </div>
            <div className="home-stat">
              <b className={critCount ? "is-crit" : undefined}>{critCount}</b>
              <span>Critical alerts</span>
            </div>
          </section>

          <section className="home-card" data-testid="recent-activity">
            <header>
              <span>Recent activity</span>
            </header>
            {recent.length === 0 ? (
              <p className="home-empty">
                Nothing has been recorded yet. Activity appears here as the platform
                produces it.
              </p>
            ) : (
              <ul className="home-feed">
                {recent.map((r) => (
                  <li key={r.id}>
                    <span className={`home-feed__dot is-${r.tone}`} />
                    <span className="home-feed__text">{r.text}</span>
                    <span className="home-feed__at">{r.when}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>

      {/* BOTTOM — four compact sections, and nothing more. */}
      <div className="home-strip">
        <section className="home-card home-card--row" data-testid="system-health">
          <div>
            <span className="home-card__label">System health</span>
            <b className="home-card__big">{health.toFixed(1)}%</b>
          </div>
          <span className="home-card__sub">
            {sim.alarms > 0 ? `${sim.alarms} alarm(s) open` : "All systems operational"}
          </span>
        </section>

        <section className="home-card home-card--row" data-testid="active-agents">
          <div>
            <span className="home-card__label">Active agents</span>
            <b className="home-card__big">{liveJobs.length || (agents?.length ?? 0)}</b>
          </div>
          <span className="home-card__sub">
            {liveJobs.length ? `${liveJobs.length} working now` : `${agents?.length ?? 0} registered`}
          </span>
        </section>

        <section className="home-card home-card--row" data-testid="pending-approvals">
          <div>
            <span className="home-card__label">Pending approvals</span>
            <b className="home-card__big">{approvals?.length ?? 0}</b>
          </div>
          <span className="home-card__sub">
            {approvals?.length ? "require review" : "0 require review"}
          </span>
        </section>

        <section className="home-card home-card--row" data-testid="quick-actions">
          <span className="home-card__label">Quick actions</span>
          <div className="home-quick">
            <button onClick={() => router.push("/console/simulation")}>Run simulation</button>
            <button onClick={() => router.push("/console/workspace")}>Ask AI</button>
            <button onClick={() => router.push("/console/documents")}>Upload document</button>
            <button onClick={() => router.push("/console/insights")}>View insights</button>
          </div>
        </section>
      </div>
    </>
  );
}
