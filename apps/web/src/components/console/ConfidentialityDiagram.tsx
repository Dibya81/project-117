"use client";

/**
 * Confidentiality architecture diagram.
 *
 * Answers, in one screen: where confidential data goes, who can see it, which
 * model serves which role, which tools exist, whether the agent can reach the
 * internet, how execution is isolated, how the result is verified, and how the
 * record is proved — by drawing the real pipeline and labelling each node with
 * the backend's own verdict.
 *
 * ## Animation is driven by real events only
 *
 * There is no idle loop, no sweeping gradient, no "scanning…" shimmer. Every
 * motion in this component is a **one-shot response to a measured change**:
 *
 *  * `signals.pulse` — built from a real `network.connection_attempt` SSE frame.
 *    `BLOCK` turns the decision edge red and stops it there; `ALLOW` on a
 *    loopback destination animates it green through to the local port; an
 *    `ALLOW` to a non-loopback host is surfaced as `REACHED`.
 *  * `signals.auditEvents` — when `GET /api/audit/integrity` reports a higher
 *    event count, the audit node pulses once.
 *  * `signals.signedCount` — when the signed total rises, the signing and
 *    verification nodes pulse once.
 *
 * When nothing arrives, the diagram is still. The only persistent colour is the
 * *last recorded* decision, printed with its timestamp and destination so it
 * cannot be mistaken for a live claim.
 *
 * ## Re-render budget
 *
 * `buildNodes()` is memoised on the fetched facts, and every node is a
 * `React.memo` card whose props are the node object, a stable callback and a
 * `flash` key that is `0` for every node except the one currently animating. A
 * single sentinel frame therefore re-renders the two related cards and the
 * external edge — not the tree.
 */
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Panel, StatusDot } from "@/components/ui/primitives";
import {
  STATUS_COLOUR,
  STATUS_TONE,
  ZONES,
  type DiagramNode,
  type EgressPulse,
  type NodeStatus,
} from "@/lib/security/confidentiality";
import type { NetworkSentinel } from "@/lib/security/useNetworkSentinel";
import { NodeDrawer } from "./ConfidentialityDrawer";

/** How long a one-shot pulse animation runs before the diagram goes calm. */
const FLASH_MS = 1600;

export interface DiagramSignals {
  /** The last real egress decision, or null when none has arrived. */
  pulse: EgressPulse | null;
  /** The chain length the last integrity probe reported. */
  auditEvents: number | null;
  /** The signed-artifact total the last signature read reported. */
  signedCount: number | null;
}

/**
 * One node.
 *
 * Memoised on the fields it actually renders rather than on the node object's
 * identity. `buildNodes()` runs again whenever any measured fact changes — which
 * a live sentinel frame causes indirectly, through the debounced re-measure — so
 * an identity comparison would re-render every card in the tree for a change
 * that touched one node's status. Comparing the rendered fields means a frame
 * redraws exactly the card it changed.
 *
 * The click passes the *current* node object, so the drawer always opens with
 * the freshest evidence even when the card itself did not re-render.
 */
const NodeCard = memo(
  function NodeCard({
    node,
    flash,
    onOpen,
  }: {
    node: DiagramNode;
    flash: number;
    onOpen: (node: DiagramNode) => void;
  }) {
    return (
      <button
        type="button"
        className={`cf-node${flash ? " is-pulsing" : ""}`}
        data-testid={`cf-node-${node.id}`}
        data-status={node.status}
        data-flash={flash || undefined}
        onClick={() => onOpen(node)}
        title={`${node.title} — ${node.status}`}
      >
        <span className="cf-node__rail" style={{ background: STATUS_COLOUR[node.status] }} aria-hidden="true" />
        <span className="cf-node__body">
          <span className="cf-node__top">
            <span className="cf-node__title">{node.title}</span>
            <span className="cf-node__state" style={{ color: STATUS_COLOUR[node.status] }}>
              <StatusDot state={STATUS_TONE[node.status]} />
              {node.status}
            </span>
          </span>
          <span className="cf-node__blurb">{node.blurb}</span>
          {node.count && (
            <span className="cf-node__count cs-mono">
              {node.count.value == null ? "—" : node.count.value}
              <span className="cf-dim"> {node.count.label}</span>
            </span>
          )}
      </span>
    </button>
  );
  },
  (a, b) =>
    a.flash === b.flash &&
    a.onOpen === b.onOpen &&
    a.node.id === b.node.id &&
    a.node.title === b.node.title &&
    a.node.blurb === b.node.blurb &&
    a.node.status === b.node.status &&
    a.node.count?.value === b.node.count?.value &&
    a.node.count?.label === b.node.count?.label,
);

/** The short connector between two nodes in the same zone/chain. */
function Arrow({ live = false }: { live?: boolean }) {
  return (
    <span className={`cf-arrow${live ? " cf-arrow--live" : ""}`} aria-hidden="true">
      <svg width="12" height="18" viewBox="0 0 12 18" fill="none">
        <path d="M6 0v13M2 10.5 6 15l4-4.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    </span>
  );
}

export function ConfidentialityDiagram({
  nodes,
  signals,
  sentinel,
}: {
  nodes: DiagramNode[];
  signals: DiagramSignals;
  sentinel: NetworkSentinel;
}) {
  const [openNode, setOpenNode] = useState<DiagramNode | null>(null);
  /**
   * Which nodes are mid-pulse, as `id -> key`. A key rather than a boolean so
   * the flash class is a prop that changes only for the node being animated:
   * every other memoised card sees `0` and does not re-render.
   */
  const [flashing, setFlashing] = useState<Record<string, number>>({});
  const [pulseFresh, setPulseFresh] = useState(false);
  const timers = useRef<number[]>([]);

  // Keep the drawer's copy of a node in sync with a fresh measurement without
  // closing it under the user.
  useEffect(() => {
    setOpenNode((prev) => (prev ? (nodes.find((n) => n.id === prev.id) ?? prev) : prev));
  }, [nodes]);

  const flash = useCallback((ids: string | string[], key: number) => {
    const list = Array.isArray(ids) ? ids : [ids];
    setFlashing((prev) => {
      const next = { ...prev };
      for (const id of list) next[id] = key;
      return next;
    });
    const t = window.setTimeout(() => {
      setFlashing((prev) => {
        const next = { ...prev };
        for (const id of list) if (next[id] === key) delete next[id];
        return next;
      });
    }, FLASH_MS);
    timers.current.push(t);
  }, []);

  // Driver 1 — a real sentinel frame.
  const pulseSeq = signals.pulse?.seq ?? 0;
  const lastPulseSeq = useRef(0);
  useEffect(() => {
    if (!signals.pulse || pulseSeq === lastPulseSeq.current) return;
    lastPulseSeq.current = pulseSeq;
    setPulseFresh(true);
    flash("allow_block", pulseSeq);
    const t = window.setTimeout(() => setPulseFresh(false), FLASH_MS);
    timers.current.push(t);
  }, [pulseSeq, signals.pulse, flash]);

  // Driver 2 — the audit chain grew.
  const auditEvents = signals.auditEvents;
  const lastAudit = useRef<number | null>(null);
  useEffect(() => {
    if (auditEvents == null) return;
    if (lastAudit.current != null && auditEvents > lastAudit.current) {
      flash("audit", auditEvents);
    }
    lastAudit.current = auditEvents;
  }, [auditEvents, flash]);

  // Driver 3 — a signature was recorded. Only a real increase animates; the
  // node's own status already reports `0 signed` when nothing has been signed.
  const signedCount = signals.signedCount;
  const lastSigned = useRef<number | null>(null);
  useEffect(() => {
    if (signedCount == null) return;
    if (lastSigned.current != null && signedCount > lastSigned.current) {
      flash(["signed_output", "verification"], signedCount);
    }
    lastSigned.current = signedCount;
  }, [signedCount, flash]);

  useEffect(() => {
    return () => {
      timers.current.forEach((t) => window.clearTimeout(t));
      timers.current = [];
    };
  }, []);

  const onOpen = useCallback((node: DiagramNode) => setOpenNode(node), []);
  const byZone = useMemo(() => {
    const map = new Map<string, DiagramNode[]>();
    for (const node of nodes) {
      const list = map.get(node.zone) ?? [];
      list.push(node);
      map.set(node.zone, list);
    }
    return map;
  }, [nodes]);

  const pulse = signals.pulse;
  const edgeState = !pulse ? "idle" : pulse.action === "ALLOW" ? "allowed" : pulse.action === "REACHED" ? "reached" : "blocked";
  const external = byZone.get("external") ?? [];
  const boundary = byZone.get("boundary")?.[0] ?? null;

  const flashFor = (id: string) => flashing[id] ?? 0;

  return (
    <div className="cf" data-testid="confidentiality-diagram">
      {/* The key. Amber and grey are deliberately not green. */}
      <div className="cf-legend" aria-label="Status key">
        {(["VERIFIED", "IMPLEMENTED", "PARTIAL", "NOT VERIFIED", "PLANNED", "UNAVAILABLE"] as NodeStatus[]).map((s) => (
          <span key={s} className="cf-legend__item">
            <StatusDot state={STATUS_TONE[s]} />
            <span className="cs-mono" style={{ color: STATUS_COLOUR[s] }}>{s}</span>
          </span>
        ))}
      </div>

      {/* ---- the boundary ---- */}
      <div className="cf-boundary" data-cf-boundary="app-layer">
        <div className="cf-boundary__label">
          <span className="cs-mono">SECURITY BOUNDARY</span>
          {boundary && (
            <button
              type="button"
              className="cf-boundary__badge"
              data-testid="cf-node-security_boundary"
              data-status={boundary.status}
              onClick={() => onOpen(boundary)}
            >
              <StatusDot state={STATUS_TONE[boundary.status]} />
              <span className="cs-mono">{boundary.status}</span>
              <span className="cf-boundary__hint">application layer · no OS firewall · no container isolation</span>
            </button>
          )}
        </div>

        <div className="cf-zones">
          {ZONES.map((zone) => {
            const zoneNodes = byZone.get(zone.id) ?? [];
            return (
              <section className="cf-zone" key={zone.id} data-cf-zone={zone.id}>
                <header className="cf-zone__head">
                  <span className="cf-zone__index cs-mono">{zone.index}</span>
                  <span className="cf-zone__title">{zone.title}</span>
                  <span className="cf-zone__caption">{zone.caption}</span>
                </header>
                <div className="cf-zone__nodes">
                  {zoneNodes.map((node, i) => (
                    <div className="cf-zone__step" key={node.id}>
                      {i > 0 && <Arrow />}
                      <NodeCard node={node} flash={flashFor(node.id)} onOpen={onOpen} />
                    </div>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      </div>

      {/* ---- outside the boundary ---- */}
      <div className="cf-external" data-cf-zone="external">
        <div className="cf-external__head">
          <span className="cs-mono">EXTERNAL / UNTRUSTED</span>
          <span className="cf-external__hint cs-dim">
            Nothing here is trusted. The only path out of the boundary crosses the sentinel, which is
            where the live decision below is taken.
          </span>
        </div>

        <div className="cf-chain">
          {external.map((node, i) => (
            <div className="cf-chain__step" key={node.id}>
              {i > 0 && (
                /* The decision edge: the one seam a real frame animates. */
                <span
                  className={`cf-edge cf-edge--${i === 2 ? edgeState : "static"}${i === 2 && pulseFresh ? " is-fresh" : ""}`}
                  data-testid={i === 2 ? "cf-edge-egress" : undefined}
                  data-cf-state={i === 2 ? edgeState : undefined}
                  data-cf-destination={i === 2 ? (pulse?.destination ?? "") : undefined}
                  aria-hidden={i === 2 ? undefined : "true"}
                  aria-label={i === 2 ? `Egress decision edge: ${edgeState}` : undefined}
                >
                  {i === 2 && edgeState === "blocked" ? (
                    /* A block stops here; the glyph says so rather than
                       animating onward. */
                    <span className="cf-edge__stop" aria-hidden="true">✕</span>
                  ) : (
                    <Arrow live={i === 2 && pulseFresh} />
                  )}
                </span>
              )}
              <NodeCard node={node} flash={flashFor(node.id)} onOpen={onOpen} />
            </div>
          ))}
        </div>

        {/* The state line. It reports the last *recorded* decision, with the
            time, so a colour on screen is never a live claim. */}
        <div className="cf-live" data-testid="cf-egress-state" data-cf-state={edgeState}>
          <StatusDot state={edgeState === "allowed" ? "ok" : edgeState === "idle" ? "unknown" : "critical"} />
          <span className="cf-live__text">
            {pulse
              ? `${pulse.action} · ${pulse.destination ?? "unnamed destination"}${
                  pulse.port ? `:${pulse.port}` : ""
                }${pulse.local ? " (loopback)" : ""} · last decision at ${new Date(pulse.at).toLocaleTimeString()}`
              : "Idle — no live egress decision has arrived since this page was opened."}
          </span>
          <span className="cf-live__stream cs-mono">
            sentinel {sentinel.state}
            {sentinel.attached ? ` · ${sentinel.events.length} frame(s) this session` : ""}
          </span>
        </div>
      </div>

      <Panel title="Reading this diagram">
        <div className="cs-panel__body">
          <p className="cs-dim" style={{ margin: 0, fontSize: 12.5, lineHeight: 1.65 }}>
            Node states are the backend&apos;s own verdicts
            (<span className="cs-mono">GET /api/security/sovereignty</span>), not a frontend
            judgement. <b>VERIFIED</b> means a probe answered on this host; <b>IMPLEMENTED</b> means
            the capability is wired but this process has no positive evidence for it yet;{" "}
            <b>PARTIAL</b> means it names more than it does and the gap is stated; <b>PLANNED</b> means
            it does not exist here. Only <b>VERIFIED</b> is green. Click any node for the real values
            behind it.
          </p>
        </div>
      </Panel>

      {openNode && (
        <NodeDrawer
          node={openNode}
          onClose={() => setOpenNode(null)}
          sentinel={sentinel}
        />
      )}
    </div>
  );
}
