"use client";

/**
 * Materials — Suppliers (/console/materials/suppliers)
 *
 * The synthetic supplier register. Two honesty rules drive the page:
 *
 *  1. **These are not real vendors.** The API returns its own note saying so,
 *     and the register banner surfaces it plus each supplier's `reference`
 *     ("SYNTHETIC DEMO — not a real vendor") and provenance note, so a name or a
 *     contact address cannot be mistaken for a real one.
 *  2. **The supplier→material relation is read, never invented.** Each supplier
 *     lists the catalogue items whose own `supplier_id` points at it; a supplier
 *     with no catalogue reference says so instead of showing a plausible list.
 *
 * The lead-time summary (active count, longest lead time) is a presentation
 * aggregate over the returned rows — the procurement risk surface the register
 * is for. No per-material quantity or cost is derived here.
 */
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  EmptyState,
  Figure,
  MaterialPanel,
  MaterialsHeader,
  ProvenanceLine,
  StatusChip,
  SyntheticDemoBadge,
  statusTone,
} from "@/components/materials/MaterialsKit";
import { MaterialMetric } from "@/components/materials/MaterialMetric";
import { consoleData } from "@/lib/data/console";
import type { MaterialRecord, SupplierRecord } from "@/lib/api";

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<SupplierRecord[] | null>(null);
  const [catalogue, setCatalogue] = useState<MaterialRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    Promise.all([
      consoleData.materials.suppliers(),
      consoleData.materials.list({ limit: 200 }).then((r) => r.items),
    ])
      .then(([s, items]) => {
        if (!alive) return;
        setSuppliers(s);
        setCatalogue(items);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (!alive) return;
        setSuppliers(null);
        setError(err instanceof Error ? err.message : "the suppliers endpoint did not answer");
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  const materialsBySupplier = useMemo(() => {
    const map = new Map<string, MaterialRecord[]>();
    for (const m of catalogue ?? []) {
      if (!m.supplier_id) continue;
      const list = map.get(m.supplier_id) ?? [];
      list.push(m);
      map.set(m.supplier_id, list);
    }
    return map;
  }, [catalogue]);

  const ordered = useMemo(
    () => [...(suppliers ?? [])].sort((a, b) => b.lead_time_days - a.lead_time_days),
    [suppliers],
  );

  const active = ordered.filter((s) => s.status.toUpperCase() === "ACTIVE");
  const qualified = ordered.filter((s) => s.status.toUpperCase() === "QUALIFIED");
  const onHold = ordered.filter((s) => s.status.toUpperCase() === "ON_HOLD");
  const longest = ordered.reduce<SupplierRecord | null>(
    (best, s) => (best === null || s.lead_time_days > best.lead_time_days ? s : best),
    null,
  );
  const referencedMaterials = (catalogue ?? []).filter((m) => m.supplier_id).length;

  // The API's own warning, taken from the supplier provenance rather than
  // written here, so the banner cannot drift from what the service says.
  const note = ordered.find((s) => s.provenance?.note)?.provenance.note;
  const reference = ordered.find((s) => s.reference)?.reference;

  return (
    <>
      <MaterialsHeader
        kicker="Materials"
        title="Suppliers"
        lede="The synthetic supplier register, with the materials each entry is referenced by in the catalogue and the lead time that sets the procurement risk surface."
      />

      <div className="mb-4 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3.5 backdrop-blur-xl">
        <div className="flex flex-wrap items-center gap-2">
          <SyntheticDemoBadge />
          <span className="text-[12.5px] font-semibold text-amber-900">
            Synthetic demonstration suppliers — not real vendors.
          </span>
        </div>
        <p className="mt-2 max-w-4xl text-[11.5px] leading-relaxed text-amber-800">
          {note ??
            "These records were generated for demonstration. No name, contact address or commercial term below refers to a real company."}
          {reference ? (
            <>
              {" "}
              Register reference: <span className="font-mono">{reference}</span>.
            </>
          ) : null}
        </p>
      </div>

      {error ? (
        <MaterialPanel title="Supplier register">
          <EmptyState
            title="The supplier register could not be read"
            detail={`${error}. No suppliers are shown, because none were received.`}
          />
        </MaterialPanel>
      ) : loading ? (
        <MaterialPanel title="Supplier register">
          <p className="m-0 text-[12.5px] text-slate-500">Reading the supplier register…</p>
        </MaterialPanel>
      ) : ordered.length === 0 ? (
        <MaterialPanel title="Supplier register">
          <EmptyState
            title="No suppliers on record"
            detail="The backend returned no supplier records, so there is no register to show and no lead time to report."
          />
        </MaterialPanel>
      ) : (
        <>
          <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MaterialMetric
              testId="suppliers-active"
              label="Active suppliers"
              value={<Figure value={active.length} />}
              sub={`of ${ordered.length} on record · ${qualified.length} qualified · ${onHold.length} on hold`}
            />
            <MaterialMetric
              testId="suppliers-longest-lead"
              label="Longest lead time"
              value={<Figure value={longest?.lead_time_days} unit="days" />}
              tone="text-amber-700"
              sub={
                longest
                  ? `${longest.name} (${longest.id}) — the slowest surface to protect`
                  : "no supplier lead time returned"
              }
            />
            <MaterialMetric
              testId="suppliers-count"
              label="Suppliers on record"
              value={<Figure value={ordered.length} />}
              sub="every row is synthetic demonstration data"
            />
            <MaterialMetric
              testId="suppliers-materials"
              label="Catalogued materials with a supplier"
              value={<Figure value={catalogue === null ? null : referencedMaterials} />}
              sub={`of ${catalogue?.length ?? "…"} catalogue items carry a supplier reference`}
            />
          </div>

          <div className="flex flex-col gap-3">
            {ordered.map((s) => {
              const supplied = materialsBySupplier.get(s.id) ?? [];
              return (
                <MaterialPanel
                  key={s.id}
                  testId={`supplier-${s.id}`}
                  title={s.name}
                  subtitle={
                    <span className="font-mono text-[10px] text-slate-400">{s.id}</span>
                  }
                  actions={
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusChip label={s.status} tone={statusTone(s.status)} />
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-300/60 bg-slate-100/70 px-2.5 py-1 font-mono text-[10px] font-semibold text-slate-600">
                        {s.lead_time_days} days lead
                      </span>
                    </div>
                  }
                >
                  <div className="flex flex-col gap-3">
                    <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
                      <span className="text-[10px] text-slate-500">
                        Contact{" "}
                        <span className="font-mono text-slate-600">{s.contact}</span>
                      </span>
                      <span className="text-[10px] text-slate-500">
                        Reference{" "}
                        <span className="font-mono text-slate-600">{s.reference}</span>
                      </span>
                      <span className="text-[10px] text-slate-500">
                        Lead time{" "}
                        <span className="font-mono text-slate-600">
                          {s.lead_time_days} days
                        </span>
                      </span>
                    </div>

                    <div>
                      <div className="mb-2 flex items-center gap-2">
                        <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                          Materials supplied
                        </span>
                        <span className="font-mono text-[10px] text-slate-400">
                          {supplied.length}
                        </span>
                      </div>
                      {supplied.length === 0 ? (
                        <p className="m-0 text-[11.5px] text-slate-500">
                          No catalogue item references this supplier id. Nothing is listed here,
                          because the relation is read from the catalogue and not assumed.
                        </p>
                      ) : (
                        <div className="flex flex-wrap gap-2">
                          {supplied.map((m) => (
                            <Link
                              key={m.id}
                              href={`/console/materials/${encodeURIComponent(m.id)}`}
                              className="group inline-flex items-center gap-2 rounded-lg border border-slate-200/60 bg-white/60 px-2.5 py-1.5 backdrop-blur-md transition-colors hover:border-cyan-500/40 hover:bg-cyan-500/5"
                            >
                              <span className="text-[12px] text-slate-700 group-hover:text-cyan-800">
                                {m.name}
                              </span>
                              <span className="font-mono text-[9.5px] text-slate-400">
                                {m.id}
                              </span>
                              <StatusChip label={m.status} tone={statusTone(m.status)} />
                            </Link>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="border-t border-slate-200/60 pt-2.5">
                      <ProvenanceLine provenance={s.provenance} />
                    </div>
                  </div>
                </MaterialPanel>
              );
            })}
          </div>
        </>
      )}
    </>
  );
}
