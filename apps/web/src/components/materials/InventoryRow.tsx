"use client";

/**
 * InventoryRow — one stock position in the register.
 *
 * The page exists to make one distinction legible: quantity, reserved and
 * available are three different numbers, and *available* is the one that
 * decides coverage. So the row renders quantity and reserved as quiet mono
 * figures and lifts `available` into a tone-bordered figure block, coloured by
 * the backend's own status verdict. Nothing here is computed: the unit price,
 * safety stock and reorder level are the backend's, and where a figure is
 * absent the row explains why instead of showing a zero.
 */
import Link from "next/link";
import { Figure, StatusChip, statusTone } from "@/components/materials/MaterialsKit";
import LimitationInline from "@/components/materials/LimitationInline";
import type { InventoryStatusRecord } from "@/lib/api";

const AVAILABLE_PILL: Record<string, string> = {
  ok: "border-emerald-300/70 bg-emerald-50/70 text-emerald-700",
  warn: "border-amber-300/70 bg-amber-50/70 text-amber-700",
  crit: "border-red-300/70 bg-red-50/70 text-red-700",
  ai: "border-cyan-300/70 bg-cyan-50/70 text-cyan-700",
  violet: "border-violet-300/70 bg-violet-50/70 text-violet-700",
  muted: "border-slate-300/70 bg-slate-50/70 text-slate-600",
};

const CLASS_LABEL: Record<string, string> = {
  RAW_MATERIAL: "Raw material",
  INTERMEDIATE: "Intermediate",
  FINISHED_PRODUCT: "Finished product",
  MAINTENANCE_SPARE: "Maintenance spare",
};

export default function InventoryRow({ position }: { position: InventoryStatusRecord }) {
  const id = position.material_id;
  const material = position.material;
  const name = material?.name?.trim() ? material.name : id;
  const materialClass = material?.material_class;
  const location = position.location ?? material?.location ?? null;
  const unit = position.unit ?? material?.unit ?? null;
  const tone = statusTone(position.status);
  const coverLimitations = position.limitations ?? [];

  return (
    <Link
      href={`/console/materials/${encodeURIComponent(id)}`}
      className="mat-inv__row"
      data-material-id={id}
      data-material-status={position.status}
      aria-label={`${name} (${id}) — ${position.available ?? "no"} ${unit ?? ""} available, status ${position.status ?? "unknown"}. Open material detail.`}
    >
      <span className="mat-inv__cell mat-inv__cell--material">
        <span className="mat-inv__name">{name}</span>
        <span className="mat-inv__id">{id}</span>
      </span>

      <span className="mat-inv__cell mat-inv__cell--class">
        {materialClass ? (CLASS_LABEL[materialClass] ?? materialClass) : <span className="text-slate-300">—</span>}
      </span>

      <span className="mat-inv__cell mat-inv__loc">
        {location ? <span className="font-mono text-[11.5px] text-slate-600">{location}</span> : <span className="text-slate-300">—</span>}
      </span>

      {/* On hand — the gross figure. Quiet, because it is not what decides coverage. */}
      <span className="mat-inv__cell mat-inv__cell--num">
        <Figure value={position.quantity} className="text-[12.5px] text-slate-500" />
      </span>

      {/* Reserved — committed elsewhere. Amber, because it is stock you cannot use. */}
      <span className="mat-inv__cell mat-inv__cell--num">
        {position.reserved === null || position.reserved === undefined ? (
          <span className="text-slate-300">—</span>
        ) : (
          <Figure value={position.reserved} className="text-[12.5px] text-amber-700" />
        )}
      </span>

      {/* Available — the point of the row. */}
      <span className="mat-inv__cell mat-inv__cell--avail">
        <span className={`mat-inv__availpill ${AVAILABLE_PILL[tone] ?? AVAILABLE_PILL.muted}`}>
          <span className="mat-inv__dot" aria-hidden="true" />
          <Figure value={position.available} className="text-[16px] font-semibold" />
        </span>
      </span>

      <span className="mat-inv__cell mat-inv__cell--num">
        <Figure value={position.safety_stock} className="text-[12.5px] text-slate-600" />
      </span>

      <span className="mat-inv__cell mat-inv__cell--num">
        <Figure value={position.reorder_level} className="text-[12.5px] text-slate-600" />
      </span>

      <span className="mat-inv__cell mat-inv__unit">
        {unit ? <span className="font-mono text-[11px] uppercase tracking-wide text-slate-500">{unit}</span> : <span className="text-slate-300">—</span>}
      </span>

      <span className="mat-inv__cell mat-inv__cell--cover">
        {position.days_of_cover === null || position.days_of_cover === undefined ? (
          <LimitationInline limitations={coverLimitations} label="no cover basis" />
        ) : (
          <Figure value={position.days_of_cover} unit="d" className="text-[12.5px] text-slate-600" />
        )}
      </span>

      <span className="mat-inv__cell mat-inv__cell--status">
        <StatusChip label={position.status ?? "unknown"} tone={tone} />
      </span>
    </Link>
  );
}
