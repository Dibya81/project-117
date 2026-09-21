"use client";

/**
 * Left navigation — glass, icon-first, role-aware.
 *
 * Three behaviours carry the redesign:
 *
 *  1. The active item is marked by a single `<motion.span layoutId="activeTab" />`
 *     rendered *inside* whichever item is active. Framer Motion sees the same
 *     layoutId disappear from one item and appear in another, and animates the
 *     shared element between them — so the highlight glides instead of blinking.
 *     `layoutId` is a prop because two nav surfaces (rail + mobile tabs) must
 *     never claim the same shared element.
 *
 *  2. Icons scale 1.05 and take a coloured glow on hover through Framer Motion
 *     `whileHover` variants, so the micro-interaction shares one spring with
 *     everything else rather than a separate CSS transition.
 *
 *  3. Label opacity is driven by the same `expanded` flag the width spring uses,
 *     so text never wraps mid-collapse.
 */
import { usePathname, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Lucide } from "@/components/ui/LucideIcon";
import { ICON_HOVER, SPRING, iconGlow } from "@/lib/ui/motion";
import { useRole } from "@/lib/role";
import { ROLE_NAV } from "@/lib/data/console";
import type { IconName } from "@/components/ui/Icon";

interface NavItem {
  id: string;
  label: string;
  href: string;
  icon: IconName;
  badge?: number;
  badgeTone?: "warn";
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

/** Accent per group, so the rail reads as themed bands rather than one list. */
const GROUP_ACCENT: Record<string, string> = {
  Work: "#0891b2",
  Industrial: "#0d9488",
  Knowledge: "#7c3aed",
  Security: "#0e7490",
  System: "#475569",
};

export function Rail({
  expanded,
  approvalsPending,
  runningTasks,
  layoutId = "activeTab",
}: {
  expanded: boolean;
  approvalsPending: number;
  runningTasks: number;
  /** Overridable so two nav surfaces can coexist without sharing one element. */
  layoutId?: string;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { role } = useRole();
  const allowed = ROLE_NAV[role];

  const groups: NavGroup[] = [
    {
      label: "Work",
      items: [
        { id: "workspace", label: "AI Workspace", href: "/console/workspace", icon: "chat", badge: runningTasks || undefined },
        { id: "home", label: "Home / Overview", href: "/console/home", icon: "home" },
        { id: "approvals", label: "Approvals", href: "/console/approvals", icon: "check", badge: approvalsPending || undefined, badgeTone: "warn" },
      ],
    },
    {
      label: "Industrial",
      items: [
        { id: "equipment", label: "Equipment", href: "/console/equipment", icon: "equipment" },
        { id: "simulation", label: "Simulation", href: "/console/simulation", icon: "gauge" },
        { id: "work-orders", label: "Work Orders", href: "/console/work-orders", icon: "workorder" },
        { id: "mat-overview", label: "Materials & Spares", href: "/console/materials", icon: "layers" },
        { id: "insights", label: "Economics & Insights", href: "/console/insights", icon: "insights" },
      ],
    },
    {
      label: "Knowledge",
      items: [
        { id: "knowledge-hub", label: "Knowledge Hub", href: "/console/knowledge/hub", icon: "database" },
        { id: "knowledge-docs", label: "Documents & Ingest", href: "/console/knowledge/documents", icon: "upload" },
        { id: "knowledge", label: "Industrial Memory", href: "/console/knowledge", icon: "graph" },
        { id: "history", label: "Operational History", href: "/console/history", icon: "history" },
      ],
    },
    {
      label: "Security",
      items: [
        { id: "sovereignty", label: "Sovereignty Control", href: "/console/sovereignty", icon: "shield" },
        { id: "confidentiality", label: "Confidentiality Architecture", href: "/console/security/confidentiality", icon: "lock" },
      ],
    },
    {
      label: "System",
      items: [
        { id: "admin", label: "Admin & Settings", href: "/console/admin", icon: "admin" },
      ],
    },
  ];

  return (
    <nav className="cs-rail__nav" aria-label="Primary">
      {groups.map((group) => {
        const visible = group.items.filter((i) => allowed.includes(i.id));
        if (!visible.length) return null;
        const accent = GROUP_ACCENT[group.label] ?? "#0891b2";
        return (
          <div className="cs-rail__group" key={group.label}>
            <div
              className={`cs-rail__grouplabel transition-opacity duration-200 ${
                expanded ? "opacity-100" : "opacity-0"
              }`}
            >
              {group.label}
            </div>
            {visible.map((item) => {
              const active = pathname.startsWith(item.href);
              return (
                <motion.button
                  key={item.id}
                  type="button"
                  className="cs-rail__item relative"
                  aria-current={active ? "page" : undefined}
                  onClick={() => router.push(item.href)}
                  title={expanded ? undefined : item.label}
                  whileHover="hover"
                  whileTap={{ scale: 0.97 }}
                  transition={SPRING.micro}
                >
                  {/* The sliding indicator. Rendered by the active item only, so
                      layoutId hands the element from one item to the next and
                      Framer Motion tweens the shared box between them. */}
                  {active && (
                    <motion.span
                      layoutId={layoutId}
                      className="pointer-events-none absolute inset-0 rounded-xl"
                      style={{
                        background: `linear-gradient(100deg, ${accent}14, ${accent}08)`,
                        border: `1px solid ${accent}33`,
                        boxShadow: `0 1px 2px rgba(15,23,42,0.04), 0 6px 18px ${accent}14`,
                      }}
                      transition={SPRING.glide}
                    />
                  )}
                  {/* Accent bar on the leading edge of the active item. */}
                  {active && (
                    <motion.span
                      layoutId={`${layoutId}-bar`}
                      className="pointer-events-none absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full"
                      style={{ background: accent, boxShadow: `0 0 8px ${accent}aa` }}
                      transition={SPRING.glide}
                    />
                  )}

                  <motion.span
                    className="cs-rail__icon relative z-10 flex shrink-0 items-center justify-center"
                    variants={{ hover: ICON_HOVER }}
                    transition={SPRING.micro}
                    style={active ? { color: accent } : undefined}
                  >
                    <motion.span
                      variants={{ hover: { filter: iconGlow(active ? accent : "#0891b2", 0.5) } }}
                      transition={SPRING.micro}
                      className="flex"
                    >
                      <Lucide name={item.icon} size={18} strokeWidth={active ? 2.3 : 1.9} />
                    </motion.span>
                  </motion.span>

                  <span
                    className={`cs-rail__label relative z-10 whitespace-nowrap transition-opacity duration-200 ${
                      expanded ? "opacity-100" : "opacity-0"
                    }`}
                    style={active ? { color: accent, fontWeight: 600 } : undefined}
                  >
                    {item.label}
                  </span>

                  {item.badge != null && (
                    <span
                      className={`cs-rail__badge relative z-10${
                        item.badgeTone ? ` cs-rail__badge--${item.badgeTone}` : ""
                      }`}
                      style={expanded ? undefined : { display: "grid" }}
                    >
                      {item.badge}
                    </span>
                  )}
                </motion.button>
              );
            })}
          </div>
        );
      })}
    </nav>
  );
}
