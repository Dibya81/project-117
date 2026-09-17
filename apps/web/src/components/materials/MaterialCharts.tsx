"use client";

/**
 * MaterialCharts — the two charts the materials pages draw.
 *
 * Recharts is used rather than `TrendChart` because both pages need real time
 * axes, a tooltip, a baseline reference line and — for production — a visible
 * distinction between a complete period and a period still in progress.
 * `TrendChart` is a sparkline with none of those, so it cannot carry a partial
 * bucket honestly.
 *
 * The charts are presentation only: they plot the arrays the backend returned
 * and perform no aggregation, unit conversion or percentage arithmetic. The
 * only derived series is the dashed "period to date" continuation, which the
 * caller builds by classifying buckets against the backend's own
 * `latest.period_end`.
 *
 * Rendering is deferred until after mount. Recharts measures its container,
 * which produces different markup on the server than in the browser; gating the
 * chart on a `mounted` flag means both first renders agree and no hydration
 * mismatch is reported.
 */
import { useEffect, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

/** Console palette — cyan is live/intelligence data, amber is caution. */
export const CHART_CYAN = "#0891b2";
export const CHART_AMBER = "#f59e0b";

export interface ProductionPoint {
  /** Axis label: a single date, or `start → end` for a multi-day bucket. */
  label: string;
  /** Quantity for a complete period, or null when the bucket is in progress. */
  complete: number | null;
  /**
   * The dashed "period to date" continuation. Null for every complete bucket
   * except the last one before an in-progress bucket, which carries its value so
   * the dashed segment connects rather than floating.
   */
  partialValue: number | null;
}

export interface PricePointView {
  label: string;
  price: number;
}

interface TooltipRow {
  name?: string;
  value?: number | string;
  color?: string;
  dataKey?: string | number;
}

interface GlassTooltipProps {
  active?: boolean;
  payload?: TooltipRow[];
  label?: string | number;
  unit?: string;
}

function GlassTooltip({ active, payload, label, unit }: GlassTooltipProps) {
  if (!active || !payload?.length) return null;
  const rows = payload.filter((p) => p.value !== null && p.value !== undefined);
  if (!rows.length) return null;
  return (
    <div className="rounded-lg border border-slate-200/80 bg-white/95 px-2.5 py-2 shadow-sm backdrop-blur-xl">
      <div className="font-mono text-[9.5px] font-semibold uppercase tracking-[0.1em] text-slate-400">
        {label}
      </div>
      {rows.map((p) => (
        <div
          key={String(p.dataKey)}
          className="mt-1 flex items-center gap-2 text-[11px] text-slate-700"
        >
          <span
            className="h-1.5 w-1.5 shrink-0 rounded-full"
            style={{ background: p.color ?? CHART_CYAN }}
          />
          <span>{p.name}</span>
          <span className="ml-auto font-mono tabular-nums">
            {Number(p.value).toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </span>
          {unit ? <span className="text-slate-400">{unit}</span> : null}
        </div>
      ))}
    </div>
  );
}

/** A fixed-height placeholder so the panel does not jump when the chart lands. */
function ChartSkeleton({ height }: { height: number }) {
  return (
    <div
      className="flex items-center justify-center rounded-xl border border-dashed border-slate-200/80 bg-slate-50/40 text-[11px] text-slate-400"
      style={{ height }}
    >
      drawing…
    </div>
  );
}

export function ProductionChart({
  points,
  unit,
  height = 280,
  idPrefix = "mat-production",
}: {
  points: ProductionPoint[];
  unit?: string | null;
  height?: number;
  idPrefix?: string;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const hasPartial = points.some((p) => p.partialValue !== null);
  const showDots = points.length <= 31;
  const gradId = `${idPrefix}-fill`;

  if (!mounted) return <ChartSkeleton height={height} />;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={points} margin={{ top: 8, right: 14, bottom: 0, left: -8 }}>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(8,145,178,0.22)" />
            <stop offset="100%" stopColor="rgba(8,145,178,0)" />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 4" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 10, fill: "#94a3b8" }}
          tickLine={false}
          axisLine={{ stroke: "#e2e8f0" }}
          minTickGap={28}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 10, fill: "#94a3b8" }}
          tickLine={false}
          axisLine={false}
          width={58}
          tickFormatter={(v: number) =>
            v.toLocaleString(undefined, { notation: "compact", maximumFractionDigits: 1 })
          }
        />
        <Tooltip content={<GlassTooltip unit={unit ?? undefined} />} />
        <Area
          type="monotone"
          dataKey="complete"
          name="complete period"
          stroke={CHART_CYAN}
          strokeWidth={2}
          fill={`url(#${gradId})`}
          dot={showDots ? { r: 2.4, fill: CHART_CYAN, strokeWidth: 0 } : false}
          activeDot={{ r: 4 }}
        />
        {hasPartial && (
          <Line
            type="monotone"
            dataKey="partialValue"
            name="period to date"
            stroke={CHART_AMBER}
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={false}
            activeDot={{ r: 4 }}
          />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export function PriceChart({
  points,
  unit,
  baseline,
  height = 280,
  idPrefix = "mat-price",
}: {
  points: PricePointView[];
  unit?: string | null;
  /** Backend baseline price, drawn as a reference line. Never recomputed here. */
  baseline?: number | null;
  height?: number;
  idPrefix?: string;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const gradId = `${idPrefix}-fill`;
  const showDots = points.length <= 31 && points.length > 1;

  if (!mounted) return <ChartSkeleton height={height} />;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={points} margin={{ top: 8, right: 14, bottom: 0, left: -8 }}>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(8,145,178,0.18)" />
            <stop offset="100%" stopColor="rgba(8,145,178,0)" />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 4" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 10, fill: "#94a3b8" }}
          tickLine={false}
          axisLine={{ stroke: "#e2e8f0" }}
          minTickGap={28}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 10, fill: "#94a3b8" }}
          tickLine={false}
          axisLine={false}
          width={60}
          domain={["auto", "auto"]}
          tickFormatter={(v: number) =>
            v.toLocaleString(undefined, { notation: "compact", maximumFractionDigits: 1 })
          }
        />
        <Tooltip content={<GlassTooltip unit={unit ?? undefined} />} />
        {baseline !== null && baseline !== undefined && (
          <ReferenceLine
            y={baseline}
            stroke="#94a3b8"
            strokeDasharray="4 4"
            label={{
              value: "baseline",
              position: "insideTopRight",
              fontSize: 9,
              fill: "#64748b",
            }}
          />
        )}
        <Line
          type="monotone"
          dataKey="price"
          name="price"
          stroke={CHART_CYAN}
          strokeWidth={2}
          dot={showDots ? { r: 2.6, fill: CHART_CYAN, strokeWidth: 0 } : false}
          activeDot={{ r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
