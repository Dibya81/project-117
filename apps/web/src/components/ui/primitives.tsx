"use client";

/** Console UI primitives — the shared vocabulary of every workbench page. */
import type { ButtonHTMLAttributes, CSSProperties, HTMLAttributes, ReactNode } from "react";
import type { HealthState } from "@/types";

export function Panel({
  title,
  actions,
  children,
  pad = true,
  glow = false,
  hud,
  ...rest
}: {
  title?: string;
  actions?: ReactNode;
  children: ReactNode;
  pad?: boolean;
  glow?: boolean;
  hud?: boolean;
} & HTMLAttributes<HTMLDivElement>) {
  void hud;
  return (
    <section className={`cs-panel${glow ? " cs-panel--glow" : ""}`} {...rest}>
      {title && (
        <header className="cs-panel__head">
          <span className="cs-panel__title">{title}</span>
          {actions && <span className="cs-panel__actions">{actions}</span>}
        </header>
      )}
      <div className={pad ? "cs-panel__body" : undefined}>{children}</div>
    </section>
  );
}

const DOT_CLASS: Record<HealthState | "ai", string> = {
  ok: "cs-dot cs-dot--ok",
  warning: "cs-dot cs-dot--warn",
  critical: "cs-dot cs-dot--crit",
  unknown: "cs-dot",
  ai: "cs-dot cs-dot--ai",
};

export function StatusDot({ state, pulse = false }: { state: HealthState | "ai"; pulse?: boolean }) {
  return <span className={`${DOT_CLASS[state]}${pulse ? " cs-dot--pulse" : ""}`} aria-hidden="true" />;
}

export function Tag({ tone, children }: { tone?: "ok" | "warn" | "crit" | "ai" | "ember" | "bad"; children: ReactNode }) {
  return <span className={`cs-tag${tone ? ` cs-tag--${tone}` : ""}`}>{children}</span>;
}

export function Button({
  variant,
  children,
  ...rest
}: { variant?: "primary" | "approve" | "reject" | "ghost" } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="button" className={`cs-btn${variant ? ` cs-btn--${variant}` : ""}`} {...rest}>
      {children}
    </button>
  );
}

export function Kpi({ label, value, state }: { label: string; value: string; state?: HealthState }) {
  return (
    <div className="cs-kpi">
      <div className="cs-kpi__label">{label}</div>
      <div className="cs-kpi__value">
        {state && <StatusDot state={state} />}
        {value}
      </div>
    </div>
  );
}

/** Tabs — underline-style tab strip. */
export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: string; label: string; count?: number }[];
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="cs-tabs" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={active === t.id}
          className={`cs-tabs__tab${active === t.id ? " is-active" : ""}`}
          onClick={() => onChange(t.id)}
        >
          {t.label}
          {t.count != null && <span className="cs-tabs__count">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

/** Progress — thin animated bar with gradient fill. */
export function Progress({ value, tone = "cyan" }: { value: number; tone?: "cyan" | "ok" | "warn" | "crit" }) {
  return (
    <div className="cs-progress" role="progressbar" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100}>
      <div className={`cs-progress__fill cs-progress__fill--${tone}`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
    </div>
  );
}

/** Ring — animated health/score ring. */
export function Ring({ value, size = 64, tone = "cyan", label }: { value: number; size?: number; tone?: "cyan" | "ok" | "warn" | "crit"; label?: string }) {
  const stroke = 5;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - Math.min(100, Math.max(0, value)) / 100);
  const colors = { cyan: "var(--cyan)", ok: "var(--ok)", warn: "var(--warn)", crit: "var(--crit)" };
  return (
    <div className="cs-ring" style={{ width: size, height: size }} role="img" aria-label={label ?? `score ${value} of 100`}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(140,180,220,.12)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={colors[tone]}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          className="cs-ring__arc"
          style={{ "--ring-c": c, "--ring-o": offset, transform: "rotate(-90deg)", transformOrigin: "50% 50%" } as CSSProperties}
        />
      </svg>
      <span className="cs-ring__value cs-mono">{value}</span>
    </div>
  );
}

export function EmptyState({ title, detail, action }: { title: string; detail?: string; action?: ReactNode }) {
  return (
    <div className="cs-empty" role="status">
      <div className="cs-empty__orb" aria-hidden="true" />
      <div className="cs-empty__title">{title}</div>
      {detail && <div>{detail}</div>}
      {action && <div style={{ marginTop: 14 }}>{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="cs-empty" role="alert">
      <div className="cs-empty__title cs-text-crit">Something went wrong</div>
      <div>{message}</div>
      {onRetry && (
        <div style={{ marginTop: 14 }}>
          <Button onClick={onRetry}>Retry</Button>
        </div>
      )}
    </div>
  );
}

export function SkeletonRows({ rows = 4, label }: { rows?: number; label?: string }) {
  return (
    <div aria-label="Loading">
      {label && (
        <div className="cs-loading">
          <i /> {label}
        </div>
      )}
    <div className="cs-skeletons">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="cs-skeleton" style={{ height: 18, width: `${88 - i * 9}%` }} />
      ))}
    </div>
    </div>
  );
}

export function timeAgo(iso: string): string {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}
