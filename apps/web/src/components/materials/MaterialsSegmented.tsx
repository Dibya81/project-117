"use client";

/**
 * MaterialsSegmented — the glass segmented pill group used by the materials
 * registers.
 *
 * One rounded glass surface per filter group; the selected chip is marked by a
 * single `<motion.span layoutId>` that Framer Motion hands between siblings, so
 * the indicator glides instead of blinking on and off. `layoutId` is a prop
 * because a page mounts several independent groups and each needs its own
 * shared element.
 *
 * Presentational only. It never decides what a chip means: the caller passes
 * the label and the real count, so nothing here can invent a number or a state.
 */
import { motion } from "framer-motion";
import { Lucide } from "@/components/ui/LucideIcon";
import { SPRING } from "@/lib/ui/motion";

export interface MaterialsSegmentOption {
  id: string;
  label: string;
  /** Real count from the register, or undefined when there is nothing honest to show. */
  count?: number;
  /** Colour for the leading glyph — always a semantic type colour. */
  tone?: string;
  /** Semantic icon name (`IconName`), resolved through LucideIcon. */
  icon?: string;
  title?: string;
}

export default function MaterialsSegmented({
  options,
  value,
  onChange,
  layoutId,
  ariaLabel,
  className = "",
}: {
  options: MaterialsSegmentOption[];
  value: string;
  onChange: (id: string) => void;
  /** Unique per mounted instance — the shared-element key for the glider. */
  layoutId: string;
  ariaLabel: string;
  className?: string;
}) {
  return (
    <div role="radiogroup" aria-label={ariaLabel} className={`mat-seg ${className}`}>
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
            className={`mat-seg__chip${active ? " is-active" : ""}`}
          >
            {/* The single glider, rendered only by the active chip. */}
            {active && (
              <motion.span
                layoutId={layoutId}
                className="mat-seg__glide"
                transition={SPRING.glide}
                aria-hidden="true"
              />
            )}
            {o.icon && (
              <span className="mat-seg__glyph" style={o.tone ? { color: o.tone } : undefined} aria-hidden="true">
                <Lucide name={o.icon} size={12} />
              </span>
            )}
            <span className="mat-seg__label">{o.label}</span>
            {o.count !== undefined && <em className="mat-seg__count">{o.count}</em>}
          </button>
        );
      })}
    </div>
  );
}
