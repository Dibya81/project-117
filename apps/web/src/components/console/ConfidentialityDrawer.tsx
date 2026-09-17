"use client";

/**
 * Node detail drawer.
 *
 * Every drawer prints the values the backend returned for that node — the role
 * → model map from `GET /api/models`, the caller's real roles and the clearance
 * levels from `GET /api/security/sovereignty`, the sandbox's own policy summary,
 * the full `GET /api/audit/integrity` payload, the live sentinel frames. Where
 * the backend said nothing, the drawer says so instead of filling the gap.
 *
 * The one action here is a real retrieval probe (`POST /api/search`), which is
 * how the clearance layer's authorized/withheld counts become visible: the
 * response's `withheld` is the backend's own count of chunks removed because
 * the caller's level was below the chunk's label.
 */
import { useCallback, useEffect, useState } from "react";
import { StatusDot, Tag } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { STATUS_COLOUR, STATUS_TONE, type DiagramNode } from "@/lib/security/confidentiality";
import type { NetworkSentinel } from "@/lib/security/useNetworkSentinel";
import { useRole } from "@/lib/role";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="cf-kv">
      <span className="cf-kv__label">{label}</span>
      <span className="cf-kv__value">{children}</span>
    </div>
  );
}

function Json({ value }: { value: unknown }) {
  return <pre className="cf-json">{JSON.stringify(value, null, 2)}</pre>;
}

/** The clearance probe: one real search, read for its withheld count. */
function ClearanceProbe() {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<
    | { ok: true; query: string; total: number; withheld: number; elapsed?: number }
    | { ok: false; error: string }
    | null
  >(null);

  const run = useCallback(() => {
    setBusy(true);
    setResult(null);
    const query = "refinery pump maintenance procedure";
    api.search
      .query({ query, top_k: 8, mode: "hybrid" })
      .then((r) =>
        setResult({ ok: true, query, total: r.total, withheld: r.withheld, elapsed: r.elapsed_seconds }),
      )
      .catch((e: unknown) =>
        setResult({ ok: false, error: e instanceof Error ? e.message : "the retrieval call failed" }),
      )
      .finally(() => setBusy(false));
  }, []);

  return (
    <div className="cf-probe">
      <div className="cf-kv">
        <span className="cf-kv__label">Clearance filter</span>
        <span className="cf-kv__value">
          <button type="button" className="cs-btn" onClick={run} disabled={busy} data-testid="cf-clearance-probe">
            {busy ? "Running a real retrieval…" : "Run a real retrieval probe"}
          </button>
        </span>
      </div>
      <p className="cs-dim" style={{ margin: 0, fontSize: 11.5, lineHeight: 1.6 }}>
        Runs <span className="cs-mono">POST /api/search</span> through the real clearance layer.
        Embedding the query against the local model takes roughly 20 seconds on this host, which is
        why this is a button and not part of the page load.
      </p>
      {result?.ok && (
        <div className="cf-stack" data-testid="cf-clearance-result">
          <Row label="Query">
            <span className="cs-mono">{result.query}</span>
          </Row>
          <Row label="Authorized (returned)">
            <b className="cs-mono">{result.total}</b>
          </Row>
          <Row label="Filtered by clearance">
            <b className="cs-mono" style={{ color: result.withheld > 0 ? "var(--warn)" : undefined }}>
              {result.withheld}
            </b>
          </Row>
          <Row label="Elapsed">
            <span className="cs-mono">{result.elapsed ?? "—"}s</span>
          </Row>
        </div>
      )}
      {result && !result.ok && (
        <p className="cs-dim" style={{ margin: 0, fontSize: 11.5 }}>
          The probe did not answer: {result.error}. Nothing is assumed from a failed call.
        </p>
      )}
    </div>
  );
}

function Body({ node, sentinel }: { node: DiagramNode; sentinel: NetworkSentinel }) {
  const { role } = useRole();
  const e = node.evidence;

  switch (node.id) {
    case "security_gate":
    case "permission_check": {
      const clearance = (e.clearance as { role_clearance?: Record<string, string> } | null)?.role_clearance ?? {};
      const roles = (e.caller_roles as string[] | null) ?? [];
      return (
        <div className="cf-stack">
          <Row label="Console role">
            <span className="cs-mono">{role}</span>{" "}
            <span className="cs-dim">— a console switch, not a backend role</span>
          </Row>
          <Row label="Backend caller">
            <span className="cs-mono">{(e.caller_user as string) ?? "—"}</span>
          </Row>
          <Row label="Backend role(s)">
            <span className="cs-mono">{roles.length ? roles.join(", ") : "—"}</span>
          </Row>
          <Row label="Authenticated">
            <Tag tone={e.caller_authenticated ? "ok" : "warn"}>
              {e.caller_authenticated ? "yes" : "no — identity is a header assertion"}
            </Tag>
          </Row>
          <Row label="Clearance">
            {roles.length ? (
              <span className="cf-stack">
                {roles.map((r) => (
                  <span key={r} className="cs-mono">
                    {r} → {clearance[r] ?? "not in the clearance map"}
                  </span>
                ))}
              </span>
            ) : (
              <span className="cs-dim">—</span>
            )}
          </Row>
          <Row label="Permissions granted">
            <span className="cf-tags">
              {((e.caller_permissions as string[] | null) ?? []).map((p) => (
                <Tag key={p}>{p}</Tag>
              ))}
              {!e.caller_permissions && <span className="cs-dim">—</span>}
            </span>
          </Row>
          <Row label="Role → clearance map">
            <Json value={clearance} />
          </Row>
          <p className="cs-dim" style={{ margin: 0, fontSize: 11.5, lineHeight: 1.6 }}>
            {(e.rbac as { roles?: unknown } | null) ? (
              <>
                Roles in the permission map:{" "}
                <span className="cs-mono">{JSON.stringify((e.rbac as { roles: unknown }).roles)}</span>
              </>
            ) : (
              "The RBAC map did not answer."
            )}
          </p>
          <ClearanceProbe />
        </div>
      );
    }

    case "model_router": {
      const roleMap = (e.roles as Record<string, string | null> | null) ?? {};
      const models = (e.models as Record<string, string[]> | null) ?? {};
      return (
        <div className="cf-stack">
          <Row label="Gateway">
            <span className="cs-mono">
              {(e.backend as { name?: string } | null)?.name ?? "—"} ·{" "}
              {(e.served_models as number | null) ?? "—"} model(s) served
            </span>
          </Row>
          <table className="cs-table">
            <thead>
              <tr>
                <th>Role</th>
                <th>Model</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(roleMap).map(([r, m]) => (
                <tr key={r} data-testid={`cf-role-${r}`}>
                  <td className="cs-mono">{r}</td>
                  <td className="cs-mono">
                    {m ?? <span className="cs-dim">unassigned</span>}
                  </td>
                </tr>
              ))}
              {Object.keys(roleMap).length === 0 && (
                <tr>
                  <td colSpan={2} className="cs-dim">
                    GET /api/models did not answer, so no role mapping is shown rather than a guessed one.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <Row label="Served by provider">
            <Json value={models} />
          </Row>
        </div>
      );
    }

    case "sandbox": {
      const probe = (e.probe as Record<string, unknown> | null) ?? null;
      return (
        <div className="cf-stack">
          <Row label="Status">
            <Tag tone="bad">{node.rawState ?? node.status}</Tag>
          </Row>
          <Row label="Network">
            {probe?.network ? (
              <>
                <span className="cs-mono">{String(probe.network)}</span>{" "}
                <span className="cs-dim">
                  — declared policy only. Nothing enforces it on this host because the sandbox is not
                  running, so this is not an isolation guarantee.
                </span>
              </>
            ) : (
              <span className="cs-dim">—</span>
            )}
          </Row>
          <Row label="Filesystem">
            <span className="cs-mono">{probe?.workspace ? String(probe.workspace) : "—"}</span>
          </Row>
          <Row label="Endpoint">
            <span className="cs-mono">{probe?.base_url ? String(probe.base_url) : "—"}</span>{" "}
            <span className="cs-dim">api key configured: {String(probe?.api_key_configured ?? "—")}</span>
          </Row>
          <Row label="Resource limits">
            <Json value={probe?.resource_limits ?? null} />
          </Row>
          <Row label="Images">
            <Json value={probe?.images ?? null} />
          </Row>
          <p className="cs-dim" style={{ margin: 0, fontSize: 11.5, lineHeight: 1.6 }}>
            {node.detail}
          </p>
        </div>
      );
    }

    case "audit": {
      const integrity = e.integrity as Record<string, unknown> | null;
      return (
        <div className="cf-stack">
          <Row label="Chain status">
            {integrity ? (
              <Tag tone={integrity.valid ? "ok" : integrity.error ? "warn" : "bad"}>
                {String(integrity.status)}
              </Tag>
            ) : (
              <span className="cs-dim">the verifier did not answer</span>
            )}
          </Row>
          <p className="cs-dim" style={{ margin: 0, fontSize: 11.5, lineHeight: 1.6 }}>
            The verifier&apos;s own payload from <span className="cs-mono">GET /api/audit/integrity</span>, unedited:
          </p>
          <Json value={integrity} />
          <Row label="Security namespaces">
            <Json value={e.security_event_namespaces ?? null} />
          </Row>
        </div>
      );
    }

    case "verification":
    case "signed_output": {
      const signatures = e.signatures as Record<string, unknown> | null;
      const totals = (signatures?.totals as Record<string, number> | undefined) ?? null;
      const artifacts = (signatures?.artifacts as Record<string, unknown>[] | undefined) ?? [];
      const integrity = (e.integrity as Record<string, unknown> | null) ?? null;
      return (
        <div className="cf-stack">
          <Row label="Signed">
            <Tag tone={totals?.signed ? "ok" : "warn"}>{totals?.signed ?? 0} signed</Tag>
            <Tag>{(totals?.unsigned ?? 0) as number} unsigned</Tag>
            {!!totals?.signature_failed && <Tag tone="bad">{totals.signature_failed} failed</Tag>}
          </Row>
          <Row label="Algorithm">
            <span className="cs-mono">
              {String(signatures?.algorithm ?? e.algorithm ?? "—")}
              {signatures?.key_id ? ` · key ${String(signatures.key_id)}` : ""}
            </span>
          </Row>
          {node.id === "verification" && (
            <Row label="Chain">
              <span className="cs-mono">
                {integrity ? `${String(integrity.status)} · ${String(integrity.events)} events` : "—"}
              </span>
            </Row>
          )}
          <p className="cs-dim" style={{ margin: 0, fontSize: 11.5, lineHeight: 1.6 }}>
            {node.detail}
          </p>
          {artifacts.length > 0 ? (
            <Json value={artifacts} />
          ) : (
            <p className="cs-dim" style={{ margin: 0, fontSize: 11.5 }}>
              No artifact rows exist, so there is nothing to sign or verify end-to-end. The count stays
              at zero rather than showing a green tick for an implementation that has never run here.
            </p>
          )}
        </div>
      );
    }

    case "external_network":
    case "network_sentinel":
    case "allow_block": {
      const totals = e.totals as Record<string, number> | null;
      const policy = e.policy as Record<string, unknown> | null;
      const recent = (policy?.recent as unknown) ?? null;
      return (
        <div className="cf-stack">
          <Row label="Policy">
            <span className="cs-mono">{String(policy?.policy ?? "—")}</span>
          </Row>
          <Row label="Totals (this process)">
            <span className="cs-mono">
              {totals
                ? `${totals.allowed ?? 0} allowed · ${totals.blocked ?? 0} blocked · ${totals.external_allowed ?? 0} external reached`
                : "—"}
            </span>
          </Row>
          <Row label="Blocked destinations">
            <Json value={e.blocked_hosts ?? policy?.blocked_hosts ?? null} />
          </Row>
          <Row label="Allowed destinations">
            <Json value={e.allowed_hosts ?? policy?.allowed_hosts ?? null} />
          </Row>
          <Row label="Recent decisions">
            <Json value={recent} />
          </Row>
          {node.id === "network_sentinel" && (
            <>
              <Row label="Stream">
                <span className="cs-mono">
                  {sentinel.state}
                  {sentinel.attached ? ` · ${sentinel.events.length} frame(s) since this page opened` : ""}
                </span>
              </Row>
              <Row label="Newest frames">
                <Json value={sentinel.events.slice(0, 5)} />
              </Row>
              <Row label="OS-level egress">
                <Tag tone="warn">PLANNED</Tag>{" "}
                <span className="cs-dim">
                  nftables/iptables is a Linux facility and this host is macOS. The application-layer
                  guard is the only egress control in force here.
                </span>
              </Row>
            </>
          )}
        </div>
      );
    }

    case "local_knowledge": {
      return (
        <div className="cf-stack">
          <Row label="Vector store (RAG)">
            <Json value={e.vector_store ?? null} />
          </Row>
          <Row label="Knowledge graph">
            <Json value={e.knowledge_graph ?? null} />
          </Row>
          <p className="cs-dim" style={{ margin: 0, fontSize: 11.5, lineHeight: 1.6 }}>
            {node.detail}
          </p>
        </div>
      );
    }

    case "security_boundary": {
      return (
        <div className="cf-stack">
          <Row label="Application egress guard">
            <Json value={e.application_egress_guard ?? null} />
          </Row>
          <Row label="Container isolation">
            <Json value={e.container_isolation ?? null} />
          </Row>
          <Row label="OS-level egress">
            <Json value={e.os_egress_enforcement ?? null} />
          </Row>
          <p className="cs-dim" style={{ margin: 0, fontSize: 11.5, lineHeight: 1.6 }}>
            {node.detail}
          </p>
        </div>
      );
    }

    default:
      return (
        <div className="cf-stack">
          <p className="cs-dim" style={{ margin: 0, fontSize: 11.5, lineHeight: 1.6 }}>
            {node.detail}
          </p>
          <Json value={e} />
        </div>
      );
  }
}

export function NodeDrawer({
  node,
  onClose,
  sentinel,
}: {
  node: DiagramNode;
  onClose: () => void;
  sentinel: NetworkSentinel;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <aside
      className="cf-drawer"
      role="dialog"
      aria-label={`${node.title} detail`}
      data-testid={`cf-drawer-${node.id}`}
    >
      <header className="cs-drawer__head">
        <span className="cf-drawer__titlerow">
          <StatusDot state={STATUS_TONE[node.status]} />
          <strong style={{ fontSize: 14 }}>{node.title}</strong>
          <span className="cs-mono" style={{ color: STATUS_COLOUR[node.status], fontSize: 11 }}>
            {node.status}
          </span>
        </span>
        <button className="cs-iconbtn" style={{ marginLeft: "auto" }} onClick={onClose} aria-label="Close">
          ✕
        </button>
      </header>
      <div className="cs-drawer__body">
        <p className="cf-drawer__blurb">{node.blurb}</p>
        {node.rawState && (
          <p className="cs-dim cs-mono" style={{ margin: "0 0 10px", fontSize: 11 }}>
            backend state: {node.rawState}
          </p>
        )}
        <Body node={node} sentinel={sentinel} />
      </div>
    </aside>
  );
}
