"use client";

/**
 * SegmentedControl — the console's glass segmented pill group.
 *
 * One rounded glass surface per filter group; the selected chip is marked by a
 * single `<motion.span layoutId>` that Framer Motion hands between siblings, so
 * the indicator glides rather than blinking on and off. `layoutId` is a prop
 * because the page mounts several independent groups (namespace, scope, assets,
 * records) and each needs its own shared element.
 *
 * Presentational only: it never decides what a chip means. The caller passes
 * the label, the real count and the type colour, so nothing here can invent a
 * number or a state.
 */
import { motion } from "framer-motion";
import { Lucide } from "@/components/ui/LucideIcon";
import { SPRING } from "@/lib/ui/motion";

export interface SegmentOption {
  id: string;
  label: string;
  /** Semantic icon name (`IconName`) resolved through LucideIcon. */
  icon?: string;
  /** Colour for the leading glyph — always a semantic type colour. */
  tone?: string;
  /** A dot instead of a glyph, used where a type colour is the meaning. */
  accent?: string;
  /** Real count from the graph, or undefined when there is nothing honest to show. */
  count?: number;
  disabled?: boolean;
  title?: string;
}

interface Props {
  options: SegmentOption[];
  value: string;
  onChange: (id: string) => void;
  /** Unique per mounted instance — the shared-element key for the glider. */
  layoutId: string;
  ariaLabel: string;
  orientation?: "horizontal" | "vertical";
  /** `tabs` keeps the existing tablist/tab ARIA; `radio` is a filter group. */
  variant?: "tabs" | "radio";
  className?: string;
  /** Extra hook kept on each chip (e.g. the legacy `.ku-nav__item`). */
  chipClassName?: string;
}

export default function SegmentedControl({
  options,
  value,
  onChange,
  layoutId,
  ariaLabel,
  orientation = "horizontal",
  variant = "radio",
  className,
  chipClassName,
}: Props) {
  const tabs = variant === "tabs";
  return (
    <div
      className={`ku-seg${orientation === "vertical" ? " ku-seg--v" : ""}${className ? ` ${className}` : ""}`}
      role={tabs ? "tablist" : "radiogroup"}
      aria-label={ariaLabel}
    >
      {options.map((o) => {
        const active = o.id === value;
        return (
          <button
            key={o.id}
            type="button"
            role={tabs ? "tab" : "radio"}
            aria-selected={tabs ? active : undefined}
            aria-checked={tabs ? undefined : active}
            disabled={o.disabled}
            title={o.title}
            onClick={() => onChange(o.id)}
            className={`ku-seg__chip${active ? " is-active" : ""}${chipClassName ? ` ${chipClassName}` : ""}`}
          >
            {/* The single glider, rendered only by the active chip. */}
            {active && (
              <motion.span
                layoutId={layoutId}
                className="ku-seg__glide"
                transition={SPRING.glide}
                aria-hidden="true"
              />
            )}
            {o.accent && <span className="ku-seg__dot" style={{ background: o.accent }} aria-hidden="true" />}
            {o.icon && (
              <span className="ku-seg__glyph" style={{ color: o.tone }} aria-hidden="true">
                <Lucide name={o.icon} size={12} />
              </span>
            )}
            <span className="ku-seg__label">{o.label}</span>
            {o.count !== undefined && <em className="ku-seg__count">{o.count}</em>}
          </button>
        );
      })}
    </div>
  );
}
