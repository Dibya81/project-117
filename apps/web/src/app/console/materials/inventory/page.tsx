"use client";

/**
 * Inventory — the stock positions register.
 *
 * One question, asked of every row: not "how much do we have", but "how much can
 * a maintenance job actually draw". The backend computes `available =
 * quantity − reserved`, so the row renders quantity and reserved quietly and
 * gives the available figure the visual weight. Nothing on this page is
 * arithmetic done in the browser: every number is the engine's.
 *
 * The summary strip is register-wide (all positions) and labelled as such; the
 * table below is what the class/search filter narrows. A filtered table says
 * "N of M" rather than silently changing the summary.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Lucide } from "@/components/ui/LucideIcon";
import {
  EmptyState,
  MaterialPanel,
  MaterialsHeader,
  Money,
  ProvenanceLine,
  SyntheticDemoBadge,
} from "@/components/materials/MaterialsKit";
import MaterialsSegmented, { type MaterialsSegmentOption } from "@/components/materials/MaterialsSegmented";
import InventoryRow from "@/components/materials/InventoryRow";
import { consoleData } from "@/lib/data/console";
import type { InventoryStatusRecord, MaterialsDashboardRecord } from "@/lib/api";

/**
 * The four classes the backend's `material_class` enum defines. This is a label
 * map for the enum, not a data source: the option is only offered because the
 * API accepts it, and the counts beside each chip are counted from the real
 * register response.
 */
const CLASS_OPTIONS: { id: string; label: string }[] = [
  { id: "RAW_MATERIAL", label: "Raw material" },
  { id: "INTERMEDIATE", label: "Intermediate" },
  { id: "FINISHED_PRODUCT", label: "Finished product" },
  { id: "MAINTENANCE_SPARE", label: "Maintenance spare" },
];

/** A register-level counter. The value is a tally over the backend's rows, never a domain computation. */
function SummaryCard({
  label,
  value,
  tone = "slate",
  detail,
}: {
  label: string;
  value: number | null;
  tone?: "slate" | "crit" | "warn" | "ok";
  detail?: string;
}) {
  const toneClass =
    tone === "crit"
      ? "text-red-600"
      : tone === "warn"
        ? "text-amber-600"
        : tone === "ok"
          ? "text-emerald-600"
          : "text-slate-900";
  return (
    <div className="mat-sum" data-summary-card={label}>
      <span className="mat-sum__label">{label}</span>
      <span className={`mat-sum__value ${toneClass}`} data-summary-value={value ?? "unavailable"}>
        {value === null ? "—" : value.toLocaleString()}
      </span>
      {detail ? <span className="mat-sum__detail">{detail}</span> : null}
    </div>
  );
}

export default function MaterialsInventoryPage() {
  const [materialClass, setMaterialClass] = useState("all");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  /** The table's rows — filtered server-side. `null` means "still loading". */
  const [rows, setRows] = useState<InventoryStatusRecord[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  /** The unfiltered register, used only for the summary counters. */
  const [register, setRegister] = useState<InventoryStatusRecord[] | null>(null);
  const [dashboard, setDashboard] = useState<MaterialsDashboardRecord | null>(null);

  // Debounce the search so a keystroke is not a request per character.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 220);
    return () => clearTimeout(t);
  }, [search]);

  /**
   * The register-wide fetch. It backs the summary strip only; it is deliberately
   * separate from the filtered fetch so the counters describe the whole
   * register and do not move when a filter is applied.
   */
  useEffect(() => {
    let alive = true;
    consoleData.materials
      .inventory({})
      .then((r) => alive && setRegister(r.items))
      .catch(() => alive && setRegister([]));
    consoleData.materials
      .overview()
      .then((r) => alive && setDashboard(r?.dashboard ?? null))
      .catch(() => alive && setDashboard(null));
    return () => {
      alive = false;
    };
  }, []);

  /** The filtered fetch. A request sequence counter drops stale responses. */
  const requestSeq = useRef(0);
  useEffect(() => {
    const seq = ++requestSeq.current;
    setRows(null);
    setLoadError(null);
    consoleData.materials
      .inventory({
        materialClass: materialClass === "all" ? undefined : materialClass,
        search: debouncedSearch || undefined,
      })
      .then((r) => {
        if (requestSeq.current !== seq) return;
        setRows(r.items);
      })
      .catch((e: unknown) => {
        if (requestSeq.current !== seq) return;
        setRows([]);
        setLoadError(e instanceof Error ? e.message : "the inventory endpoint did not return a result");
      });
  }, [materialClass, debouncedSearch]);

  const counts = useMemo(() => {
    const all = register ?? [];
    const tally = (status: string) => all.filter((r) => (r.status ?? "").toUpperCase() === status).length;
    return {
      total: all.length,
      critical: tally("CRITICAL"),
      outOfStock: tally("OUT_OF_STOCK"),
      depleting: tally("DEPLETING"),
    };
  }, [register]);

  const classOptions: MaterialsSegmentOption[] = useMemo(
    () => [
      { id: "all", label: "All classes", count: register ? register.length : undefined },
      ...CLASS_OPTIONS.map((c) => ({
        id: c.id,
        label: c.label,
        count: register ? register.filter((r) => r.material?.material_class === c.id).length : undefined,
      })),
    ],
    [register],
  );

  const filtered = materialClass !== "all" || debouncedSearch.length > 0;

  return (
    <>
      <MaterialsHeader
        kicker="Materials"
        title="Inventory"
        lede="Every stock position the engine holds, with the three figures that are routinely confused: quantity on hand, quantity reserved elsewhere, and available — the only one a maintenance job can draw against. Available is computed by the backend as quantity − reserved; this console never recomputes it."
        actions={
          <Link href="/console/materials/spares" className="cs-btn cs-btn--ghost">
            <Lucide name="wrench" size={13} /> Maintenance spares
          </Link>
        }
      />

      <div className="mat-sumstrip">
        <SummaryCard
          label="Positions"
          value={register ? counts.total : null}
          detail="in the register"
        />
        <SummaryCard
          label="Critical"
          value={register ? counts.critical : null}
          tone="crit"
          detail="available ≤ safety stock"
        />
        <SummaryCard
          label="Out of stock"
          value={register ? counts.outOfStock : null}
          tone="crit"
          detail="available ≤ 0"
        />
        <SummaryCard
          label="Depleting"
          value={register ? counts.depleting : null}
          tone="warn"
          detail="available ≤ reorder level"
        />
        {/*
          Value card. A per-position *available* value cannot be sourced: the
          inventory endpoint carries no price, and prices exist only per item
          (price-history) or per required line (recommendation). Rather than
          compute Σ(available × price) in the browser — forbidden here — the
          card shows the backend's own register-level inventory value with its
          exact basis. It is a quantity-basis figure, NOT an available-only one,
          and the card says so.
        */}
        <div className="mat-sum" data-summary-card="Recorded inventory value">
          <span className="mat-sum__label">Recorded inventory value</span>
          {dashboard ? (
            <>
              <span className="mat-sum__value text-slate-900" data-summary-value="recorded-inventory-value">
                <Money amount={dashboard.inventory_value.amount} currency={dashboard.inventory_value.currency} />
              </span>
              <span className="mat-sum__detail">
                {dashboard.inventory_value.calculation_status} · quantity basis, not available-only
              </span>
            </>
          ) : (
            <>
              <span className="mat-sum__value text-slate-400">—</span>
              <span className="mat-sum__detail">register value unavailable</span>
            </>
          )}
        </div>
      </div>
      {dashboard ? (
        <div className="mat-provenance">
          <ProvenanceLine calculationStatus={dashboard.inventory_value.calculation_status} basis={{ basis: dashboard.inventory_value.basis }} />
        </div>
      ) : null}

      <MaterialPanel
        title="Stock positions"
        subtitle={
          rows === null
            ? "Loading…"
            : filtered
              ? `${rows.length} of ${counts.total} positions`
              : `${rows.length} positions`
        }
        testId="material-inventory-table"
      >
        <div className="mat-toolbar">
          <MaterialsSegmented
            options={classOptions}
            value={materialClass}
            onChange={setMaterialClass}
            layoutId="mat-inventory-filter"
            ariaLabel="Filter inventory by material class"
          />
          <div className="cs-eqsearch mat-toolbar__search">
            <Lucide name="search" size={13} className="cs-eqsearch__glyph" />
            <input
              className="cs-eqsearch__input"
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search material, id, location…"
              aria-label="Search inventory"
              data-materials-inventory-search
            />
            {search && (
              <button type="button" className="cs-eqsearch__clear" onClick={() => setSearch("")} aria-label="Clear search">
                <Lucide name="x" size={12} />
              </button>
            )}
          </div>
          <span className="mat-toolbar__note">
            <SyntheticDemoBadge />
          </span>
        </div>

        <div className="mat-inv__scroll">
          <div className="mat-inv" aria-label="Stock positions">
            {/* Each row is a single link to the material, so the header cells are
                labels for the columns rather than a table header element. */}
            <div className="mat-inv__head">
              <span className="mat-inv__cell">Material</span>
              <span className="mat-inv__cell">Class</span>
              <span className="mat-inv__cell">Location</span>
              <span className="mat-inv__cell mat-inv__cell--num" title="Gross quantity on hand">
                On hand
              </span>
              <span className="mat-inv__cell mat-inv__cell--num" title="Committed elsewhere, not drawable">
                Reserved
              </span>
              <span className="mat-inv__cell mat-inv__cell--avail" title="quantity − reserved: what a job can draw">
                Available
              </span>
              <span className="mat-inv__cell mat-inv__cell--num" title="Stock held back from routine draw">
                Safety
              </span>
              <span className="mat-inv__cell mat-inv__cell--num" title="Level at which the position is flagged">
                Reorder
              </span>
              <span className="mat-inv__cell">Unit</span>
              <span className="mat-inv__cell mat-inv__cell--cover" title="available ÷ average daily consumption">
                Cover
              </span>
              <span className="mat-inv__cell mat-inv__cell--status">Status</span>
            </div>

            {rows === null ? (
              <div className="mat-inv__skeleton" aria-label="Loading stock positions">
                {Array.from({ length: 8 }, (_, i) => (
                  <div key={i} className="mat-inv__skeletonrow" />
                ))}
              </div>
            ) : rows.length === 0 ? (
              <div className="mat-inv__empty">
                <EmptyState
                  title={loadError ? "Inventory unavailable" : "No positions match"}
                  detail={
                    loadError
                      ? `The inventory endpoint did not return a result (${loadError}). No figures are shown rather than a fabricated register.`
                      : `No stock position matches the current class filter and search${filtered ? ` (${counts.total} position${counts.total === 1 ? "" : "s"} in the register)` : ""}.`
                  }
                />
              </div>
            ) : (
              rows.map((position) => <InventoryRow key={position.material_id} position={position} />)
            )}
          </div>
        </div>
      </MaterialPanel>
    </>
  );
}
