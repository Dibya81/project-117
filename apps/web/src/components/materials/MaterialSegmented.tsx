"use client";

/**
 * MaterialSegmented — the glass segmented control used by the materials pages.
 *
 * The active chip is marked by a single `<motion.span layoutId>` that Framer
 * Motion hands from one sibling to the next, so the indicator glides instead of
 * blinking on and off. `layoutId` is required and must be unique per mounted
 * instance: the production page mounts a period group, a product group and a
 * range group, and each needs its own shared element.
 *
 * Presentational only. It never decides what a chip means and never invents a
 * number, count or state — the caller passes real labels.
 */
import { motion } from "framer-motion";
import { SPRING } from "@/lib/ui/motion";

export interface MaterialSegmentOption {
  id: string;
  label: string;
  title?: string;
}

export function MaterialSegmented({
  options,
  value,
  onChange,
  layoutId,
  ariaLabel,
  className = "",
  testId,
}: {
  options: MaterialSegmentOption[];
  value: string;
  onChange: (id: string) => void;
  /** Unique per mounted instance — the shared-element key for the glider. */
  layoutId: string;
  ariaLabel: string;
  className?: string;
  testId?: string;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      data-testid={testId}
      className={`inline-flex flex-wrap items-center gap-0.5 rounded-full border border-slate-200/80 bg-white/70 p-1 shadow-sm backdrop-blur-xl ${className}`}
    >
      {options.map((o) => {
        const active = o.id === value;
        return (
          <button
            key={o.id}
            type="button"
            role="radio"
            aria-checked={active}
            title={o.title}
            onClick={() => onChange(o.id)}
            className={`relative rounded-full px-3 py-1.5 font-mono text-[10.5px] font-semibold uppercase tracking-[0.1em] transition-colors ${
              active ? "text-cyan-800" : "text-slate-500 hover:text-slate-800"
            }`}
          >
            {/* The one glider, rendered only by the active chip. */}
            {active && (
              <motion.span
                layoutId={layoutId}
                transition={SPRING.glide}
                aria-hidden="true"
                className="absolute inset-0 rounded-full border border-cyan-500/25 bg-white shadow-sm"
              />
            )}
            <span className="relative z-10 whitespace-nowrap">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}
