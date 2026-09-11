/**
 * Document field content.
 *
 * These are verbatim excerpts from Project 117's own knowledge corpus
 * (`data/knowledge/*.md` and `data/demo/**`). The Documents page renders them
 * as pages moving through space — the archive is the refinery's real
 * documentation, not stock imagery.
 *
 * When the generated 5-year knowledge base is present its sections are appended
 * from `public/knowledge/refinery-document.json` (see
 * `scripts/generate_refinery_document.py`).
 */

export type PageKind = "procedure" | "inspection" | "baseline" | "manual" | "record" | "register";

export interface DocPage {
  id: string;
  doc: string;
  section: string;
  kind: PageKind;
  /** Body lines, rendered as text on the page when it is large enough. */
  lines: string[];
  /** Optional table: first row is the header. */
  table?: string[][];
  /** Tags/ids the scan pass lights up — these become graph entities. */
  entities: string[];
}

export const CORPUS_PAGES: DocPage[] = [
  {
    id: "ir-204",
    doc: "IR-204_compressor_inspection.pdf",
    section: "Recycle Gas Compressor C-3 — Vibration Inspection",
    kind: "inspection",
    lines: [
      "Equipment: C-3 Recycle Gas Compressor (Elliott 29M9-6)",
      "Date of survey: 2026-09-06 · Reliability Engineering",
      "Instrument: portable analyser, tri-axial accelerometer, DE and NDE housings",
      "Overall DE vibration 6.8 mm/s RMS against a 90-day baseline of 5.8 mm/s.",
      "Increase of 18%, developed progressively over eight days — not a step change.",
      "Alarm limit for this machine is 7.1 mm/s (manual excerpt, Table 7-2).",
    ],
    table: [
      ["Frequency", "Amplitude", "Interpretation"],
      ["1x running (49.6 Hz)", "4.9 mm/s", "dominant; rising"],
      ["2x running", "1.1 mm/s", "stable"],
      ["Bearing defect (BPFO)", "0.6 mm/s", "slightly elevated"],
    ],
    entities: ["C-3", "6.8 mm/s", "IR-204", "Table 7-2", "49.6 Hz"],
  },
  {
    id: "baseline-c3",
    doc: "vibration_baseline_C-3.xlsx",
    section: "C-3 Vibration Baseline — 90-day rolling window",
    kind: "baseline",
    lines: [
      "Baseline in force for alarm evaluation: 5.80 mm/s (established 2026-09-07).",
      "Alert threshold from manual Table 7-2: 5.8 mm/s.",
      "Alarm threshold: 7.1 mm/s.",
      "Latest reading at export: 6.8 mm/s (2026-09-06 survey, IR-204).",
    ],
    table: [
      ["Window", "Mean mm/s", "P95", "Samples"],
      ["2026-06-09 → 2026-09-07", "5.80", "6.05", "2160"],
      ["2026-03-09 → 2026-06-08", "5.74", "5.98", "2184"],
      ["2025-12-09 → 2026-03-08", "5.69", "5.91", "2160"],
    ],
    entities: ["C-3", "5.80 mm/s", "7.1 mm/s", "IR-204", "2160 samples"],
  },
  {
    id: "sop-07-3",
    doc: "SOP-07.3_rev4.pdf",
    section: "Rotating Equipment Vibration Monitoring",
    kind: "procedure",
    lines: [
      "Scope: all rotating equipment on process service.",
      "§4 Baseline verification — establish a rolling 90-day baseline before",
      "any alarm evaluation. Do not evaluate against a single historical point.",
      "§5 Rising trend — a sustained rise above the alert threshold with stable",
      "2x content indicates bearing wear or an alignment shift.",
      "§6 Action — raise a work order for inspection at the next low-demand window.",
    ],
    entities: ["SOP-07.3", "§4 Baseline", "§5 Rising trend", "§6 Action", "C-3"],
  },
  {
    id: "sop-22-1",
    doc: "SOP-22.1_pump_bearing.pdf",
    section: "Centrifugal Pump Bearing Overheat and Vibration",
    kind: "procedure",
    lines: [
      "Scope: centrifugal pumps and drivers showing rising bearing temperature,",
      "rising vibration, or both, on any process service.",
      "Assessment: compare bearing temperature against the vibration trend.",
      "Temperature rising with vibration indicates mechanical bearing degradation.",
      "Temperature rising alone with stable vibration usually indicates",
      "lubrication loss or a cooling problem on the bearing housing.",
      "Immediate: reduce load, confirm the parallel path can carry the duty.",
    ],
    entities: ["SOP-22.1", "P-1042", "bearing temperature", "rev5"],
  },
  {
    id: "sop-14-2",
    doc: "SOP-14.2.pdf",
    section: "Instrument Failure Response",
    kind: "procedure",
    lines: [
      "Scope: primary measurement elements reporting BAD quality.",
      "Isolate the failed element and confirm the redundant instrument is",
      "healthy before continuing on single-element control.",
      "Inspection interval for crude-feed-line isolation work: 90 days.",
      "Revision note: interval under review following three anomalies in two",
      "quarters (see APR-218, anomaly review 2026-08).",
    ],
    entities: ["SOP-14.2", "P-1042", "90 days", "APR-218", "BAD quality"],
  },
  {
    id: "me-198",
    doc: "ME-198_maintenance_record.pdf",
    section: "C-3 Drive-End Bearing Replacement",
    kind: "record",
    lines: [
      "Work order: WO-8802 · Completed and verified.",
      "Task: replace drive-end bearing on C-3 recycle gas compressor.",
      "Post-work baseline recorded at 5.7 mm/s at 8,800 rpm.",
      "Disposition: clearance in tolerance; no coupling work required.",
      "This baseline is the reference for all subsequent C-3 evaluations.",
    ],
    table: [
      ["Parameter", "Before", "After"],
      ["DE vibration", "6.9 mm/s", "5.7 mm/s"],
      ["DE bearing temp", "82 °C", "68 °C"],
      ["RPM", "8,800", "8,800"],
    ],
    entities: ["ME-198", "C-3", "WO-8802", "5.7 mm/s", "8,800 rpm"],
  },
  {
    id: "c3-manual",
    doc: "C-3_compressor_manual_excerpt.pdf",
    section: "Elliott 29M9-6 — Alarm Limits and Service Conditions",
    kind: "manual",
    lines: [
      "Service: recycle gas, hydrotreater U-200.",
      "Rated speed 8,800 rpm. Rated discharge pressure 21.4 bar.",
      "Table 7-2 alarm limits: vibration alert 5.8 mm/s, alarm 7.1 mm/s.",
      "Bearing temperature alarm 95 °C, trip 105 °C.",
      "Lubrication: ISO VG 46, change interval 8,000 operating hours.",
    ],
    table: [
      ["Parameter", "Alert", "Alarm", "Trip"],
      ["Vibration RMS", "5.8 mm/s", "7.1 mm/s", "—"],
      ["Bearing temp", "85 °C", "95 °C", "105 °C"],
      ["Oil pressure", "1.8 bar", "1.5 bar", "1.2 bar"],
    ],
    entities: ["C-3", "Elliott 29M9-6", "Table 7-2", "8,800 rpm", "ISO VG 46"],
  },
  {
    id: "p1042",
    doc: "pump_curve_P-1042.png",
    section: "P-1042 Crude Feed Pump — Performance Curve",
    kind: "register",
    lines: [
      "Duty: crude feed to desalter, 140 m³/h at 17 bar discharge.",
      "Operating point has drifted 6% from the design curve since Q2.",
      "19 of the last 24 hourly readings exceeded the 17 bar alert threshold.",
      "SOP-14.2 requires redundant instrument confirmation before action.",
    ],
    entities: ["P-1042", "P-1042A", "17 bar", "SOP-14.2", "140 m³/h"],
  },
  {
    id: "register",
    doc: "REFINERY-TECHNICAL-KNOWLEDGE-BASE.md",
    section: "Section 4 — Equipment Register",
    kind: "register",
    lines: [
      "58 process units across 18 operating areas.",
      "Criticality A: C-3, P-1001, P-1042, COL-1044, F-1043, VS-1046.",
      "All units commissioned 2021-06 unless noted.",
      "Next maintenance windows derived from the 5-year operating history.",
    ],
    table: [
      ["Tag", "Kind", "Area", "Crit", "Health"],
      ["C-3", "compressor", "Compression", "A", "82"],
      ["P-1042", "pump", "Crude receiving", "A", "74"],
      ["E-340", "exchanger", "Distillation", "B", "88"],
      ["TK-1101", "tank", "Crude storage", "B", "91"],
    ],
    entities: ["C-3", "P-1042", "E-340", "TK-1101", "18 areas"],
  },
];

export const KIND_LABEL: Record<PageKind, string> = {
  procedure: "Procedure",
  inspection: "Inspection",
  baseline: "Baseline",
  manual: "Manual",
  record: "Record",
  register: "Register",
};

/**
 * Fetch the generated refinery document sections, if the generator has been
 * run. Failure is not an error — the corpus above is always available.
 */
export async function loadGeneratedPages(): Promise<DocPage[]> {
  try {
    const r = await fetch("/knowledge/refinery-document.json");
    if (!r.ok) return [];
    const data = (await r.json()) as {
      sections?: { slug: string; title: string; lines?: string[]; table?: string[][]; entities?: string[] }[];
    };
    return (data.sections ?? []).slice(0, 22).map((s) => ({
      id: s.slug,
      doc: "REFINERY-TECHNICAL-KNOWLEDGE-BASE.md",
      section: s.title,
      kind: "register" as PageKind,
      lines: (s.lines ?? []).slice(0, 7),
      table: s.table,
      entities: (s.entities ?? []).slice(0, 6),
    }));
  } catch {
    return [];
  }
}
