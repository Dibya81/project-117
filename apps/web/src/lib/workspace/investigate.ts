"use client";

/**
 * A real investigation: one grounded turn through POST /api/chat.
 *
 * This replaces the scripted runner that used to live in lib/demo/runTask.ts.
 * That version advanced a canned Compressor C-3 timeline on a timer and
 * returned the same fabricated result whatever the operator typed — including
 * invented claims, citations and a verified badge. Nothing about it depended on
 * the plant, the corpus, or the model.
 *
 * What is shown now is only what the turn actually produced:
 *
 *  * `context`  — the evidence chunks retrieval returned, verbatim.
 *  * `trace`    — real milestones with the backend's measured latency.
 *  * `result`   — the model's answer, unedited.
 *  * `checks`   — two gates computed from the response itself (were chunks
 *                 retrieved, and did the answer cite them by their [S<n>]
 *                 markers). A question with no grounding is reported as
 *                 pending, not as verified.
 *
 * There are deliberately no `claims`: the backend does not return per-claim
 * verification, and manufacturing it would put a green tick next to a sentence
 * nobody checked.
 */
import { api } from "@/lib/api";
import { consoleData } from "@/lib/data/console";
import type { Citation, ChatEvidence } from "@/types";
import type { WorkspaceTask } from "@/types/console";

/** Map a retrieved chunk onto the citation shape the workspace renders. */
function toCitation(e: ChatEvidence): Citation {
  const heading = e.citation.heading_path?.filter(Boolean).join(" > ");
  return {
    document_id: e.citation.document_id,
    filename: e.document?.filename ?? e.citation.document_id,
    ...(e.citation.page != null ? { page: e.citation.page } : {}),
    ...(heading ? { section: heading } : {}),
    chunk_index: e.citation.chunk_index,
    snippet: e.text,
  };
}

/**
 * Which snippets the answer actually referenced.
 *
 * The grounded system prompt requires citations in the form [S<n>], where n
 * numbers the snippets in the order they were supplied. A marker outside that
 * range does not count: it points at no evidence, so treating it as a citation
 * would overstate how well-sourced the answer is.
 */
function citedIndices(answer: string, available: number): number[] {
  const found = new Set<number>();
  for (const match of answer.matchAll(/\[S(\d+)\]/g)) {
    const n = Number(match[1]);
    if (n >= 1 && n <= available) found.add(n);
  }
  return [...found].sort((a, b) => a - b);
}

function baseTask(request: string, step: WorkspaceTask["step"]): WorkspaceTask {
  return {
    id: `chat-${Date.now()}`,
    // /api/chat does not create a job, so there is no job id. An empty string
    // is honest; inventing a plausible one would not be.
    job_id: "",
    request,
    agent: "orchestrator",
    step,
    context: [],
    trace: [],
    artifacts: [],
    checks: [],
  };
}

export interface InvestigationHandle {
  /** Cancel locally. The HTTP request is not aborted mid-flight. */
  cancel: () => void;
}

export function runInvestigation(
  prompt: string,
  onUpdate: (task: WorkspaceTask) => void,
): InvestigationHandle {
  let cancelled = false;
  const emit = (t: WorkspaceTask) => {
    if (!cancelled) onUpdate(t);
  };

  emit({
    ...baseTask(prompt, "retrieving"),
    trace: [{ label: "Request received", done: true }],
  });

  void (async () => {
    const started = performance.now();
    try {
      const turn = await api.chat.create({ message: prompt, use_rag: true });
      if (cancelled) return;

      const evidence = turn.evidence ?? [];
      const context = evidence.map(toCitation);
      const answered = Math.round(performance.now() - started);
      const cited = citedIndices(turn.response ?? "", evidence.length);

      const documents = new Set(context.map((c) => c.document_id)).size;

      emit({
        ...baseTask(prompt, "complete"),
        context,
        result: turn.response,
        trace: [
          {
            // No duration on this row: the backend does not report how long
            // retrieval took, and the wall-clock delta between the client and
            // the model call is not the same measurement. Stating only what was
            // measured is better than labelling an estimate as retrieval time.
            label: "Evidence retrieved",
            detail: evidence.length
              ? `${evidence.length} chunk${evidence.length === 1 ? "" : "s"} from ${documents} document${documents === 1 ? "" : "s"}`
              : "no grounding retrieved — answered from the model alone",
            done: true,
          },
          {
            label: `${turn.model} answered`,
            detail: `${turn.provider || "local"} · ${evidence.length} snippet${evidence.length === 1 ? "" : "s"} in prompt`,
            duration_ms: Math.round(turn.latency_ms),
            done: true,
          },
          {
            label: "Turn completed",
            detail: "end-to-end as the browser measured it",
            duration_ms: answered,
            done: true,
          },
        ],
        checks: [
          {
            name: "Evidence",
            status: evidence.length ? "verified" : "pending",
            detail: evidence.length
              ? `${evidence.length} chunk${evidence.length === 1 ? "" : "s"}`
              : "nothing retrieved for this question",
          },
          {
            name: "Citations",
            status: evidence.length && cited.length ? "verified" : "pending",
            detail: evidence.length
              ? cited.length
                ? `${cited.length} of ${evidence.length} snippets cited`
                : "the answer cites no supplied snippet"
              : "no snippets to cite",
          },
        ],
      });
    } catch (err) {
      if (cancelled) return;
      const message = err instanceof Error ? err.message : String(err);
      emit({
        ...baseTask(prompt, "failed"),
        result: message,
        trace: [{ label: "Turn failed", detail: message, done: false }],
        checks: [{ name: "Evidence", status: "failed", detail: "the turn did not complete" }],
      });
    }
  })();

  return {
    cancel: () => {
      cancelled = true;
    },
  };
}

/** Sessions are served by the real store; this keeps the import surface local. */
export const workspaceSessions = () => consoleData.workspace.sessions();
