"use client";

/**
 * Materials Overview — the command centre for the industrial-materials layer.
 *
 * Every figure on this page is rendered as the materials service returned it:
 * the counters, the inventory value and its `calculation_status`, the latest
 * production bucket, the days of cover, the insight messages and their evidence
 * objects. The browser performs no inventory arithmetic, no unit conversion and
 * no percentage maths — a second implementation of "days of cover" in the page
 * is exactly how a console comes to disagree with the engine it reports on.
 *
 * Two honesty rules are structural here, not stylistic:
 *
 *  * A cover entry with `days_of_cover: null` renders the backend's own
 *    `limitations` through `LimitationNote`. It is never a blank cell, because
 *    a blank reads as zero.
 *  * If the intelligence endpoint is not deployed, `overview()` resolves to
 *    null and the page says so. It does not fall back to invented figures.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  EmptyState,
  Figure,
  LimitationNote,
  MaterialPanel,
  MaterialsHeader,
  Money,
  MovementChip,
  StatusChip,
  statusTone,
} from "@/components/materials/MaterialsKit";
import { Lucide } from "@/components/ui/LucideIcon";
import { SkeletonRows } from "@/components/ui/primitives";
import { consoleData } from "@/lib/data/console";
import { SPRING, fadeSlide } from "@/lib/ui/motion";
import type { MaterialInsightRecord } from "@/lib/api";

type OverviewData = NonNullable<Awaited<ReturnType<typeof consoleData.materials.overview>>>;

/** Canonical class order for display. The counts themselves come from the API. */
const CLASS_ORDER = ["RAW_MATERIAL", "INTERMEDIATE", "FINISHED_PRODUCT", "MAINTENANCE_SPARE"];

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

/**
 * A fixed, locale-independent timestamp.
 *
 * `toLocaleString` renders differently on the Node server and in a browser on a
 * different locale, which React reports as a hydration mismatch. Formatting in
 * UTC from explicit parts keeps the server and client markup identical.
 */
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

/** A value the API did not return is shown as an explicit dash, never as 0. */
function Text({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="mat-empty">—</span>;
  return <>{value}</>;
}

/** Render one evidence entry exactly as typed on the wire. */
function EvidenceValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="mat-empty">—</span>;
  if (typeof value === "number") return <Figure value={value} />;
  if (typeof value === "boolean") return <>{value ? "yes" : "no"}</>;
  if (typeof value === "object") {
    return <span className="font-mono text-[10.5px] text-slate-500">{JSON.stringify(value)}</span>;
  }
  return <>{String(value)}</>;
}

function Kpi({
  label,
  accent,
  children,
}: {
  label: string;
  accent?: "ai" | "violet" | "crit" | "warn";
  children: React.ReactNode;
}) {
  return (
    <div className={`mat-kpi${accent ? ` mat-kpi--${accent}` : ""}`}>
      <div className="mat-kpi__label">{label}</div>
      {children}
    </div>
  );
}

/** Production direction is a trend word, not a health status — map it explicitly. */
function trendTone(trend: string | null | undefined): "ok" | "warn" | "muted" {
  switch ((trend ?? "").toUpperCase()) {
    case "INCREASING":
      return "ok";
    case "DECREASING":
      return "warn";
    default:
      return "muted";
  }
}

function severityTone(severity: MaterialInsightRecord["severity"]) {
  if (severity === "CRITICAL") return "crit" as const;
  if (severity === "WARNING") return "warn" as const;
  return "ai" as const;
}

function InsightCard({ insight }: { insight: MaterialInsightRecord }) {
  const evidence = Object.entries(insight.evidence ?? {});
  return (
    <article className={`mat-insight mat-insight--${insight.severity}`}>
      <div className="mat-insight__head">
        <StatusChip
          label={insight.severity}
          tone={severityTone(insight.severity)}
          pulse={insight.severity === "CRITICAL"}
        />
        <span className="mat-chip">{insight.kind}</span>
        {insight.material_id ? (
          <Link className="mat-link font-mono text-[10.5px]" href={`/console/materials/${insight.material_id}`}>
            {insight.material_id} →
          </Link>
        ) : null}
        {insight.name ? <span className="text-[11px] text-slate-400">{insight.name}</span> : null}
      </div>
      <p className="mat-insight__msg">{insight.message}</p>
      {evidence.length > 0 ? (
        <details className="mat-ev">
          <summary>Evidence</summary>
          <div className="mat-ev__grid">
            {evidence.map(([k, v]) => (
              <div key={k}>
                <div className="mat-ev__k">{k.replace(/_/g, " ")}</div>
                <div className="mat-ev__v">
                  <EvidenceValue value={v} />
                </div>
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </article>
  );
}

export default function MaterialsOverviewPage() {
  const router = useRouter();
  const [data, setData] = useState<OverviewData | null | undefined>(undefined);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setData(undefined);
    consoleData.materials
      .overview()
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const grouped = useMemo(() => {
    const insights = data?.insights ?? [];
    return {
      CRITICAL: insights.filter((i) => i.severity === "CRITICAL"),
      WARNING: insights.filter((i) => i.severity === "WARNING"),
      INFO: insights.filter((i) => i.severity === "INFO"),
    };
  }, [data]);

  const header = (
    <MaterialsHeader
      kicker="Industrial materials"
      title="Materials Overview"
      lede="Inventory position, raw-material cover, finished-product tanks and the intelligence layer's findings — every figure as computed by the materials service."
      actions={
        <>
          <Link className="cs-btn cs-btn--ghost" href="/console/materials/register">
            <Lucide name="database" size={12} /> Register
          </Link>
          <button className="cs-btn cs-btn--ghost" type="button" onClick={() => setReloadKey((k) => k + 1)}>
            <Lucide name="refresh" size={12} /> Refresh
          </button>
        </>
      }
    />
  );

  if (data === undefined) {
    return (
      <>
        {header}
        <MaterialPanel title="Intelligence layer">
          <SkeletonRows rows={6} label="Querying the materials service…" />
        </MaterialPanel>
      </>
    );
  }

  if (data === null) {
    return (
      <>
        {header}
        <MaterialPanel title="Intelligence layer">
          <EmptyState
            title="Materials intelligence is not available in this deployment"
            detail="GET /api/materials/intelligence returned no payload, so there is no dashboard to render. This page shows nothing rather than estimating inventory, cover or value."
          />
        </MaterialPanel>
      </>
    );
  }

  const { dashboard, insights, insightCounts, dataStatus } = data;
  const cover = dashboard.raw_material_cover ?? [];
  const critical = dashboard.critical_materials ?? [];
  const finished = dashboard.finished_product_positions ?? [];
  const movements = dashboard.recent_movements ?? [];
  const byClass = Object.entries(dashboard.counts?.by_class ?? {}).sort(
    (a, b) => CLASS_ORDER.indexOf(a[0]) - CLASS_ORDER.indexOf(b[0]),
  );
  const production = dashboard.production ?? {};
  const value = dashboard.inventory_value;

  return (
    <>
      {header}

      {(dashboard.limitations?.length ?? 0) > 0 ? (
        <div className="mb-3.5">
          <LimitationNote limitations={dashboard.limitations} />
        </div>
      ) : null}

      <div className="mat-kpis">
        <Kpi label="Materials on register">
          <div className="mat-kpi__value">
            <Figure value={dashboard.counts?.materials ?? null} />
          </div>
          <div className="mat-kpi__meta">Classified by the materials layer across {byClass.length} classes.</div>
          <div className="mat-kpi__foot">
            {byClass.map(([cls, count]) => (
              <span key={cls} className="mat-chip">
                {classLabel(cls)} <b>{count}</b>
              </span>
            ))}
          </div>
        </Kpi>

        <Kpi label="Inventory value" accent="violet">
          <div className="mat-kpi__value">
            <Money amount={value?.amount ?? null} currency={value?.currency ?? "INR"} />
          </div>
          <div className="mat-kpi__meta">{value?.basis ?? "The service returned no basis for this figure."}</div>
          <div className="mat-kpi__foot">
            <StatusChip label={value?.calculation_status ?? "UNKNOWN"} tone={statusTone(value?.calculation_status)} />
            <span className="mat-chip">
              materials priced <b>{value?.materials_priced ?? "—"}</b>
            </span>
          </div>
        </Kpi>

        <Kpi label={`Production · ${production.period ?? "latest period"}`} accent="ai">
          <div className="mat-kpi__value">
            <Figure value={production.latest?.quantity ?? null} unit={production.unit} />
          </div>
          <div className="mat-kpi__meta">
            {production.latest ? (
              <>
                {fmtDay(production.latest.period_start)} → {fmtDay(production.latest.period_end)}
                {production.latest.partial ? " · partial period" : ""}
              </>
            ) : (
              "The service returned no production bucket."
            )}
            {production.change_percent !== null && production.change_percent !== undefined ? (
              <>
                {" · "}
                <Figure value={production.change_percent} unit="%" /> vs previous period
              </>
            ) : null}
          </div>
          <div className="mat-kpi__foot">
            <StatusChip label={production.trend ?? "No trend reported"} tone={trendTone(production.trend)} />
          </div>
        </Kpi>

        <Kpi label="Critical materials" accent={critical.length > 0 ? "crit" : "warn"}>
          <div className="mat-kpi__value">{critical.length}</div>
          <div className="mat-kpi__meta">
            Rows in the backend&rsquo;s critical-materials list — stock at or below its recorded safety level.
          </div>
          <div className="mat-kpi__foot">
            <StatusChip label="Insight severity" tone="muted" />
            <span className="mat-chip">
              critical <b>{insightCounts?.critical ?? "—"}</b>
            </span>
            <span className="mat-chip">
              warning <b>{insightCounts?.warning ?? "—"}</b>
            </span>
            <span className="mat-chip">
              info <b>{insightCounts?.info ?? "—"}</b>
            </span>
          </div>
        </Kpi>
      </div>

      <MaterialPanel
        title="Raw material cover"
        subtitle={`${cover.length} raw material${cover.length === 1 ? "" : "s"} · days of cover as computed by the inventory layer`}
      >
        {cover.length === 0 ? (
          <EmptyState
            title="No raw material cover returned"
            detail="The dashboard returned no raw-material rows, so there is no cover to report."
          />
        ) : (
          <div className="mat-cover">
            {cover.map((c, i) => {
              const noCover = c.days_of_cover === null || c.days_of_cover === undefined;
              return (
                <motion.div
                  key={c.material_id}
                  className="mat-cover__row"
                  initial="initial"
                  animate="animate"
                  variants={fadeSlide(6)}
                  transition={{ ...SPRING.glide, delay: Math.min(i * 0.02, 0.16) }}
                >
                  <div className="mat-row__main">
                    <div className="mat-row__title">
                      <Link className="mat-link" href={`/console/materials/${c.material_id}`}>
                        {c.name ?? c.material_id}
                      </Link>
                    </div>
                    <div className="mat-row__sub font-mono">{c.material_id}</div>
                  </div>
                  <div className="mat-fig mat-fig--plain mat-fig--right">
                    <span className="mat-fig__k">On hand</span>
                    <span className="mat-fig__v">
                      <Figure value={c.quantity ?? null} unit={c.unit} />
                    </span>
                  </div>
                  <div className="mat-fig mat-fig--plain mat-fig--right">
                    <span className="mat-fig__k">Days of cover</span>
                    <span className="mat-fig__v">
                      {noCover ? (
                        <span className="text-[11px] text-slate-400">not computable</span>
                      ) : (
                        <Figure value={c.days_of_cover} unit="d" />
                      )}
                    </span>
                  </div>
                  <StatusChip label={c.status ?? "UNKNOWN"} tone={statusTone(c.status)} />
                  {noCover ? (
                    <div className="mat-cover__lim">
                      <LimitationNote limitations={c.limitations} />
                    </div>
                  ) : null}
                </motion.div>
              );
            })}
          </div>
        )}
      </MaterialPanel>

      <div className="mat-cols mat-cols--even">
        <MaterialPanel title="Critical materials" subtitle="Stock position against recorded safety level">
          {critical.length === 0 ? (
            <EmptyState title="No critical materials" detail="The dashboard's critical list is empty for this dataset." />
          ) : (
            <div className="mat-tablewrap">
              <table className="mat-table">
                <thead>
                  <tr>
                    <th>Material</th>
                    <th>Class</th>
                    <th className="mat-num">Available</th>
                    <th className="mat-num">Safety stock</th>
                    <th>Location</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {critical.map((m) => (
                    <tr key={m.material_id} onClick={() => router.push(`/console/materials/${m.material_id}`)}>
                      <td>
                        <Link className="mat-table__id" href={`/console/materials/${m.material_id}`}>
                          {m.material_id}
                        </Link>
                        <div className="mat-table__name">{m.name}</div>
                      </td>
                      <td>
                        <span className="mat-chip">{classLabel(m.material_class)}</span>
                      </td>
                      <td className="mat-num">
                        <Figure value={m.available ?? null} unit={m.unit} />
                      </td>
                      <td className="mat-num">
                        <Figure value={m.safety_stock ?? null} unit={m.unit} />
                      </td>
                      <td className="font-mono text-[11px]">
                        <Text value={m.location} />
                      </td>
                      <td>
                        <StatusChip label={m.status ?? "UNKNOWN"} tone={statusTone(m.status)} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </MaterialPanel>

        <MaterialPanel title="Finished product positions" subtitle="Tank-level stock, reserved and free to move">
          {finished.length === 0 ? (
            <EmptyState title="No finished product positions" detail="The dashboard returned no product tank positions." />
          ) : (
            <div className="mat-tablewrap">
              <table className="mat-table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th className="mat-num">Quantity</th>
                    <th className="mat-num">Reserved</th>
                    <th className="mat-num">Available</th>
                    <th>Tank</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {finished.map((p) => (
                    <tr key={p.material_id} onClick={() => router.push(`/console/materials/${p.material_id}`)}>
                      <td>
                        <Link className="mat-table__id" href={`/console/materials/${p.material_id}`}>
                          {p.material_id}
                        </Link>
                        <div className="mat-table__name">{p.name}</div>
                      </td>
                      <td className="mat-num">
                        <Figure value={p.quantity ?? null} unit={p.unit} />
                      </td>
                      <td className="mat-num">
                        <Figure value={p.reserved ?? null} unit={p.unit} />
                      </td>
                      <td className="mat-num">
                        <Figure value={p.available ?? null} unit={p.unit} />
                      </td>
                      <td>
                        {p.location ? (
                          <Link
                            className="mat-link font-mono text-[11px]"
                            href={`/console/equipment/${p.location}`}
                            onClick={(e) => e.stopPropagation()}
                          >
                            {p.location}
                          </Link>
                        ) : (
                          <span className="mat-empty">—</span>
                        )}
                      </td>
                      <td>
                        <StatusChip label={p.status ?? "UNKNOWN"} tone={statusTone(p.status)} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </MaterialPanel>
      </div>

      <div className="mat-cols">
        <MaterialPanel
          title="AI insights"
          subtitle={`${insights.length} finding${insights.length === 1 ? "" : "s"} · ordered by severity`}
          actions={
            <>
              <span className="mat-chip">
                critical <b>{insightCounts?.critical ?? "—"}</b>
              </span>
              <span className="mat-chip">
                warning <b>{insightCounts?.warning ?? "—"}</b>
              </span>
              <span className="mat-chip">
                info <b>{insightCounts?.info ?? "—"}</b>
              </span>
            </>
          }
        >
          {insights.length === 0 ? (
            <EmptyState
              title="No findings"
              detail="The intelligence layer returned no insights for the current dataset. Nothing here is generated on the client."
            />
          ) : (
            <div className="mat-list">
              {(["CRITICAL", "WARNING", "INFO"] as const).map((sev) =>
                grouped[sev].length === 0 ? null : (
                  <div key={sev} className="mat-sevgroup">
                    <div className="mat-sevgroup__head">
                      {sev} · {grouped[sev].length}
                    </div>
                    {grouped[sev].map((insight, i) => (
                      <InsightCard key={`${insight.kind}-${insight.material_id ?? "none"}-${i}`} insight={insight} />
                    ))}
                  </div>
                ),
              )}
            </div>
          )}
        </MaterialPanel>

        <MaterialPanel title="Recent movements" subtitle={`${movements.length} latest postings`}>
          {movements.length === 0 ? (
            <EmptyState title="No movements" detail="The dashboard returned no recent material movements." />
          ) : (
            <div className="mat-list">
              {movements.map((m) => (
                <div key={m.id} className="mat-move">
                  <MovementChip type={m.movement_type} />
                  <div className="mat-row__main">
                    <Link className="mat-link font-mono text-[11px]" href={`/console/materials/${m.material_id}`}>
                      {m.material_id}
                    </Link>
                    <div className="mat-move__path">
                      {m.source_location} → {m.destination_location} · {m.reference}
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

      <div className="mat-foot">
        <span>Intelligence generated {fmtTs(dashboard.generated_at)}</span>
        <span className="mat-chip">
          data status <b>{dataStatus ?? "—"}</b>
        </span>
        <span>Counts, cover, production and inventory value are the materials service&rsquo;s own figures.</span>
      </div>
    </>
  );
}
