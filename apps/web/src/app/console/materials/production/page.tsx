"use client";

/**
 * Materials — Production (/console/materials/production)
 *
 * Output quantity per period, aggregated by the backend from the daily
 * production rows. Nothing here is computed in the browser:
 *
 *  * `buckets[]`, `latest`, `previous`, `change_percent` and `trend` are the
 *    domain service's values, rendered verbatim.
 *  * The 7D/30D/90D/1Y control filters the bucket array it already fetched for
 *    display. That is array filtering, not aggregation.
 *  * A period still in progress is never presented as a full one. The backend
 *    flags the latest bucket (`latest.partial`) and returns the in-progress
 *    bucket without using it as a comparison baseline; the summary says "period
 *    to date" and the chart draws the in-progress tail dashed so the partial
 *    bucket cannot read as a real drop.
 *
 * No buckets and no limitation-free answer means an explicit empty state, never
 * a line drawn through numbers that were not measured.
 */
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import {
  EmptyState,
  Figure,
  LimitationNote,
  MaterialPanel,
  MaterialsHeader,
  ProvenanceLine,
  StatusChip,
  statusTone,
} from "@/components/materials/MaterialsKit";
import { MaterialMetric } from "@/components/materials/MaterialMetric";
import { MaterialSegmented } from "@/components/materials/MaterialSegmented";
import type { ProductionPoint } from "@/components/materials/MaterialCharts";
import { consoleData } from "@/lib/data/console";
import type { MaterialRecord, ProductionBucketRecord, ProductionSeriesRecord } from "@/lib/api";

type PeriodId = "DAILY" | "WEEKLY" | "MONTHLY";
type RangeId = "7D" | "30D" | "90D" | "1Y";

const PERIODS: { id: PeriodId; label: string }[] = [
  { id: "DAILY", label: "Daily" },
  { id: "WEEKLY", label: "Weekly" },
  { id: "MONTHLY", label: "Monthly" },
];

const RANGES: { id: RangeId; label: string; days: number }[] = [
  { id: "7D", label: "7D", days: 7 },
  { id: "30D", label: "30D", days: 30 },
  { id: "90D", label: "90D", days: 90 },
  { id: "1Y", label: "1Y", days: 365 },
];

/** The three finished products this view offers, as real catalogue ids. */
const PRODUCT_IDS = ["FP-MOTOR-SPIRIT", "FP-DIESEL", "FP-ATF"] as const;

const DAY_MS = 86_400_000;

function shortDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

function bucketRange(start: string, end: string): string {
  return start === end ? shortDate(start) : `${shortDate(start)} → ${shortDate(end)}`;
}

/** Milliseconds for an ISO date, read as UTC so the window cannot shift a day. */
function isoMs(iso: string): number {
  const d = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? NaN : d.getTime();
}

function trendTone(trend: string | null | undefined) {
  if (trend === "INCREASING") return "ok" as const;
  if (trend === "DECREASING") return "warn" as const;
  return "muted" as const;
}

/** Recharts is ~400 kB; split from the route's first load (see price-history). */
const ProductionChart = dynamic(
  () => import("@/components/materials/MaterialCharts").then((m) => m.ProductionChart),
  { ssr: false, loading: () => <div className="mat-chart-pending" aria-hidden="true" /> },
);

export default function ProductionPage() {
  const [period, setPeriod] = useState<PeriodId>("DAILY");
  const [productId, setProductId] = useState<string>("");
  const [range, setRange] = useState<RangeId>("30D");
  const [series, setSeries] = useState<ProductionSeriesRecord | null>(null);
  const [catalogue, setCatalogue] = useState<MaterialRecord[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Product display names come from the catalogue, never from a hardcoded label.
  useEffect(() => {
    let alive = true;
    consoleData.materials
      .list({ limit: 200 })
      .then((r) => {
        if (alive) setCatalogue(r.items);
      })
      .catch(() => {
        if (alive) setCatalogue([]);
      });
    return () => {
      alive = false;
    };
  }, []);

  // The requested series is the server's: period and product both change the
  // aggregation, so both refetch. The client-side range control does not.
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    consoleData.materials
      .production({ period, productId: productId || undefined })
      .then((d) => {
        if (!alive) return;
        setSeries(d);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (!alive) return;
        setSeries(null);
        setError(err instanceof Error ? err.message : "the production endpoint did not answer");
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [period, productId]);

  const buckets: ProductionBucketRecord[] = useMemo(() => series?.buckets ?? [], [series]);
  const latest = series?.latest;
  const previous = series?.previous ?? null;
  const latestPartial = latest?.partial === true;

  // The window is anchored to the latest complete period the backend reported,
  // so a 7D view still contains comparable periods at coarser granularities.
  const anchor = latest?.period_end ?? buckets[buckets.length - 1]?.period_end ?? null;
  const windowDays = RANGES.find((r) => r.id === range)?.days ?? 30;
  const anchorMs = anchor ? isoMs(anchor) : NaN;

  const windowed = useMemo(() => {
    if (!Number.isFinite(anchorMs)) return buckets;
    const cutoff = anchorMs - (windowDays - 1) * DAY_MS;
    return buckets.filter((b) => {
      const ms = isoMs(b.period_end);
      return Number.isFinite(ms) && ms >= cutoff;
    });
  }, [buckets, anchorMs, windowDays]);

  // Buckets the backend returned after the latest complete period are still in
  // progress. This is the backend's own rule (period_end > latest.period_end),
  // not a recomputation of any quantity.
  const inProgress = useMemo(
    () => (latest?.period_end ? buckets.filter((b) => b.period_end > latest.period_end) : []),
    [buckets, latest],
  );

  const chartPoints: ProductionPoint[] = useMemo(() => {
    const latestEnd = latest?.period_end;
    const isPartialAt = (i: number) =>
      Boolean(latestEnd && windowed[i] && windowed[i].period_end > latestEnd);
    return windowed.map((b, i) => {
      const partial = isPartialAt(i);
      return {
        label: b.period_start === b.period_end ? b.period_start : `${b.period_start} → ${b.period_end}`,
        complete: partial ? null : b.quantity,
        // Carry the last complete bucket's value so the dashed tail connects.
        partialValue: partial ? b.quantity : isPartialAt(i + 1) ? b.quantity : null,
      };
    });
  }, [windowed, latest]);

  const productOptions = useMemo(
    () => [
      { id: "", label: "All products", title: "No product filter" },
      ...PRODUCT_IDS.map((id) => {
        const match = catalogue?.find((m) => m.id === id);
        return { id, label: match?.name ?? id, title: `${id}${match ? ` — ${match.name}` : ""}` };
      }),
    ],
    [catalogue],
  );

  const noBuckets = !loading && !error && buckets.length === 0;
  const windowLabel = RANGES.find((r) => r.id === range)?.label ?? range;

  return (
    <>
      <MaterialsHeader
        kicker="Materials"
        title="Production"
        lede="Finished-product output per period, aggregated by the materials service from the recorded daily production rows. Period-over-period change is computed by the backend against complete periods only."
      />

      <MaterialPanel
        title="View"
        subtitle="period and product refetch from the backend · window filters the returned buckets"
        className="mb-4"
      >
        <div className="flex flex-wrap items-start gap-x-8 gap-y-4">
          <div className="flex flex-col gap-1.5">
            <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
              Product
            </span>
            <MaterialSegmented
              ariaLabel="Production product filter"
              layoutId="mat-production-product"
              options={productOptions}
              value={productId}
              onChange={setProductId}
              testId="production-product-filter"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
              Period
            </span>
            <MaterialSegmented
              ariaLabel="Production period"
              layoutId="mat-production-period"
              options={PERIODS}
              value={period}
              onChange={(id) => setPeriod(id as PeriodId)}
              testId="production-period"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
              Window
            </span>
            <MaterialSegmented
              ariaLabel="Production time range"
              layoutId="mat-production-range"
              options={RANGES}
              value={range}
              onChange={(id) => setRange(id as RangeId)}
              testId="production-range"
            />
          </div>
        </div>
      </MaterialPanel>

      {error ? (
        <MaterialPanel title="Production series">
          <EmptyState
            title="The production series could not be read"
            detail={`${error}. No figures are shown, because none were received.`}
          />
        </MaterialPanel>
      ) : loading ? (
        <MaterialPanel title="Production series">
          <p className="m-0 text-[12.5px] text-slate-500">Reading production series…</p>
        </MaterialPanel>
      ) : noBuckets ? (
        <MaterialPanel title="Production series">
          <EmptyState
            title="No production recorded for this filter"
            detail={
              series?.limitations?.[0]?.message ??
              "The backend returned no buckets, so there is nothing to plot and no trend to report."
            }
          />
        </MaterialPanel>
      ) : (
        <>
          <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MaterialMetric
              testId="production-latest"
              label={latestPartial ? "Period to date" : "Latest complete period"}
              tone={latestPartial ? "text-amber-700" : "text-slate-900"}
              value={<Figure value={latest?.quantity} unit={series?.unit} />}
              badge={
                latestPartial ? <StatusChip label="Partial" tone="warn" /> : undefined
              }
              sub={
                latest
                  ? `${bucketRange(latest.period_start, latest.period_end)}${
                      latestPartial ? " · excluded from the comparison" : ""
                    }`
                  : "—"
              }
            />
            <MaterialMetric
              testId="production-previous"
              label="Previous period"
              value={<Figure value={previous?.quantity} unit={series?.unit} />}
              sub={
                previous
                  ? bucketRange(previous.period_start, previous.period_end)
                  : "no earlier complete period was returned"
              }
            />
            <MaterialMetric
              testId="production-change"
              label="Change vs previous"
              value={
                series?.change_percent === null || series?.change_percent === undefined ? (
                  <Figure value={null} />
                ) : (
                  <span>
                    {series.change_percent > 0 ? "+" : ""}
                    <Figure value={series.change_percent} unit="%" />
                  </span>
                )
              }
              sub={
                series?.change_percent === null || series?.change_percent === undefined
                  ? "the backend reported no comparable previous period"
                  : "computed by the backend between complete periods"
              }
            />
            <MaterialMetric
              testId="production-trend"
              label="Trend"
              value={
                series?.trend ? (
                  <StatusChip label={series.trend} tone={trendTone(series.trend)} />
                ) : (
                  <Figure value={null} placeholder="—" />
                )
              }
              sub="direction reported by the backend's period-over-period comparison"
            />
          </div>

          {(latestPartial || inProgress.length > 0) && (
            <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3.5 py-3 text-[11.5px] leading-relaxed text-amber-800">
              <span className="font-semibold uppercase tracking-[0.12em]">
                {latestPartial ? "Period to date" : "Period in progress"}
              </span>
              <br />
              {latestPartial
                ? "The latest period is still open. The backend returns it but never uses it as a comparison baseline, so it is labelled period to date and no change is reported against it."
                : `${inProgress.length} returned bucket${
                    inProgress.length === 1 ? "" : "s"
                  } after the latest complete period (${shortDate(
                    inProgress[inProgress.length - 1].period_end,
                  )}) ${inProgress.length === 1 ? "is" : "are"} still in progress. They are drawn dashed and are excluded from the backend's period-over-period comparison.`}
            </div>
          )}

          <MaterialPanel
            title={`${series?.period ?? period} output`}
            subtitle={`${windowLabel} window · ${windowed.length} bucket${
              windowed.length === 1 ? "" : "s"
            }${series?.unit ? ` · ${series.unit}` : ""}`}
            className="mb-4"
            testId="production-chart"
          >
            {windowed.length === 0 ? (
              <EmptyState
                title="No bucket falls inside this window"
                detail={`The backend returned ${buckets.length} bucket${
                  buckets.length === 1 ? "" : "s"
                }, but none ends inside the selected ${windowLabel} window. Widen the window or pick a coarser period.`}
              />
            ) : (
              <>
                <ProductionChart points={chartPoints} unit={series?.unit} />
                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-slate-500">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-1.5 w-3 rounded-full" style={{ background: "#0891b2" }} />
                    complete period
                  </span>
                  {inProgress.length > 0 && (
                    <span className="inline-flex items-center gap-1.5">
                      <span
                        className="h-1.5 w-3 rounded-full"
                        style={{ background: "#f59e0b" }}
                      />
                      period to date — excluded from the comparison
                    </span>
                  )}
                  {windowed.length === 1 && (
                    <span>
                      The window covers a single {series?.period ?? period} bucket, so the chart has
                      one point.
                    </span>
                  )}
                </div>
              </>
            )}
          </MaterialPanel>

          {series?.limitations?.length ? (
            <MaterialPanel title="Limitations" className="mb-4">
              <LimitationNote limitations={series.limitations} />
            </MaterialPanel>
          ) : null}

          <MaterialPanel title="Provenance">
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
              <span className="text-[10px] text-slate-500">
                Source{" "}
                <span className="font-mono text-slate-600">{series?.source ?? "not reported"}</span>
              </span>
              <span className="text-[10px] text-slate-500">
                Records{" "}
                <span className="font-mono text-slate-600">{series?.records ?? "—"}</span>
              </span>
              <span className="text-[10px] text-slate-500">
                Buckets returned{" "}
                <span className="font-mono text-slate-600">{buckets.length}</span>
              </span>
              {series?.data_status ? (
                <StatusChip label={series.data_status} tone={statusTone(series.data_status)} />
              ) : null}
            </div>
            <div className="mt-3 border-t border-slate-200/60 pt-3">
              <ProvenanceLine basis={series?.calculation_basis} />
            </div>
          </MaterialPanel>
        </>
      )}
    </>
  );
}
