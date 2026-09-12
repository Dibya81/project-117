/**
 * Agent Response Console — event reducer.
 *
 * Pure projection of the backend's `response.*` event contract into the three
 * parallel lanes. Nothing here invents state: a lane step is only ever `done`
 * because the matching event arrived, and every displayed field (department,
 * chosen alternate, counts, prediction, summary) is copied from the payload.
 *
 * The wall-clock timeout is applied by the component, not here — this module
 * stays a function of the event log alone.
 */
import type { SimEvent } from "./types";

export interface PredictionCandidate {
  equipmentId: string;
  tag: string;
  name: string;
  risk: number;
  reasons: string[];
  horizon: string;
}

export type StepState = "pending" | "active" | "done";

export interface ChecklistItem {
  id: string;
  label: string;
  detail?: string;
  state: StepState;
  /** Sim-time of the event that completed the step (never the client clock). */
  at?: number;
  seq?: number;
}

export interface ResponseJob {
  jobId: string;
  incidentId: string;
  equipmentId: string;
  equipmentTag: string;
  faultType: string | null;
  faultName: string | null;
  severity: string;
  department: string;
  departmentSource: string;
  perceptionAt: number | null;
  perceptionSeq: number | null;
  handoff: boolean;
  laneStarted: { operations: boolean; diagnostics: boolean };
  laneAComplete: boolean;
  operationsNotified: { at: number; seq: number } | null;
  failoverEvaluating: { at: number; seq: number; candidateCount: number } | null;
  laneB: ChecklistItem[];
  laneC: ChecklistItem[];
  failover: {
    fromEquipmentId: string;
    relatedEquipmentId: string;
    relatedSensorId: string | null;
    relatedSensorTag: string | null;
    sameAsset: boolean;
    at: number;
  } | null;
  rootCause: {
    equipmentTag: string;
    failureMode: string | null;
    failureModeName: string | null;
    mechanism: string | null;
    declared: boolean;
    explanation: string;
    at: number;
  } | null;
  history: {
    maintenanceRecords: number;
    documentsRetrieved: number;
    failureModesKnown: number;
    lastInspection: string | null;
    yearsSinceInspection: number | null;
    at: number;
  } | null;
  prediction: PredictionCandidate[];
  predictionCaveat: string | null;
  predictionAt: number | null;
  userSummary: { text: string; at: number } | null;
  verified: { ok: boolean; at: number; verificationId: string | null } | null;
  lastSeq: number;
  lastAt: number;
}

const RESPONSE_EVENT_PREFIX = "response.";

function asString(v: unknown): string | null {
  return typeof v === "string" ? v : null;
}

function asNumber(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function newJob(jobId: string, incidentId: string): ResponseJob {
  return {
    jobId,
    incidentId,
    equipmentId: "",
    equipmentTag: "",
    faultType: null,
    faultName: null,
    severity: "",
    department: "",
    departmentSource: "",
    perceptionAt: null,
    perceptionSeq: null,
    handoff: false,
    laneStarted: { operations: false, diagnostics: false },
    laneAComplete: false,
    operationsNotified: null,
    failoverEvaluating: null,
    laneB: [],
    laneC: [],
    failover: null,
    rootCause: null,
    history: null,
    prediction: [],
    predictionCaveat: null,
    predictionAt: null,
    userSummary: null,
    verified: null,
    lastSeq: 0,
    lastAt: 0,
  };
}

/**
 * Is this event part of the console's contract? The response beats, the
 * orchestrator's explicit handoff, and the independent verification gate.
 */
export function isResponseEvent(ev: SimEvent): boolean {
  return (
    ev.type.startsWith(RESPONSE_EVENT_PREFIX) ||
    ev.type === "agent.started" ||
    ev.type === "verification.completed"
  );
}

/**
 * Fold the event log into one entry per job. Jobs are keyed by the payload's
 * `job_id` (falling back to `incident_id`), so two concurrent faults cannot
 * drop each other's events — each keeps its own bucket.
 */
export function reduceResponseJobs(events: SimEvent[]): ResponseJob[] {
  const jobs = new Map<string, ResponseJob>();
  const order: string[] = [];

  const jobFor = (p: Record<string, unknown>): ResponseJob => {
    const jobId = asString(p.job_id) ?? asString(p.incident_id) ?? "unknown";
    const incidentId = asString(p.incident_id) ?? jobId;
    let job = jobs.get(jobId);
    if (!job) {
      job = newJob(jobId, incidentId);
      jobs.set(jobId, job);
      order.push(jobId);
    }
    return job;
  };

  for (const ev of events) {
    if (!isResponseEvent(ev)) continue;
    const p = ev.payload as Record<string, unknown>;
    const job = jobFor(p);
    job.lastSeq = Math.max(job.lastSeq, ev.seq);
    job.lastAt = Math.max(job.lastAt, ev.at);

    switch (ev.type) {
      case "response.perception": {
        job.incidentId = asString(p.incident_id) ?? job.incidentId;
        job.equipmentId = asString(p.equipment_id) ?? job.equipmentId;
        job.equipmentTag = asString(p.equipment_tag) ?? job.equipmentTag;
        job.faultType = asString(p.fault_type);
        job.faultName = asString(p.fault_name);
        job.severity = asString(p.severity) ?? job.severity;
        job.department = asString(p.department) ?? job.department;
        job.departmentSource = asString(p.department_source) ?? job.departmentSource;
        job.perceptionAt = ev.at;
        job.perceptionSeq = ev.seq;
        break;
      }
      case "agent.started": {
        // Lane A's "routing" line: the backend states the handoff explicitly.
        job.handoff = Boolean(p.handoff);
        job.equipmentTag = asString(p.equipment_tag) ?? job.equipmentTag;
        job.faultType = asString(p.fault_type) ?? job.faultType;
        job.faultName = asString(p.fault_name) ?? job.faultName;
        job.severity = asString(p.severity) ?? job.severity;
        job.department = asString(p.department) ?? job.department;
        break;
      }
      case "response.lane_started": {
        const lane = asString(p.lane);
        if (lane === "operations") job.laneStarted.operations = true;
        if (lane === "diagnostics") job.laneStarted.diagnostics = true;
        break;
      }
      case "response.operations_notified":
        job.department = asString(p.department) ?? job.department;
        job.operationsNotified = { at: ev.at, seq: ev.seq };
        break;
      case "response.failover_evaluating":
        job.failoverEvaluating = {
          at: ev.at,
          seq: ev.seq,
          candidateCount: Array.isArray(p.candidates) ? p.candidates.length : 0,
        };
        break;
      case "response.failover_completed": {
        const related = asString(p.related_equipment_id);
        if (related) {
          job.failover = {
            fromEquipmentId: job.equipmentId,
            relatedEquipmentId: related,
            relatedSensorId: asString(p.related_sensor_id),
            relatedSensorTag: asString(p.related_sensor_tag),
            sameAsset: Boolean(p.same_asset),
            at: ev.at,
          };
        }
        break;
      }
      case "response.history_reviewed": {
        const c = (p.counts ?? {}) as Record<string, unknown>;
        job.history = {
          maintenanceRecords: asNumber(c.maintenance_records) ?? 0,
          documentsRetrieved: asNumber(c.documents_retrieved) ?? 0,
          failureModesKnown: asNumber(c.failure_modes_known) ?? 0,
          lastInspection: asString(c.last_inspection),
          yearsSinceInspection: asNumber(c.years_since_inspection),
          at: ev.at,
        };
        break;
      }
      case "response.root_cause_identified": {
        job.rootCause = {
          equipmentTag: asString(p.equipment_tag) ?? job.equipmentTag,
          failureMode: asString(p.failure_mode),
          failureModeName: asString(p.failure_mode_name),
          mechanism: asString(p.mechanism),
          declared: Boolean(p.failure_mode_declared),
          explanation: asString(p.explanation) ?? "",
          at: ev.at,
        };
        break;
      }
      case "response.prediction": {
        const raw = Array.isArray(p.candidates) ? p.candidates : [];
        job.prediction = raw
          .map((c) => c as Record<string, unknown>)
          .map((c) => ({
            equipmentId: asString(c.equipment_id) ?? "",
            tag: asString(c.tag) ?? "",
            name: asString(c.name) ?? "",
            risk: asNumber(c.risk) ?? 0,
            reasons: Array.isArray(c.reasons) ? (c.reasons as unknown[]).map(String) : [],
            horizon: asString(c.horizon) ?? "",
          }))
          .filter((c) => c.equipmentId);
        job.predictionCaveat = asString(p.caveat) ?? job.predictionCaveat;
        job.predictionAt = ev.at;
        break;
      }
      case "response.user_notified":
        job.userSummary = { text: asString(p.summary) ?? "", at: ev.at };
        break;
      case "verification.completed": {
        // The independent gate. This is the ONLY source of the Verified badge.
        job.verified = {
          ok: Boolean(p.ok),
          at: ev.at,
          verificationId: asString(p.verification_id),
        };
        break;
      }
      default:
        break;
    }
  }

  for (const job of jobs.values()) {
    job.laneAComplete = job.laneStarted.operations && job.laneStarted.diagnostics;
    job.laneB = buildLaneB(job);
    job.laneC = buildLaneC(job);
  }
  return order.map((id) => jobs.get(id)!);
}

function buildLaneB(job: ResponseJob): ChecklistItem[] {
  const notified = job.operationsNotified;
  const evaluating = job.failoverEvaluating;
  const completed = job.failover !== null;

  return [
    {
      id: "b-notified",
      label: job.department ? `Notified ${job.department} shift supervisor` : "Notified shift supervisor",
      detail: job.departmentSource ? `department from ${job.departmentSource}` : undefined,
      state: notified ? "done" : job.laneStarted.operations ? "active" : "pending",
      at: notified?.at,
      seq: notified?.seq,
    },
    {
      id: "b-failover-eval",
      label: "Evaluating failover path",
      detail: completed
        ? undefined
        : evaluating
          ? `${evaluating.candidateCount} alternate measurement(s) under review`
          : undefined,
      // Pulses while the orchestrator evaluates; only the completion event
      // settles it, so a missing completion surfaces as a no-response.
      state: completed ? "done" : evaluating ? "active" : "pending",
      at: completed ? job.failover?.at : evaluating?.at,
      seq: evaluating?.seq,
    },
    {
      id: "b-failover-done",
      label: job.failover
        ? `Switched to ${job.failover.relatedSensorTag ?? job.failover.relatedEquipmentId}`
        : "Switch to alternate measurement",
      detail: job.failover
        ? `${job.failover.relatedEquipmentId}${job.failover.sameAsset ? " · same asset" : " · alternate asset"}`
        : undefined,
      state: completed ? "done" : "pending",
      at: job.failover?.at,
      seq: job.failover ? job.lastSeq : undefined,
    },
  ];
}

function buildLaneC(job: ResponseJob): ChecklistItem[] {
  const diagStarted = job.laneStarted.diagnostics;
  const historyDone = job.history !== null;
  const rootDone = job.rootCause !== null;
  const predictionDone = job.predictionAt !== null;
  const summaryDone = job.userSummary !== null;

  const historyDetail = job.history
    ? `correlating ${job.history.maintenanceRecords} maintenance record(s), ` +
      `${job.history.documentsRetrieved} retrieved document(s)` +
      (job.history.lastInspection ? ` · last inspection ${job.history.lastInspection}` : "")
    : undefined;

  const active = (predecessorDone: boolean, done: boolean): StepState =>
    done ? "done" : predecessorDone ? "active" : "pending";

  return [
    {
      id: "c-history",
      label: "Reviewing maintenance and inspection history",
      detail: historyDetail,
      state: historyDone ? "done" : diagStarted ? "active" : "pending",
      at: job.history?.at,
    },
    {
      id: "c-root",
      label: "Root cause identified",
      detail: job.rootCause?.explanation,
      state: active(historyDone, rootDone),
      at: job.rootCause?.at,
    },
    {
      id: "c-prediction",
      label: "Predicting next at-risk equipment",
      detail: job.prediction.length ? `${job.prediction.length} candidate(s) ranked` : undefined,
      state: active(rootDone, predictionDone),
      at: job.predictionAt ?? undefined,
    },
    {
      id: "c-notify",
      label: "Notifying user",
      detail: job.userSummary?.text,
      state: active(predictionDone, summaryDone),
      at: job.userSummary?.at,
    },
  ];
}

/** Plain-language label for the mock banner and job header. */
export function jobLabel(job: ResponseJob): string {
  return `${job.equipmentTag || job.jobId} · ${job.faultName ?? job.faultType ?? "fault"}`;
}
