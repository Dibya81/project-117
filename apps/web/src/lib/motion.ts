"use client";

/**
 * Motion vocabulary.
 *
 * The console does not animate for decoration. Five verbs describe what the
 * system is actually doing, and each is bound to a real event on the SSE stream
 * — if the event does not arrive, no motion happens. That constraint is the
 * whole point: an animation that plays on a timer is a claim that something
 * occurred, and this codebase does not make claims it cannot source.
 *
 *   FLOW      telemetry moved through the process         telemetry.batch
 *   HANDOFF   work passed from one agent to another       agent.* / task.*
 *   EMERGE    evidence became available                   evidence.* / retrieval.*
 *   RESOLVE   a verification settled                      verification.* / *.completed
 *   ESCALATE  severity rose                               fault.* / alarm.*
 *
 * Reductions: `prefers-reduced-motion` collapses every verb to an instant state
 * change. Reduced motion is not "no information" — the cue still fires, it just
 * does not travel, so a user who opts out still sees that the event happened.
 */

import type { SimEvent } from "@/lib/sim/types";

export type MotionVerb = "flow" | "handoff" | "emerge" | "resolve" | "escalate";

export interface MotionCue {
  verb: MotionVerb;
  /** The event that produced this cue. Never synthesised. */
  event: SimEvent;
  /** Stable key so a surface can coalesce repeated cues for one subject. */
  subject: string;
}

/** Per-verb timing. Durations are in ms and are used by CSS transitions. */
export const MOTION: Record<MotionVerb, { duration: number; easing: string; description: string }> = {
  flow: { duration: 1400, easing: "linear", description: "telemetry moving through the process" },
  handoff: { duration: 620, easing: "cubic-bezier(0.22, 1, 0.36, 1)", description: "work passing between agents" },
  emerge: { duration: 760, easing: "cubic-bezier(0.16, 1, 0.3, 1)", description: "evidence becoming available" },
  resolve: { duration: 480, easing: "cubic-bezier(0.34, 1.3, 0.64, 1)", description: "a verification settling" },
  escalate: { duration: 900, easing: "cubic-bezier(0.36, 0, 0.66, -0.2)", description: "severity rising" },
};

/**
 * Which verb, if any, an event expresses.
 *
 * Unmatched events return null rather than a default. A default would mean
 * every event animated the same way, which tells the operator nothing and is
 * how decorative motion gets in.
 */
export function verbFor(type: string): MotionVerb | null {
  if (type.startsWith("telemetry.")) return "flow";
  if (type.startsWith("evidence.") || type.startsWith("retrieval.")) return "emerge";
  if (type.startsWith("verification.") || type.endsWith(".completed") || type.endsWith(".verified")) {
    return "resolve";
  }
  if (type.startsWith("fault.") || type.startsWith("alarm.") || type.startsWith("incident.")) {
    return "escalate";
  }
  if (type.startsWith("agent.") || type.startsWith("task.") || type.startsWith("handoff.")) {
    return "handoff";
  }
  return null;
}

/**
 * The subject a cue is about, so repeated events coalesce onto one surface
 * instead of stacking. Falls back to the plant, never to a fabricated id.
 */
export function subjectOf(event: SimEvent): string {
  const p = event.payload ?? {};
  for (const key of [
    "equipment_id",
    "related_equipment_id",
    "sensor_id",
    "job_id",
    "task_id",
    "agent",
    "department",
  ]) {
    const v = p[key];
    if (typeof v === "string" && v) return v;
  }
  return event.plant_id ?? "plant";
}

/** Classify one event. Null when it expresses no motion. */
export function cueFor(event: SimEvent): MotionCue | null {
  const verb = verbFor(String(event.type ?? ""));
  return verb ? { verb, event, subject: subjectOf(event) } : null;
}

/** True when the viewer has asked for reduced motion. */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * The duration to actually use. Zero under reduced motion, so the cue still
 * fires but arrives instantly instead of travelling.
 */
export function durationFor(verb: MotionVerb, reduced = prefersReducedMotion()): number {
  return reduced ? 0 : MOTION[verb].duration;
}

/**
 * A cue's CSS custom properties, for inline application by a surface.
 * Kept here so every surface animates with the same vocabulary and timing.
 */
export function cueStyle(verb: MotionVerb, reduced = prefersReducedMotion()) {
  return {
    "--motion-duration": `${durationFor(verb, reduced)}ms`,
    "--motion-easing": MOTION[verb].easing,
  } as React.CSSProperties;
}
