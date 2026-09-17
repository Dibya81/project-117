"use client";

/**
 * Material Detail — the full dossier for one material: what is in the tank or
 * on the shelf, what the forecast says, where it has moved, what it cost, which
 * plant assets depend on it, and how it sits in the industrial graph.
 *
 * The whole page is a renderer. Available stock, days of cover, the depletion
 * date, the price change and the coverage verdict are all computed by the
 * materials service; where the service reports `INSUFFICIENT_HISTORY` the page
 * prints the service's own limitation instead of a value, because a blank or a
 * zero would read as a measurement. `available = quantity − reserved` is shown
 * as the backend's `calculation_basis` through `ProvenanceLine` rather than as
 * arithmetic performed here.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  CoverageChip,
  EmptyState,
  Figure,
  LimitationNote,
  MaterialPanel,
  MaterialsHeader,
  Money,
  MovementBadge,
  MovementChip,
  ProvenanceLine,
  StatusChip,
  SyntheticDemoBadge,
  statusTone,
} from "@/components/materials/MaterialsKit";
import { Lucide } from "@/components/ui/LucideIcon";
import { SkeletonRows } from "@/components/ui/primitives";
import { consoleData } from "@/lib/data/console";
import type {
  GraphEdgeRecord,
  GraphNodeRecord,
  MaterialDetailEnvelope,
  PricePointRecord,
} from "@/lib/api";

type Detail = MaterialDetailEnvelope;

const CLASS_LABELS: Record<string, string> = {
  RAW_MATERIAL: "Raw material",
  INTERMEDIATE: "Intermediate",
  FINISHED_PRODUCT: "Finished product",
  MAINTENANCE_SPARE: "Maintenance spare",
};

function classLabel(value: string | null | undefined): string {
  if (!value) return "—";
  return CLASS_LABELS[value] ?? value;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Locale-independent so the server and the browser render identical markup. */
function fmtTs(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getUTCDate())} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())} UTC`;
}

function fmtDay(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${String(d.getUTCDate()).padStart(2, "0")} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

function Text({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="mat-empty">—</span>;
  return <>{value}</>;
}

/** One labelled figure. The value is whatever the service returned. */
function Fig({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="mat-fig">
      <span className="mat-fig__k">{k}</span>
      <span className="mat-fig__v">{children}</span>
    </div>
  );
}

/** A change can be negative, so the sign is part of the display, not the datum. */
function Signed({ value, unit }: { value: number | null | undefined; unit?: string | null }) {
  if (value === null || value === undefined) return <span className="mat-empty">—</span>;
  return (
    <>
      {value > 0 ? "+" : ""}
      <Figure value={value} unit={unit} />
    </>
  );
}

/**
 * The price series as a shape. Scaling to the window's own min/max is
 * presentation only — no figure on the chart is recomputed, and the axes are
 * deliberately unlabelled so the strip cannot be read as a measurement.
 */
function Sparkline({ points }: { points: PricePointRecord[] }) {
  if (points.length < 2) return null;
  const values = points.map((p) => p.price);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const W = 320;
  const H = 56;
  const pad = 7;
  const x = (i: number) => pad + (i / (points.length - 1)) * (W - pad * 2);
  const y = (v: number) => H - pad - ((v - min) / span) * (H - pad * 2);
  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.price).toFixed(1)}`).join(" ");
  const area = `${line} L${x(points.length - 1).toFixed(1)},${H} L${x(0).toFixed(1)},${H} Z`;
  return (
    <svg
      className="mat-spark"
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={`Price series, ${points.length} recorded points`}
    >
      <path d={area} fill="rgba(8,145,178,0.09)" stroke="none" />
      <path d={line} fill="none" stroke="#0891b2" strokeWidth={1.4} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/** relation → the sentence a reader needs. The raw relation is always shown too. */
const RELATION_ORDER = ["REQUIRES", "STOCKED_AT", "SUPPLIED_BY", "FLOWS_TO", "PRODUCES"];
const RELATION_GLOSS: Record<string, string> = {
  REQUIRES: "plant assets that require this material",
  STOCKED_AT: "storage locations holding this material",
  SUPPLIED_BY: "suppliers recorded for this material",
  FLOWS_TO: "downstream units this material feeds",
  PRODUCES: "upstream units that produce this material",
};

function edgeExtras(edge: GraphEdgeRecord): string[] {
  const out: string[] = [];
  if (typeof edge.quantity === "number") {
    out.push(`${edge.quantity}${edge.unit ? ` ${edge.unit}` : ""}`);
  } else if (typeof edge.unit === "string") {
    out.push(edge.unit);
  }
  if (typeof edge.schedule === "string" && edge.schedule) out.push(edge.schedule);
  if (typeof edge.failure_mode === "string" && edge.failure_mode) out.push(`failure mode ${edge.failure_mode}`);
  return out;
}

function nodeExtras(node: GraphNodeRecord | undefined): string[] {
  if (!node) return [];
  const out: string[] = [];
  if (typeof node.status === "string" && node.status) out.push(node.status);
  if (typeof node.lead_time_days === "number") out.push(`${node.lead_time_days} day lead time`);
  if (typeof node.location === "string" && node.location) out.push(node.location);
  return out;
}

export default function MaterialDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ? decodeURIComponent(params.id) : "";
  const [data, setData] = useState<Detail | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    setData(undefined);
    consoleData.materials
      .detail(id)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (data === undefined) {
    return (
      <>
        <MaterialsHeader kicker="Industrial materials" title={id || "Material"} />
        <MaterialPanel title="Material record">
          <SkeletonRows rows={6} label="Reading the material record…" />
        </MaterialPanel>
      </>
    );
  }

  if (data === null) {
    return (
      <>
        <MaterialsHeader kicker="Industrial materials" title={id || "Material"} />
        <MaterialPanel title="Material record">
          <EmptyState
            title={`“${id}” is not in the register`}
            detail="The materials service returned 404 for this id. It may have been renamed or removed from the catalogue."
          />
        </MaterialPanel>
      </>
    );
  }

  const mat = data.material;
  const inv = data.inventory ?? {};
  const forecast = data.forecast ?? {};
  const price = data.price_history ?? {};
  const movements = data.movements ?? [];
  const requiredBy = data.required_by ?? [];
  const upcoming = data.upcoming_requirements ?? [];
  const graph = data.graph;

  const nodeById: Record<string, GraphNodeRecord> = Object.fromEntries(
    (graph?.nodes ?? []).map((n) => [n.id, n]),
  );
  const edgesByRelation = new Map<string, GraphEdgeRecord[]>();
  for (const e of graph?.edges ?? []) {
    const list = edgesByRelation.get(e.relation) ?? [];
    list.push(e);
    edgesByRelation.set(e.relation, list);
  }
  const relations = Array.from(edgesByRelation.keys()).sort((a, b) => {
    const ia = RELATION_ORDER.indexOf(a);
    const ib = RELATION_ORDER.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });

  const forecastStatus = (forecast.status ?? "").toUpperCase();
  const insufficient = forecastStatus === "INSUFFICIENT_HISTORY";
  const invUnit = inv.unit ?? mat.unit;
  const priceUnit = price.current?.unit ?? null;
  const movementWindow = movements.slice(0, 14);

  return (
    <>
      <MaterialsHeader
        kicker="Industrial materials"
        title={mat.name}
        lede={mat.description || undefined}
        actions={
          <Link className="cs-btn cs-btn--ghost" href="/console/materials/register">
            <Lucide name="database" size={12} /> Register
          </Link>
        }
      />

      {/* ---------------------------------------------------------- header */}
      <MaterialPanel
        title="Material record"
        actions={
          <>
            <span className="mat-chip">{data.class_label ? classLabel(data.class_label) : "—"}</span>
            <StatusChip label={mat.status} tone={statusTone(mat.status)} />
            <SyntheticDemoBadge />
          </>
        }
      >
        <div className="mat-hero__id">{mat.id}</div>
        <h2 className="mat-hero__name">{mat.name}</h2>
        {mat.description ? <p className="mat-hero__desc">{mat.description}</p> : null}
        <div className="mat-hero__grid">
          <Fig k="Class label">
            <span className="font-mono text-[12px] tracking-[0.06em]">{data.class_label || "—"}</span>
          </Fig>
          <Fig k="Current quantity">
            <Figure value={inv.quantity ?? null} unit={invUnit} />
          </Fig>
          <Fig k="Location">
            <Text value={mat.location} />
          </Fig>
          <Fig k="Status">
            <StatusChip label={mat.status} tone={statusTone(mat.status)} />
          </Fig>
          <Fig k="Record updated">{fmtDay(mat.updated_at)}</Fig>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {mat.supplier_id ? (
            <span className="mat-chip">
              supplier <b>{mat.supplier_id}</b>
            </span>
          ) : null}
          {mat.cost_basis ? (
            <span className="mat-chip">
              cost basis <b>{mat.cost_basis}</b>
            </span>
          ) : null}
          {mat.source_process_unit ? (
            <span className="mat-chip">
              from <b>{mat.source_process_unit}</b>
            </span>
          ) : null}
          {mat.destination_process_unit ? (
            <span className="mat-chip">
              to <b>{mat.destination_process_unit}</b>
            </span>
          ) : null}
        </div>
        {Object.keys(mat.quality_attributes ?? {}).length > 0 ? (
          <div className="mt-3">
            <div className="mat-fig__k mb-1.5">Quality attributes</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(mat.quality_attributes).map(([k, v]) => (
                <span key={k} className="mat-chip">
                  {k.replace(/_/g, " ")} <b>{typeof v === "object" ? JSON.stringify(v) : String(v)}</b>
                </span>
              ))}
            </div>
          </div>
        ) : null}
      </MaterialPanel>

      {/* ------------------------------------------------------- inventory */}
      <div className="mat-section">
        <MaterialPanel
          title="Inventory"
          subtitle={inv.timestamp ? `Position at ${fmtTs(inv.timestamp)}` : undefined}
          actions={<StatusChip label={inv.status ?? "UNKNOWN"} tone={statusTone(inv.status)} />}
        >
          <div className="mat-figs">
            <Fig k="Quantity">
              <Figure value={inv.quantity ?? null} unit={invUnit} />
            </Fig>
            <Fig k="Available">
              <Figure value={inv.available ?? null} unit={invUnit} />
            </Fig>
            <Fig k="Reserved">
              <Figure value={inv.reserved ?? null} unit={invUnit} />
            </Fig>
            <Fig k="Safety stock">
              <Figure value={inv.safety_stock ?? null} unit={invUnit} />
            </Fig>
            <Fig k="Reorder level">
              <Figure value={inv.reorder_level ?? null} unit={invUnit} />
            </Fig>
            <Fig k="Days of cover">
              {inv.days_of_cover === null || inv.days_of_cover === undefined ? (
                <span className="text-[12px] text-slate-400">not computable</span>
              ) : (
                <Figure value={inv.days_of_cover} unit="d" />
              )}
            </Fig>
            <Fig k="Threshold status">
              <StatusChip label={inv.status ?? "UNKNOWN"} tone={statusTone(inv.status)} />
            </Fig>
          </div>

          <div className="mt-3.5">
            <div className="mat-fig__k mb-1.5">Calculation basis</div>
            <ProvenanceLine
              provenance={inv.provenance}
              calculationStatus={inv.data_status ?? "UNKNOWN"}
              basis={inv.calculation_basis}
            />
          </div>

          {(inv.limitations?.length ?? 0) > 0 ? (
            <div className="mt-3">
              <LimitationNote limitations={inv.limitations} />
            </div>
          ) : null}
        </MaterialPanel>
      </div>

      {/* -------------------------------------------------------- forecast */}
      <div className="mat-section">
        <MaterialPanel
          title="Forecast"
          subtitle={
            insufficient
              ? "The service could not project a depletion date"
              : forecast.window_days
                ? `${forecast.window_days}-day consumption window · ${forecast.samples ?? "—"} sample days`
                : undefined
          }
        >
          {insufficient ? (
            <>
              <div className="mat-callout mb-2.5">
                Forecast status <b className="font-mono">{forecastStatus}</b> — no depletion date is projected, so none is shown.
              </div>
              {(forecast.limitations?.length ?? 0) > 0 ? (
                <LimitationNote limitations={forecast.limitations} />
              ) : null}
            </>
          ) : (
            <>
              <div className="mat-figs">
                <Fig k="Projected depletion">
                  {forecast.projected_depletion_date ? (
                    <>
                      {fmtDay(forecast.projected_depletion_date)}
                      {forecast.days_to_depletion !== null && forecast.days_to_depletion !== undefined ? (
                        <span className="ml-1.5 text-[11px] text-slate-400">
                          in <Figure value={forecast.days_to_depletion} unit="d" />
                        </span>
                      ) : null}
                    </>
                  ) : (
                    <span className="mat-empty">not projected</span>
                  )}
                </Fig>
                <Fig k="Safety-stock crossing">
                  {forecast.projected_safety_stock_crossing_date ? (
                    <>
                      {fmtDay(forecast.projected_safety_stock_crossing_date)}
                      {forecast.days_to_safety_stock !== null && forecast.days_to_safety_stock !== undefined ? (
                        <span className="ml-1.5 text-[11px] text-slate-400">
                          in <Figure value={forecast.days_to_safety_stock} unit="d" />
                        </span>
                      ) : null}
                    </>
                  ) : (
                    <span className="mat-empty">not projected</span>
                  )}
                </Fig>
                <Fig k="Mean daily consumption">
                  <Figure value={forecast.mean_daily_consumption ?? null} unit={forecast.unit ?? invUnit} />
                </Fig>
                <Fig k="Consumption σ">
                  <Figure value={forecast.stdev_daily_consumption ?? null} unit={forecast.unit ?? invUnit} />
                </Fig>
                <Fig k="Coefficient of variation">
                  <Figure value={forecast.coefficient_of_variation ?? null} />
                </Fig>
                <Fig k="Samples">
                  <Figure value={forecast.samples ?? null} unit={forecast.window_days ? `days / ${forecast.window_days}d` : "days"} />
                </Fig>
              </div>

              <div className="mt-3.5 flex flex-wrap items-center gap-3">
                <StatusChip
                  label={forecast.confidence ?? "NO CONFIDENCE REPORTED"}
                  tone={statusTone(forecast.confidence)}
                />
                <span className="text-[11px] leading-relaxed text-slate-500">
                  {forecast.confidence_basis ?? "The service returned no confidence basis."}
                </span>
              </div>

              {(forecast.limitations?.length ?? 0) > 0 ? (
                <div className="mt-3">
                  <LimitationNote limitations={forecast.limitations} />
                </div>
              ) : null}
            </>
          )}
        </MaterialPanel>
      </div>

      {/* ------------------------------------------------ movement history */}
      <div className="mat-section">
        <MaterialPanel
          title="Movement history"
          subtitle={
            movements.length === 0
              ? "No movements recorded"
              : movements.length > movementWindow.length
                ? `latest ${movementWindow.length} of ${movements.length} postings`
                : `${movements.length} postings`
          }
        >
          {movements.length === 0 ? (
            <EmptyState
              title="No movements recorded"
              detail="The service returned no receipts, consumption, transfers or dispatches for this material."
            />
          ) : (
            <div className="mat-list">
              {movementWindow.map((m) => (
                <div key={m.id} className="mat-move">
                  <MovementChip type={m.movement_type} />
                  <div className="mat-row__main">
                    <div className="font-mono text-[11px] text-slate-600">{m.reference}</div>
                    <div className="mat-move__path">
                      {m.source_location} → {m.destination_location}
                    </div>
                  </div>
                  <div className="mat-fig mat-fig--plain mat-fig--right">
                    <span className="mat-fig__v">
                      <Figure value={m.quantity} unit={m.unit} />
                    </span>
                    <span className="mat-fig__k">{fmtTs(m.timestamp)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </MaterialPanel>
      </div>

      {/* --------------------------------------------------- price history */}
      <div className="mat-section">
        <MaterialPanel
          title="Price history"
          subtitle={price.window_days ? `${price.window_days}-day window` : undefined}
          actions={<MovementBadge movement={price.movement} />}
        >
          {!price.current ? (
            <EmptyState
              title="No price recorded"
              detail="The service returned no current price for this material, so no change is shown."
            />
          ) : (
            <>
              <div className="mat-figs">
                <Fig k="Current price">
                  <Money amount={price.current.price} />
                  <span className="ml-1.5 font-mono text-[10.5px] text-slate-400">{priceUnit}</span>
                </Fig>
                <Fig k="Baseline">
                  {price.baseline ? (
                    <>
                      <Money amount={price.baseline.price} />
                      <span className="ml-1.5 font-mono text-[10.5px] text-slate-400">
                        {price.baseline.unit} · {fmtDay(price.baseline.observed_on)}
                      </span>
                    </>
                  ) : (
                    <span className="mat-empty">—</span>
                  )}
                </Fig>
                <Fig k="Change (absolute)">
                  <Signed value={price.change_absolute} unit={priceUnit} />
                </Fig>
                <Fig k="Change (percent)">
                  <Signed value={price.change_percent} unit="%" />
                </Fig>
                <Fig k="Recorded points">
                  <Figure value={price.points ?? null} />
                  {price.series?.length ? (
                    <span className="ml-1.5 text-[11px] text-slate-400">{price.series.length} in series</span>
                  ) : null}
                </Fig>
                <Fig k="Data status">
                  <span className="font-mono text-[11px]">{price.data_status ?? "—"}</span>
                </Fig>
              </div>

              <Sparkline points={price.series ?? []} />

              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-slate-500">
                {price.source ? (
                  <span>
                    Source <span className="font-mono text-slate-600">{price.source}</span>
                  </span>
                ) : null}
                {price.last_updated ? <span>Last updated {fmtDay(price.last_updated)}</span> : null}
                {price.thresholds ? (
                  <span className="font-mono">
                    movement thresholds ±{price.thresholds.warning_pct}% warning / ±{price.thresholds.abnormal_pct}% abnormal
                  </span>
                ) : null}
                {price.calculation_basis?.formula ? (
                  <span className="font-mono">basis {String(price.calculation_basis.formula)}</span>
                ) : null}
                {price.series?.length ? <span>Strip scaled to the window&rsquo;s own range — shape only.</span> : null}
              </div>

              {(price.limitations?.length ?? 0) > 0 ? (
                <div className="mt-3">
                  <LimitationNote limitations={price.limitations} />
                </div>
              ) : null}
            </>
          )}
        </MaterialPanel>
      </div>

      {/* ------------------------------- related equipment + requirements */}
      <div className="mat-cols mat-cols--even">
        <MaterialPanel
          title="Related equipment"
          subtitle={`${requiredBy.length} plant asset${requiredBy.length === 1 ? "" : "s"} require this material`}
        >
          {requiredBy.length === 0 ? (
            <EmptyState
              title="No plant asset requires this material"
              detail="No spare definition or equipment requirement in the register references it."
            />
          ) : (
            <div className="mat-list">
              {requiredBy.map((r) => (
                <div key={r.requirement_id} className="mat-row">
                  <div className="mat-row__main">
                    <div className="mat-row__title">
                      <Link className="mat-link font-mono text-[11.5px]" href={`/console/equipment/${r.equipment_id}`}>
                        {r.equipment_id}
                      </Link>
                      <span className="ml-2">
                        <Figure value={r.quantity} unit={r.unit} />
                      </span>
                    </div>
                    <div className="mat-row__sub">
                      {r.purpose}
                      {r.schedule ? ` · ${r.schedule}` : ""}
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {r.failure_mode ? (
                        <span className="mat-chip">
                          failure mode <b>{r.failure_mode}</b>
                        </span>
                      ) : null}
                      <span className="mat-chip">
                        requirement <b>{r.requirement_id}</b>
                      </span>
                    </div>
                  </div>
                  <Lucide name="arrow" size={13} className="text-slate-300" />
                </div>
              ))}
            </div>
          )}
        </MaterialPanel>

        <MaterialPanel
          title="Upcoming requirements"
          subtitle="Required against available and safety stock"
        >
          {upcoming.length === 0 ? (
            <EmptyState
              title="No upcoming requirement"
              detail="The service returned no scheduled demand for this material."
            />
          ) : (
            <div className="mat-list">
              {upcoming.map((u, i) => (
                <div key={`${u.equipment_id}-${i}`} className="mat-row">
                  <div className="mat-row__main">
                    <div className="mat-row__title">
                      <Link className="mat-link font-mono text-[11.5px]" href={`/console/equipment/${u.equipment_id}`}>
                        {u.equipment_id}
                      </Link>
                    </div>
                    <div className="mat-row__sub">
                      {u.purpose}
                      {u.schedule ? ` · ${u.schedule}` : ""}
                    </div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      <span className="mat-chip">
                        required{" "}
                        <b>
                          {u.required_quantity} {u.unit}
                        </b>
                      </span>
                      <span className="mat-chip">
                        available <b>{u.available ?? "—"}</b>
                      </span>
                      <span className="mat-chip">
                        safety <b>{u.safety_stock}</b>
                      </span>
                      <span className="mat-chip">
                        gap <b>{u.gap}</b>
                      </span>
                    </div>
                  </div>
                  <CoverageChip coverage={u.coverage} />
                </div>
              ))}
            </div>
          )}
        </MaterialPanel>
      </div>

      {/* ------------------------------------------- supplier + memory graph */}
      <div className="mat-cols mat-cols--even">
        <MaterialPanel title="Suppliers" subtitle="Recorded source for this material">
          {!data.supplier ? (
            <EmptyState
              title="No supplier recorded"
              detail="The materials service returned no supplier for this material, so no lead time is shown."
            />
          ) : (
            <>
              <div className="mat-hero__name" style={{ fontSize: 16 }}>
                {data.supplier.name}
              </div>
              <div className="mat-figs mt-3">
                <Fig k="Supplier id">
                  <span className="font-mono text-[12px]">{data.supplier.id}</span>
                </Fig>
                <Fig k="Lead time">
                  <Figure value={data.supplier.lead_time_days} unit="days" />
                </Fig>
                <Fig k="Status">
                  <StatusChip label={data.supplier.status} tone={statusTone(data.supplier.status)} />
                </Fig>
                <Fig k="Reference">
                  <Text value={data.supplier.reference} />
                </Fig>
                <Fig k="Contact">
                  <Text value={data.supplier.contact} />
                </Fig>
              </div>
              <div className="mt-3">
                <ProvenanceLine provenance={data.supplier.provenance} />
              </div>
            </>
          )}
        </MaterialPanel>

        <MaterialPanel
          title="Industrial memory"
          subtitle={
            graph
              ? `${graph.counts?.nodes ?? 0} nodes · ${graph.counts?.edges ?? 0} relationships`
              : "No graph returned"
          }
        >
          {relations.length === 0 ? (
            <EmptyState
              title="No relationships recorded"
              detail="The industrial graph holds no node or edge for this material yet. The full canvas lives on the Knowledge page."
            />
          ) : (
            <div>
              {relations.map((relation) => (
                <div key={relation} className="mat-memory__group">
                  <div className="mat-memory__label">
                    {relation} · {edgesByRelation.get(relation)?.length ?? 0}
                  </div>
                  <div className="mat-list">
                    {(edgesByRelation.get(relation) ?? []).map((e, i) => {
                      const otherId = e.source === mat.id ? e.target : e.source;
                      const other = nodeById[otherId];
                      const isEquipment = (other?.kind ?? "").toUpperCase() === "EQUIPMENT";
                      const extras = [...edgeExtras(e), ...nodeExtras(other)];
                      return (
                        <div key={`${relation}-${otherId}-${i}`} className="mat-row">
                          <div className="mat-row__main">
                            <div className="mat-row__title">
                              {isEquipment ? (
                                <Link className="mat-link font-mono text-[11.5px]" href={`/console/equipment/${otherId}`}>
                                  {other?.label ?? otherId}
                                </Link>
                              ) : (
                                <span>{other?.label ?? otherId}</span>
                              )}
                              <span className="ml-2 font-mono text-[10px] text-slate-400">{otherId}</span>
                            </div>
                            <div className="mat-row__sub">{RELATION_GLOSS[relation] ?? "recorded relationship"}</div>
                            {extras.length > 0 ? (
                              <div className="mt-1.5 flex flex-wrap gap-1.5">
                                {extras.map((x, j) => (
                                  <span key={`${x}-${j}`} className="mat-chip">
                                    {x}
                                  </span>
                                ))}
                              </div>
                            ) : null}
                          </div>
                          {other?.kind ? <span className="mat-chip">{other.kind}</span> : null}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
          <p className="mt-3 text-[10.5px] leading-relaxed text-slate-400">
            The scoped graph for this material, read as a list. The full plant canvas is on{" "}
            <Link className="mat-link" href="/console/knowledge">
              Knowledge
            </Link>
            .
          </p>
        </MaterialPanel>
      </div>

      <div className="mat-foot">
        <span>Material record updated {fmtTs(mat.updated_at)}</span>
        <span className="mat-chip">
          data status <b>{data.data_status ?? "—"}</b>
        </span>
        <span>
          Available stock, cover, forecast and coverage are the materials service&rsquo;s own figures; this page performs no
          conversion or arithmetic.
        </span>
      </div>
    </>
  );
}
