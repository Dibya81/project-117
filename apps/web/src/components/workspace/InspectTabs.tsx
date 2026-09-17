"use client";

/**
 * InspectTabs — the Evidence / Execution / Artifacts / Verify segmented control.
 *
 * A single `<motion.span layoutId />` is rendered by the active segment only, so
 * Framer Motion hands the shared glass pill from one segment to the next and
 * glides it in place of a per-tab underline. `layoutId` is a prop because the
 * contract requires it to be unique per mounted instance.
 *
 * The control keeps the tablist/tab semantics the workspace audit gate selects
 * on (`getByRole("tab", …)`). Counts are rendered only when the caller has a
 * measured number, so an absent count shows no chip rather than a fake zero.
 */
import { motion } from "framer-motion";
import { Lucide } from "@/components/ui/LucideIcon";
import { SPRING } from "@/lib/ui/motion";
import type { IconName } from "@/components/ui/Icon";

export interface InspectTab {
  id: string;
  label: string;
  icon: IconName;
  /** Present only when the task has produced this panel's data. */
  count?: number;
}

export function InspectTabs({
  tabs,
  active,
  onChange,
  layoutId = "workspace-inspect-tab",
}: {
  tabs: InspectTab[];
  active: string;
  onChange: (id: string) => void;
  layoutId?: string;
}) {
  return (
    <div className="cs-seg" role="tablist" aria-label="Inspection panels">
      {tabs.map((t) => {
        const on = t.id === active;
        return (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={on}
            className={`cs-seg__tab${on ? " is-active" : ""}`}
            onClick={() => onChange(t.id)}
          >
            {/* Rendered by the active segment only — Framer glides the shared
                element between slots instead of blinking it. */}
            {on && (
              <motion.span
                layoutId={layoutId}
                className="cs-seg__glider"
                transition={SPRING.glide}
                aria-hidden="true"
              />
            )}
            <span className="cs-seg__inner">
              <Lucide name={t.icon} size={13} strokeWidth={on ? 2.3 : 1.9} />
              <span>{t.label}</span>
              {/* Only render a count the caller actually measured — no chip
                  beats a fabricated zero. */}
              {t.count != null && <span className="cs-seg__count">{t.count}</span>}
            </span>
          </button>
        );
      })}
    </div>
  );
}
