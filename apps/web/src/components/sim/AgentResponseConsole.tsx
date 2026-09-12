"use client";

/**
 * AgentResponseConsole — the core demo surface.
 *
 * A slide-in panel docked to the right 40% of the viewport. It renders three
 * parallel lanes (Perception → Operations + Diagnostics) that advance ONLY on
 * real backend events, plus an independent Verified badge that appears only on
 * a `verification.completed` event.
 *
 * There is one transport health input (`stream`) and one event log (`events`).
 * Nothing in here invents a state change: a checklist step is `done` because a
 * `response.*` event said so, and every field is copied from its payload.
 *
 * MOCK MODE is the single exception, and only because the brief allows a local
 * development sequence *after* the stream has failed `MOCK_RETRY_LIMIT` times.
 * It is gated on the adapter's connection status — never on an event — so no
 * real event can clear it, and a fresh successful connection always does.
 */
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Icon } from "@/components/ui/Icon";
import type { StreamStatus } from "@/lib/sim/adapter";
import { isResponseEvent, reduceResponseJobs, type ResponseJob } from "@/lib/sim/response";
import type { SimEvent } from "@/lib/sim/types";

const DEFAULT_STEP_TIMEOUT_MS = 20_000;

/** Format a backend sim-time (seconds) as the command-center clock. */
function simClock(t: number | undefined | null): string {
  if (t === undefined || t === null) return "—";
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `T+${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/** Short clock for event rows: the event's own time plus its sequence. */
function eventStamp(at: number | null | undefined, seq: number | null | undefined): string {
  if (at === undefined || at === null) return "—";
  return `${simClock(at)}${seq !== undefined && seq !== null ? ` · #${seq}` : ""}`;
}

/**
 * The explicit local development sequence. Used ONLY while the adapter reports
 * mock mode. It is deliberately namespaced and the banner above it can never be
 * dismissed from here.
 */
function buildMockSequence(plantId: string, equipmentTag: string, department: string): SimEvent[] {
  const job = "MOCK-INC-0001";
  const base = Date.now() / 1000;
  let seq = 0;
  const ev = (type: string, payload: Record<string, unknown>, at: number): SimEvent => {
    seq += 1;
    return { seq, plant_id: plantId, type, payload: { job_id: job, incident_id: job, ...payload }, at };
  };
  return [
    ev("response.perception", {
      equipment_id: "mock-equipment", equipment_tag: equipmentTag, fault_type: "sensor_failure",
      fault_name: "Sensor failure", severity: "warning", department, department_source: "mock",
    }, base),
    ev("agent.started", { equipment_tag: equipmentTag, handoff: { from: "perception", to: ["operations", "diagnostics"] }, department }, base + 1),
    ev("response.lane_started", { lane: "operations" }, base + 1),
    ev("response.lane_started", { lane: "diagnostics" }, base + 1),
    ev("response.operations_notified", { department, role: "shift supervisor" }, base + 2),
    ev("response.failover_evaluating", { origin_sensor_id: "mock-sensor", candidates: [{}, {}] }, base + 2),
    ev("response.failover_completed", {
      related_equipment_id: "mock-replacement", related_sensor_id: "mock-sensor-b",
      related_sensor_tag: "PT-MOCK-B", same_asset: false,
    }, base + 3),
    ev("response.history_reviewed", {
      counts: { maintenance_records: 1, documents_retrieved: 2, failure_modes_known: 5, last_inspection: "2026-01-01", years_since_inspection: 0.4 },
    }, base + 3),
    ev("response.root_cause_identified", {
      failure_mode: "sensor_failure", failure_mode_name: "Sensor failure", mechanism: "sensor",
      failure_mode_declared: true, explanation: "Mock mode: local development sequence.",
    }, base + 4),
    ev("response.prediction", {
      available: true, candidates: [{ equipment_id: "mock-prediction", tag: "P-MOCK", name: "Mock asset", risk: 0.42, reasons: ["mock mode"], horizon: "next quarter" }],
    }, base + 4),
    ev("response.user_notified", { summary: "Mock mode: local development sequence — not a real orchestrator response." }, base + 5),
  ];
}

export interface AgentResponseConsoleProps {
  open: boolean;
  events: SimEvent[];
  stream: StreamStatus;
  plantId: string;
  activeJobId: string | null;
  onSelectJob: (jobId: string) => void;
  onClose: () => void;
  /** Pan/highlight an asset on the canvas (prediction click). */
  onFocusEquipment: (equipmentId: string) => void;
  /** Seconds without a resolving event before a step reports no-response. */
  stepTimeoutMs?: number;
}

export function AgentResponseConsole({
  open,
  events,
  stream,
  plantId,
  activeJobId,
  onSelectJob,
  onClose,
  onFocusEquipment,
  stepTimeoutMs = DEFAULT_STEP_TIMEOUT_MS,
}: AgentResponseConsoleProps) {
  const mock = stream.state === "mock";

  // --- mock fallback (development only, banner-gated) ---------------------
  const [mockEvents, setMockEvents] = useState<SimEvent[]>([]);
  useEffect(() => {
    if (!open || !mock) {
      setMockEvents([]);
      return;
    }
    const sequence = buildMockSequence(plantId, "MOCK-P-0001", "Mock Operations");
    setMockEvents([]);
    let i = 0;
    const timer = setInterval(() => {
      i += 1;
      setMockEvents(sequence.slice(0, i));
      if (i >= sequence.length) clearInterval(timer);
    }, 650);
    return () => clearInterval(timer);
  }, [open, mock, plantId]);

  const sourceEvents = mock ? mockEvents : events;
  const jobs = useMemo(() => reduceResponseJobs(sourceEvents), [sourceEvents]);

  const activeJob: ResponseJob | null = useMemo(() => {
    if (!jobs.length) return null;
    return jobs.find((j) => j.jobId === activeJobId) ?? jobs[jobs.length - 1];
  }, [jobs, activeJobId]);

  // --- per-step activation clock, used only for the timeout --------------
  const [, forceTick] = useState(0);
  const activationRef = useRef<Record<string, number>>({});
  useEffect(() => {
    const now = Date.now();
    const seen: Record<string, boolean> = {};
    for (const job of jobs) {
      for (const step of [...job.laneB, ...job.laneC]) {
        const key = `${job.jobId}:${step.id}`;
        seen[key] = true;
        if (step.state === "done") {
          delete activationRef.current[key];
        } else if (step.state === "active" && activationRef.current[key] === undefined) {
          // The step became the in-progress one now; start its timeout clock.
          activationRef.current[key] = now;
        }
      }
    }
    for (const key of Object.keys(activationRef.current)) {
      if (!seen[key]) delete activationRef.current[key];
    }
  }, [jobs]);

  useEffect(() => {
    if (!open) return;
    const id = setInterval(() => forceTick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [open]);

  /** A step is stalled when it is the in-progress one and no event resolved it. */
  const isStalled = (jobId: string, stepId: string, state: string): boolean => {
    if (state !== "active") return false;
    const since = activationRef.current[`${jobId}:${stepId}`];
    if (since === undefined) return false;
    return Date.now() - since > stepTimeoutMs;
  };

  if (!open) return null;

  return (
    <aside
      className={`arc-panel${open ? " is-open" : ""}`}
      data-testid="agent-response-console"
      data-open="true"
      aria-label="Agent response console"
    >
      {mock && (
        <div className="arc-mockbanner" role="alert" data-testid="mock-mode-banner">
          <Icon name="alert" size={14} />
          <span>
            MOCK MODE — orchestrator not connected. This is a local development
            sequence, not a backend response.
          </span>
        </div>
      )}

      <header className="arc-head">
        <div>
          <p className="arc-head__kicker">Agent Response Console</p>
          <h2 className="arc-head__title">
            {activeJob ? activeJob.equipmentTag || activeJob.jobId : "Awaiting a fault"}
          </h2>
          {activeJob && (
            <p className="arc-head__sub cs-mono">
              {activeJob.jobId} · {activeJob.faultName ?? activeJob.faultType ?? "fault"} ·{" "}
              {activeJob.severity || "—"}
              {activeJob.department ? ` · ${activeJob.department}` : ""}
            </p>
          )}
        </div>
        <button className="arc-close" onClick={onClose} aria-label="Close agent response console">
          <Icon name="x" size={14} />
        </button>
      </header>

      {jobs.length > 1 && (
        <div className="arc-tabs" role="tablist" aria-label="Concurrent response jobs">
          {jobs.map((j) => (
            <button
              key={j.jobId}
              role="tab"
              aria-selected={j.jobId === activeJob?.jobId}
              className={`arc-tab${j.jobId === activeJob?.jobId ? " is-active" : ""}`}
              data-testid="arc-job-tab"
              data-job={j.jobId}
              onClick={() => onSelectJob(j.jobId)}
            >
              <span className="cs-mono">{j.equipmentTag || j.jobId}</span>
              <span className="arc-tab__state">{j.verified ? "verified" : "active"}</span>
            </button>
          ))}
        </div>
      )}

      <div className="arc-body">
        {!activeJob ? (
          <p className="arc-empty">
            No response job yet. Inject a fault on the canvas or from a scenario —
            the lanes fill from events the backend emits.
          </p>
        ) : (
          <>
            {/* LANE A — perception */}
            <section
              className={`arc-lane arc-lane--a${activeJob.laneAComplete ? " is-complete" : ""}`}
              data-testid="lane-a"
              data-complete={activeJob.laneAComplete ? "true" : "false"}
            >
              <div className="arc-lane__head">
                <span className="arc-lane__kicker">Lane A · Perception</span>
                <span className="arc-lane__stamp cs-mono">{eventStamp(activeJob.perceptionAt, activeJob.perceptionSeq)}</span>
              </div>
              <dl className="arc-facts">
                <div>
                  <dt>Equipment</dt>
                  <dd className="cs-mono" data-testid="lane-a-equipment">{activeJob.equipmentTag || "—"}</dd>
                </div>
                <div>
                  <dt>Fault</dt>
                  <dd data-testid="lane-a-fault">{activeJob.faultName ?? activeJob.faultType ?? "—"}</dd>
                </div>
                <div>
                  <dt>Severity</dt>
                  <dd className={`arc-sev arc-sev--${activeJob.severity || "unknown"}`} data-testid="lane-a-severity">
                    {activeJob.severity || "—"}
                  </dd>
                </div>
              </dl>
              {activeJob.handoff && (
                <p className="arc-handoff" data-testid="lane-a-handoff">
                  <Icon name="arrow" size={12} /> Routing to Operations + Diagnostics
                </p>
              )}
              {activeJob.laneAComplete && (
                <p className="arc-lane__done" data-testid="lane-a-complete">Perception complete · handed off</p>
              )}
            </section>

            {/* LANE B — operations */}
            <section className="arc-lane arc-lane--b" data-testid="lane-b">
              <div className="arc-lane__head">
                <span className="arc-lane__kicker">Lane B · Operations</span>
              </div>
              <ol className="arc-steps">
                {activeJob.laneB.map((step) => (
                  <StepRow
                    key={step.id}
                    jobId={activeJob.jobId}
                    step={step}
                    stalled={isStalled(activeJob.jobId, step.id, step.state)}
                  />
                ))}
              </ol>
              {activeJob.failover && (
                <button
                  className="arc-linkbtn"
                  data-testid="failover-target"
                  data-equipment={activeJob.failover.relatedEquipmentId}
                  onClick={() => onFocusEquipment(activeJob.failover!.relatedEquipmentId)}
                >
                  <Icon name="zap" size={11} />
                  Highlight {activeJob.failover.relatedSensorTag ?? activeJob.failover.relatedEquipmentId} on canvas
                </button>
              )}
            </section>

            {/* LANE C — diagnostics */}
            <section className="arc-lane arc-lane--c" data-testid="lane-c">
              <div className="arc-lane__head">
                <span className="arc-lane__kicker">Lane C · Diagnostic</span>
              </div>
              <ol className="arc-steps">
                {activeJob.laneC.map((step) => (
                  <StepRow
                    key={step.id}
                    jobId={activeJob.jobId}
                    step={step}
                    stalled={isStalled(activeJob.jobId, step.id, step.state)}
                  >
                    {step.id === "c-root" && activeJob.rootCause && (
                      <div className="arc-rootcard" data-testid="root-cause-card">
                        <div className="arc-rootcard__mode">
                          {activeJob.rootCause.failureModeName ?? "No declared failure mode"}
                          {activeJob.rootCause.mechanism ? (
                            <span className="cs-mono"> · {activeJob.rootCause.mechanism}</span>
                          ) : null}
                        </div>
                        {activeJob.rootCause.failureMode ? (
                          <div className="arc-rootcard__id cs-mono" data-testid="root-cause-mode">
                            {activeJob.rootCause.failureMode}
                            {activeJob.rootCause.declared ? " · declared for this equipment" : ""}
                          </div>
                        ) : (
                          <div className="arc-rootcard__id cs-mono">sensor-loss incident · no equipment failure mode</div>
                        )}
                        <p className="arc-rootcard__text">{activeJob.rootCause.explanation}</p>
                      </div>
                    )}
                    {step.id === "c-prediction" && activeJob.prediction.length > 0 && (
                      <div className="arc-predictions" data-testid="prediction-list">
                        {activeJob.prediction.map((c) => (
                          <button
                            key={c.equipmentId}
                            className="arc-prediction"
                            data-testid="prediction-item"
                            data-equipment={c.equipmentId}
                            data-risk={c.risk}
                            onClick={() => onFocusEquipment(c.equipmentId)}
                            title={c.reasons.join(" · ")}
                          >
                            <span className="arc-prediction__rank cs-mono">{Math.round(c.risk * 100)}%</span>
                            <span className="arc-prediction__tag cs-mono">{c.tag}</span>
                            <span className="arc-prediction__name">{c.name}</span>
                            <span className="arc-prediction__bar" aria-hidden="true">
                              <i style={{ width: `${Math.round(Math.min(1, c.risk) * 100)}%` }} />
                            </span>
                            <span className="arc-prediction__horizon">{c.horizon}</span>
                          </button>
                        ))}
                        {activeJob.predictionCaveat && (
                          <p className="arc-caveat">{activeJob.predictionCaveat}</p>
                        )}
                      </div>
                    )}
                    {step.id === "c-notify" && activeJob.userSummary && (
                      <div className="arc-usernotice" data-testid="user-notice">
                        <p>{activeJob.userSummary.text}</p>
                        <span className="cs-mono">{eventStamp(activeJob.userSummary.at, undefined)}</span>
                      </div>
                    )}
                  </StepRow>
                ))}
              </ol>
            </section>

            {/* Independent verification — never part of a lane's checklist. */}
            <section
              className={`arc-verified${activeJob.verified ? " is-visible" : ""}`}
              data-testid="verified-badge"
              data-visible={activeJob.verified ? "true" : "false"}
            >
              {activeJob.verified ? (
                <>
                  <span className="arc-verified__mark">
                    <Icon name="shield" size={15} />
                  </span>
                  <div>
                    <strong>Verified</strong>
                    <p className="cs-mono">
                      independent check · {activeJob.verified.ok ? "gates passed" : "gates failed"} ·{" "}
                      {activeJob.verified.verificationId ?? "verification"} · {eventStamp(activeJob.verified.at, undefined)}
                    </p>
                  </div>
                </>
              ) : (
                <span className="arc-verified__pending cs-mono">
                  Not yet verified — an agent reporting success is not proof of success.
                </span>
              )}
            </section>
          </>
        )}
      </div>
    </aside>
  );
}

function StepRow({
  jobId,
  step,
  stalled,
  children,
}: {
  jobId: string;
  step: { id: string; label: string; detail?: string; state: string; at?: number; seq?: number };
  stalled: boolean;
  children?: ReactNode;
}) {
  const state = stalled ? "stalled" : step.state;
  return (
    <li
      className={`arc-step is-${state}`}
      data-testid="arc-step"
      data-job={jobId}
      data-step={step.id}
      data-state={state}
    >
      <span className="arc-step__tick" aria-hidden="true">
        {state === "done" ? "✓" : state === "stalled" ? "!" : state === "active" ? "" : "○"}
      </span>
      <div className="arc-step__body">
        <span className="arc-step__label">{step.label}</span>
        {state === "stalled" ? (
          <span className="arc-step__detail arc-step__detail--error" data-testid="no-response">
            no response from orchestrator
          </span>
        ) : step.detail ? (
          <span className="arc-step__detail">{step.detail}</span>
        ) : null}
        {children}
      </div>
      <span className="arc-step__stamp cs-mono">{eventStamp(step.at, step.seq)}</span>
    </li>
  );
}

export { isResponseEvent };
