"use client";

/**
 * Sovereignty Center — `/console/sovereignty`.
 *
 * A security console, not a dashboard of green ticks. Two rules govern every
 * pixel of this page:
 *
 *  1. **Every status is backend-derived.** The status bar renders
 *     `/api/security/sovereignty`, which resolves each entry from a measurement
 *     taken in that request — the model gateway answering, the chain verifier
 *     walking the log, the vector store opening its table, the sandbox
 *     reporting itself unavailable. Nothing here is green because code exists.
 *     The vocabulary is `VERIFIED / IMPLEMENTED / PARTIAL / NOT AVAILABLE`, and
 *     only VERIFIED may be shown as a pass.
 *  2. **The page never re-derives a verdict.** The audit chain, the signature
 *     checks and the refusal evaluation all come from the backend endpoints
 *     that own them (`/api/audit/integrity`, the real Ed25519 verifier behind
 *     `/api/security/artifacts/{id}/verify`, and `/api/security/evaluation`).
 *     A second implementation in the browser could report a verification the
 *     service never performed.
 *
 * Performance (§21): the home page's bundle is the constraint. The heavy
 * panels — the sentinel stream, the events ledger, the access matrix and the
 * refusal evaluation — are `next/dynamic` with `ssr: false`, so they load after
 * first paint and only on this route. The sentinel stream subscribes while the
 * panel is mounted and closes its `EventSource` on unmount; nothing here is
 * started globally, so no other route pays for a security connection.
 */
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { EmptyState, ErrorState, Panel, SkeletonRows, StatusDot, Tag, timeAgo } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type {
  ArtifactSignatures,
  ArtifactVerification,
  AuditIntegrity,
  SignatureVerification,
  SignedArtifactRecord,
  SovereigntyEntry,
  SovereigntyState,
  SovereigntyStatus,
} from "@/lib/api";
import type { HealthState } from "@/types";

/** Heavy panels, fetched after first paint and only on this route. */
const SentinelStreamPanel = dynamic(
  () => import("@/components/console/SentinelStreamPanel").then((m) => m.SentinelStreamPanel),
  { ssr: false, loading: () => <SkeletonRows rows={4} label="Opening the network sentinel stream" /> },
);
const SecurityEventsPanel = dynamic(
  () => import("@/components/console/SovereigntyPanels").then((m) => m.SecurityEventsPanel),
  { ssr: false, loading: () => <SkeletonRows rows={4} label="Reading the security-event ledger" /> },
);
const SecurityEvaluationPanel = dynamic(
  () => import("@/components/console/SovereigntyPanels").then((m) => m.SecurityEvaluationPanel),
  { ssr: false, loading: () => <SkeletonRows rows={3} label="Exercising the refusal controls" /> },
);
const AccessControlPanel = dynamic(
  () => import("@/components/console/SovereigntyPanels").then((m) => m.AccessControlPanel),
  { ssr: false, loading: () => <SkeletonRows rows={3} label="Reading the access-control map" /> },
);

/**
 * The one place a state becomes a colour. `IMPLEMENTED` is amber on purpose:
 * a control that exists but has not been exercised is not a pass, and showing
 * it green is the exact false assurance this page exists to avoid.
 */
const STATE_TONE: Record<SovereigntyState, { dot: HealthState; colour: string }> = {
  VERIFIED: { dot: "ok", colour: "var(--ok, #16a34a)" },
  IMPLEMENTED: { dot: "warning", colour: "var(--warn, #d97706)" },
  PARTIAL: { dot: "warning", colour: "var(--warn, #d97706)" },
  "NOT AVAILABLE": { dot: "critical", colour: "var(--crit, #dc2626)" },
};

function StatusBar({ status }: { status: SovereigntyStatus | null }) {
  if (!status) {
    return <SkeletonRows rows={3} label="Measuring every control on the backend" />;
  }
  return (
    <div className="cs-stack" data-testid="sovereignty-statusbar">
      <div className="cs-mono" style={{ fontSize: 11, letterSpacing: "0.22em", color: "var(--ink-3)" }}>
        SOVEREIGNTY STATUS
      </div>
      <div style={{ borderTop: "1px solid var(--line, rgba(0,0,0,0.12))", paddingTop: 10 }}>
        {status.status.map((entry: SovereigntyEntry) => {
          const tone = STATE_TONE[entry.state] ?? STATE_TONE["NOT AVAILABLE"];
          return (
            <div
              key={entry.key}
              data-testid={`sovereignty-status-${entry.key}`}
              data-state={entry.state}
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(140px, 200px) 16px minmax(140px, 1fr)",
                gap: 10,
                alignItems: "baseline",
                padding: "5px 0",
              }}
            >
              <span className="cs-mono" style={{ fontSize: 12.5, letterSpacing: "0.1em", textTransform: "uppercase" }}>
                {entry.label}
              </span>
              <StatusDot state={tone.dot} />
              <span
                className="cs-mono"
                style={{ fontSize: 12.5, letterSpacing: "0.1em", color: tone.colour, textTransform: "uppercase" }}
              >
                {entry.state}
              </span>
              <span
                className="cs-dim"
                style={{ gridColumn: "1 / -1", fontSize: 11.5, lineHeight: 1.55, marginLeft: 0 }}
              >
                {entry.detail}
              </span>
            </div>
          );
        })}
      </div>
      <p className="cs-dim" style={{ margin: 0, fontSize: 11.5, lineHeight: 1.6 }}>
        Measured on the backend at {timeAgo(status.generated_at)} on{" "}
        <span className="cs-mono">
          {status.host.platform} {status.host.release} ({status.host.machine})
        </span>
        . <b>VERIFIED</b> means a probe answered; <b>IMPLEMENTED</b> means the
        control is wired but this process has no positive evidence for it yet;{" "}
        <b>NOT AVAILABLE</b> means it cannot run here, and the reason is stated.
      </p>
    </div>
  );
}

/**
 * Security Overview — the six readings that decide whether "sovereign" is true
 * today, pulled out of the long status list so they are visible at a glance.
 *
 * Every value is a slice of the same `/api/security/sovereignty` payload the
 * status bar renders; nothing here is computed a second way. The counts come
 * from each entry's own `evidence`, so a card cannot show a figure the entry
 * did not measure.
 *
 * Rendered as a labelled sub-block of the existing "Sovereignty Status" panel
 * rather than as a new panel, so the page's section list is unchanged.
 */
function SecurityOverview({ status }: { status: SovereigntyStatus }) {
  const byKey = (key: string) => status.status.find((s) => s.key === key) ?? null;
  const cards: { key: string; label: string; value: string; detail: string; tone: HealthState }[] = [];

  const egress = byKey("egress");
  if (egress) {
    cards.push({
      key: "egress",
      label: "Egress guard",
      value: egress.state,
      detail: `${String(egress.evidence.policy ?? "—")} · ${String(
        egress.evidence.external_blocked ?? "—",
      )} external refused · ${String(egress.evidence.external_allowed ?? "—")} reached`,
      tone: (STATE_TONE[egress.state] ?? STATE_TONE["NOT AVAILABLE"]).dot,
    });
  }

  const audit = byKey("audit_chain");
  if (audit) {
    cards.push({
      key: "audit_chain",
      label: "Audit chain",
      value: audit.state,
      detail: `${String(audit.evidence.events ?? "—")} events hash-linked`,
      tone: (STATE_TONE[audit.state] ?? STATE_TONE["NOT AVAILABLE"]).dot,
    });
  }

  const signing = byKey("signing");
  if (signing) {
    cards.push({
      key: "signing",
      label: "Artifact signing",
      value: signing.state,
      // The honest figure: a key exists, but nothing has been signed here.
      detail: `${String(signing.evidence.signed ?? 0)} signed · ${String(
        signing.evidence.algorithm ?? "—",
      )}`,
      tone: (STATE_TONE[signing.state] ?? STATE_TONE["NOT AVAILABLE"]).dot,
    });
  }

  const sandbox = byKey("sandbox");
  if (sandbox) {
    cards.push({
      key: "sandbox",
      label: "Sandbox isolation",
      value: sandbox.state,
      detail: "OpenSandbox is not running on this host — not enforced",
      tone: (STATE_TONE[sandbox.state] ?? STATE_TONE["NOT AVAILABLE"]).dot,
    });
  }

  const clearance = byKey("clearance");
  if (clearance) {
    cards.push({
      key: "clearance",
      label: "Clearance",
      value: clearance.state,
      detail: `${Object.keys((clearance.evidence.role_clearance as Record<string, string>) ?? {}).length} role level(s) mapped`,
      tone: (STATE_TONE[clearance.state] ?? STATE_TONE["NOT AVAILABLE"]).dot,
    });
  }

  const localAi = byKey("local_ai");
  if (localAi) {
    cards.push({
      key: "local_ai",
      label: "Local AI",
      value: localAi.state,
      detail: `${String(localAi.evidence.backend ?? "—")} · ${String(
        localAi.evidence.model_count ?? "—",
      )} model(s) served on this machine`,
      tone: (STATE_TONE[localAi.state] ?? STATE_TONE["NOT AVAILABLE"]).dot,
    });
  }

  return (
    <div className="cf-stack" data-testid="security-overview-block">
      <div className="cs-row" style={{ justifyContent: "space-between", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
        <span className="cs-mono" style={{ fontSize: 11, letterSpacing: "0.22em", color: "var(--ink-3)" }}>
          SECURITY OVERVIEW
        </span>
        <Link className="cs-btn" href="/console/security/confidentiality" data-testid="open-confidentiality">
          Open Confidentiality Architecture →
        </Link>
      </div>
      <div className="cs-grid-3" data-testid="security-overview">
        {cards.map((card) => (
          <div className="cs-kpi" key={card.key} data-testid={`security-overview-${card.key}`} data-state={card.value}>
            <div className="cs-kpi__label">{card.label}</div>
            <div className="cs-kpi__value">
              <StatusDot state={card.tone} />
              {card.value}
            </div>
            <div className="cs-dim" style={{ fontSize: 11, marginTop: 6, lineHeight: 1.5 }}>
              {card.detail}
            </div>
          </div>
        ))}
      </div>
      <p className="cs-dim" style={{ margin: 0, fontSize: 11.5, lineHeight: 1.6 }}>
        These six decide whether the deployment is sovereign today. The sandbox card reads{" "}
        <b>NOT AVAILABLE</b> on this host because every{" "}
        <span className="cs-mono">sandbox_command</span> returns{" "}
        <span className="cs-mono">ACTION BLOCKED / SANDBOX UNAVAILABLE</span>, so no isolation tick is
        shown. The data-flow view — where confidential input goes, who can see it and how the result is
        verified — is on the Confidentiality Architecture page.
      </p>
    </div>
  );
}

function CapabilityGrid({ capabilities }: { capabilities: SovereigntyEntry[] }) {  return (
    <div className="cs-stack">
      <div className="cs-mono" style={{ fontSize: 11, letterSpacing: "0.22em", color: "var(--ink-3)" }}>
        LOCAL CAPABILITIES
      </div>
      <div style={{ borderTop: "1px solid var(--line, rgba(0,0,0,0.12))", paddingTop: 10 }}>
        {capabilities.map((entry) => {
          const tone = STATE_TONE[entry.state] ?? STATE_TONE["NOT AVAILABLE"];
          return (
            <div
              key={entry.key}
              data-testid={`sovereignty-capability-${entry.key}`}
              data-state={entry.state}
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(140px, 200px) 16px minmax(140px, 1fr)",
                gap: 10,
                alignItems: "baseline",
                padding: "5px 0",
              }}
            >
              <span className="cs-mono" style={{ fontSize: 12.5 }}>{entry.label}</span>
              <StatusDot state={tone.dot} />
              <span className="cs-mono" style={{ fontSize: 12.5, color: tone.colour }}>{entry.state}</span>
              <span className="cs-dim" style={{ gridColumn: "1 / -1", fontSize: 11.5, lineHeight: 1.55 }}>
                {entry.detail}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AuditIntegrityPanel() {
  const [integrity, setIntegrity] = useState<AuditIntegrity | null>(null);
  const [error, setError] = useState(false);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);

  const verify = useCallback(() => {
    setError(false);
    api.audit
      .integrity()
      .then((v) => {
        setIntegrity(v);
        setCheckedAt(new Date().toISOString());
      })
      .catch(() => {
        setIntegrity(null);
        setError(true);
      });
  }, []);

  useEffect(() => {
    verify();
  }, [verify]);

  return (
    <Panel title="Audit Integrity">
      <div className="cs-panel__body">
        <div className="cs-row" style={{ justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <p className="cs-dim" style={{ margin: 0, fontSize: 12.5, lineHeight: 1.6, maxWidth: "62ch" }}>
            The backend walks the hash chain and returns its own verdict. A chain
            that always reported valid would be worthless, so nothing here can
            turn a broken chain green.
          </p>
          <button
            type="button"
            className="cs-btn"
            onClick={verify}
            data-testid="verify-audit-integrity"
          >
            Verify Audit Integrity
          </button>
        </div>

        {error ? (
          <ErrorState
            message="The chain verifier did not answer. The chain is unverified, which is not the same as intact."
            onRetry={verify}
          />
        ) : !integrity ? (
          <p className="cs-dim" style={{ margin: 0, fontSize: 12.5 }}>Walking the chain…</p>
        ) : (
          <div className="cs-stack">
            <div className="cs-row" style={{ gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              <StatusDot
                state={integrity.valid ? "ok" : integrity.error ? "warning" : "critical"}
              />
              <span
                className="cs-mono"
                data-testid="audit-status"
                style={{
                  fontSize: 14,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  color: integrity.valid ? "var(--ok, #16a34a)" : integrity.error ? "var(--warn, #d97706)" : "var(--crit, #dc2626)",
                }}
              >
                {integrity.status}
              </span>
              <Tag tone="ember">{integrity.algorithm}</Tag>
            </div>

            <div className="cs-mono" style={{ fontSize: 11.5, lineHeight: 1.9, wordBreak: "break-all" }}>
              <div><span className="cs-dim">events&nbsp;&nbsp;&nbsp;&nbsp;</span> {integrity.events}</div>
              <div><span className="cs-dim">head seq&nbsp;&nbsp;</span> {integrity.last_seq}</div>
              <div><span className="cs-dim">last_hash&nbsp;</span> <span data-testid="audit-last-hash">{integrity.last_hash}</span></div>
              <div><span className="cs-dim">genesis&nbsp;&nbsp;&nbsp;</span> {integrity.genesis_hash}</div>
              <div>
                <span className="cs-dim">verified&nbsp;&nbsp;</span>{" "}
                {checkedAt ? new Date(checkedAt).toLocaleTimeString() : "—"}
              </div>
            </div>

            {!integrity.valid && (
              <div className="cs-agentcard" style={{ marginBottom: 0, borderColor: "var(--crit, #dc2626)" }}>
                <div className="cs-kpi__label" style={{ color: "var(--crit, #dc2626)", marginBottom: 6 }}>
                  Broken link
                </div>
                <div className="cs-mono" style={{ fontSize: 12, marginBottom: 6 }}>
                  seq {integrity.broken_seq ?? "—"} · id {integrity.broken_id ?? "—"}
                </div>
                <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.6 }}>
                  {integrity.reason ?? integrity.error ?? "the verifier gave no reason"}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}

function SignedArtifactsPanel() {
  const [signatures, setSignatures] = useState<ArtifactSignatures | null>(null);
  const [error, setError] = useState(false);
  const [verifications, setVerifications] = useState<Record<string, ArtifactVerification | SignatureVerification>>({});
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api.artifacts
      .signatures()
      .then((v) => {
        if (alive) setSignatures(v);
      })
      .catch(() => alive && setError(true));
    return () => {
      alive = false;
    };
  }, []);

  const verify = (artifact: SignedArtifactRecord) => {
    setBusy(artifact.artifact_id);
    // The real Ed25519 implementation, reached through the security route so
    // the page cannot report a verification the service never ran.
    api.security
      .verifyArtifact(artifact.artifact_id)
      .then((r) => setVerifications((prev) => ({ ...prev, [artifact.artifact_id]: r })))
      .catch(() =>
        setVerifications((prev) => ({
          ...prev,
          [artifact.artifact_id]: {
            available: false,
            reason: "the verification request failed",
          } as ArtifactVerification,
        })),
      )
      .finally(() => setBusy(null));
  };

  return (
    <Panel title="Signed Artifacts">
      <div className="cs-panel__body">
        {error ? (
          <ErrorState message="The artifact signature records could not be read." />
        ) : !signatures ? (
          <p className="cs-dim" style={{ margin: 0, fontSize: 12.5 }}>Reading signature records…</p>
        ) : !signatures.available ? (
          <EmptyState title="No artifact store is wired" detail={signatures.scope} />
        ) : (
          <div className="cs-stack">
            <div className="cs-row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <Tag tone="ok">{signatures.totals.signed} signed</Tag>
              <Tag tone="warn">{signatures.totals.unsigned} unsigned</Tag>
              {signatures.totals.signature_failed > 0 && (
                <Tag tone="bad">{signatures.totals.signature_failed} failed</Tag>
              )}
              <span className="cs-dim" style={{ fontSize: 12.5 }}>
                {signatures.algorithm}
                {signatures.key_id ? ` · key ${signatures.key_id}` : ""}
              </span>
            </div>

            {signatures.flagged && (
              <p className="cs-dim" style={{ margin: 0, fontSize: 12.5, lineHeight: 1.6 }}>
                No signing key is configured for this deployment, so nothing here
                can be signed. Generated artifacts are recorded as unsigned rather
                than verified.
              </p>
            )}

            {signatures.artifacts.length === 0 ? (
              <EmptyState
                title="No artifacts generated yet"
                detail="Signature records appear here as artifacts are produced. Nothing is listed because nothing exists — not because the list failed to load."
              />
            ) : (
              <table className="cs-table">
                <thead>
                  <tr>
                    <th>Artifact</th>
                    <th>Type</th>
                    <th>Created</th>
                    <th>SHA-256</th>
                    <th>Signature</th>
                    <th>Verification</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {signatures.artifacts.map((artifact) => {
                    const checked = verifications[artifact.artifact_id];
                    const status = checked?.status;
                    return (
                      <tr key={artifact.artifact_id} data-testid={`artifact-${artifact.artifact_id}`}>
                        <td className="cs-mono">{artifact.filename}</td>
                        <td className="cs-mono">{artifact.type}</td>
                        <td className="cs-mono" title={artifact.created_at ?? undefined}>
                          {artifact.created_at ? timeAgo(artifact.created_at) : "—"}
                        </td>
                        <td className="cs-mono" title={artifact.sha256}>
                          {artifact.sha256.slice(0, 16)}…
                        </td>
                        <td>
                          <Tag
                            tone={
                              artifact.signature_status === "signed"
                                ? "ok"
                                : artifact.signature_status === "signature_failed"
                                  ? "bad"
                                  : "warn"
                            }
                          >
                            {artifact.signature_status}
                          </Tag>
                          <div className="cs-dim cs-mono" style={{ fontSize: 10.5, marginTop: 3 }}>
                            {artifact.algorithm ?? signatures.algorithm}
                            {artifact.signature_key_id ? ` · ${artifact.signature_key_id.slice(0, 8)}…` : ""}
                          </div>
                        </td>
                        <td className="cs-mono">
                          {checked ? (
                            status === "SIGNATURE VALID" || status === "INTEGRITY VALID" ? (
                              <Tag tone="ok">{status}</Tag>
                            ) : status === "UNSIGNED" ? (
                              <Tag tone="warn">{status}</Tag>
                            ) : (
                              <Tag tone="bad">{status ?? "UNVERIFIABLE"}</Tag>
                            )
                          ) : (
                            artifact.verification_status
                          )}
                          {checked && "available" in checked && !checked.available && (
                            <div className="cs-dim" style={{ fontSize: 10.5 }}>
                              {checked.reason ?? "the verifier did not answer"}
                            </div>
                          )}
                        </td>
                        <td>
                          <button
                            type="button"
                            className="cs-btn"
                            onClick={() => verify(artifact)}
                            disabled={busy === artifact.artifact_id}
                            data-testid={`verify-artifact-${artifact.artifact_id}`}
                          >
                            {busy === artifact.artifact_id ? "Verifying…" : "Verify Artifact"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}

            <p className="cs-dim" style={{ margin: 0, fontSize: 12, lineHeight: 1.6 }}>
              Verification is an Ed25519 check against the bytes currently on
              disk, performed by the backend — the same implementation
              <span className="cs-mono"> scripts/verify_artifact</span> uses from
              a checkout.
            </p>
          </div>
        )}
      </div>
    </Panel>
  );
}

export default function SovereigntyPage() {
  const [status, setStatus] = useState<SovereigntyStatus | null>(null);
  const [error, setError] = useState(false);

  const load = useCallback(() => {
    setError(false);
    api.security
      .sovereignty()
      .then(setStatus)
      .catch(() => {
        setStatus(null);
        setError(true);
      });
  }, []);

  useEffect(load, [load]);

  return (
    <>
      <div className="cs-pagehead">
        <div>
          <span className="cs-pagehead__kicker">System</span>
          <h1>Sovereignty Center</h1>
        </div>
        <span className="cs-pagehead__meta">
          measured posture · network sentinel · audit chain · signatures · clearance
        </span>
      </div>

      <div className="cs-stack">
        <Panel title="Sovereignty Status">
          <div className="cs-panel__body" data-testid="sovereignty-status">
            {error ? (
              <ErrorState
                message="The status endpoint did not answer, so no posture is being reported. Nothing here is assumed on its behalf."
                onRetry={load}
              />
            ) : (
              <div className="cs-stack">
                {status && <SecurityOverview status={status} />}
                <StatusBar status={status} />
                {status && <CapabilityGrid capabilities={status.capabilities} />}
              </div>
            )}
          </div>
        </Panel>

        <Panel title="Live Network Sentinel">
          <div className="cs-panel__body">
            <p className="cs-dim" style={{ margin: "0 0 12px", fontSize: 12.5, lineHeight: 1.65 }}>
              Every allow/block decision the egress guard makes, streamed as it
              happens. The subscription exists only while this panel is mounted.
              Fields the policy did not observe are shown as
              <span className="cs-mono"> —</span> rather than inferred.
            </p>
            <SentinelStreamPanel />
          </div>
        </Panel>

        <AuditIntegrityPanel />
        <SignedArtifactsPanel />
        <SecurityEventsPanel />
        <AccessControlPanel status={status?.status ?? null} />
        <SecurityEvaluationPanel />
      </div>
    </>
  );
}
