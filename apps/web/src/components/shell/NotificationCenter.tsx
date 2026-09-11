"use client";

/** Notification drawer — categorized, with contextual navigation. */
import { useRouter } from "next/navigation";
import { Drawer } from "@/components/ui/overlays";
import { StatusDot, timeAgo } from "@/components/ui/primitives";
import { Icon } from "@/components/ui/Icon";
import type { NotificationItem } from "@/types/console";

const CATEGORY_LABEL: Record<NotificationItem["category"], string> = {
  critical: "Critical",
  attention: "Attention",
  ai: "AI Activity",
  system: "System",
};

const CATEGORY_STATE: Record<NotificationItem["category"], "critical" | "warning" | "ai" | "unknown"> = {
  critical: "critical",
  attention: "warning",
  ai: "ai",
  system: "unknown",
};

export function NotificationCenter({ items, onClose }: { items: NotificationItem[]; onClose: () => void }) {
  const router = useRouter();
  const groups = (Object.keys(CATEGORY_LABEL) as NotificationItem["category"][])
    .map((cat) => ({ cat, items: items.filter((i) => i.category === cat) }))
    .filter((g) => g.items.length > 0);

  return (
    <Drawer title="Notifications" onClose={onClose}>
      {groups.map((g) => (
        <section key={g.cat} style={{ marginBottom: 20 }}>
          <p
            className="cs-mono cs-dim"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: 10,
              letterSpacing: "0.28em",
              textTransform: "uppercase",
              margin: "0 0 10px",
            }}
          >
            <StatusDot state={CATEGORY_STATE[g.cat]} pulse={g.cat === "critical"} /> {CATEGORY_LABEL[g.cat]}
          </p>
          {g.items.map((n, i) => (
            <button
              key={n.id}
              className="cs-notif"
              style={{ animationDelay: `${i * 60}ms` }}
              onClick={() => {
                if (n.href) router.push(n.href);
                onClose();
              }}
            >
              <StatusDot state={CATEGORY_STATE[n.category]} />
              <span style={{ flex: 1 }}>
                <div style={{ color: "var(--ink-1)", fontWeight: 550 }}>{n.title}</div>
                {n.detail && <div className="cs-dim" style={{ fontSize: 11.5, marginTop: 2 }}>{n.detail}</div>}
              </span>
              <span className="cs-dim cs-mono" style={{ fontSize: 10, whiteSpace: "nowrap" }}>
                {timeAgo(n.at)}
              </span>
            </button>
          ))}
        </section>
      ))}
      {items.length === 0 && <p className="cs-dim">No notifications.</p>}
    </Drawer>
  );
}

export function NotificationBell({ count, onClick }: { count: number; onClick: () => void }) {
  return (
    <button className="cs-iconbtn" onClick={onClick} aria-label={`Notifications, ${count} unread`}>
      <Icon name="bell" />
      {count > 0 && <span className="cs-iconbtn__badge">{count}</span>}
    </button>
  );
}
