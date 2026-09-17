"use client";

/**
 * Persistent top bar — floating glass shelf.
 *
 * The search field is no longer a text input with a decorative kbd hint: it is
 * a BUTTON that opens the real command palette, wearing the shortcut it
 * triggers. That is the honest control — the console never had an inline search
 * to type into, and a fake input that swallows keystrokes is worse than a button
 * that says what it does.
 *
 * Live status is the measured posture passed down from the shell, not a
 * decorative dot: it reads "Connecting" until a real reading has arrived, and
 * the tone comes from actual gateway/sandbox state.
 */
import { motion } from "framer-motion";
import { Activity, ChevronDown, Command, Gauge, Search, Settings2 } from "lucide-react";
import { SovereigntyCluster } from "./SovereigntyCluster";
import { NotificationBell } from "./NotificationCenter";
import { useRole } from "@/lib/role";
import { SPRING } from "@/lib/ui/motion";
import type { ConsoleRole, SystemPosture } from "@/types/console";

const ROLES: ConsoleRole[] = ["operator", "engineer", "maintenance", "safety", "manager", "admin"];

/** The one place that decides what "live" means for the header. */
function liveTone(posture: SystemPosture | null): {
  label: string;
  dot: string;
  ring: string;
  text: string;
} {
  if (!posture) {
    return { label: "Connecting", dot: "bg-slate-400", ring: "bg-slate-400/10", text: "text-slate-500" };
  }
  const ok = posture.model_gateway === "local" && posture.sandbox === "isolated";
  if (ok) {
    return { label: "Live", dot: "bg-emerald-500", ring: "bg-emerald-500/10", text: "text-emerald-700" };
  }
  return { label: "Degraded", dot: "bg-amber-500", ring: "bg-amber-500/10", text: "text-amber-700" };
}

function isMac(): boolean {
  if (typeof navigator === "undefined") return false;
  return /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
}

export function TopBar({
  plantName,
  posture,
  notifications,
  onOpenPalette,
  onOpenNotifications,
}: {
  /** The real plant name from the backend; null while loading or unreachable. */
  plantName: string | null;
  posture: SystemPosture | null;
  notifications: number;
  onOpenPalette: () => void;
  onOpenNotifications: () => void;
}) {
  const { role, user, setRole } = useRole();
  const tone = liveTone(posture);
  const mod = isMac() ? "⌘" : "Ctrl";

  return (
    <header className="cs-topbar">
      <span className="cs-topbar__brand">PROJECT 117</span>

      {/* The plant's own name from the dataset — never a hardcoded label. */}
      <span className="cs-topbar__plant">
        <Gauge size={14} strokeWidth={2} />
        {plantName ?? "Plant unknown"}
      </span>

      {/* Command palette trigger: frosted glass, wearing the shortcut it owns. */}
      <motion.button
        type="button"
        onClick={onOpenPalette}
        aria-label="Open command palette"
        aria-keyshortcuts="Meta+K Control+K"
        data-testid="palette-trigger"
        className="cs-search-trigger group"
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.99 }}
        transition={SPRING.micro}
      >
        <Search
          size={14}
          strokeWidth={2}
          className="shrink-0 text-slate-400 transition-colors group-hover:text-cyan-600"
        />
        <span className="truncate">Search or run a command…</span>
        <kbd className="ml-auto flex shrink-0 items-center gap-[2px]">
          {mod === "⌘" ? <Command size={10} strokeWidth={2.6} /> : null}
          <span>K</span>
        </kbd>
      </motion.button>

      {/* Live status indicators, read from the measured posture. */}
      <div className="flex items-center gap-1.5" data-testid="topbar-status">
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider ${tone.ring} ${tone.text}`}
          title={`Model gateway: ${posture?.model_gateway ?? "unknown"} · sandbox: ${posture?.sandbox ?? "unknown"}`}
        >
          <span className="relative flex h-1.5 w-1.5">
            <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-70 ${tone.dot}`} />
            <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${tone.dot}`} />
          </span>
          {tone.label}
        </span>
        <span
          className="hidden items-center gap-1.5 rounded-full bg-cyan-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-cyan-700 lg:inline-flex"
          title={`${posture?.external_calls_24h ?? 0} external calls in the last 24h`}
        >
          <Activity size={11} strokeWidth={2.4} />
          {posture ? `${posture.external_calls_24h} calls` : "—"}
        </span>
      </div>

      <SovereigntyCluster posture={posture} />
      <NotificationBell count={notifications} onClick={onOpenNotifications} />

      <div className="cs-userchip" role="group" aria-label="Active user and role">
        <span className="cs-userchip__avatar" aria-hidden="true">
          {user.slice(0, 2).toUpperCase()}
        </span>
        <span>
          <span className="cs-userchip__name">{user}</span>
          <span className="cs-userchip__role" style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <Settings2 size={10} strokeWidth={2.4} aria-hidden="true" />
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as ConsoleRole)}
              aria-label="Active role"
              style={{
                background: "none",
                border: 0,
                color: "inherit",
                font: "inherit",
                letterSpacing: "inherit",
                textTransform: "inherit",
                cursor: "pointer",
                padding: 0,
                appearance: "none",
              }}
            >
              {ROLES.map((r) => (
                <option key={r} value={r} style={{ background: "#ffffff", color: "#0f172a" }}>
                  {r}
                </option>
              ))}
            </select>
            <ChevronDown size={10} strokeWidth={2.4} aria-hidden="true" />
          </span>
        </span>
      </div>
    </header>
  );
}
