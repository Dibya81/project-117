"use client";

/**
 * Agent recovery panel — what the agents are doing about one lost measurement.
 *
 * Opens when an operator takes a sensor out of service or deletes it, and stays
 * anchored to the right edge so the circuit stays visible behind it. It is a
 * popup, not a page: the plant map must remain readable while the agents work.
 *
 * Every fact here is real engine output. The agent steps are the incident's own
 * pipeline tasks (their titles, tools and evidence come from the engine's
 * redundancy walk), and the recovery path is the same pure rule the engine uses
 * to decide whether the process is still readable. Nothing is scripted for
 * display.
 *
 * The staging is presentational: the pipeline itself runs synchronously, so the
 * panel reveals its already-computed steps in sequence and marks the last as
 * in-flight. It never claims progress that has not happened — once the reveal
 * finishes, the panel stays put showing the completed evidence.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { StatusDot, Tag } from "@/components/ui/primitives";
import { Icon } from "@/components/ui/Icon";
import type { AgentTask } from "@/lib/sim/types";
import type { RecoveryCircuit } from "@/lib/sim/recovery";

export interface RecoveryFocus {
  sensorId: string;
  sensorTag: string;
  measurement: string;
  unit: string;
  equipmentTag: string;
  action: "disable" | "remove";
  circuit: RecoveryCircuit | null;
  tasks: AgentTask[];
  planSteps: string[];
}

/** Per-step reveal cadence. Long enough to read, short enough not to drag. */
const STEP_MS = 620;

const AGENT_LABEL: Record<string, string> = {
  orchestrator: "Orchestrator",
  data_analysis: "Data analysis",
  maintenance: "Maintenance",
  operations: "Operations",
  safety: "Safety",
  documentation: "Documentation",
};

export function SensorRecoveryPanel({
  focus,
  onClose,
  onRestore,
  onReset,
}: {
  focus: RecoveryFocus | null;
  onClose: () => void;
  onRestore: () => void;
  onReset: () => void;
}) {
  const [revealed, setRevealed] = useState(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const steps = useMemo(() => focus?.tasks ?? [], [focus]);

  // Restart the reveal whenever a new recovery begins, and stop cleanly if the
  // panel closes mid-run so a stale timer cannot revive it.
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    setRevealed(0);
    if (!focus || steps.length === 0) return;
    let done = 0;
    const tick = () => {
      done += 1;
      setRevealed(done);
      if (done < steps.length) timer.current = setTimeout(tick, STEP_MS);
    };
    timer.current = setTimeout(tick, STEP_MS);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [focus, steps]);

  if (!focus) return null;

  const circuit = focus.circuit;
  const alternates = circuit?.alternates ?? [];
  const complete = revealed >= steps.length;
  const working = complete ? -1 : Math.min(revealed, Math.max(0, steps.length - 1));

  return (
    <aside className="sm-rec" role="dialog" aria-label="Agent recovery">
      <header className="sm-rec__head">
        <div className="sm-rec__headline">
          <span className="sm-rec__pulse" aria-hidden="true" />
          <span className="cs-mono sm-rec__kicker">
            {complete ? "Recovery assessed" : "Agents working"}
          </span>
        </div>
        <button className="sm-rec__close" onClick={onClose} aria-label="Close recovery panel">
          <Icon name="x" size={13} />
        </button>

        <p className="sm-rec__title">
          {focus.sensorTag} <span className="cs-dim">· {focus.measurement}</span>
        </p>
        <div className="sm-rec__chips">
          <Tag tone={focus.action === "remove" ? "crit" : "warn"}>
            {focus.action === "remove" ? "deleted" : "out of service"}
          </Tag>
          <span className="cs-mono cs-dim">on {focus.equipmentTag}</span>
        </div>
      </header>

      {/* The circuit the agents are working: the lost point and what it fed. */}
      <section className="sm-rec__section">
        <p className="sm-rec__label">Affected circuit</p>
        <div className="sm-rec__circuit">
          <div className="sm-rec__node sm-rec__node--down">
            <StatusDot state="critical" pulse />
            <div>
              <b className="cs-mono">{focus.sensorTag}</b>
              <span className="cs-mono cs-dim">measurement lost</span>
            </div>
          </div>
          <div className="sm-rec__link" aria-hidden="true">
            <span className="sm-rec__linkline" />
            <span className="sm-rec__spark" />
          </div>
          <div className="sm-rec__node">
            <Icon name="equipment" size={14} />
            <div>
              <b className="cs-mono">{focus.equipmentTag}</b>
              <span className="cs-mono cs-dim">owning unit</span>
            </div>
          </div>
          {circuit && circuit.downstream.length > 0 && (
            <>
              <div className="sm-rec__link" aria-hidden="true">
                <span className="sm-rec__linkline" />
                <span className="sm-rec__spark sm-rec__spark--delay" />
              </div>
              <div className="sm-rec__node">
                <Icon name="layers" size={14} />
                <div>
                  <b className="cs-mono">
                    {circuit.downstream.length} downstream
                  </b>
                  <span className="cs-mono cs-dim">
                    {circuit.downstream.slice(0, 3).map((e) => e.tag).join(" · ")}
                    {circuit.downstream.length > 3 ? " …" : ""}
                  </span>
                </div>
              </div>
            </>
          )}
        </div>
      </section>

      {/* The agents, revealed in pipeline order. */}
      <section className="sm-rec__section sm-rec__section--grow">
        <p className="sm-rec__label">
          Agent response · {Math.min(revealed, steps.length)}/{steps.length}
        </p>
        {steps.length === 0 ? (
          <p className="sm-rec__empty">
            No agent pipeline ran for this point. The engine raises an incident when
            the loss is safety-relevant; this one was recorded as a configuration change.
          </p>
        ) : (
          <ol className="sm-rec__steps">
            {steps.map((t, i) => {
              const state = i < revealed ? "done" : i === working ? "working" : "queued";
              const tool = t.tools[0];
              return (
                <li key={t.id} className={`sm-rec__step is-${state}`}>
                  <span className="sm-rec__bead" aria-hidden="true">
                    {state === "done" ? "✓" : state === "working" ? "" : ""}
                  </span>
                  <div className="sm-rec__body">
                    <div className="sm-rec__row">
                      <b className="cs-mono">{AGENT_LABEL[t.agent] ?? t.agent}</b>
                      {state === "working" && <span className="sm-rec__badge">working</span>}
                    </div>
                    <p className="sm-rec__task">{t.title}</p>
                    {state !== "queued" && tool && (
                      <p className="cs-mono sm-rec__tool">
                        {tool.tool} — {tool.summary}
                      </p>
                    )}
                    {state === "done" && t.result && <p className="sm-rec__result">{t.result}</p>}
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </section>

      {/* The recovery the agents found: real alternates, or an honest nothing. */}
      <section className="sm-rec__section">
        <p className="sm-rec__label">Recovery path</p>
        {alternates.length === 0 ? (
          <p className="sm-rec__empty">
            No alternate measurement available — this point is unreadable. Treat the
            condition as unknown until the instrument is back in service.
          </p>
        ) : (
          <ul className="sm-rec__alts">
            {alternates.map((a, i) => (
              <li
                key={a.sensor.id}
                className="sm-rec__alt"
                style={{ animationDelay: `${i * 90}ms` }}
              >
                <StatusDot state="ok" />
                <div>
                  <b className="cs-mono">{a.sensor.tag}</b>
                  <span className="cs-mono cs-dim">{a.why}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {focus.planSteps.length > 0 && (
        <section className="sm-rec__section">
          <p className="sm-rec__label">Plan</p>
          <ol className="sm-rec__plan">
            {focus.planSteps.map((s) => (
              <li key={s} className="cs-mono">
                {s}
              </li>
            ))}
          </ol>
        </section>
      )}

      <footer className="sm-rec__foot">
        {focus.action === "disable" && (
          <button className="sm-rec__btn" onClick={onRestore}>
            Return to service
          </button>
        )}
        <button className="sm-rec__btn sm-rec__btn--ghost" onClick={onReset}>
          Reset plant
        </button>
      </footer>
    </aside>
  );
}
