"use client";

/**
 * SessionList — the workspace's recall rail.
 *
 * Grouping is derived from the REAL `WorkspaceSession.at` timestamp. The adapter
 * returns `{ id, title, at, task_count }` and nothing else — there is no
 * project, folder, agent or tag field on the record — so the only honest axis to
 * group by is the calendar day the session happened. Inventing a grouping the
 * backend cannot support would be fabricating structure, so we do not.
 *
 * Presentation only: the timeline connectors, the collapsible day headers and
 * the hover affordances. The click target is still the same `onSelect(id)` the
 * plain rows called, and the "New session" button is still the page's own
 * `onNewSession` handler.
 */
import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Lucide } from "@/components/ui/LucideIcon";
import { ICON_HOVER, SPRING, iconGlow } from "@/lib/ui/motion";
import { timeAgo } from "@/components/ui/primitives";
import type { WorkspaceSession } from "@/types/console";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Calendar-day key from the record's real `at` field. */
function dayKey(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
}

/**
 * Deterministic day label — deliberately not `toLocaleDateString`, whose output
 * differs between the Node render and the browser and would show up as a
 * hydration mismatch.
 */
function dayLabel(iso: string): string {
  const d = new Date(iso);
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const days = Math.round((startOf(new Date()) - startOf(d)) / 86_400_000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;
  return `${MONTHS[d.getMonth()]} ${d.getDate()}`;
}

interface DayGroup {
  key: string;
  label: string;
  items: WorkspaceSession[];
}

export function SessionList({
  sessions,
  activeSession,
  onSelect,
  onNewSession,
}: {
  sessions: WorkspaceSession[];
  activeSession: string;
  onSelect: (id: string) => void;
  onNewSession: () => void;
}) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const groups = useMemo<DayGroup[]>(() => {
    const byDay = new Map<string, DayGroup>();
    for (const s of sessions) {
      const key = dayKey(s.at);
      const group = byDay.get(key);
      if (group) group.items.push(s);
      else byDay.set(key, { key, label: dayLabel(s.at), items: [s] });
    }
    return [...byDay.values()];
  }, [sessions]);

  // The adapter currently has no session source and returns `[]`. Say that
  // plainly rather than dressing the empty sidebar up as "loading".
  return (
    <div className="cs-fade-list">
      {sessions.length === 0 ? (
        <div className="cs-sessions-empty">
          <Lucide name="history" size={16} />
          <span className="cs-sessions-empty__title">No sessions to recall</span>
          <span className="cs-sessions-empty__sub">
            No workspace session source is connected yet, so there is nothing to list.
          </span>
        </div>
      ) : (
        <div className="cs-sessions">
          {groups.map((group) => {
            const open = !collapsed[group.key];
            const panelId = `sessions-${group.key}`;
            return (
              <section className="cs-sessgroup" key={group.key} aria-label={group.label}>
                <button
                  type="button"
                  className="cs-sessgroup__head"
                  aria-expanded={open}
                  aria-controls={panelId}
                  onClick={() => setCollapsed((c) => ({ ...c, [group.key]: open }))}
                >
                  <motion.span
                    className="cs-sessgroup__chev"
                    animate={{ rotate: open ? 90 : 0 }}
                    transition={SPRING.micro}
                    aria-hidden="true"
                  >
                    <Lucide name="chevron" size={12} />
                  </motion.span>
                  {group.label}
                  <span className="cs-sessgroup__count">{group.items.length}</span>
                </button>
  
                <AnimatePresence initial={false}>
                  {open && (
                    <motion.div
                      id={panelId}
                      className="cs-sesslist"
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={SPRING.panel}
                    >
                      {group.items.map((s) => {
                        const active = activeSession === s.id;
                        return (
                          <motion.button
                            key={s.id}
                            type="button"
                            className={`cs-sess${active ? " is-active" : ""}`}
                            aria-current={active ? "true" : undefined}
                            onClick={() => onSelect(s.id)}
                            whileHover="hover"
                            whileTap={{ scale: 0.99 }}
                            transition={SPRING.micro}
                          >
                            <motion.span
                              className="cs-sess__icon"
                              variants={{ hover: ICON_HOVER }}
                              transition={SPRING.micro}
                            >
                              <motion.span
                                className="flex"
                                variants={{ hover: { filter: iconGlow("#0891b2", 0.5) } }}
                                transition={SPRING.micro}
                              >
                                <Lucide name={active ? "chat" : "history"} size={14} />
                              </motion.span>
                            </motion.span>
  
                            <span className="cs-sess__text">
                              <span className="cs-row__title cs-sess__title">{s.title}</span>
                              <span className="cs-row__sub cs-sess__sub">
                                {s.task_count} task{s.task_count === 1 ? "" : "s"} · {timeAgo(s.at)}
                              </span>
                            </span>
  
                            {/* Appears on row hover — the row itself is the action. */}
                            <span className="cs-sess__open" aria-hidden="true">
                              <Lucide name="arrow" size={13} />
                            </span>
                          </motion.button>
                        );
                      })}
                    </motion.div>
                  )}
                </AnimatePresence>
              </section>
            );
          })}
        </div>
      )}

      <div style={{ padding: 12 }}>
        <button
          className="cs-btn cs-btn--ghost"
          style={{ width: "100%", justifyContent: "center" }}
          onClick={onNewSession}
        >
          <Lucide name="plus" size={13} /> New session
        </button>
      </div>
    </div>
  );
}
