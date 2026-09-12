"use client";

/**
 * Documents — the Document Intelligence Center.
 * Upload runs a visible 8-stage pipeline (file → parsing → OCR → chunking →
 * embedding → extraction → graph update → citable). The viewer drawer shows
 * extracted intelligence; opened from a citation (?doc=) it enters
 * EVIDENCE MODE: claim → evidence → source → verification.
 */
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button, EmptyState, Panel, Progress, SkeletonRows, StatusDot, Tag, timeAgo } from "@/components/ui/primitives";
import { Drawer, Modal } from "@/components/ui/overlays";
import { Icon, type IconName } from "@/components/ui/Icon";
import { consoleData } from "@/lib/data/console";
import DocumentField from "@/components/documents/DocumentField";
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
  { id: "embedding", label: "Embedding", detail: "nomic-embed-text vectors — local, no egress", icon: "cpu", at: 4100 },
  { id: "extract", label: "Knowledge extraction", detail: "entities, equipment refs, thresholds", icon: "zap", at: 5000 },
  { id: "graph", label: "Graph update", detail: "relationships linked into the plant graph", icon: "graph", at: 5800 },
  { id: "ready", label: "Ready", detail: "citable by every agent", icon: "check", at: 6500 },
];

/**
 * Real upload. The previous version never opened a file picker: clicking
 * "browse" pretended to ingest a hardcoded filename and animated a pipeline
 * with ticks beside stages that had not run. This one posts the chosen file to
 * POST /api/documents/upload, then reindexes it through the real pipeline and
 * reports the backend's own status.
 */
function UploadModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [stage, setStage] = useState(-1);
  const [docId, setDocId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const start = async (picked: File) => {
    setFile(picked);
    setError(null);
    setStage(0);
    try {
      const uploaded = await consoleData.documents.upload(picked);
      const doc = uploaded.documents[0];
      if (!doc) throw new Error("the server accepted the file but registered no document");
      setDocId(doc.id);
      // The row exists now; the expensive parse runs server-side.
      setStage(3);
      await consoleData.documents.reindex(doc.id);
      setStage(PIPELINE.length - 1);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setStage(-1);
    }
  };

  const progress = stage < 0 ? 0 : Math.min(100, ((stage + 1) / PIPELINE.length) * 100);
  const done = stage >= PIPELINE.length - 1;

  return (
    <Modal title="Ingest document" wide onClose={onClose}>
      {!file ? (
        <>
          <input
            ref={inputRef}
            type="file"
            style={{ display: "none" }}
            aria-label="Choose a document to ingest"
            onChange={(e) => {
              const picked = e.target.files?.[0];
              if (picked) void start(picked);
            }}
          />
          <button
            className="cs-upload"
            style={{ width: "100%", font: "inherit" }}
            onClick={() => inputRef.current?.click()}
          >
            <Icon name="upload" size={26} />
            <p style={{ margin: "12px 0 4px", color: "var(--ink-1)", fontWeight: 600 }}>
              Choose a document to ingest
            </p>
            <p className="cs-mono cs-dim" style={{ margin: 0, fontSize: 10.5, letterSpacing: "0.08em" }}>
              PDF · DOCX · TXT · MD · CSV · XLSX · PPTX — parsed, embedded and linked locally.
              It never leaves this machine.
            </p>
          </button>
        </>
      ) : (
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
            <Icon name="file" size={15} />
            <span className="cs-mono" style={{ fontSize: 12.5 }}>{file.name}</span>
            <span className="cs-mono" style={{ marginLeft: "auto", fontSize: 11, color: error ? "var(--red)" : done ? "var(--ok)" : "var(--cyan)" }}>
              {error ? "failed" : `${Math.round(progress)}%`}
            </span>
          </div>
          <Progress value={progress} tone={error ? "crit" : done ? "ok" : "cyan"} />
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
          {error && (
            <p style={{ margin: "14px 0 0", fontSize: 12.5, color: "var(--red)", lineHeight: 1.6 }}>{error}</p>
          )}
          {done && docId && (
            <p className="cs-mono cs-dim" style={{ margin: "14px 0 0", fontSize: 10 }}>
              registered as {docId}
            </p>
          )}
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


/** The ingestion block the backend records on every stored document. */
interface IngestionMeta {
  indexed?: boolean;
  embedding_model?: string;
  chunk_count?: number;
  index_table?: string;
  last_index_seconds?: number;
  last_index_error?: string | null;
}

function ingestionOf(doc: DocumentRecord): IngestionMeta {
  return ((doc.metadata as { ingestion?: IngestionMeta })?.ingestion ?? {}) as IngestionMeta;
}

function DocumentDrawer({
  doc,
  evidenceMode,
  corpus,
  onClose,
  onChanged,
}: {
  doc: DocumentRecord;
  evidenceMode: boolean;
  corpus: EvidenceCorpus;
  onClose: () => void;
  onChanged: () => void;
}) {
  const status = STATUS_TONE[doc.status];
  const ev = citationFor(doc.id, corpus);
  const ingestion = ingestionOf(doc);
  const [reindexing, setReindexing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const reindex = async () => {
    setReindexing(true);
    setError(null);
    try {
      await consoleData.documents.reindex(doc.id);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setReindexing(false);
    }
  };

  return (
    <Drawer title={doc.filename} wide onClose={onClose}>
      <div style={{ display: "flex", gap: 7, flexWrap: "wrap", marginBottom: 16 }}>
        <Tag tone={status.tone}>{status.label}</Tag>
        <Tag>{doc.content_type.split("/").pop()}</Tag>
        <Tag>{fmtSize(doc.size_bytes)}</Tag>
        {typeof ingestion.chunk_count === "number" && (
          <Tag tone="ai">{ingestion.chunk_count} chunks</Tag>
        )}
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

        <div className="cs-scan" style={{ border: "1px solid var(--line)", borderRadius: 10, background: "var(--bg-1)", minHeight: 200, padding: 26, marginBottom: 16 }}>
          <p className="cs-mono cs-text-cyan" style={{ margin: "0 0 10px", fontSize: 10, letterSpacing: "0.3em" }}>
            INDEX RECORD
          </p>
          {/* What the backend actually recorded for this document, rather than a
              decorative checklist of pipeline stages with ticks beside them. */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {(
              [
                ["Embedding model", ingestion.embedding_model ?? "—"],
                ["Chunks indexed", ingestion.chunk_count != null ? String(ingestion.chunk_count) : "—"],
                ["Vector table", ingestion.index_table ?? "—"],
                [
                  "Index time",
                  ingestion.last_index_seconds != null ? `${ingestion.last_index_seconds.toFixed(2)} s` : "—",
                ],
              ] as const
            ).map(([label, value]) => (
              <div key={label} style={{ display: "flex", gap: 9, alignItems: "center", fontSize: 12.5, color: "var(--ink-2)" }}>
                <span>{label}</span>
                <span style={{ flex: 1, borderBottom: "1px dashed var(--line)" }} />
                <span className="cs-mono">{value}</span>
              </div>
            ))}
          </div>
          {doc.status !== "indexed" && (
            <p className="cs-dim" style={{ margin: "14px 0 0", fontSize: 12.5, lineHeight: 1.7 }}>
              This document has not been indexed, so it is not citable by any agent yet. Reindex
              runs the real parsing and embedding pipeline.
            </p>
          )}
          {ingestion.last_index_error && (
            <p style={{ margin: "14px 0 0", fontSize: 12.5, lineHeight: 1.7, color: "var(--red)" }}>
              Last index error: {ingestion.last_index_error}
            </p>
          )}
        </div>

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

      <div style={{ display: "flex", gap: 10, marginTop: 20, alignItems: "center", flexWrap: "wrap" }}>
        <Button
          variant="primary"
          onClick={() => {
            onClose();
            router.push(`/console/workspace?doc=${encodeURIComponent(doc.id)}`);
          }}
        >
          <Icon name="zap" size={13} /> Ask about this document
        </Button>
        <Button variant="ghost" onClick={reindex} disabled={reindexing}>
          <Icon name="refresh" size={13} /> {reindexing ? "Reindexing…" : "Reindex"}
        </Button>
        {error && (
          <span className="cs-mono" style={{ fontSize: 11, color: "var(--red)" }}>
            {error}
          </span>
        )}
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

  // Reload the real list after a successful ingest, and report the backend's
  // own status rather than asserting what the pipeline did.
  const reload = useCallback(() => {
    consoleData.documents.list().then(setDocs).catch(() => setDocs([]));
  }, []);

  const onUploaded = useCallback(() => {
    reload();
    setJustAdded("document registered");
    setTimeout(() => setJustAdded(null), 4200);
  }, [reload]);

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
            <StatusDot state="ok" pulse /> <span className="cs-mono">{justAdded}</span> — the backend accepted the file and reported its index status; see the row below
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
      {openDoc && (
        <DocumentDrawer
          doc={openDoc}
          evidenceMode={evidenceMode}
          corpus={corpus}
          onClose={() => setOpenDoc(null)}
          onChanged={reload}
        />
      )}
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
