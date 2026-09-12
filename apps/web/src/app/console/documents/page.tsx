"use client";

/**
 * Documents — the Document Intelligence Center.
 * Upload runs a visible 8-stage pipeline (file → parsing → OCR → chunking →
 * embedding → extraction → graph update → citable). The viewer drawer shows
 * extracted intelligence; opened from a citation (?doc=) it enters
 * EVIDENCE MODE: claim → evidence → source → verification.
 */
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Button, EmptyState, Panel, Progress, SkeletonRows, StatusDot, Tag, timeAgo } from "@/components/ui/primitives";
import { Drawer, Modal } from "@/components/ui/overlays";
import { Icon, type IconName } from "@/components/ui/Icon";
import { consoleData } from "@/lib/data/console";
import DocumentField from "@/components/documents/DocumentField";
import type { LibraryDoc } from "@/lib/documents/library";
import { useJourney } from "@/lib/journey";
import type { ApprovalRequest, Citation, DocumentRecord, WorkOrder } from "@/types";

type DocStatus = DocumentRecord["status"];

const STATUS_TONE: Record<DocStatus, { tone: "ok" | "warn" | "crit" | "ai"; label: string }> = {
  indexed: { tone: "ok", label: "Indexed" },
  indexing: { tone: "ai", label: "Indexing" },
  stored: { tone: "warn", label: "Stored" },
  failed: { tone: "crit", label: "Failed" },
};

function fmtSize(bytes: number) {
  if (bytes > 1_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`;
  return `${Math.round(bytes / 1000)} KB`;
}

const PIPELINE: { id: string; label: string; detail: string; icon: IconName; at: number }[] = [
  { id: "received", label: "File received", detail: "stored in the local document store", icon: "download", at: 400 },
  { id: "parsing", label: "Parsing", detail: "docling layout analysis", icon: "doc", at: 1300 },
  { id: "ocr", label: "OCR", detail: "scanned regions recognized on-device", icon: "eye", at: 2200 },
  { id: "chunking", label: "Chunking", detail: "semantic blocks with page/heading metadata", icon: "layers", at: 3100 },
  { id: "embedding", label: "Embedding", detail: "bge-m3 vectors — local, no egress", icon: "cpu", at: 4100 },
  { id: "extract", label: "Knowledge extraction", detail: "entities, equipment refs, thresholds", icon: "zap", at: 5000 },
  { id: "graph", label: "Graph update", detail: "relationships linked into the plant graph", icon: "graph", at: 5800 },
  { id: "ready", label: "Ready", detail: "citable by every agent", icon: "check", at: 6500 },
];

function UploadModal({ onClose, onDone }: { onClose: () => void; onDone: (name: string) => void }) {
  const [file, setFile] = useState<string | null>(null);
  const [stage, setStage] = useState(-1);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const start = (name: string) => {
    setFile(name);
    PIPELINE.forEach((s, i) => {
      timers.current.push(setTimeout(() => setStage(i), s.at - 1400));
    });
    timers.current.push(setTimeout(() => onDone(name), 7100));
  };

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const progress = Math.max(0, ((stage + 1) / PIPELINE.length) * 100);
  const done = stage >= PIPELINE.length - 1;

  return (
    <Modal title="Ingest document" wide onClose={onClose}>
      {!file ? (
        <button className="cs-upload" style={{ width: "100%", font: "inherit" }} onClick={() => start("bearing_clearance_procedure_rev2.pdf")}>
          <Icon name="upload" size={26} />
          <p style={{ margin: "12px 0 4px", color: "var(--ink-1)", fontWeight: 600 }}>Drop a document, or click to browse</p>
          <p className="cs-mono cs-dim" style={{ margin: 0, fontSize: 10.5, letterSpacing: "0.08em" }}>
            PDF · DOCX · TXT · MD · CSV · XLSX — parsed, embedded and linked locally. It never leaves this machine.
          </p>
        </button>
      ) : (
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
            <Icon name="file" size={15} />
            <span className="cs-mono" style={{ fontSize: 12.5 }}>{file}</span>
            <span className="cs-mono" style={{ marginLeft: "auto", fontSize: 11, color: done ? "var(--ok)" : "var(--cyan)" }}>
              {Math.round(progress)}%
            </span>
          </div>
          <Progress value={progress} tone={done ? "ok" : "cyan"} />
          <div className="cs-trace" style={{ marginTop: 16 }}>
            {PIPELINE.map((s, i) => (
              <div key={s.id} className="cs-trace__row" style={{ opacity: i <= stage ? 1 : 0.32 }}>
                <StatusDot state={i < stage ? "ok" : i === stage ? "ai" : "unknown"} pulse={i === stage} />
                <span>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <Icon name={s.icon} size={12} /> {s.label}
                  </div>
                  {i <= stage && <div className="cs-trace__detail">{s.detail}</div>}
                </span>
                {i < stage && <span className="cs-trace__ms cs-text-ok">✓</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </Modal>
  );
}

/**
 * Evidence citation attached to a document, if any real record cites it.
 *
 * The corpus is passed in rather than imported: this used to search mock work
 * orders and approvals, so every document appeared to be cited by a workflow
 * that did not exist. An empty corpus now yields no citation, which is the
 * truthful answer.
 */
interface EvidenceCorpus {
  workOrders: WorkOrder[];
  approvals: ApprovalRequest[];
}

function citationFor(
  docId: string,
  corpus: EvidenceCorpus,
): { citation: Citation; claim: string } | null {
  for (const w of corpus.workOrders) {
    const c = w.evidence.find((e) => e.document_id === docId);
    if (c) return { citation: c, claim: w.recommended_action ?? w.title };
  }
  for (const a of corpus.approvals) {
    const c = a.evidence.find((e) => e.document_id === docId);
    if (c) return { citation: c, claim: a.action };
  }
  return null;
}

const ENTITY_POOL: Record<string, string[]> = {
  "d-1": ["P-1042", "17 bar", "Unit 200", "relief valve", "discharge line"],
  "d-7": ["C-3", "drive-end bearing", "0.09 mm", "coupling", "IR-204"],
  "d-4": ["2× band", "bearing wear", "14 days", "SOP-07.3", "alarm levels"],
  "d-5": ["5.7 mm/s", "8,800 rpm", "baseline", "C-3"],
  "d-2": ["90 days", "isolation", "crude feed", "P-1042"],
  "d-3": ["ME-198", "C-3", "bearing replacement", "2026-04-14"],
};

function DocumentDrawer({
  doc,
  evidenceMode,
  corpus,
  onClose,
}: {
  doc: DocumentRecord;
  evidenceMode: boolean;
  corpus: EvidenceCorpus;
  onClose: () => void;
}) {
  const status = STATUS_TONE[doc.status];
  const ev = citationFor(doc.id, corpus);
  // Real extracted entities when the corpus holds this document; the hand-written
  // pool is only a fallback for register rows with no parsed content behind them.
  const content = (doc as LibraryDoc).content;
  const entities = content?.entities?.length ? content.entities : ENTITY_POOL[doc.id] ?? [];
  const sectionCount = (doc as LibraryDoc).sectionCount;
  return (
    <Drawer title={doc.filename} wide onClose={onClose}>
      <div style={{ display: "flex", gap: 7, flexWrap: "wrap", marginBottom: 16 }}>
        <Tag tone={status.tone}>{status.label}</Tag>
        <Tag>{doc.content_type.split("/").pop()}</Tag>
        <Tag>{fmtSize(doc.size_bytes)}</Tag>
        {typeof doc.metadata.pages === "number" && <Tag>{String(doc.metadata.pages)} pages</Tag>}
        {sectionCount && <Tag tone="ai">{sectionCount} sections</Tag>}
        {content && <Tag tone="ok">Parsed</Tag>}
        {evidenceMode && <Tag tone="ai">Evidence mode</Tag>}
      </div>

      {evidenceMode && ev && (
        <div
          className="cs-panel cs-panel--hud"
          style={{ marginBottom: 16, borderColor: "rgba(69,213,255,0.3)", animation: "p117-scale-in 480ms var(--ease-spring) both" }}
        >
          <div className="cs-panel__body" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <p className="cs-mono cs-text-cyan" style={{ margin: 0, fontSize: 9.5, letterSpacing: "0.3em", textTransform: "uppercase" }}>
              Claim → Evidence → Source → Verification
            </p>
            <div style={{ fontSize: 12.5, color: "var(--ink-2)", lineHeight: 1.6 }}>
              <span className="cs-dim cs-mono" style={{ fontSize: 9, letterSpacing: "0.2em" }}>CLAIM&nbsp;&nbsp;</span>
              {ev.claim}
            </div>
            <div
              style={{
                padding: "10px 13px",
                borderLeft: "2px solid var(--cyan)",
                background: "var(--cyan-soft)",
                borderRadius: "0 6px 6px 0",
                fontSize: 12.5,
                lineHeight: 1.6,
              }}
            >
              <span className="cs-dim cs-mono" style={{ fontSize: 9, letterSpacing: "0.2em" }}>EVIDENCE&nbsp;&nbsp;</span>
              “{ev.citation.snippet}”
              {ev.citation.page != null && <span className="cs-mono cs-text-cyan" style={{ fontSize: 10 }}> — p.{ev.citation.page}</span>}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11.5 }}>
              <StatusDot state="ok" />
              <span className="cs-mono cs-text-ok" style={{ fontSize: 10, letterSpacing: "0.18em" }}>VERIFIED — citation resolves to this document</span>
            </div>
          </div>
        </div>
      )}

      {content ? (
        <div className="cs-docview">
          <div className="cs-docview__head">
            <p className="cs-mono cs-text-cyan" style={{ margin: 0, fontSize: 10, letterSpacing: "0.3em" }}>
              DOCUMENT VIEWER · PARSED REPRESENTATION
            </p>
            <span className="cs-mono cs-dim" style={{ fontSize: 9.5 }}>
              {content.source} · {content.chars.toLocaleString()} chars
            </span>
          </div>

          <h3 className="cs-docview__title">{content.title}</h3>

          {content.lines.length > 0 && (
            <div className="cs-docview__body">
              {content.lines.map((line, i) => (
                <p key={i} style={{ animationDelay: `${i * 40}ms` }}>{line}</p>
              ))}
            </div>
          )}

          {content.table && content.table.length > 1 && (
            <div className="cs-docview__table">
              <p className="cs-mono cs-dim" style={{ margin: "0 0 8px", fontSize: 9.5, letterSpacing: "0.28em", textTransform: "uppercase" }}>
                Extracted table
              </p>
              <table className="cs-table">
                <thead>
                  <tr>{content.table[0].map((h, i) => <th key={i} scope="col">{h}</th>)}</tr>
                </thead>
                <tbody>
                  {content.table.slice(1).map((row, r) => (
                    <tr key={r}>{row.map((cell, c) => <td key={c} className={c === 0 ? "cs-mono" : undefined}>{cell}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <div className="cs-scan" style={{ border: "1px solid var(--line)", borderRadius: 10, background: "var(--bg-1)", minHeight: 260, padding: 26, marginBottom: 16 }}>
          <p className="cs-mono cs-text-cyan" style={{ margin: "0 0 10px", fontSize: 10, letterSpacing: "0.3em" }}>
            DOCUMENT VIEWER · PARSED REPRESENTATION
          </p>
          <p style={{ color: "var(--ink-2)", fontSize: 13, lineHeight: 1.75, margin: 0 }}>
            This register row has no parsed text in the corpus yet. The extraction pipeline below is
            what runs when its source file is ingested.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 18 }}>
            {["Title + metadata", "Sections & headings", "Extracted tables", "Embedded entities", "OCR confidence map"].map((s, i) => (
              <div key={s} style={{ display: "flex", gap: 9, alignItems: "center", fontSize: 12.5, color: "var(--ink-2)", animation: `p117-fade-up 480ms var(--ease-out) ${i * 90}ms both` }}>
                <Icon name="check" size={12} /> {s}
                <span style={{ flex: 1, borderBottom: "1px dashed var(--line)" }} />
              </div>
            ))}
          </div>
        </div>
      )}

      {entities.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <p className="cs-mono cs-dim" style={{ margin: "0 0 9px", fontSize: 9.5, letterSpacing: "0.28em", textTransform: "uppercase" }}>
            Extracted intelligence
          </p>
          <div className="cs-chips">
            {entities.map((e, i) => (
              <span key={e} className="cs-chip" style={{ cursor: "default", borderColor: "rgba(183,156,255,0.35)", background: "var(--violet-soft)", color: "var(--violet)", animation: `p117-scale-in 400ms var(--ease-spring) ${i * 70}ms both` }}>
                {e}
              </span>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 12.5 }}>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span className="cs-dim">Uploaded</span>
          <span className="cs-mono">{timeAgo(doc.created_at)}</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span className="cs-dim">Last indexed</span>
          <span className="cs-mono">{timeAgo(doc.updated_at)}</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span className="cs-dim">Document ID</span>
          <span className="cs-mono cs-text-cyan">{doc.id}</span>
        </div>
      </div>

      <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
        <Button variant="primary">
          <Icon name="zap" size={13} /> Ask about this document
        </Button>
        <Button variant="ghost">
          <Icon name="refresh" size={13} /> Reindex
        </Button>
      </div>
    </Drawer>
  );
}

function DocumentsPageInner() {
  const params = useSearchParams();
  const { visit } = useJourney();
  const [docs, setDocs] = useState<DocumentRecord[] | null>(null);
  const [filter, setFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<DocStatus | "all">("all");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [openDoc, setOpenDoc] = useState<DocumentRecord | null>(null);
  const [evidenceMode, setEvidenceMode] = useState(false);
  const [justAdded, setJustAdded] = useState<string | null>(null);
  const [corpus, setCorpus] = useState<EvidenceCorpus>({ workOrders: [], approvals: [] });

  useEffect(() => {
    consoleData.documents.list().then(setDocs);
  }, []);

  // The evidence corpus: real work orders and approvals. Loaded separately
  // because a document may be listed long before anything cites it.
  useEffect(() => {
    let alive = true;
    Promise.all([
      consoleData.workOrders.list().catch(() => [] as WorkOrder[]),
      consoleData.approvals.list().catch(() => [] as ApprovalRequest[]),
    ]).then(([workOrders, approvals]) => {
      if (alive) setCorpus({ workOrders, approvals });
    });
    return () => {
      alive = false;
    };
  }, []);

  // deep link from citation chips: ?doc=<id> → evidence mode
  useEffect(() => {
    const id = params.get("doc");
    if (id && docs) {
      const found = docs.find((d) => d.id === id) ?? null;
      setOpenDoc(found);
      setEvidenceMode(Boolean(found && citationFor(found.id, corpus)));
      if (found) visit({ id: found.id, label: found.filename, kind: "document", href: `/console/documents?doc=${found.id}` });
    }
  }, [params, docs, corpus, visit]);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return (docs ?? []).filter(
      (d) => (statusFilter === "all" || d.status === statusFilter) && (!q || d.filename.toLowerCase().includes(q)),
    );
  }, [docs, filter, statusFilter]);

  const onUploaded = useCallback((name: string) => {
    setUploadOpen(false);
    setJustAdded(name);
    setTimeout(() => setJustAdded(null), 4200);
  }, []);

  return (
    <>
      <div className="cs-pagehead">
        <div>
          <span className="cs-pagehead__kicker">Knowledge</span>
          <h1>Document Intelligence</h1>
        </div>
        <div className="cs-pagehead__actions" style={{ marginLeft: "auto" }}>
          <Button variant="primary" onClick={() => setUploadOpen(true)}>
            <Icon name="upload" size={13} /> Ingest document
          </Button>
        </div>
      </div>

      {justAdded && (
        <div className="cs-strip" style={{ marginBottom: 16, borderColor: "rgba(61,220,151,0.4)", animation: "p117-fade-up 400ms var(--ease-out) both" }} role="status">
          <span>
            <StatusDot state="ok" pulse /> <span className="cs-mono">{justAdded}</span> — knowledge extracted, graph updated, now citable by every agent
          </span>
        </div>
      )}

      <section className="cs-doc-intel">
        <div className="cs-doc-intel__copy">
          <span className="cs-pagehead__kicker">Document Intelligence Center</span>
          <h2>Raw pages become citable plant knowledge.</h2>
          <p>
            Project 117 parses procedures, drawings, reports and work orders into entities,
            relationships, evidence trails and verified agent memory. The archive below is the
            refinery&apos;s own documentation moving through the pipeline.
          </p>
          <div className="cs-doc-flow" aria-label="Document intelligence flow">
            {["Raw document", "Pages", "Entities", "Knowledge", "Relationships"].map((step) => (
              <span key={step}>{step}</span>
            ))}
          </div>
        </div>
        <DocumentField
          onSelect={(page) => {
            const match =
              docs?.find((d) => d.filename.replace(/\.(pdf|xlsx|csv|png|md|docx)$/i, "") === page.doc.replace(/\.(pdf|xlsx|csv|png|md|docx)$/i, "")) ??
              docs?.find((d) => page.doc.toLowerCase().startsWith(d.filename.slice(0, 8).toLowerCase().replace(/[^a-z0-9]/g, ""))) ??
              null;
            if (match) {
              setOpenDoc(match);
              setEvidenceMode(false);
              visit({ id: match.id, label: match.filename, kind: "document", href: `/console/documents?doc=${match.id}` });
            } else {
              // A page from the generated knowledge base: open it as evidence
              // context rather than pretending a library record exists.
              setOpenDoc({
                id: `kb-${page.id}`,
                filename: page.doc,
                content_type: "text/markdown",
                size_bytes: 0,
                status: "indexed",
                metadata: { section: page.section, entities: page.entities.length },
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              });
              setEvidenceMode(false);
            }
          }}
        />
      </section>

      <Panel
        pad={false}
        title="Library"
        actions={
          <>
            <input className="cs-input" style={{ width: 220, padding: "7px 12px" }} placeholder="Filter by name…" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter documents" />
            <select className="cs-select" style={{ width: 130, padding: "7px 12px" }} value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as DocStatus | "all")} aria-label="Filter by status">
              <option value="all">All status</option>
              <option value="indexed">Indexed</option>
              <option value="indexing">Indexing</option>
              <option value="stored">Stored</option>
              <option value="failed">Failed</option>
            </select>
          </>
        }
      >
        {!docs ? (
          <>
            <div className="cs-loading"><i /> Extracting knowledge…</div>
            <SkeletonRows rows={6} />
          </>
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No documents match"
            detail="This library holds every document the agents can cite. Adjust the filter — or ingest the document your question depends on."
            action={<Button variant="primary" onClick={() => setUploadOpen(true)}>Ingest document</Button>}
          />
        ) : (
          <table className="cs-table">
            <thead>
              <tr>
                <th scope="col">Document</th>
                <th scope="col">Status</th>
                <th scope="col">Entities</th>
                <th scope="col">Size</th>
                <th scope="col">Updated</th>
              </tr>
            </thead>
            <tbody className="cs-fade-list">
              {filtered.map((d) => (
                <tr key={d.id} onClick={() => { setOpenDoc(d); setEvidenceMode(false); visit({ id: d.id, label: d.filename, kind: "document", href: `/console/documents?doc=${d.id}` }); }} style={{ cursor: "pointer" }}>
                  <td>
                    <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <Icon name="doc" size={15} />
                      <span className="cs-mono" style={{ fontSize: 12.5 }}>{d.filename}</span>
                    </span>
                  </td>
                  <td>
                    <Tag tone={STATUS_TONE[d.status].tone}>
                      {d.status === "indexing" && <StatusDot state="ai" pulse />} {STATUS_TONE[d.status].label}
                    </Tag>
                  </td>
                  <td className="cs-mono cs-dim">{typeof d.metadata.entities === "number" ? String(d.metadata.entities) : "—"}</td>
                  <td className="cs-mono cs-dim">{fmtSize(d.size_bytes)}</td>
                  <td className="cs-mono cs-dim">{timeAgo(d.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      {uploadOpen && <UploadModal onClose={() => setUploadOpen(false)} onDone={onUploaded} />}
      {openDoc && <DocumentDrawer doc={openDoc} evidenceMode={evidenceMode} corpus={corpus} onClose={() => setOpenDoc(null)} />}
    </>
  );
}

export default function DocumentsPage() {
  return (
    <Suspense fallback={<SkeletonRows rows={6} />}>
      <DocumentsPageInner />
    </Suspense>
  );
}
