"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { DocumentRecord, WorkspaceRecord } from "@/types";
import { Button, EmptyState, Panel, Progress, SkeletonRows, StatusDot, Tag, timeAgo } from "@/components/ui/primitives";
import { Drawer, Modal } from "@/components/ui/overlays";
import { Icon } from "@/components/ui/Icon";

interface FileUploadTask {
  id?: string;
  name: string;
  size: number;
  stage: string;
  pct: number;
  message?: string;
  status: "uploading" | "indexing" | "indexed" | "failed";
  error?: string;
}

function fmtSize(bytes: number) {
  if (bytes > 1_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`;
  if (bytes > 1000) return `${Math.round(bytes / 1000)} KB`;
  return `${bytes} B`;
}

export default function DocumentsAndIngestPage() {
  const [workspaces, setWorkspaces] = useState<WorkspaceRecord[]>([]);
  const [selectedWsId, setSelectedWsId] = useState<string>("");
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDoc, setSelectedDoc] = useState<DocumentRecord | null>(null);
  const [docChunks, setDocChunks] = useState<{ text: string; chunk_index: number }[]>([]);
  const [loadingChunks, setLoadingChunks] = useState(false);
  const [uploadTasks, setUploadTasks] = useState<FileUploadTask[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [reindexingId, setReindexingId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchWorkspaces = useCallback(async () => {
    try {
      const res = await api.workspaces.list();
      setWorkspaces(res.workspaces);
      if (!selectedWsId && res.workspaces.length > 0) {
        const def = res.workspaces.find((w) => w.name === "default") || res.workspaces[0];
        setSelectedWsId(def.id);
      }
    } catch (err) {
      console.error("Failed to list workspaces", err);
    }
  }, [selectedWsId]);

  const loadDocuments = useCallback(async (wsId: string) => {
    if (!wsId) return;
    try {
      const res = await api.documents.list({ workspaceId: wsId, limit: 100 });
      setDocuments(res.documents);
    } catch (err) {
      console.error("Failed to load documents", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchWorkspaces();
  }, [fetchWorkspaces]);

  useEffect(() => {
    if (selectedWsId) {
      void loadDocuments(selectedWsId);
      const interval = setInterval(() => {
        void loadDocuments(selectedWsId);
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [selectedWsId, loadDocuments]);

  // Load chunks when a document is selected
  useEffect(() => {
    if (!selectedDoc) {
      setDocChunks([]);
      return;
    }
    let active = true;
    setLoadingChunks(true);
    api.documents
      .chunks(selectedDoc.id, 20)
      .then((res) => {
        if (active) setDocChunks(res.chunks);
      })
      .catch(() => {
        if (active) setDocChunks([]);
      })
      .finally(() => {
        if (active) setLoadingChunks(false);
      });
    return () => {
      active = false;
    };
  }, [selectedDoc]);

  // Upload handler (supports multiple files + SSE tracking)
  const handleFilesSelected = async (files: FileList | File[]) => {
    const fileArr = Array.from(files);
    if (!fileArr.length || !selectedWsId) return;

    // Create tasks
    const newTasks: FileUploadTask[] = fileArr.map((f) => ({
      name: f.name,
      size: f.size,
      stage: "UPLOADING",
      pct: 10,
      status: "uploading",
    }));

    setUploadTasks((prev) => [...newTasks, ...prev]);

    // Upload files
    for (let i = 0; i < fileArr.length; i++) {
      const f = fileArr[i];
      try {
        const uploadRes = await api.documents.upload(f, selectedWsId);
        const doc = uploadRes.documents[0];
        if (!doc) throw new Error("Document upload returned no record");

        // Update task with doc id
        setUploadTasks((prev) =>
          prev.map((t) => (t.name === f.name ? { ...t, id: doc.id, stage: "QUEUED", pct: 30 } : t)),
        );

        // Start reindex
        void api.documents.reindex(doc.id).catch(() => {});

        // Connect SSE progress stream if supported
        try {
          const sseUrl = api.documents.progressUrl(doc.id);
          const evtSource = new EventSource(sseUrl);

          evtSource.onmessage = (event) => {
            try {
              const data = JSON.parse(event.data);
              setUploadTasks((prev) =>
                prev.map((t) =>
                  t.name === f.name
                    ? {
                        ...t,
                        stage: data.stage || t.stage,
                        pct: data.pct || t.pct,
                        message: data.message,
                        status: data.status === "failed" ? "failed" : data.pct === 100 ? "indexed" : "indexing",
                      }
                    : t,
                ),
              );
              if (data.done || data.pct === 100) {
                evtSource.close();
                void loadDocuments(selectedWsId);
              }
            } catch {
              // Ignore parse error
            }
          };

          evtSource.onerror = () => {
            evtSource.close();
          };
        } catch {
          // SSE fallback
        }
      } catch (err) {
        setUploadTasks((prev) =>
          prev.map((t) =>
            t.name === f.name
              ? {
                  ...t,
                  stage: "FAILED",
                  pct: 0,
                  status: "failed",
                  error: err instanceof Error ? err.message : "Upload failed",
                }
              : t,
          ),
        );
      }
    }

    void loadDocuments(selectedWsId);
  };

  const handleReprocess = async (docId: string) => {
    setReindexingId(docId);
    try {
      await api.documents.reprocess(docId);
      void loadDocuments(selectedWsId);
      if (selectedDoc?.id === docId) {
        const refreshed = await api.documents.get(docId);
        setSelectedDoc(refreshed);
      }
    } catch (err) {
      console.error("Reprocess failed", err);
    } finally {
      setReindexingId(null);
    }
  };

  const handleDelete = async (docId: string) => {
    if (!confirm("Are you sure you want to delete this document? Vectors and extracted knowledge will be purged.")) {
      return;
    }
    try {
      await api.documents.delete(docId);
      setSelectedDoc(null);
      void loadDocuments(selectedWsId);
    } catch (err) {
      console.error("Delete failed", err);
    }
  };

  // Filtered documents
  const filteredDocs = documents.filter((doc) => {
    if (filterStatus !== "all" && doc.status !== filterStatus) return false;
    if (searchQuery.trim() && !doc.filename.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const readyCount = documents.filter((d) => d.status === "indexed").length;
  const processingCount = documents.filter((d) => d.status === "indexing" || d.status === "stored").length;
  const failedCount = documents.filter((d) => d.status === "failed").length;

  return (
    <div className="cs-page" style={{ padding: "24px 32px", maxWidth: 1280, margin: "0 auto" }}>
      {/* Header */}
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 20,
          flexWrap: "wrap",
          gap: 16,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: "rgba(124, 58, 237, 0.15)",
                color: "#a78bfa",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Icon name="upload" size={18} />
            </span>
            <h1 style={{ margin: 0, fontSize: "1.5rem", fontWeight: 600, color: "var(--text)" }}>
              Documents & Ingestion Pipeline
            </h1>
          </div>
          <p style={{ margin: "4px 0 0 42px", color: "var(--text-dim)", fontSize: "0.875rem" }}>
            Multi-file confidential upload with real-time OCR, chunking, and knowledge graph extraction.
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <select
            value={selectedWsId}
            onChange={(e) => setSelectedWsId(e.target.value)}
            className="cs-select"
            style={{
              background: "rgba(255, 255, 255, 0.05)",
              border: "1px solid var(--border)",
              color: "var(--text)",
              padding: "6px 12px",
              borderRadius: 6,
              fontSize: "0.875rem",
            }}
          >
            {workspaces.map((ws) => (
              <option key={ws.id} value={ws.id} style={{ background: "#18181b", color: "#fff" }}>
                {ws.name} ({ws.knowledge_version})
              </option>
            ))}
          </select>

          <Link href="/console/knowledge/hub">
            <Button variant="ghost">
              <Icon name="database" size={14} style={{ marginRight: 6 }} /> Knowledge Hub
            </Button>
          </Link>
        </div>
      </header>

      {/* Drag & Drop Upload Zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          if (e.dataTransfer.files) void handleFilesSelected(e.dataTransfer.files);
        }}
        onClick={() => fileInputRef.current?.click()}
        style={{
          border: `2px dashed ${isDragging ? "var(--accent)" : "var(--border)"}`,
          borderRadius: 12,
          padding: "32px 24px",
          textAlign: "center",
          background: isDragging ? "rgba(124, 58, 237, 0.08)" : "rgba(255, 255, 255, 0.015)",
          cursor: "pointer",
          marginBottom: 24,
          transition: "all 0.2s ease",
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.txt,.md,.docx,.csv,.json"
          style={{ display: "none" }}
          onChange={(e) => {
            if (e.target.files) void handleFilesSelected(e.target.files);
          }}
        />
        <div style={{ display: "inline-flex", padding: 12, borderRadius: "50%", background: "rgba(124, 58, 237, 0.1)", color: "#a78bfa", marginBottom: 12 }}>
          <Icon name="upload" size={24} />
        </div>
        <div style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text)" }}>
          Drop multiple company documents here, or <span style={{ color: "var(--accent)" }}>browse</span>
        </div>
        <div style={{ fontSize: "0.8125rem", color: "var(--text-dim)", marginTop: 6 }}>
          Supports PDF, TXT, DOCX, CSV, MD · Processed 100% locally via Docling OCR & local embeddings
        </div>
      </div>

      {/* In-Flight Upload Tasks Progress */}
      {uploadTasks.length > 0 && (
        <Panel title="Active Ingestion Queue" style={{ marginBottom: 24 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {uploadTasks.map((task, idx) => (
              <div
                key={`${task.name}-${idx}`}
                style={{
                  padding: "12px 16px",
                  borderRadius: 8,
                  background: "rgba(255, 255, 255, 0.02)",
                  border: "1px solid var(--border)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <Icon name="doc" size={16} style={{ color: "var(--text-dim)" }} />
                    <span style={{ fontWeight: 500, fontSize: "0.875rem", color: "var(--text)" }}>{task.name}</span>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>({fmtSize(task.size)})</span>
                  </div>
                  <Tag tone={task.status === "indexed" ? "ok" : task.status === "failed" ? "crit" : "ai"}>
                    {task.stage} {task.pct ? `(${task.pct}%)` : ""}
                  </Tag>
                </div>
                <Progress value={task.pct} />
                {task.message && (
                  <div style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginTop: 4 }}>
                    {task.message}
                  </div>
                )}
                {task.error && (
                  <div style={{ fontSize: "0.75rem", color: "#f87171", marginTop: 4 }}>
                    {task.error}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Panel>
      )}

      {/* Documents List & Filters */}
      <Panel pad={false}>
        {/* Controls header */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontWeight: 600, fontSize: "0.9375rem", color: "var(--text)" }}>
              Workspace Documents ({documents.length})
            </span>
            <div style={{ fontSize: "0.8125rem", color: "var(--text-dim)" }}>
              <span style={{ color: "#34d399" }}>{readyCount} ready</span>
              {processingCount > 0 && <span> · <span style={{ color: "#38bdf8" }}>{processingCount} processing</span></span>}
              {failedCount > 0 && <span> · <span style={{ color: "#f87171" }}>{failedCount} failed</span></span>}
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {/* Search input */}
            <input
              type="text"
              placeholder="Filter by filename…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                background: "rgba(255, 255, 255, 0.05)",
                border: "1px solid var(--border)",
                color: "var(--text)",
                padding: "6px 10px",
                borderRadius: 6,
                fontSize: "0.8125rem",
                width: 180,
              }}
            />

            {/* Status filter */}
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="cs-select"
              style={{
                background: "rgba(255, 255, 255, 0.05)",
                border: "1px solid var(--border)",
                color: "var(--text)",
                padding: "6px 10px",
                borderRadius: 6,
                fontSize: "0.8125rem",
              }}
            >
              <option value="all" style={{ background: "#18181b", color: "#fff" }}>All Statuses</option>
              <option value="indexed" style={{ background: "#18181b", color: "#fff" }}>Ready (Indexed)</option>
              <option value="indexing" style={{ background: "#18181b", color: "#fff" }}>Indexing</option>
              <option value="stored" style={{ background: "#18181b", color: "#fff" }}>Stored</option>
              <option value="failed" style={{ background: "#18181b", color: "#fff" }}>Failed</option>
            </select>
          </div>
        </div>

        {/* Documents Table */}
        {loading ? (
          <div style={{ padding: 20 }}>
            <SkeletonRows rows={5} />
          </div>
        ) : filteredDocs.length === 0 ? (
          <div style={{ padding: 32 }}>
            <EmptyState
              title="No matching documents"
              detail={
                documents.length === 0
                  ? "Upload documents using the drop zone above to start building this workspace."
                  : "No documents match the current filter or search criteria."
              }
            />
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.875rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)", color: "var(--text-dim)", fontSize: "0.75rem", textTransform: "uppercase" }}>
                  <th style={{ padding: "12px 20px" }}>Document</th>
                  <th style={{ padding: "12px 16px" }}>Size</th>
                  <th style={{ padding: "12px 16px" }}>Status</th>
                  <th style={{ padding: "12px 16px" }}>Ingestion Stage</th>
                  <th style={{ padding: "12px 16px" }}>Uploaded</th>
                  <th style={{ padding: "12px 20px", textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredDocs.map((doc) => {
                  const meta = (doc.metadata || {}) as Record<string, unknown>;
                  const ingestionMeta = (meta.ingestion || {}) as Record<string, unknown>;
                  const chunkCount = ingestionMeta.chunk_count as number | undefined;

                  return (
                    <tr
                      key={doc.id}
                      onClick={() => setSelectedDoc(doc)}
                      style={{
                        borderBottom: "1px solid var(--border)",
                        cursor: "pointer",
                        background: selectedDoc?.id === doc.id ? "rgba(124, 58, 237, 0.08)" : "transparent",
                        transition: "background 0.15s ease",
                      }}
                      onMouseEnter={(e) => {
                        if (selectedDoc?.id !== doc.id) e.currentTarget.style.background = "rgba(255, 255, 255, 0.02)";
                      }}
                      onMouseLeave={(e) => {
                        if (selectedDoc?.id !== doc.id) e.currentTarget.style.background = "transparent";
                      }}
                    >
                      <td style={{ padding: "14px 20px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <Icon name="doc" size={16} style={{ color: "var(--text-dim)", flexShrink: 0 }} />
                          <div>
                            <div style={{ fontWeight: 500, color: "var(--text)" }}>{doc.filename}</div>
                            {chunkCount !== undefined && (
                              <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                                {chunkCount} vector chunks
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                      <td style={{ padding: "14px 16px", color: "var(--text-dim)" }}>
                        {fmtSize(doc.size_bytes)}
                      </td>
                      <td style={{ padding: "14px 16px" }}>
                        <Tag tone={doc.status === "indexed" ? "ok" : doc.status === "indexing" ? "ai" : doc.status === "failed" ? "crit" : "warn"}>
                          {doc.status}
                        </Tag>
                      </td>
                      <td style={{ padding: "14px 16px", color: "var(--text-dim)", fontSize: "0.8125rem" }}>
                        {doc.status === "indexed" ? "Ready (Indexed + Graph)" : doc.status === "indexing" ? "OCR & Embedding…" : doc.status}
                      </td>
                      <td style={{ padding: "14px 16px", color: "var(--text-dim)", fontSize: "0.8125rem" }}>
                        {timeAgo(doc.created_at)}
                      </td>
                      <td style={{ padding: "14px 20px", textAlign: "right" }} onClick={(e) => e.stopPropagation()}>
                        <div style={{ display: "inline-flex", gap: 6 }}>
                          <Button
                            variant="ghost"
                            onClick={() => handleReprocess(doc.id)}
                            disabled={reindexingId === doc.id}
                            title="Re-run OCR, chunking, and graph extraction"
                          >
                            <Icon name="refresh" size={14} />
                          </Button>
                          <Button
                            variant="ghost"
                            onClick={() => handleDelete(doc.id)}
                            title="Delete document and purge vectors"
                          >
                            <Icon name="x" size={14} style={{ color: "#f87171" }} />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {/* Document Detail Drawer */}
      {selectedDoc && (
        <Drawer title={selectedDoc.filename} onClose={() => setSelectedDoc(null)}>
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {/* Status & Actions */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: 16, borderBottom: "1px solid var(--border)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <StatusDot state={selectedDoc.status === "indexed" ? "ok" : "warning"} />
                <Tag tone={selectedDoc.status === "indexed" ? "ok" : "warn"}>{selectedDoc.status}</Tag>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <Button variant="ghost" onClick={() => handleReprocess(selectedDoc.id)} disabled={reindexingId === selectedDoc.id}>
                  <Icon name="refresh" size={14} style={{ marginRight: 6 }} /> Reprocess
                </Button>
                <Button variant="reject" onClick={() => handleDelete(selectedDoc.id)}>
                  <Icon name="x" size={14} style={{ marginRight: 6 }} /> Delete
                </Button>
              </div>
            </div>

            {/* Metadata summary */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, fontSize: "0.8125rem" }}>
              <div>
                <span style={{ color: "var(--text-dim)" }}>File Size:</span>
                <div style={{ fontWeight: 500, color: "var(--text)", marginTop: 2 }}>{fmtSize(selectedDoc.size_bytes)}</div>
              </div>
              <div>
                <span style={{ color: "var(--text-dim)" }}>Content Type:</span>
                <div style={{ fontWeight: 500, color: "var(--text)", marginTop: 2 }}>{selectedDoc.content_type || "application/octet-stream"}</div>
              </div>
              <div>
                <span style={{ color: "var(--text-dim)" }}>Ingested At:</span>
                <div style={{ fontWeight: 500, color: "var(--text)", marginTop: 2 }}>{new Date(selectedDoc.created_at).toLocaleString()}</div>
              </div>
              <div>
                <span style={{ color: "var(--text-dim)" }}>SHA-256 Checksum:</span>
                <div style={{ fontFamily: "monospace", fontSize: "0.75rem", color: "var(--text)", marginTop: 2, wordBreak: "break-all" }}>
                  {(selectedDoc.metadata?.checksum as string) || "—"}
                </div>
              </div>
            </div>

            {/* Parsed Chunks Preview */}
            <div>
              <div style={{ fontWeight: 600, fontSize: "0.875rem", color: "var(--text)", marginBottom: 10 }}>
                Parsed Chunks ({docChunks.length})
              </div>
              {loadingChunks ? (
                <SkeletonRows rows={3} />
              ) : docChunks.length === 0 ? (
                <div style={{ fontSize: "0.8125rem", color: "var(--text-dim)" }}>
                  No vector chunks available. Click Reprocess to run the ingestion pipeline.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 380, overflowY: "auto" }}>
                  {docChunks.map((c, i) => (
                    <div
                      key={i}
                      style={{
                        padding: "10px 12px",
                        borderRadius: 6,
                        background: "rgba(255, 255, 255, 0.03)",
                        border: "1px solid var(--border)",
                        fontSize: "0.8125rem",
                        lineHeight: 1.5,
                        color: "var(--text)",
                      }}
                    >
                      <div style={{ fontSize: "0.6875rem", color: "var(--text-dim)", marginBottom: 4 }}>
                        Chunk #{c.chunk_index ?? i + 1}
                      </div>
                      {c.text}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </Drawer>
      )}
    </div>
  );
}
