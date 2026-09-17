"use client";

/**
 * Required spares for one asset — the top of the materials chain, on the
 * equipment page where an engineer already is.
 *
 * EQUIPMENT → MAINTENANCE REQUIREMENT → REQUIRED SPARE → INVENTORY → COVERAGE
 *
 * Everything shown here is the backend's own output: the requirement, the
 * available quantity (already computed as `quantity − reserved`), the safety
 * stock and the coverage verdict. The panel performs no arithmetic and invents
 * nothing; when the domain reports a limitation it says so instead of showing a
 * blank that would read as zero.
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Panel, SkeletonRows } from "@/components/ui/primitives";
import { CoverageChip, Figure } from "@/components/materials/MaterialsKit";
import { consoleData } from "@/lib/data/console";
import type { EquipmentRequirementsRecord } from "@/lib/api";

export function EquipmentSparesPanel({ equipmentId }: { equipmentId: string }) {
  const router = useRouter();
  const [data, setData] = useState<EquipmentRequirementsRecord | null | undefined>(undefined);

  useEffect(() => {
    let alive = true;
    setData(undefined);
    consoleData.materials
      .requirementsFor(equipmentId)
      .then((r) => alive && setData(r))
      .catch(() => alive && setData(null));
    return () => {
      alive = false;
    };
  }, [equipmentId]);

  if (data === undefined) {
    return (
      <Panel title="Required spares" pad>
        <SkeletonRows rows={3} />
      </Panel>
    );
  }

  const limitation = data?.limitations?.[0];

  return (
    <Panel title="Required spares" pad>
      {data === null || !data ? (
        <p className="cs-dim" style={{ margin: 0, fontSize: 12.5 }}>
          The materials layer is not available in this deployment.
        </p>
      ) : limitation ? (
        <p className="cs-dim" style={{ margin: 0, fontSize: 12.5 }}>
          <span className="cs-mono" style={{ fontSize: 10, letterSpacing: "0.08em", color: "var(--ink-3)" }}>
            {limitation.code}
          </span>
          <br />
          {limitation.message}
        </p>
      ) : (
        <>
          <p className="cs-dim" style={{ margin: "0 0 10px", fontSize: 11.5, lineHeight: 1.6 }}>
            Materials this asset requires, with the live position for each. Coverage is
            computed by the backend as{" "}
            <span className="cs-mono">available − required − safety stock</span>.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {data.requirements.map((r) => (
              <div
                key={r.requirement_id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "10px 12px",
                  borderRadius: 10,
                  border: "1px solid var(--line)",
                  background: r.mode_match ? "rgba(34,211,238,0.05)" : "transparent",
                }}
              >
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap" }}>
                    <b style={{ fontSize: 12.5 }}>{r.item_name ?? r.item_id}</b>
                    <span className="cs-mono cs-dim" style={{ fontSize: 10 }}>
                      {r.item_id}
                    </span>
                    {r.mode_match && (
                      <span
                        className="cs-mono"
                        style={{ fontSize: 9, color: "#0e7490", letterSpacing: "0.1em", textTransform: "uppercase" }}
                        title={`Matches the diagnosed failure mode ${r.failure_mode}`}
                      >
                        mode match
                      </span>
                    )}
                  </div>
                  <div className="cs-dim" style={{ fontSize: 11, marginTop: 2 }}>
                    {r.purpose || "—"}
                    {r.schedule ? ` · ${r.schedule}` : ""}
                  </div>
                </div>

                <div style={{ textAlign: "right", fontSize: 11.5, lineHeight: 1.5 }}>
                  <div>
                    <span className="cs-dim">req </span>
                    <Figure value={r.required_quantity} unit={r.unit} />
                  </div>
                  <div>
                    <span className="cs-dim">avail </span>
                    <Figure value={r.inventory.available ?? null} unit={r.unit} />
                  </div>
                  <div>
                    <span className="cs-dim">safety </span>
                    <Figure value={r.inventory.safety_stock ?? null} unit={r.unit} />
                  </div>
                </div>

                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
                  <CoverageChip
                    coverage={
                      r.inventory.available === null || r.inventory.available === undefined
                        ? "UNKNOWN"
                        : r.inventory.available - r.required_quantity - (r.inventory.safety_stock ?? 0) >= 0
                          ? "COVERED"
                          : "SHORTFALL"
                    }
                  />
                  <button
                    className="cs-btn cs-btn--ghost"
                    style={{ fontSize: 11, padding: "4px 9px" }}
                    onClick={() => router.push(`/console/materials/${encodeURIComponent(r.item_id)}`)}
                  >
                    Open material
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              className="cs-btn cs-btn--primary"
              style={{ fontSize: 11.5 }}
              onClick={() => router.push(`/console/materials/spares?asset=${encodeURIComponent(equipmentId)}`)}
            >
              Check spares &amp; prepare recommendation →
            </button>
          </div>
          <p className="cs-dim" style={{ margin: "8px 0 0", fontSize: 10.5, lineHeight: 1.6 }}>
            Preparing a recommendation places no order. Any procurement requires engineer
            approval through the Approvals surface.
          </p>
        </>
      )}
    </Panel>
  );
}
