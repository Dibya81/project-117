"use client";

/**
 * The Security Console's data panels, split out of the route on purpose.
 *
 * Everything here is fetched after first paint: the events ledger, the
 * controlled refusal evaluation and the access-control matrix are three queries
 * that the status bar does not need, and the home page's bundle budget must not
 * pay for them. The route lazy-loads this module with `ssr: false`, the same
 * treatment it gives the sentinel stream.
 *
 * Every value rendered here is the backend's. Where a section has nothing to
 * show it says so, and where a control does not exist it says that instead of
 * showing a green tick.
 */
import { useCallback, useEffect, useState } from "react";
import { EmptyState, ErrorState, Panel, Tag, timeAgo } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type {
  EvaluationResult,
  SecurityEvaluation,
  SecurityEvent,
  SecurityEvents,
  SovereigntyEntry,
} from "@/lib/api";

const OUTCOME_TONE: Record<string, "ok" | "crit" | "warn" | "ember" | "bad"> = {
  success: "ok",
  failure: "crit",
  refused: "warn",
};

/** The namespaces the Security Events panel is looking for, and what each is. */
const NAMESPACES: { prefix: string; label: string; meaning: string }[] = [
  { prefix: "network.", label: "Network", meaning: "an egress decision the policy allowed or refused" },
  { prefix: "clearance.", label: "Clearance", meaning: "a retrieval or read refused above the caller's clearance" },
  { prefix: "permission.", label: "Permission", meaning: "a role refused an action" },
  { prefix: "audit.", label: "Audit integrity", meaning: "a chain verification" },
  { prefix: "sandbox.", label: "Sandbox", meaning: "a sandbox execution, including a refusal" },
  { prefix: "auth.", label: "Authentication", meaning: "a sign-in or token event" },
  { prefix: "approval.", label: "Approval", meaning: "a step parked for, or granted, human consent" },
];

export function SecurityEventsPanel() {
  const [data, setData] = useState<SecurityEvents | null>(null);
  const [error, setError] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let alive = true;
    api.security
      .events(40)
      .then((r) => {
        if (!alive) return;
        setData(r);
        setError(false);
      })
      .catch(() => {
        if (!alive) return;
        setData(null);
        setError(true);
      });
    return () => {
      alive = false;
    };
  }, [reload]);

  const counts = new Map<string, number>(
    (data?.namespaces ?? []).map((n) => [n.namespace, n.count]),
  );

  return (
    <Panel title="Security Events">
      <div className="cs-panel__body">
        {error ? (
          <ErrorState
            message="The security-event ledger did not answer. This is an unread ledger, not an empty one."
            onRetry={() => setReload((k) => k + 1)}
          />
        ) : !data ? (
          <p className="cs-dim" style={{ margin: 0, fontSize: 12.5 }}>Reading the ledger…</p>
        ) : (
          <div className="cs-stack">
            {/* Which controls have ever fired. A zero here is a measurement: it
                says the control has not been exercised, not that it is absent. */}
            <div className="cs-row" style={{ gap: 6, flexWrap: "wrap" }}>
              {NAMESPACES.map((ns) => {
                const count = counts.get(ns.prefix) ?? 0;
                return (
                  <Tag key={ns.prefix} tone={count > 0 ? "ok" : "ember"}>
                    {ns.label} {count}
                  </Tag>
                );
              })}
            </div>
            <p className="cs-dim" style={{ margin: 0, fontSize: 11.5, lineHeight: 1.6 }}>
              A zero is a measurement, not an assurance: it means that control has not
              fired since this log began. Transport rows (<span className="cs-mono">http.*</span>)
              are excluded — they are a request log, not a security record.
            </p>

            {data.events.length === 0 ? (
              <EmptyState
                title="No security events recorded"
                detail="Nothing in the network, clearance, permission, audit, sandbox, auth or approval namespaces has been written yet."
              />
            ) : (
              <div style={{ maxHeight: 340, overflowY: "auto", overscrollBehavior: "contain" }}>
                <table className="cs-table">
                  <thead>
                    <tr>
                      <th>When</th>
                      <th>Action</th>
                      <th>Outcome</th>
                      <th>Resource</th>
                      <th>Actor</th>
                      <th>Agent</th>
                      <th>Tool</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.events.map((event: SecurityEvent) => (
                      <tr key={event.id}>
                        <td className="cs-mono" title={event.timestamp ?? undefined}>
                          {event.timestamp ? timeAgo(event.timestamp) : "—"}
                        </td>
                        <td className="cs-mono">{event.action}</td>
                        <td>
                          <Tag tone={OUTCOME_TONE[event.outcome ?? ""] ?? "ember"}>
                            {event.outcome ?? "—"}
                          </Tag>
                        </td>
                        <td className="cs-mono">
                          {event.resource_type
                            ? `${event.resource_type}/${event.resource_id ?? "—"}`
                            : "—"}
                        </td>
                        <td className="cs-mono">{event.user ?? "—"}</td>
                        <td className="cs-mono">{event.agent ?? "—"}</td>
                        <td className="cs-mono">{event.tool ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}

const EVAL_TONE: Record<EvaluationResult["status"], "ok" | "bad" | "warn"> = {
  PASS: "ok",
  FAIL: "bad",
  "NOT IMPLEMENTED": "warn",
};

export function SecurityEvaluationPanel() {
  const [data, setData] = useState<SecurityEvaluation | null>(null);
  const [error, setError] = useState(false);
  const [running, setRunning] = useState(false);

  const run = useCallback(() => {
    setRunning(true);
    api.security
      .evaluation()
      .then((r) => {
        setData(r);
        setError(false);
      })
      .catch(() => {
        setData(null);
        setError(true);
      })
      .finally(() => setRunning(false));
  }, []);

  useEffect(() => {
    run();
  }, [run]);

  return (
    <Panel title="Security Evaluation">
      <div className="cs-panel__body">
        <div className="cs-row" style={{ justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <p className="cs-dim" style={{ margin: 0, fontSize: 12.5, lineHeight: 1.6, maxWidth: "62ch" }}>
            The refusal controls this build actually has, exercised on demand:
            real permission checks, the real egress policy, the real clearance
            layer. Nothing is written to the audit log and no external socket is
            opened. A control this build does not have is reported as such.
          </p>
          <button
            type="button"
            className="cs-btn"
            onClick={run}
            disabled={running}
            data-testid="run-security-evaluation"
          >
            {running ? "Running…" : "Re-run evaluation"}
          </button>
        </div>

        {error ? (
          <ErrorState message="The evaluation endpoint did not answer." onRetry={run} />
        ) : !data ? (
          <p className="cs-dim" style={{ margin: 0, fontSize: 12.5 }}>Exercising the controls…</p>
        ) : (
          <div className="cs-stack">
            <div className="cs-row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <Tag tone="ok">{data.passed} passed</Tag>
              <Tag tone="warn">{data.not_implemented} not implemented</Tag>
              <span className="cs-dim" style={{ fontSize: 12 }}>
                ran {timeAgo(data.generated_at)}
              </span>
            </div>
            <table className="cs-table">
              <thead>
                <tr>
                  <th>Scenario</th>
                  <th>Expected</th>
                  <th>Actual</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((row: EvaluationResult) => (
                  <tr key={row.id} data-testid={`evaluation-${row.id}`}>
                    <td>
                      <b style={{ fontWeight: 550 }}>{row.name}</b>
                      <p className="cs-dim" style={{ margin: "2px 0 0", fontSize: 11.5, lineHeight: 1.5 }}>
                        {row.detail}
                      </p>
                    </td>
                    <td className="cs-mono">{row.expected}</td>
                    <td className="cs-mono" style={{ maxWidth: 280 }}>{row.actual}</td>
                    <td>
                      <Tag tone={EVAL_TONE[row.status]}>{row.status}</Tag>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Panel>
  );
}

/** Access control, read from the backend's own role and clearance maps. */
export function AccessControlPanel({
  status,
}: {
  status: SovereigntyEntry[] | null;
}) {
  const rbac = status?.find((entry) => entry.key === "rbac");
  const clearance = status?.find((entry) => entry.key === "clearance");
  const roles = (rbac?.evidence?.roles ?? {}) as Record<string, number>;
  const levels = (clearance?.evidence?.role_clearance ?? {}) as Record<string, string>;

  return (
    <Panel title="Access Control">
      <div className="cs-panel__body">
        <div className="cs-stack">
          <p className="cs-dim" style={{ margin: 0, fontSize: 12.5, lineHeight: 1.65 }}>
            RBAC answers <i>who may perform an action</i>; clearance answers
            <i> what a caller&apos;s model context may contain</i>. The two are
            separate policies, and the retrieval path applies both — a permitted
            search still cannot return evidence above the caller&apos;s level.
          </p>

          {!rbac || !clearance ? (
            <p className="cs-dim" style={{ margin: 0, fontSize: 12.5 }}>
              The status endpoint did not report RBAC or clearance, so neither is being described.
            </p>
          ) : (
            <table className="cs-table">
              <thead>
                <tr>
                  <th>Role</th>
                  <th>Permissions</th>
                  <th>Clearance</th>
                </tr>
              </thead>
              <tbody>
                {Object.keys(roles)
                  .sort()
                  .map((role) => (
                    <tr key={role} data-testid={`access-role-${role}`}>
                      <td className="cs-mono">{role}</td>
                      <td className="cs-mono">{roles[role]}</td>
                      <td>
                        <Tag tone={role === "admin" ? "bad" : role === "viewer" ? "ok" : "warn"}>
                          {levels[role] ?? "—"}
                        </Tag>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}

          <p className="cs-dim" style={{ margin: 0, fontSize: 11.5, lineHeight: 1.6 }}>
            Levels are ordered PUBLIC → INTERNAL → RESTRICTED → CONFIDENTIAL →
            HIGHLY_CONFIDENTIAL. A record carrying no label is INTERNAL, not
            PUBLIC, so shipping this model did not make unlabelled documents
            world-readable. An explicit badge on a caller&apos;s identity
            overrides their role default in either direction.
          </p>
        </div>
      </div>
    </Panel>
  );
}
