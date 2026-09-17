"use client";

/**
 * Shared presentation for the Industrial Materials layer.
 *
 * Three rules are implemented once here rather than repeated per page, because
 * each of them is a correctness property and not a styling choice:
 *
 *  1. **SYNTHETIC DEMO is always visible.** Every materials figure in this
 *     deployment comes from generated demo data. `DataStatusBadge` renders that,
 *     so a number can never be read as a measurement.
 *  2. **A limitation is never a blank.** When the backend reports
 *     `INSUFFICIENT_HISTORY` or `DATA_UNAVAILABLE`, `LimitationNote` shows the
 *     code and the backend's own explanation. An empty cell would imply zero.
 *  3. **A computed figure shows its basis.** `Provenance` carries source,
 *     timestamp and calculation status, so a cost can be traced to
 *     `quantity × unit_price` and an inventory figure to `quantity − reserved`.
 */

import type { ReactNode } from "react";
import { AlertTriangle, Info, ShieldCheck } from "lucide-react";
import type { LimitationRecord, ProvenanceRecord } from "@/lib/api";

/** The demo-data warning. Present on every materials surface by design. */
export function SyntheticDemoBadge({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[9.5px] font-semibold uppercase tracking-[0.14em] text-amber-700 ${className}`}
      title="Generated demonstration data. Not MRPL data, not a market price, not a real supplier."
    >
      <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
      Synthetic demo
    </span>
  );
}

type Tone = "ok" | "warn" | "crit" | "ai" | "muted" | "violet";

const TONE_CLASS: Record<Tone, string> = {
  ok: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700",
  warn: "border-amber-500/30 bg-amber-500/10 text-amber-700",
  crit: "border-red-500/30 bg-red-500/10 text-red-700",
  ai: "border-cyan-500/30 bg-cyan-500/10 text-cyan-700",
  violet: "border-violet-500/30 bg-violet-500/10 text-violet-700",
  muted: "border-slate-300/60 bg-slate-100/70 text-slate-600",
};

/** A status chip. The tone is derived from the domain status, never decorative. */
export function StatusChip({ label, tone, pulse = false }: { label: string; tone: Tone; pulse?: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] ${TONE_CLASS[tone]}`}
    >
      {pulse && (
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-60" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-current" />
        </span>
      )}
      {label}
    </span>
  );
}

/**
 * Map a backend status word to a tone. Centralised so "CRITICAL" cannot be grey
 * on one page and red on another.
 */
export function statusTone(status: string | undefined | null): Tone {
  switch ((status ?? "").toUpperCase()) {
    case "AVAILABLE":
    case "NORMAL":
    case "ACTIVE":
    case "QUALIFIED":
    case "COVERED":
    case "COMPLETED":
    case "VERIFIED":
      return "ok";
    case "DEPLETING":
    case "WARNING":
    case "ON_HOLD":
    case "SHORTFALL":
    case "PENDING_APPROVAL":
    case "ESTIMATED":
    case "ILLUSTRATIVE":
      return "warn";
    case "CRITICAL":
    case "OUT_OF_STOCK":
    case "SUSPENDED":
    case "BLOCKED":
      return "crit";
    default:
      return "muted";
  }
}

/** Render a monospace figure table style: fixed width digits, no layout jump. */
export function Figure({
  value,
  unit,
  className = "",
  placeholder = "—",
}: {
  value: number | null | undefined;
  unit?: string | null;
  className?: string;
  placeholder?: string;
}) {
  const shown =
    value === null || value === undefined
      ? placeholder
      : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return (
    <span className={`font-mono tabular-nums ${className}`}>
      {shown}
      {unit ? <span className="ml-1 text-[0.8em] text-slate-400">{unit}</span> : null}
    </span>
  );
}

/** ₹ with its unit basis. A price without its basis is not a price. */
export function Money({
  amount,
  currency = "INR",
  per,
  className = "",
}: {
  amount: number | null | undefined;
  /** Nullable because the domain returns a currency only where one exists. */
  currency?: string | null;
  per?: string | null;
  className?: string;
}) {
  if (amount === null || amount === undefined) return <span className="text-slate-400">—</span>;
  const symbol = (currency ?? "INR") === "INR" ? "₹" : "";
  return (
    <span className={`font-mono tabular-nums ${className}`}>
      {symbol}
      {amount.toLocaleString(undefined, { maximumFractionDigits: 2 })}
      {per ? <span className="ml-1 text-[0.8em] text-slate-400">/{per}</span> : null}
    </span>
  );
}

/**
 * A limitation the backend reported instead of a value.
 *
 * Rendered as an explanation, never as an empty cell: "no consumption recorded in
 * the last 30 days" is information, and a blank would be read as zero.
 */
export function LimitationNote({ limitations }: { limitations?: LimitationRecord[] }) {
  if (!limitations?.length) return null;
  return (
    <ul className="flex flex-col gap-1.5">
      {limitations.map((l, i) => (
        <li
          key={`${l.code}-${i}`}
          className="flex items-start gap-2 rounded-lg border border-slate-200/70 bg-slate-50/70 px-2.5 py-2 text-[11px] leading-snug text-slate-600"
        >
          <Info size={12} strokeWidth={2.2} className="mt-[2px] shrink-0 text-slate-400" />
          <span>
            <span className="font-mono text-[9.5px] font-semibold uppercase tracking-wider text-slate-500">
              {l.code}
            </span>
            <br />
            {l.message}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Provenance: source, when, and how much to trust it. */
export function ProvenanceLine({
  provenance,
  calculationStatus,
  basis,
}: {
  provenance?: ProvenanceRecord | null;
  calculationStatus?: string | null;
  basis?: Record<string, unknown> | null;
}) {
  const entries = basis
    ? Object.entries(basis).filter(([, v]) => v !== null && v !== undefined && v !== "")
    : [];
  return (
    <div className="flex flex-col gap-1 text-[10px] leading-relaxed text-slate-500">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {provenance?.source ? (
          <span>
            Source <span className="font-mono text-slate-600">{provenance.source}</span>
          </span>
        ) : null}
        {provenance?.timestamp ? (
          <span>
            {new Date(provenance.timestamp).toLocaleString(undefined, {
              dateStyle: "medium",
              timeStyle: "short",
            })}
          </span>
        ) : null}
        {calculationStatus ? (
          <span className="font-mono uppercase tracking-wider text-amber-700">{calculationStatus}</span>
        ) : null}
      </div>
      {entries.length > 0 && (
        <div className="font-mono text-[9.5px] text-slate-400">
          {entries.map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`).join("  ·  ")}
        </div>
      )}
    </div>
  );
}

/** A glass panel with the console's standard surface. */
export function MaterialPanel({
  title,
  subtitle,
  actions,
  children,
  className = "",
  testId,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  testId?: string;
}) {
  return (
    <section
      className={`rounded-2xl border border-slate-200/80 bg-white/80 shadow-sm backdrop-blur-xl ${className}`}
      data-testid={testId}
    >
      {(title || actions) && (
        <header className="flex flex-wrap items-center gap-3 border-b border-slate-200/70 px-4 py-3">
          {title ? (
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">{title}</h2>
          ) : null}
          {subtitle ? <span className="text-[11px] text-slate-400">{subtitle}</span> : null}
          {actions ? <div className="ml-auto flex items-center gap-2">{actions}</div> : null}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

/** An explicit empty state. Never a zero, never a fabricated row. */
export function EmptyState({
  title,
  detail,
  icon,
}: {
  title: string;
  detail?: string;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-slate-300/70 bg-slate-50/50 px-6 py-10 text-center">
      <span className="text-slate-300">{icon ?? <ShieldCheck size={20} strokeWidth={1.6} />}</span>
      <p className="text-[13px] font-semibold text-slate-600">{title}</p>
      {detail ? <p className="max-w-md text-[11.5px] leading-relaxed text-slate-500">{detail}</p> : null}
    </div>
  );
}

/** Coverage verdict chip, shared by the spares, equipment and recommendation views. */
export function CoverageChip({ coverage }: { coverage: string | undefined | null }) {
  const value = (coverage ?? "UNKNOWN").toUpperCase();
  if (value === "COVERED") return <StatusChip label="Covered" tone="ok" />;
  if (value === "SHORTFALL") return <StatusChip label="Shortfall" tone="crit" pulse />;
  return <StatusChip label="Unknown" tone="muted" />;
}

/** A movement-type chip. Direction is encoded, because a receipt and a dispatch
 *  are not interchangeable and a flat table hides that. */
export function MovementChip({ type }: { type: string }) {
  const tone: Tone =
    type === "RECEIPT" || type === "PRODUCTION" ? "ok" : type === "CONSUMPTION" || type === "DISPATCH" ? "ai" : "muted";
  return <StatusChip label={type.toLowerCase().replace(/_/g, " ")} tone={tone} />;
}

/** The materials-layer masthead. One header shape across all seven pages. */
export function MaterialsHeader({
  kicker,
  title,
  lede,
  actions,
}: {
  kicker: string;
  title: string;
  lede?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-4">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0">
          <span className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-400">{kicker}</span>
          <h1 className="mt-1 text-[26px] font-bold leading-tight tracking-[-0.01em] text-slate-900">{title}</h1>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <SyntheticDemoBadge />
          {actions}
        </div>
      </div>
      {lede ? <p className="mt-2 max-w-3xl text-[13px] leading-relaxed text-slate-600">{lede}</p> : null}
    </div>
  );
}

/** Warning used when a price movement crosses the configured threshold. */
export function MovementBadge({ movement }: { movement: string | undefined | null }) {
  const value = (movement ?? "").toUpperCase();
  if (value === "ABNORMAL") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-red-500/30 bg-red-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-red-700">
        <AlertTriangle size={11} strokeWidth={2.4} />
        Abnormal
      </span>
    );
  }
  if (value === "WARNING") return <StatusChip label="Warning" tone="warn" />;
  if (value === "NORMAL") return <StatusChip label="Normal" tone="ok" />;
  return null;
}
