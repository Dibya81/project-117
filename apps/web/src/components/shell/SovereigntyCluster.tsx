"use client";

/** Sovereignty cluster — the trust whisper in the top bar. */
import { useEffect, useRef, useState } from "react";
import { StatusDot } from "@/components/ui/primitives";
import { Icon } from "@/components/ui/Icon";
import type { HealthState } from "@/types";
import type { SystemPosture } from "@/types/console";

/**
 * The cluster reads the same measured posture the rest of the console does.
 * It previously printed a fixed "MODELS: LOCAL / SANDBOX: ISOLATED / EGRESS:
 * DENIED" regardless of the actual state — a permanent green claim in the
 * chrome of every page. Before the first reading lands the honest answer is
 * "unknown", so that is what it shows.
 */
function gatewayTone(p: SystemPosture | null): HealthState {
  if (!p) return "unknown";
  return p.model_gateway === "local" ? "ok" : p.model_gateway === "degraded" ? "warning" : "critical";
}

export function SovereigntyCluster({ posture }: { posture: SystemPosture | null }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("click", onClick);
    return () => window.removeEventListener("click", onClick);
  }, [open]);

  const p = posture;
  const sandboxTone: HealthState = !p ? "unknown" : p.sandbox === "isolated" ? "ok" : "critical";
  const egressTone: HealthState = !p ? "unknown" : p.egress === "denied" ? "ok" : "warning";
  const callsTone: HealthState = !p ? "unknown" : p.external_calls_24h === 0 ? "ok" : "warning";
  const blockedTone: HealthState = !p ? "unknown" : p.egress_blocked_24h === 0 ? "ok" : "warning";

  return (
    <div ref={ref} style={{ position: "relative" }}>
      {/* Compact: a single lock glyph with a status dot. The full posture is one
          click away in the dropdown; a four-part sentence across the top bar is
          what made the header read as a dashboard. */}
      <button
        className="cs-sovereignty cs-sovereignty--compact"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label="Sovereignty status — data stays inside this environment"
        title="Local · Isolated · Egress denied"
      >
        <span className="cs-sovereignty__lock" aria-hidden="true">
          <StatusDot state={gatewayTone(p)} />
          <Icon name="lock" size={13} />
        </span>
        <span className="cs-sovereignty__label">LOCAL</span>
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Sovereignty posture"
          className="cs-panel"
          style={{ position: "absolute", right: 0, top: 40, width: 300, zIndex: 65, animation: "cs-pop 160ms ease both" }}
        >
          <div className="cs-panel__body" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <p style={{ margin: 0, color: "var(--ink-2)", fontSize: 12.5, lineHeight: 1.6 }}>
              All inference, retrieval, and execution run inside this environment.
              Nothing leaves the boundary.
            </p>
            {(
              [
                ["Model gateway", p ? p.model_gateway : "unknown", gatewayTone(p)],
                ["Sandbox", p ? p.sandbox : "unknown", sandboxTone],
                ["Network egress", p ? p.egress : "unknown", egressTone],
                ["External AI calls (24h)", p ? String(p.external_calls_24h) : "unknown", callsTone],
                ["Blocked egress attempts", p ? String(p.egress_blocked_24h) : "unknown", blockedTone],
              ] as const
            ).map(([label, value, tone]) => (
              <div key={label} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5 }}>
                <StatusDot state={tone} />
                <span className="cs-dim">{label}</span>
                <span className="cs-mono" style={{ marginLeft: "auto", textTransform: "uppercase" }}>{value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
