/**
 * Console mock data — realistic demo dataset for the workbench.
 * Typed against types/console.ts + types/index.ts, served through
 * lib/data/console.ts. Pages never import this file directly.
 * Demo story: C-3 vibration investigation, P-1042 pressure, V-2210 valve.
 */
import type {
  AdminUser,
  Alert,
  AuditEvent,
  HistoryEvent,
  LearnedRule,
  ModelStatus,
  NotificationItem,
  SystemPosture,
  WorkspaceSession,
  WorkspaceTask,
} from "@/types/console";
import type {
  AgentDescriptor,
  ApprovalRequest,
  ArtifactRecord,
  DocumentRecord,
  Equipment,
  GraphEdge,
  GraphNode,
  WorkOrder,
} from "@/types";

const t = (minsAgo: number) => new Date(Date.now() - minsAgo * 60000).toISOString();

export const EQUIPMENT: Equipment[] = [
  {
    id: "C-3", name: "Recycle Gas Compressor", kind: "compressor", zone: "Unit 300 — Compression",
    status: "warning", position: [9, 0, -6],
    sensors: [
      { key: "vibration", label: "Vibration", unit: "mm/s", value: 6.8, warnAbove: 7.1, critAbove: 11 },
      { key: "rpm", label: "Speed", unit: "rpm", value: 8840, critAbove: 10500 },
      { key: "temperature", label: "Bearing Temp", unit: "°C", value: 79, warnAbove: 85, critAbove: 95 },
    ],
    last_inspection: "2026-08-02",
    insight: "Vibration trending up 18% over 30 days. Pattern consistent with early bearing wear.",
  },
  {
    id: "P-1042", name: "Crude Feed Pump", kind: "pump", zone: "Unit 200 — Distillation",
    status: "warning", position: [0, 0, 0],
    sensors: [
      { key: "pressure", label: "Discharge Pressure", unit: "bar", value: 18.5, warnAbove: 17, critAbove: 21 },
      { key: "temperature", label: "Bearing Temp", unit: "°C", value: 73, warnAbove: 85, critAbove: 95 },
    ],
    last_inspection: "2026-08-14",
    insight: "Discharge pressure above the 17 bar threshold set by Engineering on 12 Aug.",
  },
  {
    id: "V-2210", name: "Anti-surge Valve", kind: "valve", zone: "Unit 300 — Compression",
    status: "critical", position: [-6, 0, 6],
    sensors: [{ key: "position", label: "Opening", unit: "%", value: 87 }],
    insight: "Valve opening stuck above 85% for 40 minutes — possible actuator fault.",
  },
  {
    id: "T-118", name: "Feed Surge Tank", kind: "tank", zone: "Unit 200 — Distillation",
    status: "ok", position: [-8, 0, -4],
    sensors: [
      { key: "level", label: "Level", unit: "%", value: 62 },
      { key: "temperature", label: "Temperature", unit: "°C", value: 41 },
    ],
    last_inspection: "2026-08-20",
  },
  {
    id: "E-340", name: "Feed/Effluent Exchanger", kind: "exchanger", zone: "Unit 200 — Distillation",
    status: "ok", position: [5, 0, 5],
    sensors: [
      { key: "temperature", label: "Outlet Temp", unit: "°C", value: 188 },
      { key: "flow", label: "Flow", unit: "t/h", value: 96 },
    ],
    last_inspection: "2026-07-30",
  },
  {
    id: "P-2051", name: "Lean Oil Pump", kind: "pump", zone: "Unit 400 — Treating",
    status: "ok", position: [12, 0, 3],
    sensors: [{ key: "pressure", label: "Discharge Pressure", unit: "bar", value: 11.2, warnAbove: 15 }],
    last_inspection: "2026-08-25",
  },
];

export const ALERTS: Alert[] = [
  { id: "AL-301", severity: "critical", equipment_id: "V-2210", title: "V-2210 actuator unresponsive", detail: "Opening stuck at 87% for 40 min", at: t(38), acknowledged: false },
  { id: "AL-298", severity: "warning", equipment_id: "C-3", title: "C-3 vibration above trend", detail: "6.8 mm/s, +18% over 30-day baseline", at: t(64), acknowledged: false },
  { id: "AL-297", severity: "warning", equipment_id: "P-1042", title: "P-1042 discharge pressure high", detail: "18.5 bar > 17 bar threshold", at: t(180), acknowledged: false },
  { id: "AL-291", severity: "info", equipment_id: "E-340", title: "E-340 fouling check due", detail: "Quarterly inspection window opens in 5 days", at: t(1400), acknowledged: true },
];

export const NOTIFICATIONS: NotificationItem[] = [
  { id: "n-1", category: "critical", title: "Critical alert — V-2210", detail: "Actuator unresponsive", at: t(38), href: "/console/equipment/V-2210" },
  { id: "n-2", category: "attention", title: "Approval requested", detail: "Create work order WO-8852 (C-3)", at: t(12), href: "/console/approvals" },
  { id: "n-3", category: "ai", title: "AI task completed", detail: "C-3 vibration analysis — verified ✓", at: t(9), href: "/console/workspace" },
  { id: "n-4", category: "ai", title: "Artifact verified", detail: "vibration_analysis_C-3.pdf", at: t(8), href: "/console/workspace" },
  { id: "n-5", category: "system", title: "Indexing complete", detail: "SOP-07.3 Rev 4 — 214 chunks", at: t(120), href: "/console/documents" },
];

export const AGENTS: AgentDescriptor[] = [
  { kind: "maintenance", name: "Maintenance Agent", description: "Investigates equipment anomalies, drafts verified maintenance recommendations.", model_role: "reasoning", tools: ["retrieve_documents", "graph_query", "python_analysis", "generate_report"], permissions: ["documents:read", "search:query", "code:execute", "artifacts:write"], status: "idle" },
  { kind: "operations", name: "Operations Agent", description: "Monitors plant state, drafts operational summaries.", model_role: "reasoning", tools: ["retrieve_documents", "telemetry_query"], permissions: ["documents:read", "search:query"], status: "idle" },
  { kind: "documentation", name: "Documentation Agent", description: "Keeps SOPs and reports consistent with verified findings.", model_role: "reasoning", tools: ["retrieve_documents", "generate_report"], permissions: ["documents:read", "artifacts:write"], status: "idle" },
  { kind: "data_analysis", name: "Data Analysis Agent", description: "Sandboxed statistical analysis over telemetry windows.", model_role: "coding", tools: ["python_analysis", "telemetry_query"], permissions: ["code:execute", "artifacts:write"], status: "idle" },
  { kind: "safety", name: "Safety Agent", description: "Checks planned actions against safety policy before execution.", model_role: "reasoning", tools: ["retrieve_documents", "policy_check"], permissions: ["documents:read", "search:query"], status: "idle" },
];

export const DOCUMENTS: DocumentRecord[] = [
  { id: "d-1", filename: "inspection_report_aug.pdf", content_type: "application/pdf", size_bytes: 2140000, status: "indexed", metadata: { pages: 18, entities: 34 }, created_at: "2026-08-15T09:00:00Z", updated_at: "2026-08-15T09:04:00Z" },
  { id: "d-2", filename: "SOP-14.2.pdf", content_type: "application/pdf", size_bytes: 480000, status: "indexed", metadata: { pages: 6, entities: 9 }, created_at: "2026-05-02T10:00:00Z", updated_at: "2026-05-02T10:02:00Z" },
  { id: "d-3", filename: "maintenance_history_C-3.csv", content_type: "text/csv", size_bytes: 61000, status: "indexed", metadata: { entities: 12 }, created_at: "2026-08-01T08:00:00Z", updated_at: "2026-08-01T08:00:20Z" },
  { id: "d-4", filename: "SOP-07.3_rev4.pdf", content_type: "application/pdf", size_bytes: 890000, status: "indexed", metadata: { pages: 22, entities: 41 }, created_at: t(120), updated_at: t(118) },
  { id: "d-5", filename: "vibration_baseline_C-3.xlsx", content_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", size_bytes: 204000, status: "indexed", metadata: { entities: 4 }, created_at: "2026-06-11T14:00:00Z", updated_at: "2026-06-11T14:01:00Z" },
  { id: "d-6", filename: "pump_curve_P-1042.png", content_type: "image/png", size_bytes: 310000, status: "indexing", metadata: {}, created_at: t(6), updated_at: t(6) },
  { id: "d-7", filename: "IR-204_compressor_inspection.pdf", content_type: "application/pdf", size_bytes: 1560000, status: "indexed", metadata: { pages: 11, entities: 28 }, created_at: "2026-08-02T07:30:00Z", updated_at: "2026-08-02T07:33:00Z" },
];

export const WORK_ORDERS: WorkOrder[] = [
  {
    id: "WO-8852", equipment_id: "C-3", title: "Inspect C-3 bearing assembly — vibration trend",
    priority: "high", status: "pending_approval", assignee: "maintenance-agent",
    recommended_action: "Inspect drive-end bearing during next low-demand window; baseline vibration per SOP-07.3 §4.",
    evidence: [
      { document_id: "d-5", filename: "vibration_baseline_C-3.xlsx", snippet: "Baseline 5.7 mm/s at 8,800 rpm…" },
      { document_id: "d-7", filename: "IR-204_compressor_inspection.pdf", page: 7, snippet: "Bearing clearance within tolerance as of 02 Aug…" },
    ],
  },
  {
    id: "WO-8841", equipment_id: "P-1042", title: "Inspect crude feed pump discharge line",
    priority: "high", status: "pending_approval", assignee: "maintenance-agent",
    recommended_action: "Isolate P-1042 during next low-demand window; inspect discharge line and relief valve per SOP-14.2.",
    evidence: [{ document_id: "d-1", filename: "inspection_report_aug.pdf", page: 4, snippet: "Discharge pressure trending above 17 bar since 12 Aug…" }],
  },
  { id: "WO-8837", equipment_id: "V-2210", title: "Anti-surge valve actuator diagnostics", priority: "urgent", status: "open", assignee: "unassigned", evidence: [] },
  { id: "WO-8810", equipment_id: "T-118", title: "Feed surge tank level transmitter calibration", priority: "medium", status: "in_progress", assignee: "r.kapoor", evidence: [] },
  { id: "WO-8802", equipment_id: "E-340", title: "Quarterly exchanger fouling check", priority: "medium", status: "done", assignee: "r.kapoor", evidence: [] },
  { id: "WO-8790", equipment_id: "P-2051", title: "Lean oil pump seal replacement", priority: "low", status: "done", assignee: "s.mehta", evidence: [] },
];

export const APPROVALS: ApprovalRequest[] = [
  {
    id: "APR-231", action: "Create work order WO-8852 and notify maintenance lead",
    risk: "medium", agent: "maintenance", requested_by: "maintenance-agent", equipment_id: "C-3",
    reason: "Vibration trend analysis (30-day window, sandboxed regression) indicates early bearing wear with 97% confidence. Creating the work order records an operational commitment.",
    evidence: WORK_ORDERS[0].evidence, created_at: t(12), status: "pending",
  },
  {
    id: "APR-220", action: "Create work order WO-8841 and notify maintenance lead",
    risk: "medium", agent: "maintenance", requested_by: "maintenance-agent", equipment_id: "P-1042",
    reason: "Discharge pressure above the 17 bar threshold in 19 of the last 24 hourly readings.",
    evidence: WORK_ORDERS[1].evidence, created_at: t(95), status: "pending",
  },
  {
    id: "APR-218", action: "Update SOP-14.2 inspection interval from 90d to 60d",
    risk: "high", agent: "documentation", requested_by: "documentation-agent", equipment_id: "P-1042",
    reason: "Three anomalies in two quarters suggest the current interval misses early degradation.",
    evidence: [{ document_id: "d-2", filename: "SOP-14.2.pdf", page: 2, snippet: "Inspection interval: 90 days…" }],
    created_at: t(1500), status: "pending",
  },
  {
    id: "APR-209", action: "Generate weekly operations summary for Unit 200",
    risk: "low", agent: "operations", requested_by: "operations-agent",
    reason: "Scheduled weekly summary.", evidence: [], created_at: t(2900), status: "approved",
  },
];

export const GRAPH_NODES: GraphNode[] = [
  { id: "C-3", label: "Compressor C-3", type: "equipment" },
  { id: "BRG-DE", label: "Drive-end Bearing", type: "component" },
  { id: "S-VB-03", label: "Vibration Sensor", type: "sensor" },
  { id: "IR-204", label: "Inspection IR-204", type: "inspection" },
  { id: "A-51", label: "Anomaly A-51", type: "anomaly" },
  { id: "SOP-07.3", label: "SOP-07.3", type: "specification" },
  { id: "ME-198", label: "Bearing Replacement", type: "maintenance" },
  { id: "WO-8852", label: "WO-8852", type: "work_order" },
  { id: "P-1042", label: "Pump P-1042", type: "equipment" },
  { id: "A-43", label: "Anomaly A-43", type: "anomaly" },
];

export const GRAPH_EDGES: GraphEdge[] = [
  { from: "BRG-DE", to: "C-3", relation: "installed_in" },
  { from: "C-3", to: "S-VB-03", relation: "has_sensor" },
  { from: "IR-204", to: "C-3", relation: "mentions" },
  { from: "C-3", to: "A-51", relation: "has_anomaly" },
  { from: "A-51", to: "SOP-07.3", relation: "governed_by" },
  { from: "ME-198", to: "BRG-DE", relation: "serviced_by" },
  { from: "A-51", to: "WO-8852", relation: "affects" },
  { from: "IR-204", to: "BRG-DE", relation: "mentions" },
  { from: "P-1042", to: "A-43", relation: "has_anomaly" },
];

export const HISTORY: HistoryEvent[] = [
  { id: "h-1", kind: "approval", title: "Approval requested — WO-8852", detail: "Maintenance Agent proposed C-3 bearing inspection", actor: "maintenance-agent", equipment_id: "C-3", at: t(12) },
  { id: "h-2", kind: "recommendation", title: "AI recommendation — C-3", detail: "Early bearing wear; inspect within 14 days", actor: "maintenance-agent", equipment_id: "C-3", at: t(14) },
  { id: "h-3", kind: "anomaly", title: "Anomaly detected — A-51", detail: "C-3 vibration 6.8 mm/s, +18% over baseline", actor: "system", equipment_id: "C-3", at: t(64) },
  { id: "h-4", kind: "work_order", title: "WO-8802 completed", detail: "E-340 fouling check — no issues", actor: "r.kapoor", equipment_id: "E-340", at: t(4320) },
  { id: "h-5", kind: "decision", title: "Threshold set — P-1042 17 bar", detail: "Engineering set discharge pressure alert threshold", actor: "engineering", equipment_id: "P-1042", at: t(38880) },
  { id: "h-6", kind: "inspection", title: "Inspection IR-204 filed", detail: "C-3 quarterly inspection — bearing clearance in tolerance", actor: "s.mehta", equipment_id: "C-3", at: t(54720) },
  { id: "h-7", kind: "maintenance", title: "Bearing replaced — ME-198", detail: "C-3 drive-end bearing replaced per schedule", actor: "maintenance", equipment_id: "C-3", at: t(132000) },
];

export const LEARNED_RULES: LearnedRule[] = [
  { id: "r-1", rule: "P-1042 discharge pressure alert threshold: 17 bar", set_by: "Engineering", at: "2026-08-12", status: "verified", origin: "Anomaly A-43 review", evidence_count: 19, confidence: 97, used_count: 34 },
  { id: "r-2", rule: "C-3 vibration baseline: 5.7 mm/s at 8,800 rpm", set_by: "Engineering", at: "2026-06-11", status: "verified", origin: "Post-ME-198 commissioning", evidence_count: 720, confidence: 99, used_count: 58 },
  { id: "r-3", rule: "V-2210 opening above 85% for >10 min = actuator fault signature", set_by: "Maintenance", at: "2026-07-22", status: "verified", origin: "Incident review 22 Jul", evidence_count: 6, confidence: 92, used_count: 11 },
  { id: "r-4", rule: "SOP-14.2 applies to all crude-feed-line isolation work", set_by: "Safety", at: "2026-05-02", status: "verified", origin: "Safety policy board", evidence_count: 3, confidence: 100, used_count: 21 },
];

export const ARTIFACTS: ArtifactRecord[] = [
  { id: "art-61", kind: "pdf", filename: "vibration_analysis_C-3.pdf", sha256: "c41d…9b", verified: true, job_id: "job-88", created_at: t(8) },
  { id: "art-51", kind: "pdf", filename: "maintenance_recommendation_P-1042.pdf", sha256: "9f2c…a1", verified: true, job_id: "job-71", created_at: t(1600) },
  { id: "art-44", kind: "pptx", filename: "unit200_weekly_summary.pptx", sha256: "77ab…e3", verified: true, job_id: "job-70", created_at: t(2900) },
];

export const USERS: AdminUser[] = [
  { id: "u-1", name: "R. Kapoor", email: "r.kapoor@plant.local", role: "engineer", last_active: t(20) },
  { id: "u-2", name: "S. Mehta", email: "s.mehta@plant.local", role: "maintenance", last_active: t(95) },
  { id: "u-3", name: "A. Iyer", email: "a.iyer@plant.local", role: "manager", last_active: t(30) },
  { id: "u-4", name: "D. Bhusal", email: "d.bhusal@plant.local", role: "admin", last_active: t(2) },
  { id: "u-5", name: "M. Farouk", email: "m.farouk@plant.local", role: "safety", last_active: t(400) },
  { id: "u-6", name: "T. Nguyen", email: "t.nguyen@plant.local", role: "operator", last_active: t(55) },
];

export const MODELS: ModelStatus[] = [
  { role: "reasoning", model: "qwen2.5:32b-instruct", status: "loaded", latency_ms: 1840 },
  { role: "coding", model: "qwen2.5-coder:14b", status: "loaded", latency_ms: 960 },
  { role: "embedding", model: "bge-m3", status: "loaded", latency_ms: 85 },
  { role: "vision", model: "llava:13b", status: "available" },
  { role: "reranker", model: "bge-reranker-v2-m3", status: "available" },
];

export const POSTURE: SystemPosture = {
  model_gateway: "local",
  sandbox: "isolated",
  egress: "denied",
  external_calls_24h: 0,
  database: "ok",
  storage_used_gb: 41.2,
  storage_total_gb: 256,
  version: "0.19.0",
};

export const AUDIT: AuditEvent[] = [
  { id: "au-1", at: t(8), actor: "maintenance-agent", action: "artifact.verified", tool: "generate_report", model: "qwen2.5:32b", job_id: "job-88" },
  { id: "au-2", at: t(10), actor: "maintenance-agent", action: "sandbox.execute", tool: "python_analysis", job_id: "job-88" },
  { id: "au-3", at: t(12), actor: "maintenance-agent", action: "approval.requested", job_id: "job-88", approval_id: "APR-231" },
  { id: "au-4", at: t(30), actor: "a.iyer", action: "approval.viewed", approval_id: "APR-220" },
  { id: "au-5", at: t(64), actor: "system", action: "alert.created" },
  { id: "au-6", at: t(95), actor: "s.mehta", action: "document.uploaded", tool: "ingestion" },
  { id: "au-7", at: t(120), actor: "system", action: "document.indexed", tool: "ingestion" },
  { id: "au-8", at: t(200), actor: "d.bhusal", action: "settings.viewed" },
];

export const SESSIONS: WorkspaceSession[] = [
  { id: "s-1", title: "C-3 vibration investigation", at: t(15), task_count: 1 },
  { id: "s-2", title: "Unit 200 weekly summary", at: t(2900), task_count: 2 },
  { id: "s-3", title: "P-1042 pressure anomaly", at: t(1600), task_count: 1 },
];

export const C3_TASK: WorkspaceTask = {
  id: "task-88",
  job_id: "job-88",
  request: "Analyze Compressor C-3 and tell me why vibration increased.",
  agent: "maintenance",
  step: "complete",
  context: [
    { document_id: "d-5", filename: "vibration_baseline_C-3.xlsx", snippet: "Baseline 5.7 mm/s at 8,800 rpm (set 11 Jun)…" },
    { document_id: "d-7", filename: "IR-204_compressor_inspection.pdf", page: 7, snippet: "Bearing clearance within tolerance as of 02 Aug…" },
    { document_id: "d-3", filename: "maintenance_history_C-3.csv", snippet: "Drive-end bearing replaced 2026-04-14 (ME-198)…" },
  ],
  trace: [
    { label: "Task received", done: true },
    { label: "Context retrieved", detail: "3 documents · graph neighborhood · 30-day telemetry", duration_ms: 920, done: true },
    { label: "Knowledge graph queried", detail: "9 nodes · 8 relationships", duration_ms: 240, done: true },
    { label: "Sandbox analysis executed", detail: "opensandbox exec 7f2c · regression over 720 points", duration_ms: 4360, done: true },
    { label: "Calculation verified", duration_ms: 110, done: true },
    { label: "Artifact generated + verified", detail: "vibration_analysis_C-3.pdf · sha256 c41d…9b", done: true },
  ],
  result:
    "C-3 vibration rose 18% over 30 days (5.7 → 6.8 mm/s), accelerating in the last 9 days. The pattern matches early drive-end bearing wear, not process upset: temperature and speed are stable, and the rise is concentrated in the 2× running-speed band. Recommend bearing inspection within 14 days per SOP-07.3 §4.",
  claims: [
    { text: "Vibration rose 18% over 30 days (5.7 → 6.8 mm/s)", verified: true, citations: [{ document_id: "d-5", filename: "vibration_baseline_C-3.xlsx", snippet: "Baseline 5.7 mm/s…" }] },
    { text: "Bearing clearance was within tolerance on 02 Aug", verified: true, citations: [{ document_id: "d-7", filename: "IR-204_compressor_inspection.pdf", page: 7, snippet: "…clearance within tolerance…" }] },
    { text: "2× running-speed band dominance indicates bearing wear", verified: true, citations: [{ document_id: "d-4", filename: "SOP-07.3_rev4.pdf", page: 9, snippet: "2× band dominance → rolling-element wear…" }] },
  ],
  artifacts: [ARTIFACTS[0]],
  checks: [
    { name: "Evidence", status: "verified", detail: "3 sources attached" },
    { name: "Citations", status: "verified", detail: "3/3 claims cited" },
    { name: "Calculation", status: "verified", detail: "regression reproduced in sandbox" },
    { name: "Execution", status: "verified", detail: "exec 7f2c completed, exit 0" },
    { name: "Artifact", status: "verified", detail: "sha256 c41d…9b" },
    { name: "Policy", status: "verified", detail: "no egress · sandboxed" },
  ],
  needs_approval: { approval_id: "APR-231", action: "Create work order WO-8852" },
  structured: {
    executive: "C-3 vibration is early drive-end bearing wear — not process upset. Inspect within 14 days; no immediate trip risk.",
    finding: "Vibration rose 18% over 30 days (5.7 → 6.8 mm/s), accelerating in the last 9 days, concentrated in the 2× running-speed band — the rolling-element wear signature in SOP-07.3 §4.2.",
    factors: [
      "Bearing clearance was in tolerance at the 02 Aug inspection — wear is recent and progressing",
      "Bearing temperature stable at 79 °C — lubrication is not the driver",
      "Speed steady at 8,840 rpm — not an operating-point artifact",
      "Drive-end bearing last replaced 14 Apr (ME-198) — 5 months in service",
    ],
    action: "Inspect C-3 drive-end bearing and coupling alignment during the next low-demand window, per SOP-07.3 §4.",
    risk: "Medium — degraded bearing can cascade to seal damage if run >30 days unattended",
    next: "Create work order WO-8852 (awaiting your approval) → assign maintenance → verify post-work vibration against the 5.7 mm/s baseline.",
  },
};
