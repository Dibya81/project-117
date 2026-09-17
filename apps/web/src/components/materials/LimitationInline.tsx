"use client";

/**
 * LimitationInline — the backend's limitation code, rendered inline where a
 * dense register row has no room for the full `LimitationNote`.
 *
 * A missing figure is never a blank and never a zero: the row shows the
 * limitation the backend reported instead, with the backend's own message as
 * the hover title. Rows that carry no limitation at all fall back to the
 * console's honest "—" placeholder rather than inventing a value.
 */
import { Info } from "lucide-react";
import type { LimitationRecord } from "@/lib/api";

export default function LimitationInline({
  limitations,
  label,
}: {
  limitations?: LimitationRecord[];
  /** Short override for the chip text; defaults to the first limitation code. */
  label?: string;
}) {
  if (!limitations?.length) {
    return (
      <span className="text-slate-300" aria-label="No value reported">
        —
      </span>
    );
  }
  const title = limitations.map((l) => `${l.code}: ${l.message}`).join("\n");
  return (
    <span
      className="mat-lim"
      title={title}
      aria-label={limitations.map((l) => `${l.code}: ${l.message}`).join("; ")}
    >
      <Info size={11} strokeWidth={2.4} aria-hidden="true" />
      <span className="mat-lim__code">{label ?? limitations[0].code}</span>
      {limitations.length > 1 && <span className="mat-lim__more">+{limitations.length - 1}</span>}
    </span>
  );
}
