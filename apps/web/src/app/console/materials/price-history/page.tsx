"use client";

/**
 * Materials — Price History (/console/materials/price-history)
 *
 * The append-only price series for one material, with the backend's own window
 * comparison. The page performs no price arithmetic at all: `change_absolute`,
 * `change_percent` and `movement` are rendered as returned, and the unit that
 * came with the price (`INR/EA`, `INR/MT`, `INR/KL`) is always shown next to it,
 * because a price without its basis is not a price.
 *
 * Every series in this deployment is generated demonstration data. The page
 * says so in words next to the figure — "Synthetic demonstration price — not a
 * market quotation." — so nothing here can be read as a market quote. When the
 * backend returns no points, or a `PRICE_HISTORY_UNAVAILABLE` limitation, the
 * page renders an empty state instead of a fabricated series.
 */
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import {
  EmptyState,
  Figure,
  LimitationNote,
  MaterialPanel,
  MaterialsHeader,
  MovementBadge,
  ProvenanceLine,
  StatusChip,
  SyntheticDemoBadge,
  statusTone,
} from "@/components/materials/MaterialsKit";
import { MaterialMetric } from "@/components/materials/MaterialMetric";
import { MaterialSegmented } from "@/components/materials/MaterialSegmented";
/**
 * Recharts is ~400 kB. These pages exist to show a chart, so it cannot be
 * deferred past the point of usefulness — but it does not have to be in the
 * route's *first* load. Splitting it means the page shell, the KPI figures and
 * the provenance strip paint immediately and the plot arrives with its own
 * chunk, rather than the whole route blocking on the charting library.
 */
const PriceChart = dynamic(() => import("@/components/materials/MaterialCharts").then((m) => m.PriceChart), {
  ssr: false,
  loading: () => <div className="mat-chart-pending" aria-hidden="true" />,
});
import { consoleData } from "@/lib/data/console";
import { ApiError } from "@/lib/api";
import type { MaterialRecord, PriceHistoryRecord } from "@/lib/api";

type WindowId = "7D" | "30D" | "90D" | "1Y";

const WINDOWS: { id: WindowId; label: string; days: number }[] = [
  { id: "7D", label: "7D", days: 7 },
  { id: "30D", label: "30D", days: 30 },
  { id: "90D", label: "90D", days: 90 },
  { id: "1Y", label: "1Y", days: 365 },
];

const DEFAULT_ITEM = "RM-CRUDE-LIGHT";

const SYNTHETIC_WORDING = "Synthetic demonstration price — not a market quotation.";

function isDemoStatus(status: string | undefined | null): boolean {
  const value = (status ?? "").toUpperCase();
  return value === "SYNTHETIC_DEMO" || value === "MANUAL";
}

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

export default function PriceHistoryPage() {
  const [itemId, setItemId] = useState<string>(DEFAULT_ITEM);
  const [windowId, setWindowId] = useState<WindowId>("30D");
  const [query, setQuery] = useState("");
  const [catalogue, setCatalogue] = useState<MaterialRecord[] | null>(null);
  const [data, setData] = useState<PriceHistoryRecord | null>(null);
  const [error, setError] = useState<{ code?: string; message: string } | null>(null);
  const [loading, setLoading] = useState(true);

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

  useEffect(() => {
    let alive = true;
    const days = WINDOWS.find((w) => w.id === windowId)?.days ?? 30;
    setLoading(true);
    setError(null);
    consoleData.materials
      .priceHistory(itemId, days)
      .then((d) => {
        if (!alive) return;
        setData(d);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (!alive) return;
        setData(null);
        setError({
          code: err instanceof ApiError ? err.code : undefined,
          message: err instanceof Error ? err.message : "the price-history endpoint did not answer",
        });
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [itemId, windowId]);

  const matches = useMemo(() => {
    const list = catalogue ?? [];
    const q = query.trim().toLowerCase();
    if (!q) return list;
    return list.filter(
      (m) => m.name.toLowerCase().includes(q) || m.id.toLowerCase().includes(q),
    );
  }, [catalogue, query]);

  const series = useMemo(() => data?.series ?? [], [data]);
  const current = data?.current;
  const baseline = data?.baseline;
  const unavailable = data?.limitations?.find((l) => l.code === "PRICE_HISTORY_UNAVAILABLE");
  const noSeries = !loading && !error && (data === null || (data.points ?? 0) === 0 || series.length === 0);
  const demo = isDemoStatus(data?.data_status);
  const selectedName =
    data?.name ?? catalogue?.find((m) => m.id === itemId)?.name ?? "Price series";

  const chartPoints = useMemo(
    () => series.map((p) => ({ label: p.date, price: p.price })),
    [series],
  );

  return (
    <>
      <MaterialsHeader
        kicker="Materials"
        title="Price History"
        lede="The append-only price series for one material, with the backend's window comparison and movement flag. Prices are generated demonstration data; the page labels them as such wherever a figure appears."
      />

      <MaterialPanel
        title="Item"
        subtitle={`${catalogue?.length ?? "…"} materials in the catalogue · search by name or id`}
        className="mb-4"
      >
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="flex flex-col gap-1.5">
            <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
              Window
            </span>
            <div className="flex flex-wrap items-center gap-3">
              <MaterialSegmented
                ariaLabel="Price history window"
                layoutId="mat-price-window"
                options={WINDOWS}
                value={windowId}
                onChange={(id) => setWindowId(id as WindowId)}
                testId="price-window"
              />
              <span className="text-[11px] text-slate-500">
                Selected{" "}
                <span className="font-semibold text-slate-700">{selectedName}</span>{" "}
                <span className="font-mono text-[10px] text-slate-400">{itemId}</span>
              </span>
            </div>
            {demo && (
              <div className="mt-2 flex flex-wrap items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11.5px] font-semibold text-amber-800">
                <SyntheticDemoBadge />
                <span>{SYNTHETIC_WORDING}</span>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <label className="flex flex-col gap-1.5">
              <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                Find a material
              </span>
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search catalogue…"
                data-testid="price-item-search"
                className="w-full rounded-lg border border-slate-200/80 bg-white/80 px-3 py-2 text-[12px] text-slate-700 outline-none backdrop-blur-xl transition-colors placeholder:text-slate-400 focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/15"
              />
            </label>
            <div
              data-testid="price-item-list"
              className="max-h-44 overflow-y-auto rounded-lg border border-slate-200/60 bg-white/50 p-1 backdrop-blur-md"
            >
              {catalogue === null ? (
                <p className="m-0 px-2 py-1.5 text-[11px] text-slate-400">Loading catalogue…</p>
              ) : matches.length === 0 ? (
                <p className="m-0 px-2 py-1.5 text-[11px] text-slate-400">
                  No catalogue item matches “{query}”.
                </p>
              ) : (
                matches.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => setItemId(m.id)}
                    aria-pressed={m.id === itemId}
                    className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors ${
                      m.id === itemId ? "bg-cyan-500/10" : "hover:bg-slate-50/80"
                    }`}
                  >
                    <span className="min-w-0 flex-1 truncate text-[12px] text-slate-700">
                      {m.name}
                    </span>
                    <span className="shrink-0 font-mono text-[9.5px] text-slate-400">{m.id}</span>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      </MaterialPanel>

      {error ? (
        <MaterialPanel title="Price series">
          <EmptyState
            title={
              error.code === "PRICE_HISTORY_UNAVAILABLE"
                ? "No price history for this material"
                : "The price series could not be read"
            }
            detail={`${error.message}${
              error.code ? ` (${error.code})` : ""
            }. No series is drawn, because none was received.`}
          />
        </MaterialPanel>
      ) : loading ? (
        <MaterialPanel title="Price series">
          <p className="m-0 text-[12.5px] text-slate-500">Reading price history…</p>
        </MaterialPanel>
      ) : noSeries ? (
        <MaterialPanel title="Price series">
          <EmptyState
            title="No price points in this window"
            detail={
              unavailable?.message ??
              "The backend returned no price points for this material and window, so there is nothing to plot. A shorter window may be empty while a longer one is not."
            }
          />
          {data?.limitations?.length ? (
            <div className="mt-3">
              <LimitationNote limitations={data.limitations} />
            </div>
          ) : null}
        </MaterialPanel>
      ) : (
        <>
          <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            <MaterialMetric
              testId="price-current"
              label={`Current price · ${data?.window_days ?? windowId}`}
              tone={demo ? "text-amber-700" : "text-slate-900"}
              value={<Figure value={current?.price} unit={current?.unit} />}
              badge={demo ? <StatusChip label="Synthetic" tone="warn" /> : undefined}
              sub={
                current
                  ? `observed ${shortDate(current.observed_on)}${
                      demo ? ` · ${SYNTHETIC_WORDING}` : ""
                    }`
                  : "—"
              }
            />
            <MaterialMetric
              testId="price-baseline"
              label="Baseline"
              value={<Figure value={baseline?.price} unit={baseline?.unit} />}
              sub={baseline ? `observed ${shortDate(baseline.observed_on)}` : "—"}
            />
            <MaterialMetric
              testId="price-change-abs"
              label="Absolute change"
              value={
                <span>
                  {data?.change_absolute !== null && data?.change_absolute !== undefined && data.change_absolute > 0
                    ? "+"
                    : ""}
                  <Figure value={data?.change_absolute} unit={current?.unit} />
                </span>
              }
              sub="rendered exactly as the backend returned it"
            />
            <MaterialMetric
              testId="price-change-pct"
              label="Percentage change"
              value={
                <span>
                  {data?.change_percent !== null && data?.change_percent !== undefined && data.change_percent > 0
                    ? "+"
                    : ""}
                  <Figure value={data?.change_percent} unit="%" />
                </span>
              }
              sub={`backend basis: ${String(
                data?.calculation_basis?.formula ?? "not reported",
              )}`}
            />
            <MaterialMetric
              testId="price-movement"
              label="Movement"
              value={<MovementBadge movement={data?.movement} />}
              sub="the backend's verdict against its configured thresholds"
            />
          </div>

          <MaterialPanel
            title={`${selectedName} — price series`}
            subtitle={`${series.length} point${series.length === 1 ? "" : "s"}${
              current?.unit ? ` · ${current.unit}` : ""
            }`}
            className="mb-4"
            testId="price-chart"
          >
            <PriceChart
              points={chartPoints}
              unit={current?.unit}
              baseline={baseline?.price}
            />
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-slate-500">
              <span>
                Dashed line is the backend baseline price
                {baseline?.unit ? ` (${baseline.unit})` : ""}; it is drawn, not recomputed.
              </span>
              {demo && <span className="font-semibold text-amber-700">{SYNTHETIC_WORDING}</span>}
            </div>
          </MaterialPanel>

          <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <MaterialPanel title="Thresholds" subtitle="why the movement flag reads as it does">
              <div className="flex flex-wrap gap-3">
                <div className="flex-1 rounded-xl border border-slate-200/60 bg-white/60 px-4 py-3 backdrop-blur-md">
                  <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                    Warning at
                  </span>
                  <div className="mt-1 text-[17px] font-bold text-amber-700">
                    <Figure value={data?.thresholds?.warning_pct} unit="%" />
                  </div>
                </div>
                <div className="flex-1 rounded-xl border border-slate-200/60 bg-white/60 px-4 py-3 backdrop-blur-md">
                  <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                    Abnormal at
                  </span>
                  <div className="mt-1 text-[17px] font-bold text-red-700">
                    <Figure value={data?.thresholds?.abnormal_pct} unit="%" />
                  </div>
                </div>
              </div>
              <p className="mt-3 text-[11.5px] leading-relaxed text-slate-500">
                The backend computes movement from the magnitude of the percentage change: at or
                above the abnormal threshold it reports ABNORMAL, at or above the warning threshold
                it reports WARNING, otherwise NORMAL. The values above are the configured thresholds
                returned with this series.
              </p>
            </MaterialPanel>

            <MaterialPanel title="Provenance">
              <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
                <span className="text-[10px] text-slate-500">
                  Source{" "}
                  <span className="font-mono text-slate-600">
                    {data?.source ?? "not reported"}
                  </span>
                </span>
                <span className="text-[10px] text-slate-500">
                  Last updated{" "}
                  <span className="font-mono text-slate-600">
                    {data?.last_updated ?? "not reported"}
                  </span>
                </span>
                <span className="text-[10px] text-slate-500">
                  Points <span className="font-mono text-slate-600">{data?.points ?? "—"}</span>
                </span>
                {data?.data_status ? (
                  <StatusChip label={data.data_status} tone={statusTone(data.data_status)} />
                ) : null}
              </div>
              {demo && (
                <p className="mt-2 text-[11.5px] font-semibold text-amber-700">
                  {SYNTHETIC_WORDING}
                </p>
              )}
              {data?.conversion_note ? (
                <p className="mt-2 text-[11px] text-slate-500">{data.conversion_note}</p>
              ) : null}
              <div className="mt-3 border-t border-slate-200/60 pt-3">
                {/* Source, timestamp and status are printed verbatim above.
                    ProvenanceLine carries the backend's calculation basis. */}
                <ProvenanceLine basis={data?.calculation_basis} />
              </div>
              {data?.limitations?.length ? (
                <div className="mt-3">
                  <LimitationNote limitations={data.limitations} />
                </div>
              ) : null}
            </MaterialPanel>
          </div>
        </>
      )}
    </>
  );
}
