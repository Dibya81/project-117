"use client";

/**
 * AppShell — the persistent workbench frame.
 * Aurora (calm) + rail + top bar + journey bar + palette + drawers.
 * Landing (/) never sees this; it wraps /console/* only.
 */
import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Rail } from "./Rail";
import { TopBar } from "./TopBar";
import { CommandPalette } from "./CommandPalette";
import { NotificationCenter } from "./NotificationCenter";
import { AgentRoster } from "./AgentRoster";
import { StatusDot } from "@/components/ui/primitives";
import { Icon, type IconName } from "@/components/ui/Icon";
import { Aurora } from "@/components/fx/Aurora";
import { JourneyProvider, JourneyBar } from "@/lib/journey";
import { RoleProvider } from "@/lib/role";
import { consoleData } from "@/lib/data/console";
import type { AgentDescriptor } from "@/types";
import type { NotificationItem, SystemPosture } from "@/types/console";

import "@/styles/console.css";
import "@/styles/sim.css";

const LIVE_STATES = new Set(["QUEUED", "PLANNING", "RETRIEVING", "EXECUTING", "VERIFYING"]);

/**
 * The console paints a bright workspace, but `html/body` colours come from the
 * shared token layer that the cinematic landing page also depends on. Rather
 * than change those globally and risk the landing, the light page background is
 * applied while the shell is mounted and reverted on unmount.
 */
function useBrightPageBackground() {
  useEffect(() => {
    const root = document.documentElement;
    const prevBodyBg = document.body.style.background;
    const prevBodyColor = document.body.style.color;
    const prevScheme = root.style.colorScheme;
    document.body.style.background = "#f8f9fa";
    document.body.style.color = "#0f172a";
    root.style.colorScheme = "light";
    return () => {
      document.body.style.background = prevBodyBg;
      document.body.style.color = prevBodyColor;
      root.style.colorScheme = prevScheme;
    };
  }, []);
}

const MOBILE_TABS: { label: string; href: string; icon: IconName; match: RegExp }[] = [
  { label: "Home", href: "/console/home", icon: "home", match: /^\/console\/home/ },
  { label: "Ask", href: "/console/workspace", icon: "chat", match: /^\/console\/workspace/ },
  { label: "Plant", href: "/console/equipment", icon: "equipment", match: /^\/console\/equipment/ },
  { label: "Orders", href: "/console/work-orders", icon: "workorder", match: /^\/console\/work-orders/ },
  { label: "More", href: "/console/insights", icon: "dots", match: /^\/console\/(insights|approvals|admin|documents|knowledge|history)/ },
];

function MobileTabs() {
  const pathname = usePathname();
  const router = useRouter();
  return (
    <nav className="cs-mobiletabs" aria-label="Primary mobile">
      {MOBILE_TABS.map((t) => (
        <button
          key={t.label}
          className={t.match.test(pathname) ? "is-active" : undefined}
          onClick={() => router.push(t.href)}
          aria-current={t.match.test(pathname) ? "page" : undefined}
        >
          <Icon name={t.icon} size={17} />
          {t.label}
        </button>
      ))}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  useBrightPageBackground();
  const [expanded, setExpanded] = useState(true);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [notifsOpen, setNotifsOpen] = useState(false);
  const [rosterOpen, setRosterOpen] = useState(false);

  const [posture, setPosture] = useState<SystemPosture | null>(null);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [agents, setAgents] = useState<AgentDescriptor[]>([]);
  const [approvalsPending, setApprovalsPending] = useState(0);
  const [runningTasks, setRunningTasks] = useState(0);

  useEffect(() => {
    consoleData.admin.posture().then(setPosture);
    consoleData.notifications.list().then(setNotifications);
    consoleData.agents.list().then(setAgents);
    consoleData.approvals.pending().then((p) => setApprovalsPending(p.length));
    consoleData.jobs.list().then((js) => setRunningTasks(js.filter((j) => LIVE_STATES.has(j.state)).length));
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <RoleProvider>
      <JourneyProvider>
        <Aurora calm />
        <div className={`cs cs-shell${expanded ? " cs-shell--expanded" : ""}`}>
          <aside className="cs-rail">
            <button
              className="cs-rail__logo"
              style={{ background: "none", border: 0, cursor: "pointer", color: "var(--ink-1)" }}
              onClick={() => setExpanded((v) => !v)}
              aria-label={expanded ? "Collapse navigation" : "Expand navigation"}
            >
              PROJECT <b>117</b>
            </button>
            <Rail expanded={expanded} approvalsPending={approvalsPending} runningTasks={runningTasks} />
            {/* Sovereignty posture — fills the rail's lower space with the
                product's core promise instead of leaving a black void. */}
            <div className="cs-rail__posture" aria-label="Sovereignty posture">
              <span className="cs-rail__posture-title">Sovereignty posture</span>
              {(
                [
                  ["Model gateway", posture?.model_gateway ?? "local"],
                  ["Sandbox", posture?.sandbox ?? "isolated"],
                  ["Egress", posture?.egress ?? "denied"],
                  ["External calls · 24h", String(posture?.external_calls_24h ?? 0)],
                ] as const
              ).map(([label, value]) => (
                <span key={label} className="cs-rail__posture-row">
                  <StatusDot state="ok" />
                  <span className="cs-rail__posture-label">{label}</span>
                  <span className="cs-rail__posture-value">{value}</span>
                </span>
              ))}
            </div>
            <div className="cs-rail__footer">
              <button className="cs-rail__item" onClick={() => setRosterOpen(true)} title="AI workforce">
                <span className="cs-rail__icon"><StatusDot state="ai" pulse /></span>
                <span className="cs-rail__label">AI Workforce</span>
              </button>
              <div className="cs-rail__item" style={{ cursor: "default" }} title="System status">
                <span className="cs-rail__icon"><StatusDot state="ok" pulse /></span>
                <span className="cs-rail__label cs-mono" style={{ fontSize: 10, color: "var(--ink-3)", letterSpacing: "0.14em" }}>
                  SYSTEM OK · v{posture?.version ?? "…"}
                </span>
              </div>
            </div>
          </aside>

          <div className="cs-main">
            <TopBar
              posture={posture}
              notifications={notifications.length}
              onOpenPalette={() => setPaletteOpen(true)}
              onOpenNotifications={() => setNotifsOpen(true)}
            />
            <JourneyBar />
            <main className="cs-content">{children}</main>
            <MobileTabs />
          </div>

          <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} onOpenRoster={() => setRosterOpen(true)} />
          {notifsOpen && <NotificationCenter items={notifications} onClose={() => setNotifsOpen(false)} />}
          {rosterOpen && <AgentRoster agents={agents} onClose={() => setRosterOpen(false)} />}
        </div>
      </JourneyProvider>
    </RoleProvider>
  );
}
