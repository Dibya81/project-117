"use client";

/**
 * Materials Register — the catalogue, filtered by class and searched by name.
 *
 * The register is server-paginated: the page asks the materials service for one
 * page at a time and prints the `total` the service reports, so "showing 13–24
 * of 25" is the backend's count and not a client-side guess. Nothing is
 * filtered, counted or sorted in the browser.
 *
 * One adapter note is recorded here because this page cannot fix it: the
 * console adapter forwards query keys verbatim, and the materials route binds
 * `material_class` (snake_case) rather than the `materialClass` key its own
 * type documents. The page therefore sends both spellings — the server stays
 * the single authority on what the catalogue contains, which is the property
 * that matters. If the adapter later maps the key, this stays correct.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  EmptyState,
  Figure,
  MaterialPanel,
  MaterialsHeader,
  StatusChip,
  statusTone,
} from "@/components/materials/MaterialsKit";
import { Lucide } from "@/components/ui/LucideIcon";
import { SkeletonRows } from "@/components/ui/primitives";
import { consoleData } from "@/lib/data/console";
import { SPRING } from "@/lib/ui/motion";
import type { MaterialRecord } from "@/lib/api";

const PAGE_SIZE = 12;

const CLASSES: { value: string; label: string }[] = [
  { value: "", label: "All classes" },
  { value: "RAW_MATERIAL", label: "Raw material" },
  { value: "INTERMEDIATE", label: "Intermediate" },
  { value: "FINISHED_PRODUCT", label: "Finished product" },
  { value: "MAINTENANCE_SPARE", label: "Maintenance spare" },
];

const CLASS_LABELS: Record<string, string> = Object.fromEntries(
  CLASSES.filter((c) => c.value).map((c) => [c.value, c.label]),
);

function classLabel(value: string | null | undefined): string {
  if (!value) return "—";
  return CLASS_LABELS[value] ?? value;
}

/** See the file header: the API binds `material_class`; the adapter type says `materialClass`. */
function classParams(value: string): { materialClass?: string; material_class?: string } {
  return value ? { materialClass: value, material_class: value } : {};
}

export default function MaterialsRegisterPage() {
  const router = useRouter();
  const [materialClass, setMaterialClass] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [rows, setRows] = useState<{ items: MaterialRecord[]; total: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [counts, setCounts] = useState<Record<string, number | null>>({});

  // Debounce the search box so typing does not fire a request per keystroke.
  useEffect(() => {
    const t = setTimeout(() => {
      setQuery(search.trim());
      setOffset(0);
    }, 280);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const params = {
      ...classParams(materialClass),
      search: query || undefined,
      limit: PAGE_SIZE,
      offset,
    };
    consoleData.materials
      .list(params)
      .then((r) => {
        if (cancelled) return;
        setRows({ items: r.items, total: r.total });
        setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setRows(null);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [materialClass, query, offset]);

  // Class counts are the service's own totals, fetched one row deep.
  useEffect(() => {
    let cancelled = false;
    Promise.all(
      CLASSES.map((c) =>
        consoleData.materials
          .list({ ...classParams(c.value), limit: 1 })
          .then((r) => [c.value, r.total] as const)
          .catch(() => [c.value, null] as const),
      ),
    ).then((entries) => {
      if (!cancelled) setCounts(Object.fromEntries(entries) as Record<string, number | null>);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const total = rows?.total ?? null;
  const shown = rows?.items.length ?? 0;
  const first = shown === 0 ? 0 : offset + 1;
  const last = offset + shown;
  const atEnd = total !== null && last >= total;
  const hasFilters = materialClass !== "" || query !== "";

  const clearFilters = useCallback(() => {
    setMaterialClass("");
    setSearch("");
    setQuery("");
    setOffset(0);
  }, []);

  return (
    <>
      <MaterialsHeader
        kicker="Industrial materials"
        title="Materials Register"
        lede="The full material catalogue — raw materials, intermediates, finished products and maintenance spares — served page by page with the service's own total."
        actions={
          <Link className="cs-btn cs-btn--ghost" href="/console/materials">
            <Lucide name="layers" size={12} /> Overview
          </Link>
        }
      />

      <MaterialPanel
        title="Catalogue"
        subtitle={
          total === null
            ? "Register unavailable"
            : `${total} material${total === 1 ? "" : "s"}${hasFilters ? " matching the current filter" : " on the register"}`
        }
      >
        <div className="mat-toolbar">
          <div className="cs-seg mat-seg" role="tablist" aria-label="Filter by material class">
            {CLASSES.map((c) => {
              const active = materialClass === c.value;
              const count = counts[c.value];
              return (
                <button
                  key={c.value || "all"}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  className={`cs-seg__tab${active ? " is-active" : ""}`}
                  onClick={() => {
                    setMaterialClass(c.value);
                    setOffset(0);
                  }}
                >
                  {active ? (
                    <motion.span
                      layoutId="mat-register-filter"
                      className="cs-seg__glider"
                      transition={SPRING.glide}
                    />
                  ) : null}
                  <span className="cs-seg__inner">
                    {c.label}
                    {count !== null && count !== undefined ? <span className="cs-seg__count">{count}</span> : null}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="mat-search">
            <Lucide name="search" size={13} className="text-slate-400" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search id, name or description…"
              aria-label="Search the material catalogue"
            />
            {search ? (
              <button className="mat-search__clear" type="button" onClick={() => setSearch("")} aria-label="Clear search">
                <Lucide name="x" size={12} />
              </button>
            ) : null}
          </div>
        </div>

        {loading && !rows ? (
          <SkeletonRows rows={8} label="Reading the material catalogue…" />
        ) : rows === null ? (
          <EmptyState
            title="The catalogue could not be read"
            detail="GET /api/materials did not answer, so no materials are listed. Nothing is shown from cache or estimate."
          />
        ) : rows.items.length === 0 ? (
          <EmptyState
            title="No material matches"
            detail={
              hasFilters
                ? `The service returned no row for the current class filter and search (${total ?? 0} material${total === 1 ? "" : "s"} match this filter in total).`
                : "The materials register returned no rows."
            }
          />
        ) : (
          <>
            <div className="mat-tablewrap">
              <table className="mat-table" data-material-rows={shown}>
                <thead>
                  <tr>
                    <th>Material</th>
                    <th>Class</th>
                    <th>Unit</th>
                    <th>Location</th>
                    <th>Status</th>
                    <th aria-label="Open" />
                  </tr>
                </thead>
                <tbody>
                  {rows.items.map((m) => (
                    <tr key={m.id} onClick={() => router.push(`/console/materials/${m.id}`)}>
                      <td>
                        <Link className="mat-table__id" href={`/console/materials/${m.id}`}>
                          {m.id}
                        </Link>
                        <div className="mat-table__name">{m.name}</div>
                      </td>
                      <td>
                        <span className="mat-chip">{classLabel(m.material_class)}</span>
                      </td>
                      <td className="font-mono text-[11.5px]">{m.unit || <span className="mat-empty">—</span>}</td>
                      <td className="font-mono text-[11px]">
                        {m.location ? (
                          <Link
                            className="mat-link"
                            href={`/console/equipment/${m.location}`}
                            onClick={(e) => e.stopPropagation()}
                            title="Storage asset"
                          >
                            {m.location}
                          </Link>
                        ) : (
                          <span className="mat-empty" title="No storage location recorded for this material">
                            —
                          </span>
                        )}
                      </td>
                      <td>
                        <StatusChip label={m.status} tone={statusTone(m.status)} />
                      </td>
                      <td className="mat-num text-slate-300">
                        <Lucide name="chevron" size={13} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mat-pager">
              <span className="mat-pager__meta">
                Showing {first}–{last} of {total ?? "—"}
              </span>
              <span className="mat-pager__spacer" />
              {hasFilters ? (
                <button className="cs-btn cs-btn--ghost" type="button" onClick={clearFilters}>
                  <Lucide name="filter" size={12} /> Clear filters
                </button>
              ) : null}
              <button
                className="cs-btn cs-btn--ghost"
                type="button"
                disabled={offset === 0 || loading}
                onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
              >
                ← Previous
              </button>
              <button
                className="cs-btn cs-btn--ghost"
                type="button"
                disabled={atEnd || loading}
                onClick={() => setOffset((o) => o + PAGE_SIZE)}
              >
                Next →
              </button>
            </div>
          </>
        )}
      </MaterialPanel>

      <div className="mat-foot">
        <span>
          Page size {PAGE_SIZE} · totals and rows are the materials service&rsquo;s own pagination, not a client-side slice.
        </span>
        <span className="mat-chip">
          endpoint <b>/api/materials</b>
        </span>
      </div>
    </>
  );
}
