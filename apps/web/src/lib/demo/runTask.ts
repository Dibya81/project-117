"use client";

/**
 * Demo task runner — drives the C-3 investigation through its visible states.
 * Today it scripts the timeline; when the backend websocket is live, job/tool/
 * verification events replace these timers with the same state transitions.
 */
import type { TaskStep, WorkspaceTask } from "@/types/console";
import { C3_TASK } from "@/lib/mock/console";

const TIMELINE: Array<{ at: number; step: TaskStep; traceUpTo?: number }> = [
  { at: 0, step: "request" },
  { at: 700, step: "retrieving", traceUpTo: 1 },
  { at: 2100, step: "analyzing", traceUpTo: 2 },
  { at: 3400, step: "analyzing", traceUpTo: 3 },
  { at: 4200, step: "executing", traceUpTo: 4 },
  { at: 6800, step: "verifying", traceUpTo: 5 },
  { at: 8000, step: "complete", traceUpTo: 6 },
];

export function runC3Investigation(onUpdate: (task: WorkspaceTask) => void): () => void {
  const timers: ReturnType<typeof setTimeout>[] = [];

  for (const beat of TIMELINE) {
    timers.push(
      setTimeout(() => {
        const traceCount = beat.traceUpTo ?? 0;
        const snapshot: WorkspaceTask = {
          ...C3_TASK,
          step: beat.step,
          trace: C3_TASK.trace.map((row, i) => ({ ...row, done: i < traceCount })),
          result: beat.step === "complete" ? C3_TASK.result : undefined,
          claims: beat.step === "complete" ? C3_TASK.claims : undefined,
          artifacts: beat.step === "complete" ? C3_TASK.artifacts : [],
          checks: beat.step === "complete" ? C3_TASK.checks : [],
          needs_approval: beat.step === "complete" ? C3_TASK.needs_approval : null,
          context: traceCount >= 1 ? C3_TASK.context : [],
        };
        onUpdate(snapshot);
      }, beat.at),
    );
  }

  return () => timers.forEach(clearTimeout);
}
