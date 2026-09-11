"use client";

/**
 * Equipment — zone-grouped asset explorer, status-sorted.
 * Each card: identity, live sensor chips, health ring, insight. Click → detail.
 */
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Panel, Ring, SkeletonRows, StatusDot, Tag } from "@/components/ui/primitives";
import { Tilt } from "@/components/fx/Tilt";
import { Icon } from "@/components/ui/Icon";
import { consoleData } from "@/lib/data/console";
import type { Equipment, HealthState } from "@/types";

const STATUS_RANK: Record<HealthState, number> = { critical: 0, warning: 1, ok: 2, unknown: 3 };

/** Health score heuristic from sensor threshold proximity. */
function healthOf(e: Equipment): number {
  let worst = 100;
  for (const s of e.sensors) {
    if (s.critAbove && s.value >= s.critAbove) worst = Math.min(worst, 35);
    else if (s.warnAbove && s.value >= s.warnAbove) worst = Math.min(worst, 62);
    else if (s.warnAbove && s.value >= s.warnAbove * 0.92) worst = Math.min(worst, 80);
  }
  return worst;
}

function ringTone(h: number): "ok" | "warn" | "crit" {
  return h >= 85 ? "ok" : h >= 65 ? "warn" : "crit";
}

export default function EquipmentPage() {
  const router = useRouter();
  const [equipment, setEquipment] = useState<Equipment[] | null>(null);
  const [zoneFilter, setZoneFilter] = useState("all");
  const [attention, setAttention] = useState(false);

  useEffect(() => {
    consoleData.equipment.list().then(setEquipment);
  }, []);

  const zones = useMemo(() => Array.from(new Set((equipment ?? []).map((e) => e.zone))), [equipment]);

  const sorted = useMemo(
    () =>
      (equipment ?? [])
        .filter((e) => zoneFilter === "all" || e.zone === zoneFilter)
        .slice()
        .sort((a, b) =>
          attention
            ? healthOf(a) - healthOf(b) // lowest health first = highest attention
            : STATUS_RANK[a.status] - STATUS_RANK[b.status],
        ),
    [equipment, zoneFilter, attention],
  );

  return (
    <>
      <div className="cs-pagehead">
        <div>
          <span className="cs-pagehead__kicker">Plant</span>
          <h1>Equipment</h1>
        </div>
        <div className="cs-pagehead__actions" style={{ marginLeft: "auto" }}>
          <button
            className={`cs-btn${attention ? " cs-btn--primary" : " cs-btn--ghost"}`}
            onClick={() => setAttention((v) => !v)}
            aria-pressed={attention}
            title="Rank by risk, anomaly, maintenance urgency and operational impact"
          >
            <Icon name="zap" size={13} /> AI attention
          </button>
          <select
            className="cs-select"
            style={{ width: 220 }}
            value={zoneFilter}
            onChange={(e) => setZoneFilter(e.target.value)}
            aria-label="Filter by zone"
          >
            <option value="all">All zones</option>
            {zones.map((z) => (
              <option key={z} value={z}>{z}</option>
            ))}
          </select>
        </div>
      </div>

      {!equipment ? (
        <Panel><SkeletonRows rows={6} label="Synchronizing telemetry…" /></Panel>
      ) : (
        <div className="cs-eqgrid cs-fade-list">
          {sorted.map((e) => {
            const health = healthOf(e);
            return (
              <Tilt key={e.id} max={5}>
                <div
                  className={`cs-eqcard cs-eqcard--${e.status}`}
                  onClick={() => router.push(`/console/equipment/${e.id}`)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(ev) => ev.key === "Enter" && router.push(`/console/equipment/${e.id}`)}
                  aria-label={`Open ${e.name}`}
                >
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                        <StatusDot state={e.status} pulse={e.status === "critical"} />
                        <span className="cs-mono cs-text-cyan" style={{ fontSize: 12, fontWeight: 700 }}>{e.id}</span>
                        <Tag>{e.kind}</Tag>
                        {attention && (
                          <Tag tone={health < 65 ? "crit" : health < 85 ? "warn" : "ok"}>
                            attention #{sorted.indexOf(e) + 1}
                          </Tag>
                        )}
                      </div>
                      <h3 style={{ margin: "8px 0 3px", fontSize: 15.5, letterSpacing: "-0.01em" }}>{e.name}</h3>
                      <p className="cs-mono cs-dim" style={{ margin: 0, fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase" }}>
                        {e.zone}
                      </p>
                    </div>
                    <Ring value={health} tone={ringTone(health)} size={58} label={`health ${health}`} />
                  </div>

                  <div style={{ display: "flex", gap: 7, flexWrap: "wrap", margin: "14px 0 0" }}>
                    {e.sensors.map((s) => {
                      const hot = (s.critAbove != null && s.value >= s.critAbove) || (s.warnAbove != null && s.value >= s.warnAbove);
                      return (
                        <span key={s.key} className={`cs-tag${hot ? " cs-tag--warn" : ""}`}>
                          {s.label} <b className="cs-mono">{s.value} {s.unit}</b>
                        </span>
                      );
                    })}
                  </div>

                  {e.insight && (
                    <p
                      style={{
                        margin: "13px 0 0",
                        padding: "9px 12px",
                        fontSize: 12,
                        lineHeight: 1.55,
                        color: "var(--ink-2)",
                        borderLeft: "2px solid var(--cyan)",
                        background: "rgba(69,213,255,0.05)",
                        borderRadius: "0 6px 6px 0",
                      }}
                    >
                      <Icon name="zap" size={11} /> {e.insight}
                    </p>
                  )}

                  <div className="cs-mono cs-dim" style={{ marginTop: 13, fontSize: 10, display: "flex", justifyContent: "space-between" }}>
                    <span>inspected {e.last_inspection ?? "—"}</span>
                    <span className="cs-text-cyan">OPEN →</span>
                  </div>
                </div>
              </Tilt>
            );
          })}
        </div>
      )}
    </>
  );
}
