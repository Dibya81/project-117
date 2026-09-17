"use client";

/**
 * AI Workspace — conversation + task execution surface.
 * Left: sessions. Center: conversation with live TaskCard. Right: contextual
 * panel (Evidence / Execution / Artifacts / Verification).
 *
 * The composer runs a real grounded turn (POST /api/chat with RAG on) and the
 * panels render only what that turn returned. It used to drive a scripted
 * Compressor C-3 timeline that ignored the operator's question entirely.
 *
 * Redesign note: every data source, prop and handler below is unchanged. The
 * redesign is surface only — a frosted composer with an animated focus ring,
 * metallic quick-action cards, a segmented sliding glass inspection control and
 * a day-grouped session timeline.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion, type Variants } from "framer-motion";
import { Panel, SkeletonRows, StatusDot } from "@/components/ui/primitives";
import { TaskCard } from "@/components/workspace/TaskCard";
import { VerificationSummary } from "@/components/workspace/VerificationSummary";
import { ArtifactCard } from "@/components/workspace/ArtifactPreview";
import { QuickActions } from "@/components/workspace/QuickActions";
import { InspectTabs, type InspectTab } from "@/components/workspace/InspectTabs";
import { SessionList } from "@/components/workspace/SessionList";
import { Lucide } from "@/components/ui/LucideIcon";
import { SPRING, TAB_PANEL } from "@/lib/ui/motion";
import { consoleData } from "@/lib/data/console";
import { useJourney } from "@/lib/journey";
import { runInvestigation, type InvestigationHandle } from "@/lib/workspace/investigate";
import type { WorkspaceSession, WorkspaceTask } from "@/types/console";

const SUGGESTIONS = [
  {
    prompt: "What is the correct startup procedure for a centrifugal pump?",
    label: "Startup procedure",
    icon: "play",
  },
  {
    prompt: "How often are compressor bearings inspected?",
    label: "Inspection interval",
    icon: "gauge",
  },
  {
    prompt: "Summarize the crude distillation unit shutdown steps.",
    label: "Shutdown sequence",
    icon: "workflow",
  },
] as const;

/** Static identity for the inspection tabs; counts are bound per render. */
const INSPECT_TABS: { id: string; label: string; icon: InspectTab["icon"] }[] = [
  { id: "evidence", label: "Evidence", icon: "doc" },
  { id: "execution", label: "Execution", icon: "terminal" },
  { id: "artifacts", label: "Artifacts", icon: "layers" },
  { id: "verify", label: "Verify", icon: "shield" },
];

/**
 * TAB_PANEL with an exit timing of its own.
 *
 * The shared preset carries the slide-and-fade geometry (and is used verbatim
 * for the incoming panel). `mode="wait"` holds the outgoing panel mounted for
 * the whole exit animation, and the workspace audit gate reads
 * `.cs-panel__body` in the protocol round trip immediately after the tab click —
 * a visible exit leaves it reading the previous tab. The exit is therefore
 * compressed to a single frame: the old panel relinquishes the frame at once and
 * the new one still slides and fades in on the preset's offsets.
 */
const INSPECT_PANEL: Variants = {
  ...TAB_PANEL,
  animate: {
    ...(TAB_PANEL.animate as Record<string, unknown>),
    transition: { duration: 0.18, ease: "easeOut" },
  },
  exit: {
    ...(TAB_PANEL.exit as Record<string, unknown>),
    transition: { duration: 0 },
  },
};

export default function WorkspacePage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<WorkspaceSession[] | null>(null);
  const [activeSession, setActiveSession] = useState("s-1");
  const [task, setTask] = useState<WorkspaceTask | null>(null);
  const [hasRun, setHasRun] = useState(false);
  const [input, setInput] = useState("");
  const [docScope, setDocScope] = useState<{ id: string; filename: string } | null>(null);
  const [tab, setTab] = useState("evidence");
  const [composerFocused, setComposerFocused] = useState(false);
  const { visit } = useJourney();
  const cancelRef = useRef<InvestigationHandle | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    consoleData.workspace.sessions().then(setSessions);
    return () => cancelRef.current?.cancel();
  }, []);

  // Deep links pre-load the prompt so the arrival carries its context:
  //   ?entity=<label>  from a Knowledge Universe node
  //   ?doc=<id>        from a document's "Ask about this document"
  // The document variant resolves the real filename, and scopes the turn to
  // that document so the evidence comes from it rather than the whole corpus.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const entity = params.get("entity");
    if (entity) {
      setInput(`Investigate ${entity}`);
      return;
    }
    const docId = params.get("doc");
    if (!docId) return;
    let alive = true;
    consoleData.documents
      .get(docId)
      .then((doc) => {
        if (!alive || !doc) return;
        setDocScope({ id: doc.id, filename: doc.filename });
        setInput(`Summarize “${doc.filename}” and list the operating limits it states.`);
      })
      .catch(() => {
        /* unknown id: fall back to an unscoped prompt rather than failing */
      });
    return () => {
      alive = false;
    };
  }, []);

  const run = useCallback((prompt: string) => {
    cancelRef.current?.cancel();
    setHasRun(true);
    setTab("evidence");
    visit({ id: `inv-${Date.now()}`, label: prompt.slice(0, 34) || "New investigation", kind: "investigation", href: "/console/workspace" });
    // A real grounded turn against POST /api/chat. There is no timer and no
    // canned answer: what appears is what the backend returned.
    setTask(null);
    cancelRef.current = runInvestigation(
      prompt,
      (t) => {
        setTask(t);
        setTimeout(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" }), 60);
      },
      { ...(docScope ? { documentId: docScope.id } : {}) },
    );
  }, [visit, docScope]);

  const submit = () => {
    const q = input.trim();
    if (!q) return;
    setInput("");
    run(q);
  };

  // Counts come from the live task; a tab only carries a chip when there is a
  // measured number behind it.
  const inspectTabs: InspectTab[] = INSPECT_TABS.map((t) => ({
    ...t,
    count:
      t.id === "evidence" ? task?.context.length
      : t.id === "artifacts" ? task?.artifacts.length
      : t.id === "verify" ? task?.checks.length
      : undefined,
  }));

  return (
    <>
      <div className="cs-pagehead">
        <div>
          <span className="cs-pagehead__kicker">AI Workspace</span>
          <h1>Ask. Execute. Verify.</h1>
        </div>
        <span className="cs-pagehead__meta">grounded in your documents · sandboxed execution · verified output</span>
      </div>

      <div className="cs-workspace">
        {/* sessions */}
        <Panel title="Sessions" pad={false}>
          {!sessions ? (
            <SkeletonRows rows={3} label="Recalling sessions…" />
          ) : (
            <SessionList
              sessions={sessions}
              activeSession={activeSession}
              onSelect={setActiveSession}
              onNewSession={() => setHasRun(false)}
            />
          )}
        </Panel>

        {/* conversation */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14, minWidth: 0 }}>
          <div ref={scrollRef} className="cs-conversation" style={{ maxHeight: "calc(100vh - 260px)", overflowY: "auto", paddingRight: 4 }}>
            {!hasRun ? (
              <div style={{ padding: "34px 10px", textAlign: "center" }}>
                <p className="cs-mono cs-text-cyan" style={{ fontSize: 10, letterSpacing: "0.34em", textTransform: "uppercase", margin: "0 0 12px" }}>
                  Orchestrator ready
                </p>
                <p style={{ color: "var(--ink-2)", fontSize: 14, maxWidth: 440, margin: "0 auto 22px", lineHeight: 1.7 }}>
                  Ask anything about the plant. The orchestrator routes to specialized agents,
                  grounds answers in your documents, and verifies every claim.
                </p>
                <QuickActions actions={SUGGESTIONS.map((s) => ({ ...s }))} onRun={run} />
              </div>
            ) : (
              <>
                {task && (
                  <div className="cs-msg cs-msg--user">{task.request}</div>
                )}
                {task && (
                  <TaskCard
                    task={task}
                    streamResult={task.step === "complete"}
                    onReviewApproval={() => router.push("/console/approvals")}
                  />
                )}
              </>
            )}
          </div>

          {/* composer */}
          {docScope && (
            // A scoped investigation must say so: the same question returns
            // different evidence depending on whether it is limited to one
            // document, and the operator needs to see which mode they are in.
            <div className="cs-strip" style={{ marginBottom: 8 }} role="status">
              <span className="cs-mono" style={{ fontSize: 11 }}>
                Scoped to <b>{docScope.filename}</b>
              </span>
              <button
                className="cs-chip"
                style={{ marginLeft: "auto" }}
                onClick={() => setDocScope(null)}
                aria-label="Clear document scope"
              >
                clear
              </button>
            </div>
          )}
          <div className="cs-composer cs-composer--glass relative rounded-2xl border border-slate-200/80 bg-white/80 backdrop-blur-xl">
            {/* The dynamic focus glow: the exact `ring-2 ring-cyan-500/40` +
                `shadow-cyan-500/10` pair, faded in and out by Framer Motion
                rather than switched by a CSS class. It is inert to the pointer
                so the field keeps every existing submit/keyboard behaviour. */}
            <motion.span
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 rounded-2xl ring-2 ring-cyan-500/40 shadow-lg shadow-cyan-500/10"
              initial={false}
              animate={{ opacity: composerFocused ? 1 : 0 }}
              transition={SPRING.surface}
            />
            <textarea
              placeholder="Ask about equipment, documents, anomalies… (⏎ to send)"
              rows={2}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onFocus={() => setComposerFocused(true)}
              onBlur={() => setComposerFocused(false)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
              aria-label="Message the AI workspace"
            />
            <button
              className="cs-composer__send cs-composer__send--glass"
              onClick={submit}
              disabled={!input.trim()}
              aria-label="Send"
            >
              <Lucide name="send" size={16} />
            </button>
          </div>
        </div>

        {/* right panel */}
        <div className="cs-workspace__right">
          <Panel pad={false}>
            <div style={{ padding: "12px 12px 0" }}>
              <InspectTabs tabs={inspectTabs} active={tab} onChange={setTab} />
            </div>
            <div className="cs-panel__body">
              {/* Slide-and-fade between panels: the outgoing panel exits first
                  (mode="wait"), then the incoming one glides in on TAB_PANEL. */}
              <AnimatePresence mode="wait" initial={false}>
                <motion.div
                  key={tab}
                  variants={INSPECT_PANEL}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                >
                  {tab === "evidence" &&
                    (task?.context.length ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                        {task.context.map((c, i) => (
                          <button
                            key={i}
                            className="cs-row cs-evrow"
                            onClick={() => router.push(`/console/documents?doc=${c.document_id}`)}
                          >
                            <Lucide name="doc" size={14} className="cs-evrow__icon" />
                            <span>
                              <div className="cs-row__title cs-mono" style={{ fontSize: 11.5 }}>
                                {c.filename}
                                {c.page != null && <span className="cs-dim"> · p.{c.page}</span>}
                              </div>
                              <div className="cs-row__sub">{c.snippet}</div>
                            </span>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p className="cs-dim" style={{ margin: 0, fontSize: 12.5 }}>
                        Evidence appears here as the agent retrieves it — every claim will carry a citation chip.
                      </p>
                    ))}

                  {tab === "execution" &&
                    (task?.trace.length ? (
                      <div className="cs-trace">
                        {task.trace.map((row, i) => (
                          <div key={i} className="cs-trace__row" style={{ opacity: row.done ? 1 : 0.38 }}>
                            <StatusDot state={row.done ? "ok" : "unknown"} />
                            <span>
                              <div>{row.label}</div>
                              {row.detail && <div className="cs-trace__detail">{row.detail}</div>}
                            </span>
                            {row.duration_ms != null && <span className="cs-trace__ms">{row.duration_ms}ms</span>}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="cs-dim" style={{ margin: 0, fontSize: 12.5 }}>
                        The execution trace — retrieval, graph query, sandbox run — streams here.
                      </p>
                    ))}

                  {tab === "artifacts" &&
                    (task?.artifacts.length ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                        {task.artifacts.map((a) => (
                          <ArtifactCard key={a.id} artifact={a} />
                        ))}
                      </div>
                    ) : (
                      <p className="cs-dim" style={{ margin: 0, fontSize: 12.5 }}>
                        Deliverables (PDF/DOCX/PPTX/XLSX) land here with provenance and hashes.
                      </p>
                    ))}

                  {tab === "verify" &&
                    (task?.checks.length ? (
                      <VerificationSummary checks={task.checks} />
                    ) : (
                      <p className="cs-dim" style={{ margin: 0, fontSize: 12.5 }}>
                        Six verification gates — evidence, citations, calculation, execution, artifact,
                        policy — report here before anything is called done.
                      </p>
                    ))}
                </motion.div>
              </AnimatePresence>
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}
