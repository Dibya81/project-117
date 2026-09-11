"use client";

/**
 * VerificationSummary — the trust component, reused everywhere results appear.
 * Checks: evidence / citations / calculation / execution / artifact / policy.
 * Unsupported claims are never hidden — they render as UNVERIFIED.
 */
import { Icon } from "@/components/ui/Icon";

export interface VerifyCheck {
  name: string;
  status: "verified" | "pending" | "failed";
  detail?: string;
}

export function VerificationSummary({ checks }: { checks: VerifyCheck[] }) {
  const failed = checks.filter((c) => c.status === "failed");
  const pending = checks.filter((c) => c.status === "pending");
  const allVerified = checks.length > 0 && failed.length === 0 && pending.length === 0;

  return (
    <div role="status" aria-label="Verification summary">
      <div className="cs-verify">
        {checks.map((c, i) => (
          <div key={c.name} className="cs-verify__item" style={{ animationDelay: `${i * 90}ms` }}>
            <span className={`cs-verify__icon cs-verify__icon--${c.status}`} style={{ animationDelay: `${i * 90 + 120}ms` }}>
              <Icon name={c.status === "verified" ? "check" : c.status === "pending" ? "clock" : "x"} size={11} />
            </span>
            <span>
              <div style={{ fontWeight: 550 }}>{c.name}</div>
              {c.detail && <div className="cs-dim" style={{ fontSize: 11 }}>{c.detail}</div>}
            </span>
            <span
              className="cs-mono"
              style={{
                marginLeft: "auto",
                fontSize: 9.5,
                letterSpacing: "0.14em",
                color:
                  c.status === "verified" ? "var(--ok)" : c.status === "pending" ? "var(--warn)" : "var(--crit)",
              }}
            >
              {c.status === "verified" ? "VERIFIED" : c.status.toUpperCase()}
            </span>
          </div>
        ))}
      </div>
      {checks.length > 0 && (
        <div
          className="cs-mono"
          style={{
            marginTop: 12,
            padding: "10px 14px",
            borderRadius: 8,
            border: `1px solid ${allVerified ? "rgba(61,220,151,0.4)" : failed.length ? "rgba(255,93,93,0.4)" : "rgba(255,180,84,0.4)"}`,
            background: allVerified ? "var(--ok-soft)" : failed.length ? "var(--crit-soft)" : "var(--warn-soft)",
            color: allVerified ? "var(--ok)" : failed.length ? "var(--crit)" : "var(--warn)",
            fontSize: 11,
            letterSpacing: "0.24em",
            textAlign: "center",
            animation: "p117-scale-in 480ms var(--ease-spring) 700ms both",
          }}
        >
          {allVerified ? "◆ VERIFIED — ALL CHECKS PASSED" : failed.length ? "◇ VERIFICATION FAILED" : "◇ VERIFICATION PENDING"}
        </div>
      )}
    </div>
  );
}
