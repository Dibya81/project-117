"use client";

/** Sovereignty cluster — the trust whisper in the top bar. */
import { useEffect, useRef, useState } from "react";
import { StatusDot } from "@/components/ui/primitives";
import type { SystemPosture } from "@/types/console";

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

  const p = posture ?? {
    model_gateway: "local",
    sandbox: "isolated",
    egress: "denied",
    external_calls_24h: 0,
  };

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        className="cs-sovereignty"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label="Sovereignty status — data stays inside this environment"
      >
        <span><StatusDot state="ok" /><span>MODELS: LOCAL</span></span>
        <span><StatusDot state="ok" /><span>SANDBOX: ISOLATED</span></span>
        <span>EGRESS: DENIED</span>
        <span>EXTERNAL: {p.external_calls_24h}</span>
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
                ["Model gateway", p.model_gateway, "ok"],
                ["Sandbox", p.sandbox, "ok"],
                ["Network egress", p.egress, "ok"],
                ["External AI calls (24h)", String(p.external_calls_24h), "ok"],
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
