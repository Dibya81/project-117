"use client";

/**
 * QuickActions — the workspace's suggested first questions, as launch cards.
 *
 * Each card carries the page's own SUGGESTIONS prompt; this component only
 * changes how the prompt is offered. `onRun(prompt)` is the exact handler the
 * old pill button called, so the turn, the scoping and the journey event are
 * unchanged.
 *
 * Hover is one shared micro-interaction: the card lifts `y: -4` on `SPRING.micro`
 * with a soft cyan wash, the icon scales and takes a cyan drop-shadow glow. The
 * lift uses the `LIFT_HOVER` preset rather than a locally invented spring.
 */
import { motion } from "framer-motion";
import { Lucide } from "@/components/ui/LucideIcon";
import { ICON_HOVER, LIFT_HOVER, SPRING, iconGlow } from "@/lib/ui/motion";
import type { IconName } from "@/components/ui/Icon";

export interface QuickAction {
  prompt: string;
  label: string;
  icon: IconName;
}

export function QuickActions({
  actions,
  onRun,
}: {
  actions: QuickAction[];
  onRun: (prompt: string) => void;
}) {
  return (
    <div className="mx-auto flex w-full max-w-[500px] flex-col gap-2">
      {actions.map((a, i) => (
        <motion.button
          key={a.prompt}
          type="button"
          className="group relative flex w-full items-center gap-3 rounded-xl border border-slate-200/70 bg-gradient-to-br from-white to-slate-100/80 px-4 py-3 text-left shadow-sm"
          onClick={() => onRun(a.prompt)}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0, transition: { ...SPRING.surface, delay: i * 0.06 } }}
          whileHover="hover"
          whileTap={{ scale: 0.985 }}
          variants={{
            hover: {
              ...LIFT_HOVER,
              borderColor: "rgba(6, 182, 212, 0.38)",
              boxShadow: "0 10px 26px rgba(8, 145, 178, 0.16)",
            },
          }}
          transition={SPRING.micro}
        >
          <motion.span
            className="flex h-8 w-8 flex-none items-center justify-center rounded-lg border border-cyan-500/25 bg-cyan-500/10 text-cyan-600"
            variants={{ hover: ICON_HOVER }}
            transition={SPRING.micro}
          >
            <motion.span
              className="flex"
              variants={{ hover: { filter: iconGlow("#0891b2", 0.55) } }}
              transition={SPRING.micro}
            >
              <Lucide name={a.icon} size={15} />
            </motion.span>
          </motion.span>

          <span className="min-w-0">
            <span className="block font-mono text-[9.5px] uppercase tracking-[0.22em] text-slate-400">
              {a.label}
            </span>
            <span className="mt-0.5 block text-[12.5px] leading-snug text-slate-600">{a.prompt}</span>
          </span>

          <span
            aria-hidden="true"
            className="ml-auto flex flex-none text-cyan-600 opacity-0 transition-opacity duration-150 group-hover:opacity-100"
          >
            <Lucide name="arrow" size={14} />
          </span>
        </motion.button>
      ))}
    </div>
  );
}
