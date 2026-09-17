"use client";

/**
 * Home / Command Center — an operational dashboard, not a hero.
 *
 *   Tier 1  a live posture bar: plant · alarm state · engine clock · egress
 *   Tier 2  the vitals — six measured cards, each with a worded status badge
 *   Tier 3  the asset network at 8 columns beside a 4-column action queue
 *   Tier 4  system health · predictive insights · model telemetry
 *   Tier 5  the full-width activity register
 *
 * The 3D Knowledge Core that used to occupy the upper-centre is gone from this
 * page (the component is still used elsewhere). In its place is a real,
 * interactive asset network built from the same knowledge graph the Knowledge
 * Universe renders — filtered to the asset classes an operator scans, coloured
 * by each unit's real dataset `state` and sized by its real `criticality`. A
 * node click is a navigation control: it filters the Action Queue to that asset.
 *
 * Every figure is read from `consoleData`, the simulation stream, or the
 * backend's own endpoints. Nothing here invents a number, a trend, a
 * recommendation or a timestamp: a value that has not loaded renders an em dash,
 * and a widget with no backing data renders an honest empty state.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import {
  Activity,
  ArrowRight,
  CircleAlert,
  CircleCheck,
  Cpu,
  Gauge,
  Play,
  Sparkles,
  TrendingUp,
  TriangleAlert,
  Upload,
} from "lucide-react";
import { Counter } from "@/components/fx/Counter";
import { Tag, timeAgo } from "@/components/ui/primitives";
import { MaterialSegmented } from "@/components/materials/MaterialSegmented";
import { consoleData } from "@/lib/data/console";
import { api } from "@/lib/api";
import { useSimulation } from "@/lib/sim/store";
import { reduceResponseJobs, type ResponseJob } from "@/lib/sim/response";
import { SPRING } from "@/lib/ui/motion";

/**
 * The asset network is the heaviest thing on the page: it builds the plant
 * graph (the 103 KB definition, its sensors, documents, work orders and the
 * materials subgraph), runs a force layout over the filtered set, and mounts the
 * canvas renderer. None of it is needed for the operator's first question —
 * "is anything wrong right now?" — which the posture bar and vitals answer from
 * data already in flight.
 *
 * So it is split out and mounted after first paint behind a placeholder that
 * occupies the exact same box: the vitals, the action queue and the activity
 * register paint first, and the map appears when its chunk lands.
 */
const AssetNetworkMap = dynamic(
  () => import("@/components/knowledge/AssetNetworkMap").then((m) => m.AssetNetworkMap),
  {
    ssr: false,
    loading: () => <div className="home-net home-net--pending" aria-hidden="true" />,
  },
);

import type { Alert, HistoryEvent, SystemPosture } from "@/types/console";
import type { AgentDescriptor, ApprovalRequest, Equipment, JobRecord, WorkOrder } from "@/types";

/* ------------------------------------------------------------- activity feed */

/** The five feeds the operator scans for. Every predicate is data-derived. */
type FeedFilter = "all" | "alerts" | "agents" | "approvals" | "documents";

const FEED_FILTERS: { id: FeedFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "alerts", label: "Alerts" },
  { id: "agents", label: "Agents" },
  { id: "approvals", label: "Approvals" },
  { id: "documents", label: "Documents" },
];

/**
 * Which feed a row belongs to, read off the real action namespace the backend
 * writes (`mobile.login`, `document.uploaded`, `chat.completed`, …) plus the
 * memory stage the adapter derived from it. No row is dropped from "All".
 */
function feedMatches(filter: FeedFilter, e: HistoryEvent): boolean {
  const action = e.title.toLowerCase();
  switch (filter) {
    case "alerts":
      return e.kind === "anomaly" || /failed|rejected/.test(action);
    case "agents":
      return /(^|\.)agent[._]|^chat\.|^model\./.test(action);
    case "approvals":
      return e.kind === "approval" || action.startsWith("approval.");
    case "documents":
      return action.startsWith("document.") || e.kind === "recommendation";
    default:
      return true;
  }
}

/**
 * Severity, from the action namespace and the memory stage. The dot is never
 * the only signal — every row carries the stage as a word in its chip.
 */
const DOT_TONE: Record<HistoryEvent["kind"], "ok" | "warn" | "crit" | "ai" | "neutral"> = {
  anomaly: "crit",
  inspection: "warn",
  decision: "ai",
  approval: "warn",
  maintenance: "ok",
  work_order: "neutral",
  recommendation: "ai",
  event: "neutral",
};

function dotTone(e: HistoryEvent): "ok" | "warn" | "crit" | "ai" | "neutral" {
  if (/failed|rejected/.test(e.title.toLowerCase())) return "crit";
  return DOT_TONE[e.kind];
}

/**
 * The memory stage, mirroring `KIND_STYLE` on /console/history (kept local
 * because this page must not reach into another route's module).
 */
const KIND_CHIP: Record<
  HistoryEvent["kind"],
  { tone?: "ok" | "warn" | "crit" | "ai" | "ember" | "bad"; label: string }
> = {
  anomaly: { tone: "crit", label: "Observed" },
  inspection: { tone: "ember", label: "Observed" },
  decision: { tone: "ai", label: "Decided" },
  approval: { tone: "warn", label: "Decided" },
  maintenance: { tone: "ok", label: "Acted" },
  work_order: { label: "Acted" },
  recommendation: { tone: "ai", label: "Verified" },
  event: { label: "Recorded" },
};

/** The audit record's own clock — 24-hour, zero-padded, locale-independent. */
function clockOf(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString("en-GB", { hour12: false });
}

/** Day bucket for the sticky sub-headers. */
function dayOf(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Undated";
  const midnight = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((midnight(new Date()) - midnight(d)) / 86_400_000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

/** The initial an actor's avatar carries. Never the only identifier — the
 *  actor's full name is rendered beside it. */
function initialOf(actor: string): string {
  const m = actor.trim().match(/[a-z0-9]/i);
  return m ? m[0].toUpperCase() : "·";
}

/* ------------------------------------------------------------------ page */

/** The real per-role model mapping, straight from `GET /api/models`. */
interface ModelTelemetry {
  backend: string | null;
  served: number;
  roles: { role: string; model: string | null }[];
}

const PRIORITY_RANK: Record<WorkOrder["priority"], number> = { critical: 0, high: 1, medium: 2, low: 3 };

export default function HomePage() {
  const router = useRouter();
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [equipment, setEquipment] = useState<Equipment[] | null>(null);
  const [workOrders, setWorkOrders] = useState<WorkOrder[] | null>(null);
  const [approvals, setApprovals] = useState<ApprovalRequest[] | null>(null);
  const [agents, setAgents] = useState<AgentDescriptor[] | null>(null);
  const [jobs, setJobs] = useState<JobRecord[] | null>(null);
  const [posture, setPosture] = useState<SystemPosture | null>(null);
  const [plant, setPlant] = useState<{ id: string; name: string } | null>(null);
  const [models, setModels] = useState<ModelTelemetry | null | undefined>(undefined);

  useEffect(() => {
    consoleData.alerts.active().then(setAlerts);
    consoleData.equipment.list().then(setEquipment);
    consoleData.workOrders.list().then(setWorkOrders);
    consoleData.approvals.pending().then(setApprovals);
    consoleData.agents.list().then(setAgents);
    consoleData.jobs.list().then(setJobs);
    consoleData.admin.posture().then(setPosture).catch(() => setPosture(null));
    consoleData.plant.identity().then(setPlant);

    /**
     * The model endpoint's real shape is `{backend, models, roles}`: what the
     * local gateway serves, and how each role resolves. There is no training
     * progress, no inference ratio and no per-agent model binding anywhere in
     * this system, so none is shown. A failure reads as `null` ("did not
     * answer") rather than as an empty roster that looks like "no models".
     */
    let alive = true;
    api.models
      .status()
      .then((raw) => {
        if (!alive) return;
        const body = raw as {
          backend?: { name?: string | null; providers?: string[] };
          models?: Record<string, string[]>;
          roles?: Record<string, string | null>;
        };
        const served = Object.values(body.models ?? {}).reduce(
          (n, list) => n + (Array.isArray(list) ? list.length : 0),
          0,
        );
        setModels({
          backend: body.backend?.name ?? null,
          served,
          roles: Object.entries(body.roles ?? {}).map(([role, model]) => ({ role, model: model ?? null })),
        });
      })
      .catch(() => {
        if (alive) setModels(null);
      });
    return () => {
      alive = false;
    };
  }, []);

  /**
   * The activity register, read once at the summary depth. `null` means the
   * read has not answered yet; an empty array means the platform genuinely has
   * nothing recorded, and the two say different things in the panel.
   */
  const [history, setHistory] = useState<HistoryEvent[] | null>(null);
  useEffect(() => {
    let alive = true;
    consoleData.history
      .list()
      .then((ev) => {
        if (alive) setHistory(ev);
      })
      .catch(() => {
        /* no register: the panel says so rather than inventing events */
      });
    return () => {
      alive = false;
    };
  }, []);
  const [feedFilter, setFeedFilter] = useState<FeedFilter>("all");

  /**
   * One simulation subscription for the whole page.
   *
   * The engine clock, the verification gate's last outcome and the failure
   * prediction all come from the same SSE stream, so they are read from one
   * `useSimulation` at the root rather than three subscriptions replaying the
   * same events. The projection publishes only when the engine clock, the
   * incident set or the event count actually moves (≈1 Hz on a live plant).
   */
  const sim = useSimulation(plant?.id ?? null);
  const responseJobs = useMemo<ResponseJob[]>(() => reduceResponseJobs(sim.events), [sim.events]);

  /** The newest job that actually produced a prediction — not an empty placeholder. */
  const predictionJob = useMemo<ResponseJob | null>(() => {
    for (let i = responseJobs.length - 1; i >= 0; i -= 1) {
      if (responseJobs[i].prediction.length > 0) return responseJobs[i];
    }
    return null;
  }, [responseJobs]);

  /** The most recent independent verification outcome, when one has run. */
  const lastVerified = useMemo(() => {
    for (let i = responseJobs.length - 1; i >= 0; i -= 1) {
      if (responseJobs[i].verified) return responseJobs[i].verified;
    }
    return null;
  }, [responseJobs]);

  const openWOs = useMemo(() => workOrders?.filter((w) => w.status !== "completed") ?? [], [workOrders]);
  const liveJobs = useMemo(
    () => jobs?.filter((j) => ["QUEUED", "PLANNING", "RETRIEVING", "EXECUTING", "VERIFYING"].includes(j.state)) ?? [],
    [jobs],
  );

  const sensorTotal = equipment?.reduce((n, e) => n + e.sensors.length, 0) ?? 0;
  const critCount = alerts?.filter((a) => a.severity === "critical").length ?? 0;
  const pendingApprovals = approvals?.length ?? 0;
  const equipmentOk = equipment?.filter((e) => e.status === "ok").length ?? 0;
  const highOpen = openWOs.filter((w) => w.priority === "high" || w.priority === "critical").length;
  const ragAgents = agents?.filter((a) => a.requires_rag).length ?? 0;
  const [reduceMotion, setReduceMotion] = useState(false);
  useEffect(() => {
    setReduceMotion(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }, []);

  /** Map selection, owned here so the Action Queue and the network agree. */
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const onSelectNode = useCallback((id: string | null) => setSelectedNode(id), []);
  const selectedAsset = selectedNode?.startsWith("equipment:")
    ? selectedNode.slice("equipment:".length)
    : null;

  /** Real id ↔ tag crosswalk (`e-P-1001` ↔ `P-1001`) from the equipment rows. */
  const idToTag = useMemo(
    () => new Map((equipment ?? []).map((e) => [e.id, e.tag ?? e.id])),
    [equipment],
  );
  const tagOf = useCallback(
    (w: WorkOrder) => idToTag.get(w.equipment_id) ?? w.equipment_id.replace(/^e-/, ""),
    [idToTag],
  );

  /** The queue, narrowed to the network selection and ordered by real priority. */
  const queueWOs = useMemo(() => {
    const list = selectedAsset
      ? openWOs.filter((w) => w.equipment_id === selectedAsset || w.equipment_id === `e-${selectedAsset}` || w.equipment_id.replace(/^e-/, "") === selectedAsset)
      : openWOs;
    return [...list].sort(
      (a, b) => PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority] || a.id.localeCompare(b.id),
    );
  }, [openWOs, selectedAsset]);

  /**
   * Alarm state, from the alerts the backend is actually serving. `unknown`
   * before the first read — the bar never claims "nominal" it has not measured.
   */
  const alarmState: "ok" | "warn" | "crit" | "unknown" =
    alerts === null ? "unknown" : critCount > 0 ? "crit" : alerts.length > 0 ? "warn" : "ok";
  const alarmStateWord = { ok: "Nominal", warn: "Alarm", crit: "Critical", unknown: "Unknown" }[alarmState];
  const alarmWord =
    alerts === null ? "alarm state unknown" : alerts.length === 0 ? "0 alarms" : `${alerts.length} alarm${alerts.length === 1 ? "" : "s"} open`;

  const engineClock =
    sim.stream.state === "live" && Number.isFinite(sim.t) ? `T+${Math.max(0, Math.floor(sim.t))}s` : "T+—";

  /** The filtered, day-grouped feed the panel renders. */
  const groups = useMemo(() => {
    const rows = (history ?? []).filter((e) => feedMatches(feedFilter, e)).slice(0, 40);
    const out: { day: string; rows: HistoryEvent[] }[] = [];
    for (const e of rows) {
      const day = dayOf(e.at);
      const last = out[out.length - 1];
      if (last && last.day === day) last.rows.push(e);
      else out.push({ day, rows: [e] });
    }
    return out;
  }, [history, feedFilter]);
  const shownRows = groups.reduce((n, g) => n + g.rows.length, 0);

  const nominalTone = equipment === null ? "neutral" : equipmentOk === equipment.length ? "ok" : "warn";

  return (
    <div className="home-dash">
      {/* TIER 1 — a live posture bar. Answers "is anything wrong right now?"
          in one line: state and its word, plant, alarm count, engine clock,
          egress posture. Colour is never the only signal. */}
      <header className="home-command cs-pagehead">
        <h1 className="home-sr">Plant command centre</h1>
        <div className="home-posture">
          <span className="home-posture__state" data-state={alarmState}>
            <span className="home-posture__dot" aria-hidden="true" />
            {alarmStateWord}
          </span>
          <span className="home-posture__sep" aria-hidden="true" />
          <b className="home-posture__plant">{plant?.name ?? "—"}</b>
          <span className="home-posture__sep" aria-hidden="true" />
          <span className="home-posture__alarms">{alarmWord}</span>
          <span className="home-posture__sep" aria-hidden="true" />
          <span className="home-posture__clock" title="Simulation engine clock (sim.t)">
            {engineClock}
          </span>
          <span className="home-posture__sep" aria-hidden="true" />
          <span className="home-posture__egress" title="Egress posture — GET /api/admin/posture">
            egress: {posture?.egress ?? "—"}
          </span>
        </div>
        <div className="home-command__actions">
          <button className="cs-btn cs-btn--primary" onClick={() => router.push("/console/simulation")}>
            Run simulation →
          </button>
        </div>
      </header>

      {/* TIER 2 — the vitals. Six measured cards; every badge pairs its colour
          with a word, and every figure has a real denominator behind it. */}
      <section className="home-vitals" data-testid="plant-status" aria-labelledby="home-vitals-title">
        <h2 className="home-tier" id="home-vitals-title">
          Plant status
        </h2>
        <div className="home-vitals__grid">
          <div className="home-stat">
            {equipment === null ? <b>—</b> : <Counter as="b" value={equipment.length} />}
            <span className="home-stat__label">Equipment</span>
            <span className="home-stat__badge" data-tone={nominalTone}>
              {equipment === null ? "reading" : `${equipmentOk}/${equipment.length} nominal`}
            </span>
          </div>

          <div className="home-stat">
            {equipment === null ? <b>—</b> : <Counter as="b" value={sensorTotal} />}
            <span className="home-stat__label">Sensors</span>
            <span className="home-stat__badge" data-tone="neutral">
              {equipment === null ? "reading" : `on ${equipment.length} assets`}
            </span>
          </div>

          <div className="home-stat" data-testid="active-agents">
            {agents === null ? <b>—</b> : <Counter as="b" value={agents.length} />}
            <span className="home-stat__label">Active agents</span>
            <span className="home-stat__badge" data-tone="neutral">
              {agents === null ? "reading" : `${ragAgents} retrieval-grounded`}
            </span>
          </div>

          <div className="home-stat" data-accent={critCount > 0 ? "crit" : undefined}>
            {alerts === null ? (
              <b>—</b>
            ) : (
              <Counter as="b" value={critCount} className={critCount ? "is-crit" : undefined} />
            )}
            <span className="home-stat__label">Critical alerts</span>
            <span className="home-stat__badge" data-tone={alerts === null ? "neutral" : critCount > 0 ? "crit" : "ok"}>
              {alerts === null ? "reading" : critCount > 0 ? "action required" : "clear"}
            </span>
          </div>

          <div
            className="home-stat"
            data-testid="pending-approvals"
            data-accent={pendingApprovals > 0 ? "crit" : undefined}
          >
            {approvals === null ? (
              <b>—</b>
            ) : (
              <Counter as="b" value={pendingApprovals} className={pendingApprovals ? "is-crit" : undefined} />
            )}
            <span className="home-stat__label">
              Pending approvals
              {pendingApprovals > 0 && <CircleAlert size={11} strokeWidth={2.6} aria-hidden="true" />}
            </span>
            <span
              className="home-stat__badge"
              data-tone={approvals === null ? "neutral" : pendingApprovals > 0 ? "crit" : "ok"}
            >
              {approvals === null ? "reading" : pendingApprovals > 0 ? "blocking" : "none"}
            </span>
          </div>

          {/* The sixth card, backed by the real open work-order set the queue
              already reads — added only because that data genuinely exists. */}
          <div className="home-stat" data-accent={highOpen > 0 ? "warn" : undefined}>
            {workOrders === null ? <b>—</b> : <Counter as="b" value={openWOs.length} />}
            <span className="home-stat__label">Open work orders</span>
            <span
              className="home-stat__badge"
              data-tone={workOrders === null ? "neutral" : highOpen > 0 ? "warn" : "ok"}
            >
              {workOrders === null ? "reading" : highOpen > 0 ? `${highOpen} high+` : "none high+"}
            </span>
          </div>
        </div>
      </section>

      {/* TIER 3a — the interactive asset network, 8 of 12 columns. It replaces
          the 3D orb with the real topology: click a node and the queue beside
          it narrows to that asset. */}
      <div className="home-topology">
        <section className="home-card home-glass home-nettop" aria-labelledby="home-net-title">
          <header className="home-card__head">
            <span className="home-card__eyebrow" id="home-net-title">
              <Sparkles size={12} strokeWidth={2.4} aria-hidden="true" />
              Asset network
            </span>
            <span className="home-card__sub">Real plant topology · click a node to filter the queue</span>
          </header>
          <AssetNetworkMap selected={selectedNode} onSelect={onSelectNode} />
        </section>
      </div>

      {/* TIER 3b — the critical action queue: what needs a human, in the
          operator's priority order, with real destinations only. */}
      <aside className="home-queue">
        <section className="home-card home-glass home-queuecard" aria-label="Critical action queue">
          <header className="home-card__head">
            <span className="home-card__eyebrow">
              <Gauge size={12} strokeWidth={2.4} aria-hidden="true" />
              Critical action queue
            </span>
            {queueWOs.length + liveJobs.length > 0 ? (
              <span className="home-badge home-badge--warn" data-tone="warn">
                {queueWOs.length + liveJobs.length} open
              </span>
            ) : (
              <span className="home-badge home-badge--ok" data-tone="ok">
                Clear
              </span>
            )}
          </header>

          {selectedAsset && (
            <div className="home-queue__filter">
              <span>filtered to</span>
              <b className="cs-mono">{selectedAsset}</b>
              <button
                type="button"
                onClick={() => setSelectedNode(null)}
                aria-label={`Clear the ${selectedAsset} filter`}
              >
                ×
              </button>
            </div>
          )}

          <div className="home-queue__scroll">
            {workOrders === null ? (
              <p className="home-empty">Reading the work-order store…</p>
            ) : queueWOs.length === 0 ? (
              <p className="home-empty">
                {selectedAsset
                  ? `No open work order targets ${selectedAsset}.`
                  : "No open work orders. Nothing is waiting on maintenance."}
              </p>
            ) : (
              <ul className="home-queue__list" aria-label="Open work orders">
                {queueWOs.map((w) => (
                  <li key={w.id}>
                    <div className="home-queue__top">
                      <Link className="home-queue__id" href={`/console/work-orders/${w.id}`}>
                        {w.id}
                      </Link>
                      <Link className="home-queue__asset" href={`/console/equipment/${tagOf(w)}`}>
                        {tagOf(w)}
                      </Link>
                      <Tag
                        tone={
                          w.priority === "critical"
                            ? "bad"
                            : w.priority === "high"
                              ? "crit"
                              : w.priority === "medium"
                                ? "warn"
                                : undefined
                        }
                      >
                        {w.priority.toUpperCase()}
                      </Tag>
                    </div>
                    <p className="home-queue__title">{w.title}</p>
                    {/* Real destinations only: the detail route, the asset
                        route and the approvals queue all exist and all do
                        exactly what their label says. The backend has no
                        "re-assign" or "impact analysis" endpoint, so neither
                        is offered. */}
                    <div className="home-queue__links">
                      <Link href={`/console/work-orders/${w.id}`}>Work order</Link>
                      <Link href={`/console/equipment/${tagOf(w)}`}>Equipment</Link>
                      <Link href="/console/approvals">Approvals</Link>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {liveJobs.length > 0 && (
              <ul className="home-queue__list home-queue__list--jobs" aria-label="Running jobs">
                {liveJobs.map((j) => (
                  <li key={j.id}>
                    <div className="home-queue__top">
                      <span className="home-queue__id">{j.id}</span>
                      <span className="home-queue__asset">{j.agent}</span>
                      <Tag tone="ai">{j.state}</Tag>
                    </div>
                    <p className="home-queue__title">{j.title}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="home-quick" data-testid="quick-actions">
            {[
              { label: "Run simulation", href: "/console/simulation", Icon: Play },
              { label: "Ask AI", href: "/console/workspace", Icon: Sparkles },
              { label: "Upload document", href: "/console/documents", Icon: Upload },
              { label: "View insights", href: "/console/insights", Icon: TrendingUp },
            ].map(({ label, href, Icon: ActionIcon }) => (
              <motion.button
                key={label}
                type="button"
                className="home-action"
                onClick={() => router.push(href)}
                whileHover={reduceMotion ? undefined : { y: -3 }}
                whileTap={{ scale: 0.98 }}
                transition={SPRING.micro}
              >
                <ActionIcon size={12} strokeWidth={2.3} aria-hidden="true" />
                {label}
                <ArrowRight size={11} strokeWidth={2.3} className="home-action__go" aria-hidden="true" />
              </motion.button>
            ))}
          </div>
        </section>
      </aside>

      {/* TIER 4a — system health, from real signals only. There is no
          efficiency metric in this system, so none is shown: the headline is
          literally the share of assets reporting `normal`. */}
      <section className="home-card home-glass home-health" data-testid="system-health" aria-label="System health">
        <header className="home-card__head">
          <span className="home-card__eyebrow">
            <Activity size={12} strokeWidth={2.4} aria-hidden="true" />
            System health
          </span>
          <span className="home-badge" data-tone={nominalTone}>
            {equipment === null ? "reading" : `${equipmentOk}/${equipment.length} nominal`}
          </span>
        </header>
        <div className="home-queue__rows">
          <div className="home-queue__row">
            <span>Assets reporting normal</span>
            <b className="home-queue__value">
              {equipment === null ? "—" : `${equipmentOk}/${equipment.length}`}
            </b>
          </div>
          <div className="home-queue__row">
            <span>Open alarms</span>
            <b className="home-queue__value">{alerts === null ? "—" : alerts.length}</b>
          </div>
          <div className="home-queue__row">
            <span>Last verification</span>
            <b className="home-queue__value">
              {lastVerified === null ? "—" : lastVerified.ok ? "passed" : "failed"}
            </b>
          </div>
          <div className="home-queue__row">
            <span>Egress posture</span>
            <b className="home-queue__value">{posture?.egress ?? "—"}</b>
          </div>
          <div className="home-queue__row">
            <span>Engine clock</span>
            <b className="home-queue__value">{engineClock}</b>
          </div>
        </div>
        <p className="home-health__cap">
          “Assets reporting normal” is the share of the dataset&apos;s equipment whose real <code>state</code> is
          normal. This platform has no efficiency score; this is not one.
        </p>
      </section>

      {/* TIER 4b — predictive maintenance, from the engine's own
          `response.prediction` event. With no prediction in this session it
          says so rather than recommending anything. */}
      <section className="home-card home-glass home-insights" aria-label="Predictive maintenance">
        <header className="home-card__head">
          <span className="home-card__eyebrow">
            <TrendingUp size={12} strokeWidth={2.4} aria-hidden="true" />
            Predictive maintenance
          </span>
          {predictionJob ? (
            <span className="home-badge home-badge--warn" data-tone="warn">
              {predictionJob.prediction.length} at risk
            </span>
          ) : (
            <span className="home-badge" data-tone="neutral">
              none this session
            </span>
          )}
        </header>

        {!predictionJob ? (
          <p className="home-empty">
            No failure prediction has been produced in this session. The engine emits one only after an incident
            has been diagnosed and its maintenance history reviewed, so an empty panel means “not computed yet” —
            not “all clear”.
          </p>
        ) : (
          <>
            <ul className="home-insight__list">
              {predictionJob.prediction.map((c) => {
                const band = c.risk >= 0.6 ? "crit" : c.risk >= 0.3 ? "warn" : "ok";
                const word = band === "crit" ? "High" : band === "warn" ? "Elevated" : "Low";
                const Glyph = band === "crit" ? TriangleAlert : band === "warn" ? CircleAlert : CircleCheck;
                return (
                  <li key={c.equipmentId} data-band={band}>
                    <span className="home-insight__glyph" data-band={band} aria-hidden="true">
                      <Glyph size={14} strokeWidth={2.4} />
                    </span>
                    <div className="home-insight__body">
                      <div className="home-insight__line">
                        <b className="cs-mono">{c.tag || c.equipmentId}</b>
                        <span className="home-insight__name">{c.name}</span>
                        <span className="home-insight__risk cs-mono">
                          {Math.round(c.risk * 100)}% · {word}
                        </span>
                      </div>
                      <div className="home-insight__meta">
                        {c.horizon}
                        {c.reasons[0] ? ` · ${c.reasons[0]}` : ""}
                      </div>
                    </div>
                    <Link className="home-insight__go" href={`/console/equipment/${c.tag || c.equipmentId}`}>
                      Open
                    </Link>
                  </li>
                );
              })}
            </ul>
            {predictionJob.predictionCaveat && (
              <p className="home-insight__caveat">{predictionJob.predictionCaveat}</p>
            )}
            <p className="home-insight__src">response.prediction · engine t={predictionJob.predictionAt ?? "—"}s</p>
          </>
        )}
      </section>

      {/* TIER 4c — model telemetry, exactly the shape `GET /api/models`
          returns. Not a training progress bar, because no such metric exists. */}
      <section className="home-card home-glass home-models" aria-label="Model telemetry">
        <header className="home-card__head">
          <span className="home-card__eyebrow">
            <Cpu size={12} strokeWidth={2.4} aria-hidden="true" />
            Model telemetry
          </span>
          {models === undefined ? (
            <span className="home-badge" data-tone="neutral">
              reading
            </span>
          ) : models === null ? (
            <span className="home-badge" data-tone="crit">
              endpoint silent
            </span>
          ) : (
            <span className="home-badge home-badge--ok" data-tone="ok">
              {models.served} served
            </span>
          )}
        </header>

        {models === null ? (
          <p className="home-empty">
            <code>GET /api/models</code> did not answer, so no role mapping is shown rather than a guessed one.
          </p>
        ) : models === undefined ? (
          <p className="home-empty">Reading the model gateway…</p>
        ) : models.roles.length === 0 ? (
          <p className="home-empty">The gateway reports no configured role mapping.</p>
        ) : (
          <ul className="home-models__list" aria-label="Model roles">
            {models.roles.map((r) => (
              <li className="home-model" key={r.role}>
                <span className="home-model__role">{r.role}</span>
                <b className="home-model__name cs-mono">{r.model ?? "—"}</b>
                <span className="home-stat__badge" data-tone={r.model ? "ok" : "neutral"}>
                  {r.model ? "available" : "unset"}
                </span>
              </li>
            ))}
          </ul>
        )}

        <p className="home-models__cap">
          {models?.backend ? `Backend ${models.backend}` : "No model backend reported"} ·{" "}
          {agents === null ? "—" : agents.length} agents registered. No training or inference-progress metric is
          exposed by this backend.
        </p>
      </section>

      {/* TIER 5 — the audit register: severity, actor, both clocks, category,
          target, and the actor's initial. */}
      <section className="home-card home-glass home-feedcard" data-testid="recent-activity">
        <header className="home-card__head">
          <span className="home-card__eyebrow">
            <Sparkles size={12} strokeWidth={2.4} aria-hidden="true" />
            Recent activity
            <span className="home-feed__count">{history === null ? "—" : shownRows}</span>
          </span>
          <MaterialSegmented
            options={FEED_FILTERS}
            value={feedFilter}
            onChange={(id) => setFeedFilter(id as FeedFilter)}
            layoutId="home-feed-filter"
            ariaLabel="Filter recent activity"
            testId="recent-activity-filter"
          />
        </header>

        {history === null ? (
          <p className="home-empty">Reading the activity register…</p>
        ) : shownRows === 0 ? (
          <p className="home-empty">
            {history.length === 0
              ? "Nothing has been recorded yet. Activity appears here as the platform produces it."
              : "No activity matches this filter."}
          </p>
        ) : (
          <div className="home-feed__scroll">
            {groups.map((g) => (
              <div key={g.day} className="home-feed__group">
                <div className="home-feed__day">{g.day}</div>
                <ul className="home-feed">
                  {g.rows.map((e) => {
                    const chip = KIND_CHIP[e.kind];
                    // An agent/system actor is marked by a glyph as well as a
                    // tone, so the distinction survives without colour.
                    const agentActor = /^(system|agent|orchestrator|ai|model)/i.test(e.actor);
                    return (
                      <li key={e.id} data-tone={dotTone(e)}>
                        <span className="home-feed__avatar" data-kind={agentActor ? "agent" : "human"} aria-hidden="true">
                          {agentActor ? <Cpu size={11} strokeWidth={2.4} /> : initialOf(e.actor)}
                        </span>
                        <span className="home-feed__dot" aria-hidden="true" />
                        <div className="home-feed__body">
                          <div className="home-feed__line">
                            <span className="home-feed__action">{e.title}</span>
                            <span
                              className="home-feed__actor"
                              data-kind={agentActor ? "agent" : "human"}
                              title={`actor: ${e.actor}`}
                            >
                              {agentActor && <Cpu size={10} strokeWidth={2.4} aria-hidden="true" />}
                              {e.actor}
                            </span>
                          </div>
                          <div className="home-feed__line home-feed__line--meta">
                            <span className="home-feed__time">{timeAgo(e.at)}</span>
                            <span className="home-feed__sep" aria-hidden="true">
                              ·
                            </span>
                            <time className="home-feed__time" dateTime={e.at}>
                              {clockOf(e.at)}
                            </time>
                            {e.equipment_id ? (
                              <>
                                <span className="home-feed__sep" aria-hidden="true">
                                  ·
                                </span>
                                <span className="home-feed__target">{e.equipment_id}</span>
                              </>
                            ) : null}
                          </div>
                        </div>
                        <Tag tone={chip.tone}>{chip.label}</Tag>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
