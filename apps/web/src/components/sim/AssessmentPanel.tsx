"use client";

/**
 * Post-incident assessment — the closing beat of the response.
 *
 * Renders three things, all derived from recorded state rather than asserted:
 *
 *   1. an outcome checklist, each line tied to a condition that is actually
 *      true in the incident/snapshot (never a fixed set of ticks)
 *   2. a ranked root-cause assessment with the evidence that moved it
 *   3. the next asset at elevated risk, with the reasons it scored
 *
 * The two assessment blocks come from `lib/sim/assessment`, which is pure over
 * `(plant, snapshot, incident)` so it behaves the same whether the engine is
 * running in the browser or on the backend.
 */
import { useMemo } from "react";
import { assessRootCause, predictNextFailure } from "@/lib/sim/assessment";
import type { Incident, PlantDef, SimSnapshot } from "@/lib/sim/types";
import { Icon } from "@/components/ui/Icon";

const pct = (v: number) => `${Math.round(v * 100)}%`;

export function AssessmentPanel({
  plant,
  snapshot,
  incident,
  tasks,
  onCreateWorkOrder,
  onViewEvidence,
  onDismiss,
}: {
  plant: PlantDef;
  snapshot: SimSnapshot | null;
  incident: Incident;
  tasks: { agent: string; evidence: { id: string }[]; status: string }[];
  onCreateWorkOrder?: () => void;
  onViewEvidence?: () => void;
  onDismiss?: () => void;
}) {
  const root = useMemo(
    () => (snapshot ? assessRootCause(plant, snapshot, incident) : null),
    [plant, snapshot, incident],
  );
  const next = useMemo(
    () => (snapshot ? predictNextFailure(plant, snapshot, incident) : null),
    [plant, snapshot, incident],
  );

  const evidenceCount = tasks.reduce((n, t) => n + (t.evidence?.length ?? 0), 0);

  // Backup-sensor state, read from the snapshot rather than assumed.
  const originSensorId = incident.origin_sensor;
  const originReading = originSensorId && snapshot ? snapshot.sensors[originSensorId] : undefined;
  // `substituted` is the engine's own marker that telemetry now comes from a
  // backup; `resolved` means the incident ran through action and verification.
  const failoverDone =
    originReading?.quality === "substituted" || incident.status === "resolved";
  const originMeasurement = originSensorId
    ? plant.equipment
        .find((e) => e.id === incident.origin_equipment)
        ?.sensors.find((s) => s.id === originSensorId)?.measurement
    : undefined;
  const backupVerified = Boolean(
    originMeasurement &&
      plant.equipment.some(
        (e) =>
          e.id !== incident.origin_equipment &&
          e.sensors.some((s) => s.measurement === originMeasurement),
      ),
  ) || Boolean(
    originMeasurement &&
      plant.equipment
        .find((e) => e.id === incident.origin_equipment)
        ?.sensors.some((s) => s.id !== originSensorId && s.measurement === originMeasurement),
  );

  const checklist: { label: string; done: boolean }[] = [
    { label: "Failure detected", done: true },
    { label: "Agents coordinated", done: tasks.length > 0 },
    { label: "Evidence retrieved", done: evidenceCount > 0 },
    { label: "Backup instrument available", done: backupVerified },
    { label: "Telemetry failover executed", done: failoverDone },
    { label: "Root cause assessed", done: Boolean(root?.available) },
    { label: "Predictive analysis completed", done: Boolean(next?.available && next.candidates.length > 0) },
  ];
  const allDone = checklist.every((c) => c.done);

  const top = root?.hypotheses[0];
  const risk = next?.candidates[0];

  return (
    <section className="asm" aria-label="Incident response assessment">
      <header className="asm__head">
        <div>
          <p className="asm__kicker">Project 117</p>
          <h3 className="asm__title">
            {allDone ? "Incident response complete" : "Response in progress"}
          </h3>
          <p className="asm__sub">
            {incident.id} · {incident.title} · status {incident.status.replace(/_/g, " ")}
          </p>
        </div>
        <span className={`asm__badge asm__badge--${allDone ? "ok" : "warn"}`}>
          {allDone ? "CONTAINED" : "ACTIVE"}
        </span>
      </header>

      <ol className="asm__checks">
        {checklist.map((c) => (
          <li key={c.label} className={c.done ? "is-done" : "is-pending"}>
            <span className="asm__tick" aria-hidden="true">{c.done ? "✓" : "○"}</span>
            {c.label}
            <span className="asm__sr">{c.done ? "complete" : "pending"}</span>
          </li>
        ))}
      </ol>

      {top && (
        <div className="asm__block">
          <h4>Root cause assessment</h4>
          <div className="asm__hyp">
            <span className="asm__hyp-label">{top.label}</span>
            <span className="asm__hyp-conf">{pct(top.confidence)} confidence</span>
            <span className="asm__bar" aria-hidden="true">
              <i style={{ width: pct(top.confidence) }} />
            </span>
            <p className="asm__rationale">{top.rationale}</p>
          </div>

          {root!.hypotheses.length > 1 && (
            <ul className="asm__alts">
              {root!.hypotheses.slice(1).map((h) => (
                <li key={h.id}>
                  <span>{h.label}</span>
                  <em>{pct(h.confidence)}</em>
                </li>
              ))}
            </ul>
          )}

          <details className="asm__evidence">
            <summary>{root!.evidence.length} pieces of evidence</summary>
            <ul>
              {root!.evidence.map((e) => (
                <li key={e.id}>
                  <span className="asm__ev-src">{e.source}</span>
                  <span className="asm__ev-detail">{e.detail}</span>
                </li>
              ))}
            </ul>
          </details>

          {root!.caveat && <p className="asm__caveat">{root!.caveat}</p>}
        </div>
      )}

      {risk && (
        <div className="asm__block asm__block--risk">
          <h4>
            <Icon name="alert" size={12} /> Early warning — predicted next risk
          </h4>
          <div className="asm__risk">
            <span className="asm__risk-tag">{risk.tag}</span>
            <span className="asm__risk-name">{risk.name}</span>
            <span className="asm__risk-pct">{pct(risk.risk)}</span>
            <span className="asm__bar asm__bar--risk" aria-hidden="true">
              <i style={{ width: pct(risk.risk) }} />
            </span>
            <span className="asm__horizon">{risk.horizon}</span>
          </div>
          <ul className="asm__reasons">
            {risk.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          {next!.candidates.length > 1 && (
            <p className="asm__also">
              Also elevated:{" "}
              {next!.candidates.slice(1).map((c) => `${c.tag} ${pct(c.risk)}`).join(" · ")}
            </p>
          )}
          {next!.caveat && <p className="asm__caveat">{next!.caveat}</p>}
        </div>
      )}

      <footer className="asm__actions">
        {onViewEvidence && (
          <button className="btn btn--ghost" onClick={onViewEvidence}>
            <Icon name="eye" size={12} /> View evidence
          </button>
        )}
        {onCreateWorkOrder && (
          <button className="btn btn--primary" onClick={onCreateWorkOrder}>
            <Icon name="workorder" size={12} /> Create work order
          </button>
        )}
        {onDismiss && (
          <button className="btn btn--ghost" onClick={onDismiss}>
            Dismiss
          </button>
        )}
      </footer>
    </section>
  );
}
