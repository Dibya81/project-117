/**
 * Agent trace panel.
 *
 * Renders the orchestrator's trace for the current job. In live mode the list
 * grows only from frames that arrived on the socket — there is no timer and no
 * pre-scripted sequence. In mock mode the entries are banner-marked and each
 * row is individually tagged, so a fallback can never be read as a live run.
 *
 * PLAN and EXECUTION are the same event stream split by stage: perceive/plan
 * are the planning half, act/verify/complete are the execution half. A stage
 * that has not reported yet shows as waiting rather than being faked.
 */
import { useMemo } from "react";
import { useOrchestrator } from "../ws/orchestrator";
import type { TraceEntry, TraceStage } from "../types";

const PLAN_STAGES: TraceStage[] = ["perceive", "plan"];
const EXEC_STAGES: TraceStage[] = ["act", "verify", "complete", "recover"];

const STAGE_LABEL: Record<TraceStage, string> = {
  perceive: "PERCEIVE",
  plan: "PLAN",
  act: "ACT",
  verify: "VERIFY",
  complete: "COMPLETE",
  recover: "RECOVER",
};

/** What we are still waiting for, per half — shown instead of inventing steps. */
const PLAN_EXPECTED = ["Job accepted", "Plan issued"];
const EXEC_EXPECTED = ["Tool completed", "Verification", "Artifact"];

function StageColumn({
  title,
  stages,
  entries,
  expected,
  synthetic,
}: {
  title: string;
  stages: TraceStage[];
  entries: TraceEntry[];
  expected: string[];
  synthetic: boolean;
}) {
  const mine = entries.filter((e) => stages.includes(e.stage));
  const waiting = expected.length - Math.min(expected.length, mine.length);

  return (
    <div className="trace__col">
      <h4>
        {title}
        {synthetic && <span className="trace__synthetic-tag">mock</span>}
      </h4>
      <ol className="trace__list">
        {mine.map((e) => (
          <li key={e.id} className={`trace__item trace__item--${e.stage}${e.synthetic ? " is-synthetic" : ""}`}>
            <span className="trace__stage">{STAGE_LABEL[e.stage]}</span>
            <span className="trace__label">{e.label}</span>
            {e.detail && <span className="trace__detail">{e.detail}</span>}
            <span className="trace__time">{new Date(e.at).toLocaleTimeString()}</span>
          </li>
        ))}
        {Array.from({ length: Math.max(0, waiting) }).map((_, i) => (
          <li key={`w-${i}`} className="trace__item trace__item--waiting">
            <span className="trace__stage">WAITING</span>
            <span className="trace__label">Awaiting the next orchestrator event…</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function AgentTracePanel() {
  const { traces, artifacts, jobId, status, mockReason, lastError, reset } = useOrchestrator();

  const synthetic = traces.some((t) => t.synthetic);
  const connected = status === "open";

  const headline = useMemo(() => {
    if (status === "open") return { tone: "ok", text: `Orchestrator connected — job ${jobId ?? "none"}` };
    if (status === "connecting") return { tone: "warn", text: "Connecting to the orchestrator…" };
    if (status === "mock") return { tone: "mock", text: "MOCK MODE — no orchestrator is connected" };
    return { tone: "idle", text: "Idle — inject a fault to open a job" };
  }, [status, jobId]);

  return (
    <section className={`trace trace--${headline.tone}`} aria-label="Agent trace">
      <header className="trace__head">
        <div className="trace__title">
          <span className="trace__kicker">Agent trace</span>
          <span className="trace__status">{headline.text}</span>
        </div>
        <div className="trace__actions">
          {traces.length > 0 && (
            <button className="btn btn--ghost" onClick={reset}>
              Clear
            </button>
          )}
        </div>
      </header>

      {status === "mock" && (
        <div className="mockbanner" role="alert">
          <strong>MOCK MODE</strong>
          <span>{mockReason ?? lastError ?? "The orchestrator WebSocket is not reachable."}</span>
          <span className="mockbanner__note">
            The sequence below is generated in the browser and is not a real investigation.
            Set <code>VITE_ORCHESTRATOR_WS_URL</code> and reload to run live.
          </span>
        </div>
      )}

      {!connected && status !== "mock" && (
        <p className="trace__hint">
          Nothing is pre-scripted. The list below fills only from events that arrive on the socket.
        </p>
      )}

      <div className="trace__cols">
        <StageColumn
          title="Plan"
          stages={PLAN_STAGES}
          entries={traces}
          expected={PLAN_EXPECTED}
          synthetic={synthetic}
        />
        <StageColumn
          title="Execution"
          stages={EXEC_STAGES}
          entries={traces}
          expected={EXEC_EXPECTED}
          synthetic={synthetic}
        />
      </div>

      {artifacts.length > 0 && (
        <div className="trace__artifacts">
          <h4>Artifacts</h4>
          <ul>
            {artifacts.map((a) => (
              <li key={a.id}>
                <a href={a.url} download={a.filename} className="artifact">
                  <span className="artifact__name">{a.filename}</span>
                  <span className="artifact__job">{a.job_id}</span>
                  <span className="artifact__dl">download</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
