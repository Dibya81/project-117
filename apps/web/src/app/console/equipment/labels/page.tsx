"use client";

/**
 * Printable QR label sheet — one label per plant asset.
 *
 * This is the "dashboard PC" half of the feature: the operator prints these,
 * sticks one on each machine, and the Project 117 Android app scans it. The
 * symbol is rendered by the backend (`GET /api/equipment/{id}/qr.svg`) and its
 * payload is namespaced (`P117:EQUIP:<tag>`), so a generic camera app sees
 * opaque text while the Project 117 client resolves the real asset.
 *
 * `?asset=<tag|id>` narrows the sheet to one machine — that is where the detail
 * page's "Print label" affordance lands. The print stylesheet lives in
 * `console.css` under `body.cs-labels-page`; it hides the console chrome, forces
 * black-on-white and keeps a label from splitting across pages, so the sheet can
 * go straight onto label stock.
 */
import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { EmptyState, Panel, SkeletonRows } from "@/components/ui/primitives";
import { Lucide } from "@/components/ui/LucideIcon";
import { QrSymbol } from "@/components/equipment/AssetQrLabel";
import { consoleData } from "@/lib/data/console";

interface LabelRow {
  id: string;
  tag: string;
  name: string;
  zone: string;
  svg: string | null;
}

function LabelSheet() {
  const params = useSearchParams();
  const asset = params.get("asset");
  const [rows, setRows] = useState<LabelRow[] | null>(null);

  // The print stylesheet is scoped by this body class so printing any *other*
  // console page is untouched.
  useEffect(() => {
    document.body.classList.add("cs-labels-page");
    return () => document.body.classList.remove("cs-labels-page");
  }, []);

  useEffect(() => {
    consoleData.equipment.labelSheet().then(setRows);
  }, []);

  const visible = useMemo(() => {
    if (!rows) return null;
    if (!asset) return rows;
    return rows.filter((r) => r.id === asset || r.tag === asset);
  }, [rows, asset]);

  return (
    <>
      <div className="cs-pagehead cs-labels__noprint">
        <div>
          <span className="cs-pagehead__kicker">
            <Link href="/console/equipment">Equipment</Link> / Labels
          </span>
          <h1>{asset ? `QR label — ${asset}` : "QR labels"}</h1>
        </div>
        <div className="cs-pagehead__actions" style={{ marginLeft: "auto" }}>
          <Link className="cs-btn cs-btn--ghost" href="/console/equipment">
            <Lucide name="arrow" size={13} /> Back to equipment
          </Link>
          <button
            type="button"
            className="cs-btn cs-btn--primary"
            onClick={() => window.print()}
            disabled={!visible || visible.length === 0}
          >
            <Lucide name="printer" size={13} /> Print {visible?.length ?? 0} label
            {visible?.length === 1 ? "" : "s"}
          </button>
        </div>
      </div>

      {visible === null ? (
        <Panel>
          <SkeletonRows rows={6} label="Rendering QR labels…" />
        </Panel>
      ) : visible.length === 0 ? (
        <EmptyState
          title={asset ? `No equipment “${asset}”` : "No equipment to label"}
          detail={
            asset
              ? "The label sheet covers every asset in the plant register; this one is not in it."
              : "The plant register returned no assets, so there is nothing to print."
          }
          action={
            <Link className="cs-btn cs-btn--ghost" href="/console/equipment">
              Back to equipment
            </Link>
          }
        />
      ) : (
        <div className="cs-labels" data-label-count={visible.length}>
          {visible.map((r) => (
            <article className="cs-label" key={r.id} data-label-asset={r.id}>
              <QrSymbol svg={r.svg} alt={r.tag} size={96} className="cs-label__qr" />
              <div className="cs-label__meta">
                <span className="cs-label__tag cs-mono">{r.tag}</span>
                <span className="cs-label__name">{r.name}</span>
                <span className="cs-label__zone cs-dim">{r.zone}</span>
                <span className="cs-label__id cs-mono cs-dim">{r.id}</span>
              </div>
            </article>
          ))}
        </div>
      )}
    </>
  );
}

export default function EquipmentLabelsPage() {
  return (
    <Suspense
      fallback={
        <Panel>
          <SkeletonRows rows={6} label="Rendering QR labels…" />
        </Panel>
      }
    >
      <LabelSheet />
    </Suspense>
  );
}
