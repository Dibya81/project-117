"use client";

/**
 * Equipment Detail — flagship reusable template.
 * Header (identity, status, live KPI chips) → tabs: Overview · Sensors ·
 * Maintenance · Documents · History. Telemetry renders with threshold bands.
 */
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button, EmptyState, Kpi, Panel, SkeletonRows, StatusDot, Tabs, Tag, timeAgo } from "@/components/ui/primitives";
import { TrendChart } from "@/components/ui/TrendChart";
import { Icon } from "@/components/ui/Icon";
import { consoleData } from "@/lib/data/console";
import { EquipmentRenderer, normalizeEquipmentAsset, preferredAssetSize } from "@/components/equipment";
import { AssetQrLabel } from "@/components/equipment/AssetQrLabel";
import { EquipmentSparesPanel } from "@/components/materials/EquipmentSparesPanel";
import { useJourney } from "@/lib/journey";
import type { EquipmentDetailData } from "@/types/console";

function DetailEquipmentAsset({ data }: { data: EquipmentDetailData }) {
  const asset = normalizeEquipmentAsset(data.kind, data.name, data.id, data.registerName);
  const preferred = preferredAssetSize[asset];
  const scale = Math.min(330 / preferred.w, 250 / preferred.h);
  const box = {
    x: (360 - preferred.w * scale) / 2,
    y: (282 - preferred.h * scale) / 2 + 6,
    w: preferred.w * scale,
    h: preferred.h * scale,
  };
  return (
    <div className="cs-equipment-hero">
      <svg className="cs-equipment-hero__svg" viewBox="0 0 360 306" role="img" aria-label={`${data.name} refinery asset`}>
        <EquipmentRenderer asset={asset} kind={data.kind} name={data.name} id={data.registerTag ?? data.id} status={data.status} selected box={box} />
      </svg>
      <div className="cs-equipment-hero__meta">
        <span className="cs-mono">{data.registerTag ?? data.id}</span>
        <b>{data.name}</b>
        <small>{data.kind} · {data.zone}</small>
      </div>
    </div>
  );
}

export default function EquipmentDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = decodeURIComponent(params.id);
  const [data, setData] = useState<EquipmentDetailData | null | undefined>(undefined);
  const [tab, setTab] = useState("overview");
  const { visit } = useJourney();

  useEffect(() => {
    setData(undefined);
    consoleData.equipment.detail(id).then((d) => {
      setData(d);
      if (d) visit({ id: d.id, label: `${d.id} · ${d.name}`, kind: "equipment", href: `/console/equipment/${d.id}` });
    });
  }, [id, visit]);

  if (data === undefined) {
    return (
      <Panel>
        <SkeletonRows rows={6} />
      </Panel>
    );
  }

  if (data === null) {
    return (
      <EmptyState
        title={`No equipment “${id}”`}
        detail="It may have been renamed or removed from the registry."
        action={<Button onClick={() => router.push("/console/equipment")}>Back to equipment</Button>}
      />
    );
  }

  const tone = data.status === "ok" ? "ok" : data.status === "warning" ? "warn" : "crit";

  /** The live instrument readings for this asset. */
  const readings = data.readings ?? [];

  /**
   * An anomaly exists only when a real reading has crossed a real threshold.
   *
   * The chain below used to read `data.insight ? "pattern detected" : "none"`,
   * and `insight` is the backend's descriptive summary — present for every
   * asset ("Offloading Pump A is a pump in Crude Receiving; criticality
   * medium…"). So every healthy unit was labelled as having a detected anomaly
   * pattern, in red, at the top of its own page.
   */
  const breached = readings.filter(
    (r) => r.warnAbove != null && r.value >= r.warnAbove,
  );
  const anomaly = breached.length
    ? `${breached.length} reading${breached.length === 1 ? "" : "s"} above threshold`
    : "none";

  /** Sensor snapshot for the twin diagram. */
  const twinSensors = data.telemetry.map((t) => ({
    key: t.key,
    label: t.label,
    unit: t.unit,
    value: t.points[t.points.length - 1]?.value ?? 0,
    warnAbove: t.warnAbove,
    critAbove: t.critAbove,
  }));

  /** Chain of evidence — sensor reading to the action it produced. */
  const chain: { label: string; value: string; color: string }[] = [
    { label: "Sensors", value: `${readings.length} instrumented point${readings.length === 1 ? "" : "s"}`, color: "var(--cyan)" },
    { label: "Anomaly", value: anomaly, color: breached.length ? "var(--crit)" : "var(--ink-2)" },
    { label: "Evidence", value: `${data.documents.length} documents linked`, color: "var(--violet)" },
    { label: "AI finding", value: data.insight ? "see insight below" : "—", color: "var(--cyan)" },
    { label: "Action", value: data.open_work_orders[0] ?? "no open work order", color: "var(--warn)" },
  ];

  return (
    <>
      <div className="cs-pagehead">
        <div>
          <span className="cs-pagehead__kicker">
            <button
              onClick={() => router.push("/console/equipment")}
              style={{ background: "none", border: 0, color: "inherit", cursor: "pointer", font: "inherit", letterSpacing: "inherit", padding: 0 }}
            >
              Equipment
            </button>{" "}
            / {data.registerTag ?? data.id}
          </span>
          <h1 style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <StatusDot state={data.status} pulse={data.status !== "ok"} />
            {data.name}
            <Tag tone={tone}>{data.status.toUpperCase()}</Tag>
          </h1>
        </div>
        <div className="cs-pagehead__actions" style={{ marginLeft: "auto" }}>
          <Button variant="primary" onClick={() => router.push("/console/workspace")}>
            <Icon name="zap" size={13} /> Ask AI about {data.id}
          </Button>
        </div>
      </div>

      {/* Arrived under the register tag for the machine the console calls
          something else — say so rather than silently rewriting the URL. */}
      {data.registerTag && data.mappingConfidence && (
        <div className="cs-crosswalk" role="note">
          <span className={`cs-crosswalk__tag cs-crosswalk__tag--${data.mappingConfidence}`}>
            {data.mappingConfidence === "exact" ? "exact match" : data.mappingConfidence === "twin" ? "register twin" : "partial match"}
          </span>
          <span>
            <b>{data.registerTag}</b> is the simulation-register designation for{" "}
            <b>{data.id}</b>{data.registerName ? ` (${data.registerName})` : ""}.
          </span>
          {data.mappingBasis && <em>{data.mappingBasis}</em>}
          <button onClick={() => router.push(`/console/knowledge?entity=${encodeURIComponent(`${data.id}`)}`)}>
            Open in knowledge graph →
          </button>
        </div>
      )}

      <div className="cs-kpis" style={{ marginBottom: 18 }}>
        {data.kpis.map((k) => (
          <Kpi key={k.label} label={k.label} value={k.value} state={k.state} />
        ))}
      </div>

      {/* The physical label for this machine. The symbol is the backend's SVG
          (namespaced `P117:EQUIP:<tag>` payload, resolved only by the Project
          117 app) and the tag is printed beneath it, so a scuffed code is still
          readable. "Print label" opens the printable sheet for this asset. */}
      <Panel title="Asset QR label" style={{ marginBottom: 18 }}>
        <AssetQrLabel
          id={data.id}
          tag={data.tag ?? data.registerTag ?? data.id}
          name={data.name}
          zone={data.zone}
        />
      </Panel>

      <Panel pad={false}>
        <div style={{ padding: "12px 16px 0" }}>
          <Tabs
            tabs={[
              { id: "overview", label: "Overview" },
              { id: "sensors", label: "Sensors", count: readings.length },
              { id: "maintenance", label: "Maintenance", count: data.maintenance.length },
              { id: "documents", label: "Documents", count: data.documents.length },
              { id: "history", label: "History", count: data.history.length },
            ]}
            active={tab}
            onChange={setTab}
          />
        </div>
        <div className="cs-panel__body">
          {tab === "overview" && (
            <div className="cs-stack">
              <div className="cs-grid-2" style={{ gridTemplateColumns: "minmax(0, 1.15fr) minmax(0, 1fr)" }}>
                <Panel title="Refinery asset" hud pad={false}>
                  <DetailEquipmentAsset data={data} />
                  <div className="cs-equipment-sensor-strip">
                    {twinSensors.length === 0 ? (
                      <button type="button" onClick={() => setTab("sensors")}>No live sensor readings available</button>
                    ) : (
                      twinSensors.map((s) => {
                        const state = s.critAbove != null && s.value >= s.critAbove ? "critical" : s.warnAbove != null && s.value >= s.warnAbove ? "warning" : "ok";
                        return (
                          <button key={s.key} type="button" onClick={() => setTab("sensors")} className={`cs-equipment-sensor cs-equipment-sensor--${state}`}>
                            <StatusDot state={state} pulse={state === "critical"} />
                            <span>{s.label}</span>
                            <b className="cs-mono">{s.value} {s.unit}</b>
                          </button>
                        );
                      })
                    )}
                  </div>
                </Panel>
                <Panel title="Chain of evidence" pad>
                  <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
                    {chain.map((item, i) => (
                      <div key={item.label} style={{ display: "flex", gap: 12, animation: `p117-fade-up 500ms var(--ease-out) ${i * 110}ms both` }}>
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 14 }}>
                          <span style={{ width: 8, height: 8, borderRadius: "50%", background: item.color, boxShadow: `0 0 8px ${item.color}`, marginTop: 5 }} />
                          {i < chain.length - 1 && <span style={{ flex: 1, width: 1, background: "var(--line-2)", minHeight: 16 }} />}
                        </div>
                        <div style={{ paddingBottom: 14 }}>
                          <div className="cs-mono" style={{ fontSize: 8.5, letterSpacing: "0.26em", textTransform: "uppercase", color: item.color }}>
                            {item.label}
                          </div>
                          <div style={{ fontSize: 12.5, color: "var(--ink-2)", marginTop: 2 }}>{item.value}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </Panel>
              </div>
              {data.insight && (
                <div
                  style={{
                    padding: "14px 16px",
                    border: "1px solid rgba(69,213,255,0.3)",
                    borderRadius: 10,
                    background: "linear-gradient(120deg, rgba(69,213,255,0.09), transparent)",
                    animation: "p117-fade-up 480ms var(--ease-out) both",
                  }}
                >
                  <p className="cs-mono cs-text-cyan" style={{ margin: "0 0 6px", fontSize: 9.5, letterSpacing: "0.3em", textTransform: "uppercase" }}>
                    <Icon name="zap" size={11} /> AI insight
                  </p>
                  <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--ink-1)" }}>{data.insight}</p>
                </div>
              )}
              <div className="cs-grid-2">
                <Panel title="Related equipment" pad={false}>
                  {data.related.map((r) => (
                    <button
                      key={r.id}
                      className="cs-row"
                      style={{ width: "100%", background: "none", border: "0", font: "inherit", textAlign: "left" }}
                      onClick={() => router.push(`/console/equipment/${r.id}`)}
                    >
                      <Icon name="equipment" size={14} />
                      <span>
                        <div className="cs-row__title">{r.name}</div>
                        <div className="cs-row__sub">{r.relation}</div>
                      </span>
                      <span className="cs-row__meta cs-mono cs-text-cyan" style={{ fontSize: 11 }}>{r.id}</span>
                    </button>
                  ))}
                </Panel>
                <Panel title="Open work orders" pad={false}>
                  {data.open_work_orders.length === 0 && <p className="cs-dim" style={{ padding: 16, margin: 0, fontSize: 12.5 }}>None open.</p>}
                  {data.open_work_orders.map((w) => (
                    <button
                      key={w}
                      className="cs-row"
                      style={{ width: "100%", background: "none", border: "0", font: "inherit", textAlign: "left" }}
                      onClick={() => router.push(`/console/work-orders/${w}`)}
                    >
                      <Icon name="workorder" size={14} />
                      <span className="cs-row__title cs-mono">{w}</span>
                      <span className="cs-row__meta"><Icon name="chevron" size={12} /></span>
                    </button>
                  ))}
                </Panel>
              </div>
            </div>
          )}

          {tab === "sensors" && (
            <div className="cs-grid-2">
              {data.telemetry.map((s) => {
                const latest = s.points[s.points.length - 1]?.value ?? 0;
                const state = s.critAbove != null && latest >= s.critAbove ? "crit" : s.warnAbove != null && latest >= s.warnAbove ? "warn" : "ok";
                return (
                  <Panel key={s.key} title={`${s.label} — ${s.unit}`} pad glow={state !== "ok"}>
                    <TrendChart
                      points={s.points}
                      threshold={s.warnAbove}
                      critThreshold={s.critAbove}
                      unit={s.unit}
                      tone={state === "crit" ? "red" : state === "warn" ? "amber" : "cyan"}
                      live
                    />
                  </Panel>
                );
              })}
            </div>
          )}

          {tab === "maintenance" && (
            /* Required spares for this asset — the top of the materials chain,
               surfaced where an engineer planning the job already is:
               EQUIPMENT → REQUIREMENT → SPARE → INVENTORY → COVERAGE.
               The component existed but was never mounted on any page, so the
               chain stopped one hop short of the user. */
            <EquipmentSparesPanel equipmentId={id} />
          )}

          {tab === "maintenance" && (
            <div className="cs-trace">
              {data.maintenance.map((m, i) => (
                <div key={m.id} className="cs-trace__row" style={{ animationDelay: `${i * 90}ms` }}>
                  <StatusDot state="ok" />
                  <span>
                    <div>{m.title}</div>
                    <div className="cs-trace__detail">by {m.by}</div>
                  </span>
                  <span className="cs-trace__ms">{m.id} · {m.at}</span>
                </div>
              ))}
            </div>
          )}

          {tab === "documents" && (
            <div className="cs-fade-list" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {data.documents.map((d) => (
                <button
                  key={d.id}
                  className="cs-row"
                  style={{ border: "1px solid var(--line)", borderRadius: 8, background: "rgba(6,10,16,0.5)", font: "inherit", textAlign: "left" }}
                  onClick={() => router.push(`/console/documents?doc=${d.id}`)}
                >
                  <Icon name="doc" size={14} />
                  <span className="cs-row__title cs-mono" style={{ fontSize: 12 }}>{d.filename}</span>
                  <span className="cs-row__meta"><Tag>{d.kind}</Tag></span>
                </button>
              ))}
            </div>
          )}

          {tab === "history" && (
            <div className="cs-timeline" style={{ marginLeft: 8, paddingTop: 6 }}>
              {data.history.length === 0 && <p className="cs-dim" style={{ fontSize: 12.5 }}>No recorded events for this asset.</p>}
              {data.history.map((h, i) => (
                <div key={h.id} className="cs-tl-item" style={{ animationDelay: `${i * 90}ms` }}>
                  <strong style={{ fontSize: 13 }}>{h.title}</strong>
                  <p className="cs-dim" style={{ margin: "3px 0", fontSize: 12 }}>{h.detail}</p>
                  <p className="cs-mono" style={{ margin: 0, fontSize: 10, color: "var(--ink-3)" }}>
                    {timeAgo(h.at)} · {h.actor}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </Panel>
    </>
  );
}
