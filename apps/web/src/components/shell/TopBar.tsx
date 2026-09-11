"use client";

/** Persistent top bar: plant label, ⌘K, sovereignty, notifications, role. */
import { Icon } from "@/components/ui/Icon";
import { SovereigntyCluster } from "./SovereigntyCluster";
import { NotificationBell } from "./NotificationCenter";
import { useRole } from "@/lib/role";
import { ConsoleCommandDock } from "@/components/threeui/ThreeUIScenes";
import type { ConsoleRole, SystemPosture } from "@/types/console";

const ROLES: ConsoleRole[] = ["operator", "engineer", "maintenance", "safety", "manager", "admin"];

export function TopBar({
  posture,
  notifications,
  onOpenPalette,
  onOpenNotifications,
}: {
  posture: SystemPosture | null;
  notifications: number;
  onOpenPalette: () => void;
  onOpenNotifications: () => void;
}) {
  const { role, user, setRole } = useRole();

  return (
    <header className="cs-topbar">
      <ConsoleCommandDock />

      <span className="cs-topbar__brand">PROJECT 117</span>
      <span className="cs-topbar__plant">
        <Icon name="gauge" size={13} />
        Plant Alpha
      </span>

      <button className="cs-search-trigger" onClick={onOpenPalette} aria-label="Open command palette">
        <Icon name="search" size={13} />
        <span>Search or command…</span>
        <kbd>⌘K</kbd>
      </button>

      <SovereigntyCluster posture={posture} />
      <NotificationBell count={notifications} onClick={onOpenNotifications} />

      <div className="cs-userchip" role="group" aria-label="Active user and role">
        <span className="cs-userchip__avatar" aria-hidden="true">
          {user.slice(0, 2).toUpperCase()}
        </span>
        <span>
          <span className="cs-userchip__name">{user}</span>
          <span className="cs-userchip__role" style={{ display: "flex", alignItems: "center", gap: 6 }}>
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
              }}
            >
              {ROLES.map((r) => (
                <option key={r} value={r} style={{ background: "#0b121b", color: "#eaf2fa" }}>
                  {r}
                </option>
              ))}
            </select>
          </span>
        </span>
      </div>
    </header>
  );
}
