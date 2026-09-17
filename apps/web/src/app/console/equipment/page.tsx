"use client";

/**
 * Equipment — zone-grouped asset explorer, status-sorted.
 * Each card: 3D tilt surface with identity, live sensor chips, health ring,
 * insight and per-instrument trend strips (see SensorTrend for the data note).
 * Click → detail.
 */
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { EmptyState, Panel, SkeletonRows } from "@/components/ui/primitives";
import { Icon } from "@/components/ui/Icon";
import { Lucide } from "@/components/ui/LucideIcon";
import { EquipmentTiltCard, STATUS_RANK, healthOf } from "@/components/equipment/EquipmentTiltCard";
import { consoleData } from "@/lib/data/console";
import type { Equipment } from "@/types";

export default function EquipmentPage() {
  const router = useRouter();
  const [equipment, setEquipment] = useState<Equipment[] | null>(null);
  const [zoneFilter, setZoneFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [attention, setAttention] = useState(false);

  useEffect(() => {
    consoleData.equipment.list().then(setEquipment);
  }, []);

  const zones = useMemo(() => Array.from(new Set((equipment ?? []).map((e) => e.zone))), [equipment]);

  const sorted = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (equipment ?? [])
      .filter((e) => zoneFilter === "all" || e.zone === zoneFilter)
      .filter(
        (e) =>
          !needle ||
          e.name.toLowerCase().includes(needle) ||
          e.id.toLowerCase().includes(needle) ||
          e.kind.toLowerCase().includes(needle) ||
          e.zone.toLowerCase().includes(needle),
      )
      .slice()
      .sort((a, b) =>
        attention
          ? healthOf(a) - healthOf(b) // lowest health first = highest attention
          : STATUS_RANK[a.status] - STATUS_RANK[b.status],
      );
  }, [equipment, zoneFilter, attention, query]);

  return (
    <>
      <div className="cs-pagehead">
        <div>
          <span className="cs-pagehead__kicker">Plant</span>
          <h1>Equipment</h1>
        </div>
        <div className="cs-pagehead__actions" style={{ marginLeft: "auto" }}>
          <div className="cs-eqsearch">
            <Lucide name="search" size={13} className="cs-eqsearch__glyph" />
            <input
              className="cs-eqsearch__input"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search tag, name, zone…"
              aria-label="Search equipment"
              data-equipment-search
            />
            {query && (
              <button
                type="button"
                className="cs-eqsearch__clear"
                onClick={() => setQuery("")}
                aria-label="Clear search"
              >
                <Lucide name="x" size={12} />
              </button>
            )}
          </div>
          <Link
            className="cs-btn cs-btn--ghost"
            href="/console/equipment/labels"
            title="Printable QR labels for every asset"
          >
            <Lucide name="printer" size={13} /> QR labels
          </Link>
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
      ) : sorted.length === 0 ? (
        <Panel>
          <EmptyState
            title="No equipment matches"
            detail={
              equipment.length === 0
                ? "The plant register returned no assets."
                : `No asset matches the current search and zone filter (${equipment.length} asset${equipment.length === 1 ? "" : "s"} in the register).`
            }
            action={
              (query || zoneFilter !== "all") ? (
                <button
                  className="cs-btn cs-btn--ghost"
                  onClick={() => {
                    setQuery("");
                    setZoneFilter("all");
                  }}
                >
                  Clear filters
                </button>
              ) : undefined
            }
          />
        </Panel>
      ) : (
        <div className="cs-eqgrid cs-fade-list" data-equipment-count={sorted.length}>
          {sorted.map((e) => (
            <EquipmentTiltCard
              key={e.id}
              equipment={e}
              {...(attention ? { attentionRank: sorted.indexOf(e) + 1 } : {})}
              onOpen={() => router.push(`/console/equipment/${e.id}`)}
            />
          ))}
        </div>
      )}
    </>
  );
}
