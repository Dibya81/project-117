"use client";

/**
 * SimPanel — the reference panel shell.
 *
 * Every console panel in the reference shares one anatomy, so it is one
 * component rather than six lookalikes: a coloured title bar carrying the
 * panel's identity, a row of filters and a search field, a dense table, and a
 * detail column for whatever row is selected. The accent colour encodes the
 * panel's domain, not its state — state is always carried inside the rows.
 */

import { useMemo, useState, type ReactNode } from "react";
import { Icon, type IconName } from "@/components/ui/Icon";

export type Accent = "sensors" | "equipment" | "control" | "scenarios" | "incidents" | "agents";

const ACCENT: Record<Accent, { bar: string; ink: string }> = {
  sensors: { bar: "linear-gradient(135deg,#1d4ed8,#2563eb)", ink: "#fff" },
  equipment: { bar: "linear-gradient(135deg,#b45309,#d97706)", ink: "#fff" },
  control: { bar: "linear-gradient(135deg,#047857,#059669)", ink: "#fff" },
  scenarios: { bar: "linear-gradient(135deg,#6d28d9,#7c3aed)", ink: "#fff" },
  incidents: { bar: "linear-gradient(135deg,#b91c1c,#dc2626)", ink: "#fff" },
  agents: { bar: "linear-gradient(135deg,#0e7490,#0891b2)", ink: "#fff" },
};

export interface SimPanelProps {
  accent: Accent;
  title: string;
  subtitle?: string;
  icon: IconName;
  /** Filter controls rendered beside the search field. */
  filters?: { id: string; label: string; options: string[]; value: string; onChange: (v: string) => void }[];
  search?: { value: string; onChange: (v: string) => void; placeholder?: string };
  /** The table, and the detail column for its selected row. */
  children: ReactNode;
  detail?: ReactNode;
  /** Right-hand actions in the title bar. */
  actions?: ReactNode;
  testId?: string;
}

export function SimPanel({
  accent,
  title,
  subtitle,
  icon,
  filters = [],
  search,
  children,
  detail,
  actions,
  testId,
}: SimPanelProps) {
  const a = ACCENT[accent];
  return (
    <section className="simpanel" data-accent={accent} data-testid={testId}>
      <header className="simpanel__bar" style={{ background: a.bar, color: a.ink }}>
        <span className="simpanel__badge">
          <Icon name={icon} size={16} />
        </span>
        <div className="simpanel__id">
          <span className="simpanel__title">{title}</span>
          {subtitle && <span className="simpanel__sub">{subtitle}</span>}
        </div>
        <span className="simpanel__actions">{actions}</span>
      </header>

      {(filters.length > 0 || search) && (
        <div className="simpanel__filters">
          {filters.map((f) => (
            <label key={f.id} className="simpanel__filter">
              <span>{f.label}</span>
              <select value={f.value} onChange={(e) => f.onChange(e.target.value)} aria-label={f.label}>
                {f.options.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            </label>
          ))}
          {search && (
            <label className="simpanel__search">
              <Icon name="search" size={12} />
              <input
                value={search.value}
                onChange={(e) => search.onChange(e.target.value)}
                placeholder={search.placeholder ?? "Search…"}
                aria-label={`Search ${title}`}
              />
            </label>
          )}
        </div>
      )}

      <div className={`simpanel__body${detail ? " has-detail" : ""}`}>
        <div className="simpanel__table">{children}</div>
        {detail && <aside className="simpanel__detail">{detail}</aside>}
      </div>
    </section>
  );
}

/** A filter value list built from what the data actually contains. */
export function optionsFrom(values: (string | undefined | null)[], allLabel = "All"): string[] {
  const set = new Set<string>();
  for (const v of values) if (v) set.add(v);
  return [allLabel, ...[...set].sort()];
}

/** Hook for the search + filter triple every panel needs. */
export function usePanelFilters() {
  const [q, setQ] = useState("");
  const [area, setArea] = useState("All");
  const [type, setType] = useState("All");
  const [state, setState] = useState("All");
  const match = useMemo(
    () =>
      (row: { text: string; area?: string; type?: string; state?: string }) =>
        (!q || row.text.toLowerCase().includes(q.toLowerCase())) &&
        (area === "All" || row.area === area) &&
        (type === "All" || row.type === type) &&
        (state === "All" || row.state === state),
    [q, area, type, state],
  );
  return { q, setQ, area, setArea, type, setType, state, setState, match };
}
