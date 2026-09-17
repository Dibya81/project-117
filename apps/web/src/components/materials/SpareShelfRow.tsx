"use client";

/**
 * SpareShelfRow — one maintenance spare, with the asset requirements the engine
 * recorded against it.
 *
 * The chain this row has to make readable in one glance is
 * equipment → spare → inventory → coverage. Inventory figures come from the
 * register; `required_by` and the forecast come from the material detail the
 * backend composes, so the row never guesses which asset consumes a spare. When
 * a mapping or a forecast is absent the row says so rather than showing a zero.
 */
import Link from "next/link";
import { Figure, StatusChip, statusTone } from "@/components/materials/MaterialsKit";
import LimitationInline from "@/components/materials/LimitationInline";
import type { InventoryStatusRecord, MaterialDetailEnvelope } from "@/lib/api";

const AVAILABLE_PILL: Record<string, string> = {
  ok: "border-emerald-300/70 bg-emerald-50/70 text-emerald-700",
  warn: "border-amber-300/70 bg-amber-50/70 text-amber-700",
  crit: "border-red-300/70 bg-red-50/70 text-red-700",
  ai: "border-cyan-300/70 bg-cyan-50/70 text-cyan-700",
  violet: "border-violet-300/70 bg-violet-50/70 text-violet-700",
  muted: "border-slate-300/70 bg-slate-50/70 text-slate-600",
};

export default function SpareShelfRow({
  position,
  detail,
  onPickAsset,
  selected,
}: {
  position: InventoryStatusRecord;
  /** `undefined` while the detail is still loading; `null` when it could not be read. */
  detail: MaterialDetailEnvelope | null | undefined;
  onPickAsset: (equipmentId: string) => void;
  /** True when this spare's asset is the one loaded in the coverage workbench. */
  selected: boolean;
}) {
  const id = position.material_id;
  const name = position.material?.name?.trim() ? position.material.name : id;
  const unit = position.unit ?? position.material?.unit ?? null;
  const location = position.location ?? position.material?.location ?? null;
  const tone = statusTone(position.status);
  const forecast = detail?.forecast;
  const requiredBy = detail?.required_by ?? [];

  return (
    <article className={`mat-spare${selected ? " is-selected" : ""}`} data-spare-id={id} data-spare-status={position.status}>
      <div className="mat-spare__main">
        <div className="mat-spare__ident">
          <Link href={`/console/materials/${encodeURIComponent(id)}`} className="mat-spare__name">
            {name}
          </Link>
          <span className="mat-spare__id">{id}</span>
        </div>

        <span className={`mat-spare__pill ${AVAILABLE_PILL[tone] ?? AVAILABLE_PILL.muted}`}>
          <span className="mat-inv__dot" aria-hidden="true" />
          <Figure value={position.available} className="text-[15px] font-semibold" />
          {unit ? <span className="mat-spare__pillunit">{unit}</span> : null}
        </span>

        <span className="mat-spare__fig">
          <span className="mat-spare__figlabel">Safety</span>
          <Figure value={position.safety_stock} className="text-[12.5px] text-slate-700" />
        </span>
        <span className="mat-spare__fig">
          <span className="mat-spare__figlabel">Reorder</span>
          <Figure value={position.reorder_level} className="text-[12.5px] text-slate-700" />
        </span>
        <span className="mat-spare__fig">
          <span className="mat-spare__figlabel">Cover</span>
          {position.days_of_cover === null || position.days_of_cover === undefined ? (
            <LimitationInline limitations={position.limitations} label="no basis" />
          ) : (
            <Figure value={position.days_of_cover} unit="d" className="text-[12.5px] text-slate-700" />
          )}
        </span>
        <span className="mat-spare__fig mat-spare__fig--loc">
          <span className="mat-spare__figlabel">Location</span>
          {location ? <span className="font-mono text-[11.5px] text-slate-600">{location}</span> : <span className="text-slate-300">—</span>}
        </span>

        <span className="mat-spare__status">
          <StatusChip label={position.status ?? "unknown"} tone={tone} />
        </span>
      </div>

      <div className="mat-spare__meta">
        <span className="mat-spare__forecast">
          <span className="mat-spare__metalabel">Forecast</span>
          {detail === undefined ? (
            <span className="text-slate-400">loading…</span>
          ) : detail === null ? (
            <span className="text-slate-400">forecast unavailable — material detail did not load</span>
          ) : forecast?.days_to_depletion === null || forecast?.days_to_depletion === undefined ? (
            <LimitationInline limitations={forecast?.limitations} label="no forecast basis" />
          ) : (
            <span className="mat-spare__forecastline">
              <span>
                to empty <Figure value={forecast.days_to_depletion} unit="d" className="text-[12px] text-slate-700" />
              </span>
              <span className="mat-spare__forecastsep">·</span>
              <span>
                to safety{" "}
                <Figure value={forecast.days_to_safety_stock} unit="d" className="text-[12px] text-slate-700" />
              </span>
              {forecast.confidence ? (
                <StatusChip label={`${forecast.confidence} confidence`} tone={statusTone(forecast.confidence)} />
              ) : null}
              {forecast.projected_depletion_date ? (
                <span className="mat-spare__forecastbasis" title={forecast.confidence_basis}>
                  projected {forecast.projected_depletion_date}
                </span>
              ) : null}
            </span>
          )}
        </span>

        <span className="mat-spare__reqby">
          <span className="mat-spare__metalabel">Required by</span>
          {detail === undefined ? (
            <span className="text-slate-400">loading…</span>
          ) : detail === null ? (
            <span className="text-slate-400">requirement mapping unavailable</span>
          ) : requiredBy.length === 0 ? (
            <span className="text-slate-400">no asset requirement recorded</span>
          ) : (
            <span className="mat-spare__reqchips">
              {requiredBy.map((r) => (
                <button
                  key={`${r.equipment_id}-${r.requirement_id}`}
                  type="button"
                  className="mat-reqchip"
                  onClick={() => onPickAsset(r.equipment_id)}
                  title={`Load ${r.equipment_id} in the coverage workbench — ${r.purpose}`}
                  data-required-by={r.equipment_id}
                >
                  <span className="mat-reqchip__id">{r.equipment_id}</span>
                  <span className="mat-reqchip__qty">
                    ×<Figure value={r.quantity} unit={r.unit} className="text-[10.5px]" />
                  </span>
                  {r.failure_mode ? <span className="mat-reqchip__mode">{r.failure_mode}</span> : null}
                </button>
              ))}
            </span>
          )}
        </span>
      </div>
    </article>
  );
}
