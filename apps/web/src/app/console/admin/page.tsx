"use client";

/**
 * Admin — one page, five tabs: Users & Roles · Models · Security · Audit · System.
 * The sovereignty posture panel is the centerpiece: proof nothing leaves.
 */
import { useEffect, useState } from "react";
import { ErrorState, Panel, Progress, Ring, SkeletonRows, StatusDot, Tabs, Tag, timeAgo } from "@/components/ui/primitives";
import { Icon } from "@/components/ui/Icon";
import { consoleData } from "@/lib/data/console";
import type { AdminUser, AuditEvent, ModelStatus, SystemPosture } from "@/types/console";
import { api } from "@/lib/api";
import type { HealthResponse } from "@/types";

function PostureGauge({ posture }: { posture: SystemPosture }) {
  const score =
    (posture.model_gateway === "local" ? 25 : 0) +
    (posture.sandbox === "isolated" ? 25 : 0) +
    (posture.egress === "denied" ? 25 : 0) +
    (posture.external_calls_24h === 0 ? 25 : 10);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
      <Ring value={score} size={104} tone={score === 100 ? "ok" : "warn"} label={`sovereignty score ${score}`} />
      <div>
        <p className="cs-mono cs-text-ok" style={{ margin: "0 0 6px", fontSize: 10, letterSpacing: "0.3em", textTransform: "uppercase" }}>
          Sovereignty score
        </p>
        <p style={{ margin: 0, fontSize: 12.5, color: "var(--ink-2)", lineHeight: 1.65, maxWidth: 380 }}>
          Every model runs on-prem, execution is sandboxed, and egress is denied.
          A lower score appears the moment any boundary weakens.
        </p>
      </div>
    </div>
  );
}

export default function AdminPage() {
  const [tab, setTab] = useState("security");
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [models, setModels] = useState<ModelStatus[] | null>(null);
  const [posture, setPosture] = useState<SystemPosture | null>(null);
  /** True only when the posture request actually failed — an endless skeleton
   *  would read as "still loading" forever. */
  const [postureError, setPostureError] = useState(false);
  const [audit, setAudit] = useState<AuditEvent[] | null>(null);
  const [auditFilter, setAuditFilter] = useState("");
  /**
   * The real model runtime, probed from the backend. `undefined` = probing,
   * `null` = unreachable. The seeded model list below is presentation data;
   * this panel is the operational truth and says so when they disagree.
   */
  const [runtime, setRuntime] = useState<HealthResponse | null | undefined>(undefined);

  useEffect(() => {
    // `alive` guards every setState, not just the health probe: this page makes
    // five independent requests and any of them can resolve after unmount.
    let alive = true;
    consoleData.admin.users().then((v) => { if (alive) setUsers(v); });
    consoleData.admin.models().then((v) => { if (alive) setModels(v); });
    // Probe the real model runtime. A failure is reported as offline — it is
    // never softened into "probably fine".
    api
      .health()
      .then((h) => { if (alive) setRuntime(h); })
      .catch(() => { if (alive) setRuntime(null); });
    // These two used to sit *after* the cleanup `return`, which made them
    // unreachable: posture and audit were never fetched and the Security,
    // Audit and System tabs rendered an endless skeleton. The blank panels
    // were the symptom; the misplaced `return` was the cause.
    consoleData.admin
      .posture()
      .then((p) => { if (alive) setPosture(p); })
      .catch(() => { if (alive) setPostureError(true); });
    consoleData.admin.audit().then((a) => { if (alive) setAudit(a); });
    return () => { alive = false; };
  }, []);

  return (
    <>
      <div className="cs-pagehead">
        <div>
          <span className="cs-pagehead__kicker">System</span>
          <h1>Admin</h1>
        </div>
        <span className="cs-pagehead__meta">users · local models · security posture · audit ledger</span>
      </div>

      <Panel pad={false}>
        <div style={{ padding: "12px 16px 0" }}>
          <Tabs
            tabs={[
              { id: "security", label: "Security Posture" },
              { id: "users", label: "Users & Roles", count: users?.length },
              { id: "models", label: "Models", count: models?.length },
              { id: "audit", label: "Audit Log", count: audit?.length },
              { id: "system", label: "System" },
            ]}
            active={tab}
            onChange={setTab}
          />
        </div>

        <div className="cs-panel__body">
          {tab === "security" &&
            (posture ? (
              <div className="cs-stack">
                <PostureGauge posture={posture} />
                <div className="cs-grid-2">
                  {(
                    [
                      ["Model gateway", posture.model_gateway, "All inference on local models (Ollama → vLLM). No external AI endpoints configured.", "cpu", posture.model_gateway === "local" ? "ok" : posture.model_gateway === "degraded" ? "warn" : "crit"],
                      ["Execution sandbox", posture.sandbox, "Code runs in an isolated sandbox: no network, no host filesystem, resource-capped.", "lock", posture.sandbox === "isolated" ? "ok" : "crit"],
                      ["Network egress", posture.egress, "Outbound traffic denied by default; nothing phones home. Allowlist changes are audited.", "shield", posture.egress === "denied" ? "ok" : "warn"],
                      [
                        "External calls · process lifetime",
                        String(posture.external_calls_24h),
                        posture.external_calls_24h === 0
                          ? "Measured zero. Every outbound request passes the egress guard, which records the destination host. Loopback traffic to the local model server is counted separately and is not external."
                          : `${posture.external_calls_24h} outbound request(s) reached a non-loopback host. See the audit log for what initiated them.`,
                        "globe",
                        posture.external_calls_24h === 0 ? "ok" : "warn",
                      ],
                      [
                        "Blocked egress attempts",
                        String(posture.egress_blocked_24h),
                        "Requests the policy refused before they could leave. A non-zero count is the guard working, not a breach.",
                        "shield",
                        "ok",
                      ],
                    ] as const
                  ).map(([label, value, detail, icon, tone], i) => (
                    <div
                      key={label}
                      className="cs-agentcard"
                      style={{ marginBottom: 0, animationDelay: `${i * 90}ms` }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 8 }}>
                        <Icon name={icon} size={14} />
                        <strong style={{ fontSize: 13 }}>{label}</strong>
                        <span
                          className={`cs-mono ${tone === "ok" ? "cs-text-ok" : tone === "warn" ? "cs-text-warn" : ""}`}
                          style={{ marginLeft: "auto", fontSize: 11, textTransform: "uppercase" }}
                        >
                          {value}
                        </span>
                      </div>
                      <p className="cs-dim" style={{ margin: 0, fontSize: 12, lineHeight: 1.6 }}>{detail}</p>
                    </div>
                  ))}
                </div>
              </div>
            ) : postureError ? (
              <ErrorState message="The sovereignty posture probe failed. /health did not answer, so no posture can be reported — this is not a clean bill of health." />
            ) : (
              <SkeletonRows rows={4} />
            ))}

          {tab === "users" &&
            (users ? (
              <table className="cs-table">
                <thead>
                  <tr>
                    <th scope="col">User</th>
                    <th scope="col">Role</th>
                    <th scope="col">Email</th>
                    <th scope="col">Last active</th>
                  </tr>
                </thead>
                <tbody className="cs-fade-list">
                  {users.map((u) => (
                    <tr key={u.id}>
                      <td>
                        <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <span className="cs-userchip__avatar">{u.name.split(" ").map((p) => p[0]).join("").slice(0, 2).toUpperCase()}</span>
                          {u.name}
                        </span>
                      </td>
                      <td><Tag tone={u.role === "admin" ? "ember" : "ai"}>{u.role}</Tag></td>
                      <td className="cs-mono cs-dim">{u.email}</td>
                      <td className="cs-mono cs-dim">{timeAgo(u.last_active)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <SkeletonRows rows={5} />
            ))}

          {tab === "models" && (
            <Panel
              title="Model runtime"
              hud
              style={{ marginBottom: 14 }}
              actions={
                <span className="cs-mono" style={{ fontSize: 9, letterSpacing: "0.18em" }}>
                  {runtime === undefined
                    ? "PROBING…"
                    : runtime === null
                      ? "UNREACHABLE"
                      : runtime.llm?.running
                        ? "CONNECTED"
                        : "OFFLINE"}
                </span>
              }
            >
              {runtime === undefined ? (
                <SkeletonRows rows={2} label="Probing the model gateway…" />
              ) : runtime === null ? (
                <div className="cs-strip" style={{ borderColor: "rgba(220,38,38,0.4)", margin: 0 }}>
                  <span><StatusDot state="critical" /> OLLAMA OFFLINE — the backend did not answer <code>/health</code>.</span>
                  <span className="cs-dim" style={{ marginLeft: "auto", fontSize: 11 }}>
                    Local inference is unavailable. Start the API and Ollama, then reload.
                  </span>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div className="cs-strip" style={{ margin: 0, borderColor: runtime.llm?.running ? "rgba(16,185,129,0.35)" : "rgba(245,158,11,0.4)" }}>
                    <span>
                      <StatusDot state={runtime.llm?.running ? "ok" : "warning"} pulse={Boolean(runtime.llm?.running)} />
                      {runtime.llm?.running ? "OLLAMA CONNECTED" : "OLLAMA OFFLINE"}
                    </span>
                    <span className="cs-mono cs-dim" style={{ fontSize: 10 }}>
                      gateway {runtime.llm?.backend ?? "unknown"} · db {runtime.database ?? "?"} · v{runtime.version ?? "?"}
                    </span>
                    <span className="cs-dim" style={{ marginLeft: "auto", fontSize: 11 }}>
                      serving {runtime.llm?.models?.length ?? 0} local model{(runtime.llm?.models?.length ?? 0) === 1 ? "" : "s"}
                    </span>
                  </div>

                  {runtime.llm?.error && (
                    <p className="cs-dim" style={{ margin: 0, fontSize: 11.5 }}>Gateway error: {runtime.llm.error}</p>
                  )}

                  {(runtime.llm?.models?.length ?? 0) > 0 && (
                    <div className="cs-chips">
                      {runtime.llm!.models!.map((m) => (
                        <span key={m} className="cs-chip" style={{ cursor: "default", borderColor: "rgba(37,99,235,0.3)" }}>{m}</span>
                      ))}
                    </div>
                  )}

                  {runtime.services && Object.keys(runtime.services).length > 0 && (
                    <div className="cs-chips">
                      {Object.entries(runtime.services).map(([name, v]) => (
                        <span key={name} className="cs-chip" style={{ cursor: "default" }}>
                          {name} {v.configured ? "configured" : "not configured"}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </Panel>
          )}

          {tab === "models" &&
            (models ? (
              <table className="cs-table">
                <thead>
                  <tr>
                    <th scope="col">Role</th>
                    <th scope="col">Model</th>
                    <th scope="col">Status</th>
                    <th scope="col">Latency</th>
                  </tr>
                </thead>
                <tbody className="cs-fade-list">
                  {models.map((m) => (
                    <tr key={m.role}>
                      <td className="cs-mono cs-text-cyan">{m.role}</td>
                      <td className="cs-mono">{m.model}</td>
                      <td>
                        <Tag tone={m.status === "loaded" ? "ok" : m.status === "available" ? "warn" : "crit"}>
                          <StatusDot state={m.status === "loaded" ? "ok" : m.status === "available" ? "warning" : "critical"} />
                          {m.status}
                        </Tag>
                      </td>
                      <td className="cs-mono cs-dim">{m.latency_ms != null ? `${m.latency_ms} ms` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <SkeletonRows rows={5} />
            ))}

          {tab === "audit" &&
            (audit ? (
              <>
                <input
                  className="cs-input"
                  style={{ marginBottom: 14, maxWidth: 340 }}
                  placeholder="Filter by actor or action…"
                  value={auditFilter}
                  onChange={(e) => setAuditFilter(e.target.value)}
                  aria-label="Filter audit log"
                />
                <div className="cs-trace">
                  {audit
                    .filter((a) => `${a.actor} ${a.action}`.toLowerCase().includes(auditFilter.toLowerCase()))
                    .map((a, i) => {
                      // The dot reflects the recorded outcome, not a guess from
                      // the action's spelling. A failed row used to be
                      // indistinguishable from a successful one, and carried an
                      // "ai" dot either way.
                      const failed = a.outcome === "failure";
                      return (
                        <div key={a.id} className="cs-trace__row" style={{ animationDelay: `${i * 60}ms` }}>
                          <StatusDot state={failed ? "critical" : a.outcome ? "ok" : "unknown"} />
                          <span>
                            <div className="cs-mono" style={{ fontSize: 12.5 }}>{a.action}</div>
                            <div className="cs-trace__detail">
                              {a.actor}
                              {a.resource_type && ` · ${a.resource_type}`}
                              {a.resource_id && ` · ${a.resource_id}`}
                              {a.agent && ` · ${a.agent}`}
                              {a.tool && ` · ${a.tool}`}
                              {a.model && ` · ${a.model}`}
                              {a.approval && ` · approval ${a.approval}`}
                            </div>
                            {a.error && (
                              <div className="cs-trace__detail" style={{ color: "var(--red)" }}>
                                {a.error}
                              </div>
                            )}
                          </span>
                          <span className="cs-trace__ms">
                            {failed ? "FAILED · " : ""}
                            {timeAgo(a.at)}
                          </span>
                        </div>
                      );
                    })}
                </div>
              </>
            ) : (
              <SkeletonRows rows={5} />
            ))}

          {tab === "system" &&
            (posture ? (
              <div className="cs-grid-2">
                <Panel title="Storage">
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5, marginBottom: 9 }}>
                    <span className="cs-dim">Document store + indices</span>
                    <span className="cs-mono">
                      {posture.storage_total_gb > 0
                        ? `${posture.storage_used_gb} / ${posture.storage_total_gb} GB`
                        : "unavailable"}
                    </span>
                  </div>
                  <Progress
                    value={
                      posture.storage_total_gb > 0
                        ? (posture.storage_used_gb / posture.storage_total_gb) * 100
                        : 0
                    }
                    tone="cyan"
                  />
                </Panel>
                <Panel title="Runtime">
                  <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 12.5 }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span className="cs-dim">Version</span>
                      <span className="cs-mono cs-text-cyan">v{posture.version}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span className="cs-dim">Database</span>
                      <Tag tone={posture.database === "ok" ? "ok" : "crit"}>{posture.database}</Tag>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span className="cs-dim">API gateway</span>
                      <Tag tone="ok">healthy</Tag>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span className="cs-dim">Deployment</span>
                      <span className="cs-mono">single-node · on-prem</span>
                    </div>
                  </div>
                </Panel>
              </div>
            ) : (
              <SkeletonRows rows={4} />
            ))}
        </div>
      </Panel>
    </>
  );
}
