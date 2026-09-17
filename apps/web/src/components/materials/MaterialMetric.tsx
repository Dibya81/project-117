"use client";

/**
 * MaterialMetric — the inner glass card the materials pages use for a headline
 * figure.
 *
 * It renders a label, a value slot and an optional sub-line, and nothing else:
 * every figure inside `value` is a backend value passed through verbatim by the
 * page (`Figure`, `Money`), so this component cannot invent or recompute one.
 */
import type { ReactNode } from "react";

export function MaterialMetric({
  label,
  value,
  sub,
  badge,
  tone = "text-slate-900",
  testId,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  /** A chip or flag rendered on the label row (e.g. a data-status marker). */
  badge?: ReactNode;
  /** Value colour. Semantic only — cyan for live data, amber for caution. */
  tone?: string;
  testId?: string;
}) {
  return (
    <div
      data-testid={testId}
      className="rounded-xl border border-slate-200/60 bg-white/60 px-4 py-3 backdrop-blur-md"
    >
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
          {label}
        </span>
        {badge ? <span className="ml-auto">{badge}</span> : null}
      </div>
      <div className={`mt-1.5 text-[19px] font-bold leading-tight tracking-[-0.01em] ${tone}`}>
        {value}
      </div>
      {sub ? (
        <div className="mt-1 text-[11px] leading-snug text-slate-500">{sub}</div>
      ) : null}
    </div>
  );
}
