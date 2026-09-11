"use client";

/** Left rail navigation — role-aware, collapsible, badge-driven. */
import { usePathname, useRouter } from "next/navigation";
import { Icon, type IconName } from "@/components/ui/Icon";
import { useRole } from "@/lib/role";
import { ROLE_NAV } from "@/lib/data/console";

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

export function Rail({
  expanded,
  approvalsPending,
  runningTasks,
}: {
  expanded: boolean;
  approvalsPending: number;
  runningTasks: number;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { role } = useRole();
  const allowed = ROLE_NAV[role];

  const groups: NavGroup[] = [
    {
      label: "Operate",
      items: [
        { id: "home", label: "Home", href: "/console/home", icon: "home" },
        { id: "workspace", label: "AI Workspace", href: "/console/workspace", icon: "chat", badge: runningTasks || undefined },
        { id: "approvals", label: "Approvals", href: "/console/approvals", icon: "check", badge: approvalsPending || undefined, badgeTone: "warn" },
        { id: "simulation", label: "Simulation", href: "/console/simulation", icon: "gauge" },
      ],
    },
    {
      label: "Knowledge",
      items: [
        { id: "documents", label: "Documents", href: "/console/documents", icon: "doc" },
        { id: "knowledge", label: "Knowledge Graph", href: "/console/knowledge", icon: "graph" },
        { id: "history", label: "Operational History", href: "/console/history", icon: "history" },
      ],
    },
    {
      label: "Plant",
      items: [
        { id: "equipment", label: "Equipment", href: "/console/equipment", icon: "equipment" },
        { id: "work-orders", label: "Work Orders", href: "/console/work-orders", icon: "workorder" },
        { id: "insights", label: "Insights", href: "/console/insights", icon: "insights" },
      ],
    },
    {
      label: "System",
      items: [{ id: "admin", label: "Admin", href: "/console/admin", icon: "admin" }],
    },
  ];

  return (
    <nav className="cs-rail__nav" aria-label="Primary">
      {groups.map((group) => {
        const visible = group.items.filter((i) => allowed.includes(i.id));
        if (!visible.length) return null;
        return (
          <div className="cs-rail__group" key={group.label}>
            <div className="cs-rail__grouplabel">{group.label}</div>
            {visible.map((item) => {
              const active = pathname.startsWith(item.href);
              return (
                <button
                  key={item.id}
                  className="cs-rail__item"
                  aria-current={active ? "page" : undefined}
                  onClick={() => router.push(item.href)}
                  title={item.label}
                >
                  <span className="cs-rail__icon">
                    <Icon name={item.icon} />
                  </span>
                  <span className="cs-rail__label">{item.label}</span>
                  {item.badge != null && (
                    <span className={`cs-rail__badge${item.badgeTone ? ` cs-rail__badge--${item.badgeTone}` : ""}`}>
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        );
      })}
    </nav>
  );
}
