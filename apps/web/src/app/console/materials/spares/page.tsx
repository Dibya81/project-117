"use client";

/**
 * Maintenance Spares — the equipment → spare → inventory → coverage surface.
 *
 * Four questions, in order, and the page is laid out in that order:
 *
 *  1. What is on the shelf, and which of it will stop a maintenance job?
 *     The shelf groups spares by the engine's own status, worst first.
 *  2. What does a chosen asset require? `maintenance-requirements/{id}` returns
 *     required / available / safety stock and the engine's coverage verdict per
 *     line — the console renders that verdict, it does not derive one.
 *  3. What would it cost? `procurement-recommendations` composes the proposal.
 *  4. Who decides? An engineer, in the Approvals surface. The recommendation is
 *     read-only and this page places no order.
 *
 * No figure here is computed in the browser: availability, surplus, shortfall,
 * coverage, price and cost all arrive from the engine.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Lucide } from "@/components/ui/LucideIcon";
import {
  CoverageChip,
  EmptyState,
  Figure,
  LimitationNote,
  MaterialPanel,
  MaterialsHeader,
  Money,
  ProvenanceLine,
  StatusChip,
  statusTone,
} from "@/components/materials/MaterialsKit";
import MaterialsSegmented, { type MaterialsSegmentOption } from "@/components/materials/MaterialsSegmented";
import LimitationInline from "@/components/materials/LimitationInline";
import SpareShelfRow from "@/components/materials/SpareShelfRow";
import RecommendationView from "@/components/materials/RecommendationView";
import { consoleData } from "@/lib/data/console";
import type { Equipment } from "@/types";
import type {
  EquipmentRequirementsRecord,
  InventoryStatusRecord,
  MaterialDetailEnvelope,
  MaterialRequirementRecord,
  RecommendationRecord,
} from "@/lib/api";

/**
 * Presentation-only ordering. `OUT_OF_STOCK` and `CRITICAL` are the shelf items
 * that stop a job, so they lead both the groups and the sort. This is a rank for
 * display; it is not a re-derivation of the backend's status rule.
 */
const STATUS_RANK: Record<string, number> = { OUT_OF_STOCK: 0, CRITICAL: 1, DEPLETING: 2, AVAILABLE: 3 };
const rankOf = (status: string | undefined) => STATUS_RANK[(status ?? "").toUpperCase()] ?? 4;

const GROUPS: { id: string; label: string; detail: string; match: (status: string) => boolean }[] = [
  {
    id: "stop",
    label: "Shelf stoppers",
    detail: "Out of stock or at/below safety stock — these stop a maintenance job",
    match: (s) => s === "OUT_OF_STOCK" || s === "CRITICAL",
  },
  {
    id: "watch",
    label: "Depleting",
    detail: "At or below reorder level",
    match: (s) => s === "DEPLETING",
  },
  {
    id: "ok",
    label: "Above reorder level",
    detail: "No action flagged by the engine",
    match: () => true,
  },
];

export default function MaintenanceSparesPage() {
  const [spares, setSpares] = useState<InventoryStatusRecord[] | null>(null);
  const [sparesError, setSparesError] = useState<string | null>(null);
  const [details, setDetails] = useState<Record<string, MaterialDetailEnvelope | null>>({});
  const [equipment, setEquipment] = useState<Equipment[] | null>(null);

  const [selectedEquipmentId, setSelectedEquipmentId] = useState("");
  const [failureMode, setFailureMode] = useState("all");
  const [assetQuery, setAssetQuery] = useState("");

  const [requirements, setRequirements] = useState<EquipmentRequirementsRecord | null>(null);
  const [coverage, setCoverage] = useState<MaterialRequirementRecord | null>(null);
  const [requirementsLoading, setRequirementsLoading] = useState(false);

  const [recommendation, setRecommendation] = useState<RecommendationRecord | null>(null);
  const [recommendLoading, setRecommendLoading] = useState(false);
  const [recommendError, setRecommendError] = useState<string | null>(null);
  const recommendationRef = useRef<HTMLDivElement | null>(null);

  /* ------------------------------------------------------------------ shelf */
  useEffect(() => {
    let alive = true;
    consoleData.materials
      .inventory({ materialClass: "MAINTENANCE_SPARE" })
      .then((r) => {
        if (!alive) return;
        setSpares(r.items);
        // One detail read per spare gives `required_by` and the forecast; the
        // backend composes both, so they are fetched rather than inferred.
        Promise.all(
          r.items.map(async (p) => {
            try {
              const d = await consoleData.materials.detail(p.material_id);
              return [p.material_id, d] as const;
            } catch {
              return [p.material_id, null] as const;
            }
          }),
        ).then((pairs) => {
          if (!alive) return;
          setDetails(Object.fromEntries(pairs));
        });
      })
      .catch((e: unknown) => {
        if (!alive) return;
        setSpares([]);
        setSparesError(e instanceof Error ? e.message : "the inventory endpoint did not return a result");
      });
    consoleData.equipment
      .list()
      .then((e) => alive && setEquipment(e))
      .catch(() => alive && setEquipment([]));
    return () => {
      alive = false;
    };
  }, []);

  /**
   * The default asset is not hardcoded: it is the asset whose required spares are
   * in the worst inventory state, taken from the real `required_by` mappings.
   */
  useEffect(() => {
    if (selectedEquipmentId || !spares?.length || !Object.keys(details).length) return;
    const worst = new Map<string, number>();
    for (const position of spares) {
      const detail = details[position.material_id];
      if (!detail) continue;
      const rank = rankOf(position.status);
      for (const r of detail.required_by) {
        worst.set(r.equipment_id, Math.min(worst.get(r.equipment_id) ?? 9, rank));
      }
    }
    const candidate = [...worst.entries()].sort((a, b) => a[1] - b[1] || a[0].localeCompare(b[0]))[0]?.[0];
    if (candidate) setSelectedEquipmentId(candidate);
    else if (equipment?.length) setSelectedEquipmentId(equipment[0].id);
  }, [selectedEquipmentId, spares, details, equipment]);

  const selectAsset = useCallback((id: string) => {
    setSelectedEquipmentId(id);
    setFailureMode("all");
  }, []);

  /* ------------------------------------------------- asset requirement read */
  useEffect(() => {
    if (!selectedEquipmentId) return;
    let alive = true;
    setRequirementsLoading(true);
    setRecommendation(null);
    setRecommendError(null);
    const mode = failureMode === "all" ? undefined : failureMode;
    Promise.all([
      consoleData.materials.requirementsFor(selectedEquipmentId).catch(() => null),
      consoleData.materials.maintenanceRequirement(selectedEquipmentId, mode).catch(() => null),
    ]).then(([reqs, cover]) => {
      if (!alive) return;
      setRequirements(reqs);
      setCoverage(cover);
      setRequirementsLoading(false);
    });
    return () => {
      alive = false;
    };
  }, [selectedEquipmentId, failureMode]);

  const failureModes = useMemo(() => {
    const modes = new Set<string>();
    for (const r of requirements?.requirements ?? []) {
      if (r.failure_mode) modes.add(r.failure_mode);
    }
    return [...modes].sort();
  }, [requirements]);

  const failureOptions: MaterialsSegmentOption[] = useMemo(
    () => [
      { id: "all", label: "All requirements" },
      ...failureModes.map((m) => ({ id: m, label: m })),
    ],
    [failureModes],
  );

  const assetOptions = useMemo(() => {
    const q = assetQuery.trim().toLowerCase();
    const list = (equipment ?? []).filter(
      (e) => !q || e.id.toLowerCase().includes(q) || e.name.toLowerCase().includes(q),
    );
    if (selectedEquipmentId && !list.some((e) => e.id === selectedEquipmentId)) {
      const current = (equipment ?? []).find((e) => e.id === selectedEquipmentId);
      if (current) list.unshift(current);
    }
    return list;
  }, [equipment, assetQuery, selectedEquipmentId]);

  const selectedAsset = useMemo(
    () => (equipment ?? []).find((e) => e.id === selectedEquipmentId) ?? null,
    [equipment, selectedEquipmentId],
  );

  /* ----------------------------------------------------- the proposal read */
  const prepareRecommendation = useCallback(async () => {
    if (!selectedEquipmentId) return;
    setRecommendLoading(true);
    setRecommendError(null);
    try {
      const rec = await consoleData.materials.recommendation(
        selectedEquipmentId,
        failureMode === "all" ? undefined : failureMode,
      );
      setRecommendation(rec);
      requestAnimationFrame(() => recommendationRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (e: unknown) {
      setRecommendation(null);
      setRecommendError(
        e instanceof Error ? e.message : "the recommendation endpoint did not return a result",
      );
    } finally {
      setRecommendLoading(false);
    }
  }, [selectedEquipmentId, failureMode]);

  /** Line prices and costs, present only once a proposal has been composed. */
  const recByItem = useMemo(() => {
    const map = new Map<string, RecommendationRecord["lines"][number]>();
    for (const line of recommendation?.lines ?? []) map.set(line.item_id, line);
    return map;
  }, [recommendation]);

  /* ---------------------------------------------------------------- groups */
  const grouped = useMemo(() => {
    const rows = spares ?? [];
    const used = new Set<string>();
    return GROUPS.map((group) => {
      const items = rows
        .filter((p) => !used.has(p.material_id) && group.match((p.status ?? "").toUpperCase()))
        .sort((a, b) => rankOf(a.status) - rankOf(b.status) || (a.days_of_cover ?? Infinity) - (b.days_of_cover ?? Infinity));
      items.forEach((p) => used.add(p.material_id));
      return { ...group, items };
    }).filter((g) => g.items.length > 0);
  }, [spares]);

  const shelfCounts = useMemo(() => {
    const rows = spares ?? [];
    const tally = (s: string) => rows.filter((r) => (r.status ?? "").toUpperCase() === s).length;
    return { total: rows.length, out: tally("OUT_OF_STOCK"), critical: tally("CRITICAL"), depleting: tally("DEPLETING") };
  }, [spares]);

  const reqLines = coverage?.lines ?? [];
  const modeLabel = failureMode === "all" ? "all requirements" : failureMode;

  return (
    <>
      <MaterialsHeader
        kicker="Materials"
        title="Maintenance Spares"
        lede="The shelf items a maintenance job depends on, and the assets that consume them. Availability, safety stock, surplus and the coverage verdict are computed by the engine; a composed procurement proposal is a proposal only — it places no order and is executed nowhere but through an engineer's decision in Approvals."
        actions={
          <>
            <Link href="/console/materials/inventory" className="cs-btn cs-btn--ghost">
              <Lucide name="database" size={13} /> Inventory register
            </Link>
            <Link href="/console/approvals" className="cs-btn cs-btn--ghost">
              <Lucide name="shield" size={13} /> Approvals
            </Link>
          </>
        }
      />

      <div className="mat-sumstrip">
        <div className="mat-sum" data-summary-card="Spares">
          <span className="mat-sum__label">Spares</span>
          <span className="mat-sum__value text-slate-900">{spares ? shelfCounts.total.toLocaleString() : "—"}</span>
          <span className="mat-sum__detail">MAINTENANCE_SPARE positions</span>
        </div>
        <div className="mat-sum" data-summary-card="Out of stock">
          <span className="mat-sum__label">Out of stock</span>
          <span className="mat-sum__value text-red-600">{spares ? shelfCounts.out.toLocaleString() : "—"}</span>
          <span className="mat-sum__detail">available ≤ 0</span>
        </div>
        <div className="mat-sum" data-summary-card="Critical">
          <span className="mat-sum__label">Critical</span>
          <span className="mat-sum__value text-red-600">{spares ? shelfCounts.critical.toLocaleString() : "—"}</span>
          <span className="mat-sum__detail">available ≤ safety stock</span>
        </div>
        <div className="mat-sum" data-summary-card="Depleting">
          <span className="mat-sum__label">Depleting</span>
          <span className="mat-sum__value text-amber-600">{spares ? shelfCounts.depleting.toLocaleString() : "—"}</span>
          <span className="mat-sum__detail">available ≤ reorder level</span>
        </div>
        <div className="mat-sum" data-summary-card="Assets requiring spares">
          <span className="mat-sum__label">Assets requiring spares</span>
          <span className="mat-sum__value text-slate-900">
            {Object.keys(details).length === 0
              ? "—"
              : new Set(Object.values(details).flatMap((d) => (d?.required_by ?? []).map((r) => r.equipment_id))).size.toLocaleString()}
          </span>
          <span className="mat-sum__detail">from recorded requirements</span>
        </div>
      </div>

      {/* ------------------------------------------------ coverage workbench */}
      <MaterialPanel
        title="Asset coverage"
        subtitle={selectedAsset ? `${selectedAsset.id} — ${selectedAsset.name}` : "choose an asset"}
        actions={
          coverage ? (
            <span className="mat-workbench__verdict">
              {coverage.multiplier !== undefined && failureMode !== "all" ? (
                <span className="mat-workbench__mult">multiplier ×{coverage.multiplier}</span>
              ) : null}
              <CoverageChip coverage={coverage.overall_coverage} />
            </span>
          ) : null
        }
        testId="material-coverage-workbench"
      >
        <div className="mat-toolbar mat-toolbar--workbench">
          <div className="cs-eqsearch mat-toolbar__search">
            <Lucide name="search" size={13} className="cs-eqsearch__glyph" />
            <input
              className="cs-eqsearch__input"
              type="search"
              value={assetQuery}
              onChange={(e) => setAssetQuery(e.target.value)}
              placeholder="Filter assets…"
              aria-label="Filter assets"
              data-materials-asset-search
            />
            {assetQuery && (
              <button type="button" className="cs-eqsearch__clear" onClick={() => setAssetQuery("")} aria-label="Clear asset filter">
                <Lucide name="x" size={12} />
              </button>
            )}
          </div>
          <select
            className="cs-select mat-assetselect"
            value={selectedEquipmentId}
            onChange={(e) => selectAsset(e.target.value)}
            aria-label="Select an asset"
            data-materials-asset-picker
          >
            {assetOptions.length === 0 ? <option value="">No asset matches</option> : null}
            {assetOptions.map((e) => (
              <option key={e.id} value={e.id}>
                {e.id} — {e.name}
              </option>
            ))}
          </select>

          {failureModes.length > 0 ? (
            <MaterialsSegmented
              options={failureOptions}
              value={failureMode}
              onChange={setFailureMode}
              layoutId="mat-spares-failure-mode"
              ariaLabel="Filter requirements by failure mode"
            />
          ) : null}

          <button
            type="button"
            className="cs-btn cs-btn--primary mat-prepare"
            onClick={prepareRecommendation}
            disabled={!selectedEquipmentId || recommendLoading}
            data-materials-prepare
          >
            <Lucide name="sparkles" size={13} />
            {recommendLoading ? "Composing…" : "Prepare recommendation"}
          </button>
        </div>

        <p className="mat-workbench__hint">
          Composing a recommendation reads requirement, inventory and price data and returns a proposal awaiting an
          engineer&apos;s decision. It places no order.
        </p>

        {requirementsLoading ? (
          <div className="mat-workbench__loading" aria-label="Loading requirements">
            <div className="mat-inv__skeletonrow" />
            <div className="mat-inv__skeletonrow" />
          </div>
        ) : !selectedEquipmentId ? (
          <EmptyState
            title="No asset selected"
            detail="Choose an asset above to see the spares it requires and whether available stock covers the job."
          />
        ) : !coverage || reqLines.length === 0 ? (
          <EmptyState
            title="No requirement returned for this asset"
            detail={`The engine recorded no maintenance requirement for ${selectedEquipmentId} under ${modeLabel}. Nothing is shown rather than an assumed zero requirement.`}
          />
        ) : (
          <>
            <div className="mat-req__scroll">
              <div className="mat-req__table" aria-label={`Requirements for ${selectedEquipmentId}`}>
                <div className="mat-req__row mat-req__row--head">
                  <span>Required item</span>
                  <span className="mat-req__num">Required</span>
                  <span className="mat-req__num">Available</span>
                  <span className="mat-req__num">Safety stock</span>
                  <span className="mat-req__num">Surplus / shortfall</span>
                  <span>Coverage</span>
                  <span className="mat-req__num">Unit price</span>
                  <span className="mat-req__num">Cost</span>
                </div>
                {reqLines.map((line) => {
                  const recLine = recByItem.get(line.item_id);
                  return (
                    <div className="mat-req__row" key={line.requirement_id} data-requirement-item={line.item_id}>
                      <span className="mat-req__item">
                        <span className="mat-req__itemname">{line.item_name?.trim() ? line.item_name : line.item_id}</span>
                        <span className="mat-req__itemid">{line.item_id}</span>
                        {line.purpose ? <span className="mat-req__itemmeta">{line.purpose}</span> : null}
                        <span className="mat-req__itemmeta">
                          {line.schedule ? `${line.schedule} · ` : ""}
                          <StatusChip label={line.inventory_status ?? "unknown"} tone={statusTone(line.inventory_status)} />
                          {line.failure_mode ? (
                            <span className={`mat-req__mode${line.mode_match ? " is-match" : ""}`}>{line.failure_mode}</span>
                          ) : null}
                        </span>
                      </span>
                      <span className="mat-req__num">
                        <Figure value={line.required_quantity} unit={line.unit} className="text-[12.5px] text-slate-700" />
                      </span>
                      <span className="mat-req__num">
                        {line.available === null || line.available === undefined ? (
                          <LimitationInline limitations={line.limitations} label="no stock" />
                        ) : (
                          <Figure value={line.available} unit={line.unit} className="text-[12.5px] text-slate-700" />
                        )}
                      </span>
                      <span className="mat-req__num">
                        <Figure value={line.safety_stock} unit={line.unit} className="text-[12.5px] text-slate-500" />
                      </span>
                      <span className="mat-req__num">
                        {line.surplus_after_requirement_and_safety === null ||
                        line.surplus_after_requirement_and_safety === undefined ? (
                          <LimitationInline limitations={line.limitations} label="no surplus basis" />
                        ) : (
                          <>
                            <span
                              className={
                                line.coverage === "SHORTFALL"
                                  ? "text-red-600"
                                  : line.coverage === "COVERED"
                                    ? "text-emerald-600"
                                    : "text-slate-600"
                              }
                            >
                              <Figure
                                value={line.surplus_after_requirement_and_safety}
                                unit={line.unit}
                                className="text-[12.5px] font-semibold"
                              />
                            </span>
                            {line.coverage === "SHORTFALL" ? (
                              <span className="mat-req__short">
                                short <Figure value={line.shortfall_quantity} unit={line.unit} className="text-[11px]" />
                              </span>
                            ) : null}
                          </>
                        )}
                      </span>
                      <span>
                        <CoverageChip coverage={line.coverage} />
                      </span>
                      <span className="mat-req__num mat-req__price">
                        {recLine?.price?.current ? (
                          <>
                            <Money amount={recLine.price.current.price} className="text-[12.5px] text-slate-700" />
                            <span className="mat-rec__unitbasis">{recLine.price.current.unit}</span>
                          </>
                        ) : (
                          <span
                            className="mat-req__pending"
                            title="The backend reports a price for a line only once a recommendation has been composed for this asset. Press 'Prepare recommendation' above."
                          >
                            compose to price
                          </span>
                        )}
                      </span>
                      <span className="mat-req__num mat-req__cost">
                        {recLine?.cost?.amount === null || recLine?.cost?.amount === undefined ? (
                          <span
                          className="mat-req__pending"
                          title="The backend computes a line cost only once a recommendation has been composed for this asset."
                        >
                          compose to cost
                        </span>
                        ) : (
                          <>
                            <Money
                              amount={recLine.cost.amount}
                              currency={recLine.cost.currency}
                              className="text-[12.5px] font-semibold text-slate-800"
                            />
                            {recLine.cost.calculation_status ? (
                              <span className="mat-rec__calcstatus">{recLine.cost.calculation_status}</span>
                            ) : null}
                          </>
                        )}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
            <div className="mat-req__foot">
              <LimitationNote limitations={coverage.limitations} />
              <LimitationNote limitations={requirements?.limitations} />
            </div>
          </>
        )}

        {recommendError ? (
          <div className="mat-workbench__error" role="alert">
            Recommendation unavailable — {recommendError}. No proposal is shown rather than an assumed one.
          </div>
        ) : null}

        {/* Provenance of the requirement read the workbench just performed. */}
        {requirements?.requirements?.[0]?.provenance ? (
          <div className="mat-provenance">
            <ProvenanceLine provenance={requirements.requirements[0].provenance} />
          </div>
        ) : null}
      </MaterialPanel>

      <div ref={recommendationRef}>
        {recommendation ? <RecommendationView recommendation={recommendation} /> : null}
      </div>

      {/* --------------------------------------------------------- the shelf */}
      <MaterialPanel
        title="Spare shelf"
        subtitle={
          spares === null
            ? "Loading…"
            : `${shelfCounts.total} maintenance spares · worst inventory state first`
        }
        actions={
          <span className="mat-panelnote">Required-by mappings and forecasts come from each material&apos;s detail read</span>
        }
        testId="material-spare-shelf"
      >
        {spares === null ? (
          <div className="mat-inv__skeleton" aria-label="Loading spares">
            {Array.from({ length: 5 }, (_, i) => (
              <div key={i} className="mat-inv__skeletonrow" />
            ))}
          </div>
        ) : sparesError ? (
          <EmptyState
            title="Spare shelf unavailable"
            detail={`The inventory endpoint did not return a result (${sparesError}). No shelf is shown rather than a fabricated one.`}
          />
        ) : grouped.length === 0 ? (
          <EmptyState title="No maintenance spares in the register" detail="The engine returned no MAINTENANCE_SPARE positions." />
        ) : (
          <div className="mat-shelf">
            {grouped.map((group) => (
              <section className="mat-shelf__group" key={group.id} data-spare-group={group.id}>
                <header className="mat-shelf__head">
                  <span className={`mat-shelf__mark mat-shelf__mark--${group.id}`} aria-hidden="true" />
                  <h3 className="mat-shelf__title">{group.label}</h3>
                  <span className="mat-shelf__count">{group.items.length}</span>
                  <span className="mat-shelf__detail">{group.detail}</span>
                </header>
                <div className="mat-shelf__rows">
                  {group.items.map((position) => (
                    <SpareShelfRow
                      key={position.material_id}
                      position={position}
                      detail={details[position.material_id]}
                      selected={(details[position.material_id]?.required_by ?? []).some(
                        (r) => r.equipment_id === selectedEquipmentId,
                      )}
                      onPickAsset={(id) => {
                        selectAsset(id);
                        document
                          .querySelector<HTMLElement>('[data-testid="material-coverage-workbench"]')
                          ?.scrollIntoView({ behavior: "smooth", block: "start" });
                      }}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </MaterialPanel>
    </>
  );
}
