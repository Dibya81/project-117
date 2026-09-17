"use client";

/**
 * LIVE SECURITY SIGNALS — the compact panel beside the diagram.
 *
 * Deliberately secondary: this is the numeric companion to the architecture
 * view, not another dashboard. Every row is one backend reading, printed with
 * the endpoint it came from. A reading that did not arrive says so; it never
 * falls back to a zero, because "0 blocked" and "the monitor did not answer"
 * are different facts about the world.
 */
import { Panel, StatusDot, Tag } from "@/components/ui/primitives";
import type {
  ArtifactSignatures,
  AuditIntegrity,
  CallerIdentity,
  ModelsStatus,
  SecurityEvents,
  SovereigntyStatus,
} from "@/lib/api";
import type { HealthResponse } from "@/types";
import type { EgressPulse } from "@/lib/security/confidentiality";
import type { NetworkSentinel } from "@/lib/security/useNetworkSentinel";
import { STATUS_TONE } from "@/lib/security/confidentiality";

export interface SignalSources {
  sovereignty: SovereigntyStatus | null;
  models: ModelsStatus | null;
  integrity: AuditIntegrity | null;
  signatures: ArtifactSignatures | null;
  health: HealthResponse | null;
  identity: CallerIdentity | null;
  events: SecurityEvents | null;
  modelError: boolean;
  integrityError: boolean;
}

function Signal({
  label,
  source,
  tone,
  value,
  detail,
  testId,
}: {
  label: string;
  source: string;
  tone: "ok" | "warning" | "critical" | "unknown";
  value: string;
  detail?: string;
  testId?: string;
}) {
  return (
    <div className="cf-signal" data-testid={testId}>
      <div className="cf-signal__head">
        <StatusDot state={tone} />
        <span className="cf-signal__label">{label}</span>
        <span className="cf-signal__value cs-mono">{value}</span>
      </div>
      <div className="cf-signal__source cs-mono">{source}</div>
      {detail && <div className="cf-signal__detail cs-dim">{detail}</div>}
    </div>
  );
}

export function SecuritySignalsPanel({
  sources,
  sentinel,
  pulse,
}: {
  sources: SignalSources;
  sentinel: NetworkSentinel;
  pulse: EgressPulse | null;
}) {
  const { sovereignty, models, integrity, signatures, health, identity, events, modelError, integrityError } = sources;
  const net = health?.network;
  const egress = sovereignty?.status.find((s) => s.key === "egress") ?? null;
  const signing = sovereignty?.status.find((s) => s.key === "signing") ?? null;
  const sandbox = sovereignty?.status.find((s) => s.key === "sandbox") ?? null;

  const rolesAssigned = models ? Object.values(models.roles ?? {}).filter((m) => m != null).length : null;
  const rolesTotal = models ? Object.keys(models.roles ?? {}).length : null;

  return (
    <Panel
      title="Live Security Signals"
      actions={
        <span className="cs-mono" style={{ fontSize: 10, letterSpacing: "0.14em", color: "var(--ink-3)" }}>
          REAL BACKEND READINGS
        </span>
      }
    >
      <div className="cs-panel__body">
        <div className="cf-signals" data-testid="cf-signals">
          <Signal
            label="Audit events"
            source="GET /api/audit/integrity → events"
            tone={integrityError ? "unknown" : integrity?.valid ? "ok" : "critical"}
            value={integrityError ? "unavailable" : `${integrity?.events ?? "—"}`}
            detail={
              integrityError
                ? "The chain verifier did not answer, so the chain is unverified."
                : integrity
                  ? `${integrity.status} · sha256 head ${integrity.last_hash.slice(0, 16)}…`
                  : "Reading the chain…"
            }
            testId="cf-signal-audit-events"
          />
          <Signal
            label="Audit integrity"
            source="GET /api/audit/integrity → status"
            tone={integrityError ? "unknown" : integrity?.valid ? "ok" : "critical"}
            value={integrityError ? "UNAVAILABLE" : (integrity?.status ?? "—")}
            detail={
              integrity
                ? `${integrity.algorithm} · genesis ${integrity.genesis_hash.slice(0, 12)}…`
                : "The verifier's own verdict, never re-derived in the browser."
            }
            testId="cf-signal-audit-integrity"
          />
          <Signal
            label="Egress policy"
            source="GET /api/security/sovereignty → egress"
            tone={egress ? STATUS_TONE[egress.state === "VERIFIED" ? "VERIFIED" : egress.state === "PARTIAL" ? "PARTIAL" : "IMPLEMENTED"] : "unknown"}
            value={egress ? egress.state : "unavailable"}
            detail={
              egress
                ? `${String(egress.evidence.policy ?? "—")} · ${String(egress.evidence.external_blocked ?? "—")} external refused · ${String(
                    egress.evidence.external_allowed ?? "—",
                  )} reached`
                : "The egress entry did not answer."
            }
            testId="cf-signal-egress"
          />
          <Signal
            label="Recently blocked"
            source="GET /health → network.totals.blocked"
            tone={net ? "warning" : "unknown"}
            value={net ? `${net.totals?.blocked ?? "—"}` : "unavailable"}
            detail={
              net
                ? `hosts: ${(net.blocked_hosts ?? []).join(", ") || "none recorded"}`
                : "GET /health did not report the network monitor."
            }
            testId="cf-signal-blocked"
          />
          <Signal
            label="Recently allowed (loopback)"
            source="GET /health → network.totals.local_allowed"
            tone={net ? "ok" : "unknown"}
            value={net ? `${net.totals?.local_allowed ?? "—"}` : "unavailable"}
            detail={
              net
                ? `allowed hosts: ${(net.allowed_hosts ?? []).join(", ") || "none"} · external reached: ${
                    net.external_allowed ?? "—"
                  }`
                : "—"
            }
            testId="cf-signal-allowed"
          />
          <Signal
            label="Signed artifacts"
            source="GET /api/artifacts/signatures → totals"
            tone={signatures ? (signatures.totals.signed > 0 ? "ok" : "warning") : "unknown"}
            value={signatures ? `${signatures.totals.signed} signed` : "unavailable"}
            detail={
              signatures
                ? `${signatures.algorithm}${signatures.key_id ? ` · key ${signatures.key_id}` : ""} · ${
                    signatures.totals.unsigned
                  } unsigned`
                : "signing reported through the sovereignty entry instead"
            }
            testId="cf-signal-signed"
          />
          <Signal
            label="Security events"
            source="GET /api/security/events → total"
            tone={events?.available ? "ok" : "unknown"}
            value={events?.available ? `${events.total}` : "unavailable"}
            detail={
              events?.available
                ? `namespaces: ${events.namespaces.map((n) => `${n.namespace}${n.count}`).join(" ") || "none"}`
                : (events?.reason ?? "the security-event ledger did not answer")
            }
            testId="cf-signal-security-events"
          />
          <Signal
            label="Models"
            source="GET /api/models → roles"
            tone={modelError ? "unknown" : models ? "ok" : "unknown"}
            value={modelError ? "unavailable" : models ? `${rolesAssigned}/${rolesTotal} roles` : "reading…"}
            detail={
              modelError
                ? "The model endpoint did not answer, so no role mapping is shown."
                : models
                  ? `${models.backend.name ?? "—"} · ${Object.values(models.models ?? {}).reduce(
                      (n, l) => n + (l?.length ?? 0),
                      0,
                    )} model(s) served`
                  : "—"
            }
            testId="cf-signal-models"
          />
          <Signal
            label="Sandbox"
            source="GET /api/security/sovereignty → sandbox"
            tone={sandbox ? STATUS_TONE["UNAVAILABLE"] : "unknown"}
            value={sandbox ? sandbox.state : "unavailable"}
            detail={sandbox?.detail ?? "No sandbox entry answered. Isolation is not claimed."}
            testId="cf-signal-sandbox"
          />
          <Signal
            label="Network sentinel stream"
            source="GET /api/network/stream (SSE)"
            tone={sentinel.state === "live" ? "ok" : sentinel.state === "lost" ? "warning" : "unknown"}
            value={sentinel.state}
            detail={
              sentinel.attached
                ? `${sentinel.events.length} frame(s) received since this page opened${
                    pulse ? ` · last ${pulse.action}` : ""
                  }`
                : "Opening the sentinel stream. Subscribed only while this page is mounted."
            }
            testId="cf-signal-sentinel"
          />
          <Signal
            label="Caller identity"
            source="GET /api/auth/me → roles"
            tone={identity ? (identity.authRequired ? "ok" : "warning") : "unknown"}
            value={identity ? identity.roles.join(", ") || "none" : "unavailable"}
            detail={
              identity
                ? `user ${identity.user} · authenticated ${String(identity.authenticated)} · authRequired ${String(
                    identity.authRequired,
                  )}`
                : "The identity endpoint did not answer."
            }
            testId="cf-signal-identity"
          />
        </div>

        {pulse && (
          <p className="cf-signals__last cs-mono" data-testid="cf-signal-last-decision">
            LAST DECISION · {pulse.action} · {pulse.destination ?? "unnamed"}
            {pulse.port ? `:${pulse.port}` : ""} · {new Date(pulse.at).toLocaleTimeString()} ·{" "}
            {pulse.local ? "loopback" : "non-loopback"}
          </p>
        )}

        <p className="cs-dim" style={{ margin: "10px 0 0", fontSize: 11.5, lineHeight: 1.6 }}>
          Values are read from the endpoints named beside them. Where an endpoint did not answer the
          row says <i>unavailable</i> rather than showing a zero.
          {sandbox && (
            <>
              {" "}
              Sandbox isolation is <Tag tone="bad">not available</Tag> on this host.
            </>
          )}
        </p>
      </div>
    </Panel>
  );
}
