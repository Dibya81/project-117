/** Console mock data part 2 — equipment detail + insights series. */
import type { EquipmentDetailData, InsightSeries } from "@/types/console";
import { EQUIPMENT, HISTORY, WORK_ORDERS } from "./console";

function series(base: number, drift: number, points = 60): { t: number; value: number }[] {
  const out: { t: number; value: number }[] = [];
  const t0 = Date.now() - points * 3600000;
  let v = base;
  for (let i = 0; i < points; i++) {
    v += drift + Math.sin(i / 5) * base * 0.012;
    out.push({ t: t0 + i * 3600000, value: Number(v.toFixed(2)) });
  }
  return out;
}

export function equipmentDetail(id: string): EquipmentDetailData | null {
  if (id === "C-3") {
    return {
      id: "C-3", name: "Recycle Gas Compressor", kind: "compressor", zone: "Unit 300 — Compression",
      status: "warning",
      kpis: [
        { label: "Vibration", value: "6.8 mm/s", state: "warning" },
        { label: "Speed", value: "8,840 rpm", state: "ok" },
        { label: "Bearing temp", value: "79 °C", state: "ok" },
        { label: "Health", value: "82 / 100", state: "warning" },
      ],
      insight: "Vibration trending up 18% over 30 days. Pattern consistent with early drive-end bearing wear. Inspection recommended within 14 days (SOP-07.3 §4).",
      telemetry: [
        { key: "vibration", label: "Vibration", unit: "mm/s", warnAbove: 7.1, critAbove: 11, points: series(5.7, 0.018) },
        { key: "temperature", label: "Bearing Temperature", unit: "°C", warnAbove: 85, points: series(76, 0.02) },
        { key: "rpm", label: "Speed", unit: "rpm", critAbove: 10500, points: series(8800, 0.6) },
      ],
      maintenance: [
        { id: "ME-198", title: "Drive-end bearing replacement", at: "2026-04-14", by: "maintenance" },
        { id: "ME-174", title: "Coupling alignment", at: "2025-11-02", by: "maintenance" },
      ],
      documents: [
        { id: "d-7", filename: "IR-204_compressor_inspection.pdf", kind: "Inspection" },
        { id: "d-4", filename: "SOP-07.3_rev4.pdf", kind: "SOP" },
        { id: "d-5", filename: "vibration_baseline_C-3.xlsx", kind: "Data" },
        { id: "d-3", filename: "maintenance_history_C-3.csv", kind: "History" },
      ],
      history: HISTORY.filter((h) => h.equipment_id === "C-3"),
      related: [
        { id: "V-2210", name: "Anti-surge Valve", relation: "protects" },
        { id: "T-118", name: "Feed Surge Tank", relation: "upstream" },
      ],
      open_work_orders: ["WO-8852"],
    };
  }
  const eq = EQUIPMENT.find((e) => e.id === id);
  if (!eq) return null;
  return {
    id: eq.id, name: eq.name, kind: eq.kind, zone: eq.zone, status: eq.status,
    kpis: eq.sensors.map((s) => ({
      label: s.label,
      value: `${s.value} ${s.unit}`,
      state: s.critAbove && s.value >= s.critAbove ? "critical" : s.warnAbove && s.value >= s.warnAbove ? "warning" : "ok",
    })),
    insight: eq.insight,
    telemetry: eq.sensors.map((s) => ({
      key: s.key, label: s.label, unit: s.unit, warnAbove: s.warnAbove, critAbove: s.critAbove,
      points: series(s.value * 0.94, 0.001),
    })),
    maintenance: [{ id: "ME-201", title: "Routine inspection", at: eq.last_inspection ?? "2026-07-01", by: "maintenance" }],
    documents: [{ id: "d-1", filename: "inspection_report_aug.pdf", kind: "Inspection" }],
    history: HISTORY.filter((h) => h.equipment_id === eq.id),
    related: [{ id: "C-3", name: "Recycle Gas Compressor", relation: "same train" }],
    open_work_orders: WORK_ORDERS.filter((w) => w.equipment_id === eq.id && w.status !== "completed").map((w) => w.id),
  };
}

export const INSIGHTS: InsightSeries[] = [
  {
    id: "anomalies", question: "Are anomalies increasing?", summary: "3 this week vs 1.4 weekly average — elevated, driven by Unit 300.",
    unit: "anomalies / day", threshold: 0.4,
    points: series(0.2, 0.004, 30).map((p, i) => ({ ...p, value: Math.max(0, p.value + (i > 24 ? 0.25 : 0)) })),
  },
  {
    id: "effort", question: "Where is maintenance effort going?", summary: "Rotating equipment takes 58% of hours this quarter.",
    unit: "hours", points: series(40, 0.2, 12),
    table: [
      { label: "Compressors", value: "34 h", state: "warning" },
      { label: "Pumps", value: "22 h" },
      { label: "Valves", value: "14 h", state: "warning" },
      { label: "Exchangers", value: "9 h" },
    ],
  },
  {
    id: "degrading", question: "Which assets are degrading?", summary: "C-3 and P-1042 health scores fell fastest over 30 days.",
    unit: "health score", threshold: 75, points: series(91, -0.35, 30),
    table: [
      { label: "C-3", value: "82 (−9)", state: "warning" },
      { label: "P-1042", value: "79 (−11)", state: "warning" },
      { label: "V-2210", value: "64 (−3)", state: "critical" },
      { label: "E-340", value: "93 (+1)", state: "ok" },
    ],
  },
  {
    id: "workforce", question: "What did the AI workforce do?", summary: "47 tasks this week · 96% verified · 2 awaiting approval.",
    unit: "tasks / day", points: series(5.4, 0.05, 30),
    table: [
      { label: "Maintenance Agent", value: "19 tasks · 95% ✓" },
      { label: "Operations Agent", value: "14 tasks · 100% ✓" },
      { label: "Data Analysis Agent", value: "9 tasks · 89% ✓" },
      { label: "Documentation Agent", value: "5 tasks · 100% ✓" },
    ],
  },
];
