"use client";

/**
 * AppShell — the persistent workbench frame.
 * Ice-blue mesh + glass rail + glass top bar + journey bar + palette + drawers.
 * Landing (/) never sees this; it wraps /console/* only.
 */
import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { motion, useMotionTemplate, useSpring } from "framer-motion";
import { ChevronRight } from "lucide-react";
import { Rail } from "./Rail";
import { TopBar } from "./TopBar";
import { GlassBackdrop } from "./GlassBackdrop";
import { CommandPalette } from "./CommandPalette";
import { NotificationCenter } from "./NotificationCenter";
import { AgentRoster } from "./AgentRoster";
import { StatusDot } from "@/components/ui/primitives";
import type { IconName } from "@/components/ui/Icon";
import { Lucide } from "@/components/ui/LucideIcon";
import { JourneyProvider, JourneyBar } from "@/lib/journey";
import { RoleProvider } from "@/lib/role";
import { consoleData } from "@/lib/data/console";
import { SPRING, SPRING_OPTIONS } from "@/lib/ui/motion";
import type { AgentDescriptor, HealthState } from "@/types";
import type { NotificationItem, SystemPosture } from "@/types/console";

import "@/styles/console.css";
import "@/styles/sim.css";

const LIVE_STATES = new Set(["QUEUED", "PLANNING", "RETRIEVING", "EXECUTING", "VERIFYING"]);

/**
 * Maps a measured posture field to a status tone. A missing posture means the
 * reading has not arrived, which is "unknown" — never a default of "ok".
 */
function postureTone(
  posture: SystemPosture | null,
  field: "model_gateway" | "sandbox" | "egress" | "calls" | "blocked",
): HealthState {
  if (!posture) return "unknown";
  switch (field) {
    case "model_gateway":
      return posture.model_gateway === "local"
        ? "ok"
        : posture.model_gateway === "degraded"
          ? "warning"
          : "critical";
    case "sandbox":
      return posture.sandbox === "isolated" ? "ok" : "critical";
    case "egress":
      return posture.egress === "denied" ? "ok" : "warning";
    case "calls":
      return posture.external_calls_24h === 0 ? "ok" : "warning";
    case "blocked":
      // A blocked attempt is the guard succeeding, so it is never a failure
      // state — but a rising count is worth seeing, so it is not "ok" either
      // once it is non-zero.
      return posture.egress_blocked_24h === 0 ? "ok" : "warning";
  }
}

/**
 * The console paints a bright workspace, but `html/body` colours come from the
 * shared token layer that the cinematic landing page also depends on. Rather
 * than change those globally and risk the landing, the ice-blue page base is
 * applied while the shell is mounted and reverted on unmount.
 *
 * The gradient itself lives in `GlassBackdrop`; this only stops the body from
 * showing through at the edges on overscroll, so the tone matches.
 */
function useBrightPageBackground() {
  useEffect(() => {
    const root = document.documentElement;
    const prevBodyBg = document.body.style.background;
    const prevBodyColor = document.body.style.color;
    const prevScheme = root.style.colorScheme;
    document.body.style.background = "#F0F7FF";
    document.body.style.color = "#0f172a";
    root.style.colorScheme = "light";
    return () => {
      document.body.style.background = prevBodyBg;
      document.body.style.color = prevBodyColor;
      root.style.colorScheme = prevScheme;
    };
  }, []);
}

/** Collapsed and expanded rail widths. Exported so pages can offset for them. */
export const RAIL_W = 64;
export const RAIL_W_EXPANDED = 232;

const MOBILE_TABS: { label: string; href: string; icon: IconName; match: RegExp }[] = [
  { label: "Home", href: "/console/home", icon: "home", match: /^\/console\/home/ },
  { label: "Ask", href: "/console/workspace", icon: "chat", match: /^\/console\/workspace/ },
  { label: "Plant", href: "/console/equipment", icon: "equipment", match: /^\/console\/equipment/ },
  { label: "Orders", href: "/console/work-orders", icon: "workorder", match: /^\/console\/work-orders/ },
  { label: "More", href: "/console/insights", icon: "dots", match: /^\/console\/(insights|approvals|admin|documents|knowledge|history|sovereignty|security)/ },
];

function MobileTabs() {
  const pathname = usePathname();
  const router = useRouter();
  return (
    <nav className="cs-mobiletabs" aria-label="Primary mobile">
      {MOBILE_TABS.map((t) => {
        const active = t.match.test(pathname);
        return (
          <motion.button
            key={t.label}
            className={active ? "is-active" : undefined}
            onClick={() => router.push(t.href)}
            aria-current={active ? "page" : undefined}
            whileTap={{ scale: 0.94 }}
            transition={SPRING.micro}
          >
            <Lucide name={t.icon} size={18} strokeWidth={active ? 2.4 : 1.9} />
            {t.label}
          </motion.button>
        );
      })}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  useBrightPageBackground();
  /**
   * Navigation is a rail by default, not a permanent panel.
   *
   * A 232px column of text is what made this read as an admin dashboard and it
   * took a sixth of the width from the plant. The rail shows icons; it expands
   * when the pointer enters it and collapses when it leaves. `pinned` keeps it
   * open for anyone who wants that, and the choice survives the session.
   */
  // Start from the server's value and apply the stored pin AFTER mount.
  //
  // Reading sessionStorage inside the initialiser made the first client render
  // disagree with the server HTML whenever the rail was pinned ("▶" on the
  // server, "◀" on the client). React treats that as a hydration mismatch and
  // re-renders the whole shell on the client, which is both an error in the
  // console and a visible flash.
  const [pinned, setPinned] = useState(false);
  useEffect(() => {
    setPinned(window.sessionStorage.getItem("p117.rail.pinned") === "1");
  }, []);
  const [hovered, setHovered] = useState(false);
  const expanded = pinned || hovered;

  /**
   * The rail's width is a motion value, not React state.
   *
   * Framer Motion writes the animated width straight to the DOM node, so the
   * collapse never re-renders the page tree — only the grid column reflows. The
   * spring is the one the spec names (stiffness 300, damping 30): fast enough to
   * feel like the rail snaps open under the pointer, damped enough that the
   * labels do not visibly wobble on the way.
   *
   * Because this is an inline `grid-template-columns`, a plain media query
   * cannot override it at mobile widths. `console.css` therefore forces the
   * single-column layout with `!important` under 860px and re-places
   * `.cs-main`; without that, the hidden rail removed the first grid item and
   * the whole page auto-placed into the 64px rail column.
   */
  const railW = useSpring(RAIL_W, SPRING_OPTIONS.panel);
  useEffect(() => {
    railW.set(expanded ? RAIL_W_EXPANDED : RAIL_W);
  }, [expanded, railW]);
  const gridTemplate = useMotionTemplate`${railW}px 1fr`;

  const [paletteOpen, setPaletteOpen] = useState(false);
  const [notifsOpen, setNotifsOpen] = useState(false);
  const [rosterOpen, setRosterOpen] = useState(false);

  const [posture, setPosture] = useState<SystemPosture | null>(null);
  const [plantName, setPlantName] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [agents, setAgents] = useState<AgentDescriptor[]>([]);
  const [approvalsPending, setApprovalsPending] = useState(0);
  const [runningTasks, setRunningTasks] = useState(0);

  useEffect(() => {
    consoleData.admin.posture().then(setPosture);
    consoleData.plant.identity().then((p) => setPlantName(p?.name ?? null));
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
        <GlassBackdrop />
        <motion.div
          className={`cs cs-shell${expanded ? " cs-shell--expanded" : ""}`}
          style={{ gridTemplateColumns: gridTemplate }}
        >
          <aside
            className="cs-rail"
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            data-expanded={expanded ? "true" : "false"}
          >
            <button
              className="cs-rail__logo"
              onClick={() => setPinned((v) => {
                const next = !v;
                window.sessionStorage.setItem("p117.rail.pinned", next ? "1" : "0");
                return next;
              })}
              title={pinned ? "Unpin navigation" : "Pin navigation open"}
              aria-pressed={pinned}
              aria-label={pinned ? "Unpin navigation" : "Pin navigation open"}
            >
              <motion.span
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-400 to-blue-600 text-[11px] font-bold text-white shadow-sm shadow-cyan-500/30"
                whileHover={{ scale: 1.08, rotate: -4 }}
                transition={SPRING.micro}
                aria-hidden="true"
              >
                17
              </motion.span>
              <span
                className={`whitespace-nowrap transition-opacity duration-200 ${expanded ? "opacity-100" : "opacity-0"}`}
              >
                PROJECT <b>117</b>
              </span>
              <motion.span
                className="cs-rail__pin"
                aria-hidden="true"
                animate={{ rotate: pinned ? 180 : 0 }}
                transition={SPRING.panel}
              >
                <ChevronRight size={11} strokeWidth={2.6} />
              </motion.span>
            </button>
            <Rail expanded={expanded} approvalsPending={approvalsPending} runningTasks={runningTasks} />
            {/* Sovereignty posture — real readings from /health, never a
                hardcoded green. Before the first reading arrives every row
                reads "unknown" rather than asserting a state we have not
                measured. */}
            <div className="cs-rail__posture" aria-label="Sovereignty posture">
              <span className="cs-rail__posture-title">Sovereignty posture</span>
              {(
                [
                  ["Model gateway", posture ? posture.model_gateway : "unknown", postureTone(posture, "model_gateway")],
                  ["Sandbox", posture ? posture.sandbox : "unknown", postureTone(posture, "sandbox")],
                  ["Egress", posture ? posture.egress : "unknown", postureTone(posture, "egress")],
                  [
                    "External calls · 24h",
                    posture ? String(posture.external_calls_24h) : "—",
                    postureTone(posture, "calls"),
                  ],
                  [
                    "Blocked egress · 24h",
                    posture ? String(posture.egress_blocked_24h) : "—",
                    postureTone(posture, "blocked"),
                  ],
                ] as const
              ).map(([label, value, tone]) => (
                <span key={label} className="cs-rail__posture-row">
                  <StatusDot state={tone} />
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
              plantName={plantName}
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
        </motion.div>
      </JourneyProvider>
    </RoleProvider>
  );
}
