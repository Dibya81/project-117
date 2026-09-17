"use client";

/**
 * Confidentiality Architecture — `/console/security/confidentiality`.
 *
 * The animated diagram is the page. Everything here exists to feed it real
 * measurements and to keep the subscription to the live egress stream scoped to
 * this route:
 *
 *  * The sentinel `EventSource` lives in `useNetworkSentinel`, which opens it in
 *    an effect and closes it in that effect's cleanup. Nothing is started
 *    globally, so no other page pays for a security connection — the Security
 *    Console asserts exactly this (`/health → sentinel_subscribers`).
 *  * A real decision writes an audit row, so after a frame arrives the audit
 *    chain, the network monitor, the signature totals and the security-event
 *    ledger are re-read once, debounced — the audit node then updates because
 *    the backend's own count moved, not because the browser animated it.
 *  * The diagram is heavy, so it is `next/dynamic` with `ssr: false` (the
 *    pattern `/console/home` uses) and the signals panel loads alongside it.
 */
import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ErrorState, Panel, SkeletonRows, StatusDot, Tag } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type {
  ArtifactSignatures,
  AuditIntegrity,
  CallerIdentity,
  ModelsStatus,
  SecurityEvents,
  SovereigntyStatus,
} from "@/lib/api";
import { consoleData } from "@/lib/data/console";
import type { AgentDescriptor, HealthResponse } from "@/types";
import { useNetworkSentinel } from "@/lib/security/useNetworkSentinel";
import { buildNodes, pulseFromEvent } from "@/lib/security/confidentiality";
import type { ConfidentialityFacts } from "@/lib/security/confidentiality";
import "@/styles/confidentiality.css";

const ConfidentialityDiagram = dynamic(
  () => import("@/components/console/ConfidentialityDiagram").then((m) => m.ConfidentialityDiagram),
  { ssr: false, loading: () => <SkeletonRows rows={8} label="Drawing the confidentiality architecture" /> },
);
const SecuritySignalsPanel = dynamic(
  () => import("@/components/console/SecuritySignalsPanel").then((m) => m.SecuritySignalsPanel),
  { ssr: false, loading: () => <SkeletonRows rows={6} label="Reading live security signals" /> },
);

export default function ConfidentialityPage() {
  const [sovereignty, setSovereignty] = useState<SovereigntyStatus | null>(null);
  const [models, setModels] = useState<ModelsStatus | null>(null);
  const [integrity, setIntegrity] = useState<AuditIntegrity | null>(null);
  const [signatures, setSignatures] = useState<ArtifactSignatures | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [identity, setIdentity] = useState<CallerIdentity | null>(null);
  const [events, setEvents] = useState<SecurityEvents | null>(null);
  const [agents, setAgents] = useState<AgentDescriptor[] | null>(null);
  const [postureError, setPostureError] = useState(false);
  const [modelError, setModelError] = useState(false);
  const [integrityError, setIntegrityError] = useState(false);

  const loadSovereignty = useCallback(() => {
    setPostureError(false);
    api.security
      .sovereignty()
      .then(setSovereignty)
      .catch(() => {
        setSovereignty(null);
        setPostureError(true);
      });
  }, []);
  const loadModels = useCallback(() => {
    setModelError(false);
    api.models
      .status()
      .then(setModels)
      .catch(() => {
        setModels(null);
        setModelError(true);
      });
  }, []);
  const loadIntegrity = useCallback(() => {
    setIntegrityError(false);
    api.audit
      .integrity()
      .then(setIntegrity)
      .catch(() => {
        setIntegrity(null);
        setIntegrityError(true);
      });
  }, []);
  const loadSignatures = useCallback(() => {
    api.artifacts
      .signatures(25)
      .then(setSignatures)
      .catch(() => setSignatures(null));
  }, []);
  const loadHealth = useCallback(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);
  const loadEvents = useCallback(() => {
    api.security
      .events(20)
      .then(setEvents)
      .catch(() => setEvents(null));
  }, []);

  useEffect(() => {
    loadSovereignty();
    loadModels();
    loadIntegrity();
    loadSignatures();
    loadHealth();
    loadEvents();
    api.auth
      .me()
      .then(setIdentity)
      .catch(() => setIdentity(null));
    consoleData.agents
      .list()
      .then(setAgents)
      .catch(() => setAgents(null));
  }, [loadSovereignty, loadModels, loadIntegrity, loadSignatures, loadHealth, loadEvents]);

  const sentinel = useNetworkSentinel();

  /**
   * The last real frame, as an edge state. `pulseFromEvent` walks the frame's
   * own fields; nothing here is synthesised.
   */
  const pulse = useMemo(
    () => (sentinel.lastEvent ? pulseFromEvent(sentinel.lastEvent, sentinel.lastSeq) : null),
    [sentinel.lastEvent, sentinel.lastSeq],
  );

  /**
   * After a real decision, re-measure what it changed. Debounced, and the
   * cleanup doubles as the unmount cancel.
   */
  const remeasure = useRef<number | null>(null);
  useEffect(() => {
    if (sentinel.lastSeq === 0) return;
    if (remeasure.current) window.clearTimeout(remeasure.current);
    remeasure.current = window.setTimeout(() => {
      loadIntegrity();
      loadHealth();
      loadSignatures();
      loadEvents();
    }, 1500);
    return () => {
      if (remeasure.current) window.clearTimeout(remeasure.current);
    };
  }, [sentinel.lastSeq, loadIntegrity, loadHealth, loadSignatures, loadEvents]);

  const facts: ConfidentialityFacts = useMemo(
    () => ({ sovereignty, models, integrity, signatures, health, identity, events, agents }),
    [sovereignty, models, integrity, signatures, health, identity, events, agents],
  );
  const nodes = useMemo(() => buildNodes(facts), [facts]);
  const signals = useMemo(
    () => ({
      pulse,
      auditEvents: integrity?.events ?? null,
      signedCount: signatures?.totals.signed ?? null,
    }),
    [pulse, integrity, signatures],
  );

  const reloadAll = useCallback(() => {
    loadSovereignty();
    loadModels();
    loadIntegrity();
    loadSignatures();
    loadHealth();
    loadEvents();
  }, [loadSovereignty, loadModels, loadIntegrity, loadSignatures, loadHealth, loadEvents]);

  return (
    <>
      <div className="cs-pagehead">
        <div>
          <span className="cs-pagehead__kicker">Security</span>
          <h1>Confidentiality Architecture</h1>
        </div>
        <span className="cs-pagehead__meta">
          data flow · clearance · model routing · egress · isolation · verification · audit
        </span>
      </div>

      <div className="cs-stack" data-testid="confidentiality-page">
        <Panel
          title="Where confidential data goes"
          actions={
            <span className="cs-row" style={{ gap: 8, alignItems: "center" }}>
              <span className="cs-mono" style={{ fontSize: 10, color: "var(--ink-3)" }}>
                {sovereignty ? `MEASURED ${new Date(sovereignty.generated_at).toLocaleTimeString()}` : "MEASURING…"}
              </span>
              <button type="button" className="cs-btn" onClick={reloadAll} data-testid="cf-remeasure">
                Re-measure
              </button>
            </span>
          }
        >
          <div className="cs-panel__body">
            <p className="cs-dim" style={{ margin: "0 0 14px", fontSize: 12.5, lineHeight: 1.65, maxWidth: "88ch" }}>
              One pipeline, from the plant&apos;s own data to a signed, approved output. Node states are
              the backend&apos;s verdicts; the animated seam is the network sentinel, and it moves only
              when a real egress decision arrives on{" "}
              <span className="cs-mono">GET /api/network/stream</span>.
            </p>
            {postureError && (
              <ErrorState
                message="The sovereignty endpoint did not answer, so no status is being reported. Every node below would read NOT VERIFIED — a missing measurement is not a pass."
                onRetry={loadSovereignty}
              />
            )}
            <ConfidentialityDiagram nodes={nodes} signals={signals} sentinel={sentinel} />
          </div>
        </Panel>

        <SecuritySignalsPanel
          sources={{ sovereignty, models, integrity, signatures, health, identity, events, modelError, integrityError }}
          sentinel={sentinel}
          pulse={pulse}
        />

        <Panel title="What this page will not claim">
          <div className="cs-panel__body">
            <ul className="cf-caveats">
              <li>
                <StatusDot state="critical" />
                <span>
                  <b>No sandbox isolation.</b> OpenSandbox is not running on this host; every{" "}
                  <span className="cs-mono">sandbox_command</span> returns{" "}
                  <span className="cs-mono">ACTION BLOCKED / SANDBOX UNAVAILABLE</span>. The sandbox node
                  is red for that reason and never shows an isolation tick.
                </span>
              </li>
              <li>
                <StatusDot state="unknown" />
                <span>
                  <b>No OS-level egress control.</b> nftables/iptables is a Linux facility and this host
                  is macOS. Application-layer egress filtering is <Tag tone="warn">PLANNED</Tag> as an OS
                  control.
                </span>
              </li>
              <li>
                <StatusDot state="warning" />
                <span>
                  <b>No air-gap and no zero-egress claim.</b> The guard refuses external destinations and
                  the counter for non-loopback hosts reached reads{" "}
                  <span className="cs-mono">{health?.network?.external_allowed ?? "—"}</span> — a measured
                  figure from this process, not an assertion about the network.
                </span>
              </li>
              <li>
                <StatusDot state="warning" />
                <span>
                  <b>No signature is claimed.</b> Ed25519 signing and verification are implemented, but{" "}
                  <span className="cs-mono">{signatures?.totals.signed ?? 0}</span> artifact(s) have been
                  signed on this host, so the signing node reads IMPLEMENTED and the count stays at zero.
                </span>
              </li>
            </ul>
          </div>
        </Panel>
      </div>
    </>
  );
}
