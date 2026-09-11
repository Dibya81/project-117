/** Console mock data part 3 — jobs, tools, workflows, search, analytics.
 * Same demo story (C-3 / P-1042 / V-2210), served through lib/data/console.ts. */
import type { JobRecord, ToolDescriptor, WorkflowDefinition } from "@/types";

const t = (minsAgo: number) => new Date(Date.now() - minsAgo * 60000).toISOString();

export const JOBS: JobRecord[] = [
  { id: "job-88", title: "C-3 vibration root-cause investigation", state: "COMPLETED", agent: "maintenance", created_at: t(15), updated_at: t(8) },
  { id: "job-89", title: "V-2210 actuator fault diagnostics", state: "VERIFYING", agent: "maintenance", created_at: t(34), updated_at: t(2) },
  { id: "job-90", title: "Unit 200 weekly operations summary", state: "EXECUTING", agent: "operations", created_at: t(52), updated_at: t(6) },
  { id: "job-91", title: "P-1042 pressure anomaly regression", state: "NEEDS_APPROVAL", agent: "data_analysis", created_at: t(95), updated_at: t(12) },
  { id: "job-92", title: "SOP-14.2 interval review draft", state: "QUEUED", agent: "documentation", created_at: t(7), updated_at: t(7) },
  { id: "job-71", title: "P-1042 maintenance recommendation", state: "COMPLETED", agent: "maintenance", created_at: t(1620), updated_at: t(1600) },
  { id: "job-70", title: "Unit 200 weekly summary deck", state: "COMPLETED", agent: "operations", created_at: t(2920), updated_at: t(2900) },
  { id: "job-66", title: "E-340 fouling trend scan", state: "FAILED", agent: "data_analysis", created_at: t(4300), updated_at: t(4290) },
];

export const TOOLS: ToolDescriptor[] = [
  { name: "retrieve_documents", description: "Hybrid vector + full-text retrieval over indexed plant documents with page-level citations.", kind: "retrieval", permissions: ["documents:read"] },
  { name: "graph_query", description: "Traverse the equipment knowledge graph — components, anomalies, inspections, specifications.", kind: "retrieval", permissions: ["graph:read"] },
  { name: "telemetry_query", description: "Windowed sensor telemetry with baselines, thresholds and anomaly flags.", kind: "retrieval", permissions: ["telemetry:read"] },
  { name: "python_analysis", description: "Run sandboxed Python over retrieved data. No network, no host filesystem, resource-capped.", kind: "execution", permissions: ["code:execute"] },
  { name: "generate_report", description: "Assemble verified findings into PDF/DOCX/PPTX/XLSX artifacts with provenance.", kind: "generation", permissions: ["artifacts:write"] },
  { name: "policy_check", description: "Check a planned action against safety and operational policy before it may proceed.", kind: "policy", permissions: ["policy:read"] },
];

export const WORKFLOWS: WorkflowDefinition[] = [
  {
    name: "anomaly-investigation",
    description: "From detected anomaly to verified recommendation and drafted work order.",
    steps: [
      { id: "s1", name: "Retrieve context", type: "retrieval" },
      { id: "s2", name: "Graph neighborhood", type: "retrieval" },
      { id: "s3", name: "Sandbox analysis", type: "execution" },
      { id: "s4", name: "Draft recommendation", type: "generation" },
      { id: "s5", name: "Safety policy check", type: "policy" },
      { id: "s6", name: "Create work order", type: "action", requires_approval: true },
    ],
  },
  {
    name: "weekly-operations-summary",
    description: "Scheduled roll-up of plant state, anomalies and AI activity into a deck.",
    steps: [
      { id: "s1", name: "Collect metrics", type: "retrieval" },
      { id: "s2", name: "Analyze trends", type: "execution" },
      { id: "s3", name: "Generate deck", type: "generation" },
      { id: "s4", name: "Verify + publish", type: "verification" },
    ],
  },
  {
    name: "document-deep-audit",
    description: "Re-index a document, re-extract entities and refresh graph links.",
    steps: [
      { id: "s1", name: "Parse + OCR", type: "ingestion" },
      { id: "s2", name: "Chunk + embed", type: "ingestion" },
      { id: "s3", name: "Entity extraction", type: "extraction" },
      { id: "s4", name: "Graph link refresh", type: "extraction" },
    ],
  },
];

export interface SearchResult {
  id: string;
  filename: string;
  page?: number;
  section?: string;
  score: number;
  snippet: string;
}

export function searchMock(query: string): SearchResult[] {
  const q = query.toLowerCase();
  const pool: SearchResult[] = [
    { id: "r-1", filename: "vibration_baseline_C-3.xlsx", section: "Sheet 1", score: 0.94, snippet: "Baseline 5.7 mm/s at 8,800 rpm — set by Engineering 11 Jun. Alarm at 7.1 mm/s, trip at 11 mm/s." },
    { id: "r-2", filename: "IR-204_compressor_inspection.pdf", page: 7, section: "§3 Bearings", score: 0.91, snippet: "Drive-end bearing clearance measured 0.09 mm — within tolerance band as of 02 Aug inspection." },
    { id: "r-3", filename: "SOP-07.3_rev4.pdf", page: 9, section: "§4.2 Diagnostics", score: 0.88, snippet: "Dominance in the 2× running-speed band indicates rolling-element bearing wear; schedule inspection within 14 days." },
    { id: "r-4", filename: "inspection_report_aug.pdf", page: 4, section: "Unit 200", score: 0.84, snippet: "P-1042 discharge pressure trending above 17 bar since 12 Aug; relief valve last tested Q1." },
    { id: "r-5", filename: "SOP-14.2.pdf", page: 2, section: "§1 Scope", score: 0.8, snippet: "Applies to all crude-feed-line isolation work. Inspection interval: 90 days." },
    { id: "r-6", filename: "maintenance_history_C-3.csv", score: 0.77, snippet: "2026-04-14 — drive-end bearing replaced (ME-198). Post-work vibration 5.6 mm/s." },
  ];
  if (!q.trim()) return pool;
  return pool
    .map((r) => ({
      ...r,
      score:
        r.snippet.toLowerCase().includes(q) || r.filename.toLowerCase().includes(q)
          ? Math.min(0.99, r.score + 0.05)
          : r.score * 0.82,
    }))
    .sort((a, b) => b.score - a.score);
}

export const ANALYTICS_SUMMARY = {
  anomalies_7d: 9,
  anomalies_delta: +3,
  work_orders_open: 4,
  mttr_hours: 6.2,
  mtbf_hours: 412,
  agent_tasks_7d: 47,
  verification_rate: 96,
  external_calls_24h: 0,
};
