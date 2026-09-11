"use client";

/**
 * AI Workspace — conversation + task execution surface.
 * Left: sessions. Center: conversation with live TaskCard. Right: contextual
 * panel (Evidence / Execution / Artifacts / Verification).
 * Demo mode: the composer drives the scripted C-3 investigation timeline.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Panel, StatusDot, Tag, SkeletonRows, timeAgo } from "@/components/ui/primitives";
import { Tabs } from "@/components/ui/primitives";
import { TaskCard } from "@/components/workspace/TaskCard";
import { VerificationSummary } from "@/components/workspace/VerificationSummary";
import { ArtifactCard } from "@/components/workspace/ArtifactPreview";
import { Icon } from "@/components/ui/Icon";
import { consoleData } from "@/lib/data/console";
import { useJourney } from "@/lib/journey";
import { runC3Investigation } from "@/lib/demo/runTask";
import type { WorkspaceSession, WorkspaceTask } from "@/types/console";

const SUGGESTIONS = [
  "Analyze Compressor C-3 and tell me why vibration increased.",
  "Draft a work order for the P-1042 pressure anomaly.",
  "Summarize Unit 200 performance this week.",
];

export default function WorkspacePage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<WorkspaceSession[] | null>(null);
  const [activeSession, setActiveSession] = useState("s-1");
  const [task, setTask] = useState<WorkspaceTask | null>(null);
  const [hasRun, setHasRun] = useState(false);
  const [input, setInput] = useState("");
  const [tab, setTab] = useState("evidence");
  const { visit } = useJourney();
  const cancelRef = useRef<(() => void) | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    consoleData.workspace.sessions().then(setSessions);
    return () => cancelRef.current?.();
  }, []);

  // Deep link from the Knowledge Universe: ?entity=<label> pre-loads the
  // investigation prompt so the graph node arrives as context.
  useEffect(() => {
    const entity = new URLSearchParams(window.location.search).get("entity");
    if (entity) setInput(`Investigate ${entity}`);
  }, []);

  const run = useCallback((prompt: string) => {
    cancelRef.current?.();
    setHasRun(true);
    setTab("evidence");
    visit({ id: `inv-${Date.now()}`, label: prompt.slice(0, 34) || "New investigation", kind: "investigation", href: "/console/workspace" });
    void prompt;
    cancelRef.current = runC3Investigation((t) => {
      setTask({ ...t, request: prompt || t.request });
      setTimeout(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" }), 60);
    });
  }, [visit]);

  const submit = () => {
    const q = input.trim();
    if (!q) return;
    setInput("");
    run(q);
  };

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
            <div className="cs-fade-list">
              {sessions.map((s) => (
                <button
                  key={s.id}
                  className="cs-row"
                  style={{
                    width: "100%",
                    background: activeSession === s.id ? "rgba(69,213,255,0.07)" : "none",
                    border: "0",
                    textAlign: "left",
                    font: "inherit",
                    boxShadow: activeSession === s.id ? "inset 2px 0 0 var(--cyan)" : "none",
                  }}
                  onClick={() => setActiveSession(s.id)}
                >
                  <span>
                    <div className="cs-row__title" style={{ fontSize: 12.5 }}>{s.title}</div>
                    <div className="cs-row__sub">{s.task_count} task{s.task_count === 1 ? "" : "s"} · {timeAgo(s.at)}</div>
                  </span>
                </button>
              ))}
              <div style={{ padding: 12 }}>
                <button className="cs-btn cs-btn--ghost" style={{ width: "100%", justifyContent: "center" }} onClick={() => setHasRun(false)}>
                  <Icon name="plus" size={13} /> New session
                </button>
              </div>
            </div>
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
                <div style={{ display: "flex", flexDirection: "column", gap: 8, maxWidth: 460, margin: "0 auto" }}>
                  {SUGGESTIONS.map((s, i) => (
                    <button
                      key={s}
                      className="cs-row"
                      style={{
                        border: "1px solid var(--line)",
                        borderRadius: 8,
                        background: "rgba(6,10,16,0.5)",
                        font: "inherit",
                        textAlign: "left",
                        animation: `p117-fade-up 520ms var(--ease-out) ${i * 110}ms both`,
                      }}
                      onClick={() => run(s)}
                    >
                      <Icon name="zap" size={13} />
                      <span style={{ fontSize: 12.5 }}>{s}</span>
                    </button>
                  ))}
                </div>
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
          <div className="cs-composer">
            <textarea
              placeholder="Ask about equipment, documents, anomalies… (⏎ to send)"
              rows={2}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
              aria-label="Message the AI workspace"
            />
            <button className="cs-composer__send" onClick={submit} disabled={!input.trim()} aria-label="Send">
              <Icon name="send" size={16} />
            </button>
          </div>
        </div>

        {/* right panel */}
        <div className="cs-workspace__right">
          <Panel pad={false}>
            <div style={{ padding: "12px 12px 0" }}>
              <Tabs
                tabs={[
                  { id: "evidence", label: "Evidence", count: task?.context.length },
                  { id: "execution", label: "Execution" },
                  { id: "artifacts", label: "Artifacts", count: task?.artifacts.length },
                  { id: "verify", label: "Verify", count: task?.checks.length },
                ]}
                active={tab}
                onChange={setTab}
              />
            </div>
            <div className="cs-panel__body">
              {tab === "evidence" &&
                (task?.context.length ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {task.context.map((c, i) => (
                      <button
                        key={i}
                        className="cs-row"
                        style={{ border: "1px solid var(--line)", borderRadius: 8, background: "rgba(6,10,16,0.5)", font: "inherit", textAlign: "left" }}
                        onClick={() => router.push(`/console/documents?doc=${c.document_id}`)}
                      >
                        <Icon name="doc" size={14} />
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
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}
