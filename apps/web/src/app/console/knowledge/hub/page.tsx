"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { DocumentRecord, WorkspaceHealthRecord, WorkspaceRecord } from "@/types";
import { Button, EmptyState, Panel, SkeletonRows, StatusDot, Tag, timeAgo } from "@/components/ui/primitives";
import { Icon } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/overlays";

export default function KnowledgeHubPage() {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<WorkspaceRecord[]>([]);
  const [selectedWsId, setSelectedWsId] = useState<string>("");
  const [health, setHealth] = useState<WorkspaceHealthRecord | null>(null);
  const [recentDocs, setRecentDocs] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [rebuildMsg, setRebuildMsg] = useState<string | null>(null);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newWsName, setNewWsName] = useState("");
  const [newWsDesc, setNewWsDesc] = useState("");
  const [creating, setCreating] = useState(false);

  const fetchWorkspaces = useCallback(async () => {
    try {
      const res = await api.workspaces.list();
      setWorkspaces(res.workspaces);
      if (!selectedWsId && res.workspaces.length > 0) {
        // Pick default workspace or first
        const def = res.workspaces.find((w) => w.name === "default") || res.workspaces[0];
        setSelectedWsId(def.id);
      }
    } catch {
      // If none, fallback
    }
  }, [selectedWsId]);

  const loadData = useCallback(async (wsId: string) => {
    if (!wsId) return;
    try {
      const [h, docsRes] = await Promise.all([
        api.workspaces.health(wsId),
        api.documents.list({ workspaceId: wsId, limit: 10 }),
      ]);
      setHealth(h);
      setRecentDocs(docsRes.documents);
    } catch (err) {
      console.error("Failed to load knowledge hub data", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchWorkspaces();
  }, [fetchWorkspaces]);

  useEffect(() => {
    if (selectedWsId) {
      void loadData(selectedWsId);
      const interval = setInterval(() => {
        void loadData(selectedWsId);
      }, 6000);
      return () => clearInterval(interval);
    }
  }, [selectedWsId, loadData]);

  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWsName.trim()) return;
    setCreating(true);
    try {
      const created = await api.workspaces.create({
        name: newWsName.trim(),
        description: newWsDesc.trim() || undefined,
      });
      setCreateModalOpen(false);
      setNewWsName("");
      setNewWsDesc("");
      await fetchWorkspaces();
      setSelectedWsId(created.id);
    } catch (err) {
      console.error("Create workspace failed", err);
    } finally {
      setCreating(false);
    }
  };

  const handleRebuild = async () => {
    if (!selectedWsId) return;
    setRebuilding(true);
    setRebuildMsg(null);
    try {
      const res = await api.knowledgeHub.rebuild(selectedWsId);
      setRebuildMsg(res.message);
      void loadData(selectedWsId);
    } catch (err) {
      setRebuildMsg(err instanceof Error ? err.message : "Rebuild failed");
    } finally {
      setRebuilding(false);
    }
  };

  const statusTone = (status?: string): "ok" | "warn" | "crit" | "ai" => {
    if (status === "READY") return "ok";
    if (status === "UPDATING") return "ai";
    if (status === "DEGRADED") return "warn";
    if (status === "FAILED") return "crit";
    return "warn";
  };

  return (
    <div className="cs-page" style={{ padding: "24px 32px", maxWidth: 1200, margin: "0 auto" }}>
      {/* Header bar */}
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 24,
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
              <Icon name="database" size={18} />
            </span>
            <h1 style={{ margin: 0, fontSize: "1.5rem", fontWeight: 600, color: "var(--text)" }}>
              Company Knowledge Hub
            </h1>
          </div>
          <p style={{ margin: "4px 0 0 42px", color: "var(--text-dim)", fontSize: "0.875rem" }}>
            Local RAG index, structured entities, and plant intelligence.
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {/* Workspace selector */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <label htmlFor="ws-select" style={{ fontSize: "0.8125rem", color: "var(--text-dim)" }}>
              Workspace:
            </label>
            <select
              id="ws-select"
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
          </div>

          <Button variant="ghost" onClick={() => setCreateModalOpen(true)}>
            <Icon name="plus" size={14} style={{ marginRight: 6 }} /> New Workspace
          </Button>

          <Link href="/console/knowledge/documents">
            <Button variant="primary">
              <Icon name="upload" size={14} style={{ marginRight: 6 }} /> Ingest Documents
            </Button>
          </Link>
        </div>
      </header>

      {/* Main Health Card */}
      <Panel pad={false} style={{ marginBottom: 24, overflow: "hidden" }}>
        <div
          style={{
            padding: "20px 24px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            background: "rgba(255, 255, 255, 0.02)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <StatusDot state={health?.status === "READY" ? "ok" : health?.status === "UPDATING" ? "ai" : "warning"} pulse={health?.status === "UPDATING"} />
            <div>
              <div style={{ fontWeight: 600, fontSize: "1rem", color: "var(--text)" }}>
                Knowledge State: <Tag tone={statusTone(health?.status)}>{health?.status || "LOADING"}</Tag>
              </div>
              <div style={{ fontSize: "0.8125rem", color: "var(--text-dim)", marginTop: 2 }}>
                {health?.last_updated ? `Last synchronized ${timeAgo(health.last_updated)}` : "No updates yet"} · Version {health?.knowledge_version || "v0"}
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: 10 }}>
            <Button variant="ghost" onClick={handleRebuild} disabled={rebuilding}>
              <Icon name="refresh" size={14} style={{ marginRight: 6 }} />
              {rebuilding ? "Rebuilding Graph…" : "Rebuild Graph"}
            </Button>
            <Button variant="ghost" onClick={() => router.push("/console/knowledge")}>
              <Icon name="graph" size={14} style={{ marginRight: 6 }} />
              Explore Graph
            </Button>
          </div>
        </div>

        {rebuildMsg && (
          <div style={{ padding: "8px 24px", background: "rgba(124, 58, 237, 0.1)", fontSize: "0.8125rem", color: "#c4b5fd" }}>
            {rebuildMsg}
          </div>
        )}

        {/* Stats Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: 1,
            background: "var(--border)",
          }}
        >
          <div style={{ background: "var(--surface)", padding: "20px 24px" }}>
            <div style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-dim)" }}>
              Documents
            </div>
            <div style={{ fontSize: "1.75rem", fontWeight: 700, color: "var(--text)", marginTop: 6 }}>
              {health?.documents ?? 0}
            </div>
            <div style={{ fontSize: "0.8125rem", color: "var(--text-dim)", marginTop: 4 }}>
              <span style={{ color: "#34d399" }}>{health?.indexed ?? 0} ready</span>
              {health?.processing ? ` · ${health.processing} active` : ""}
              {health?.failed ? ` · ${health.failed} failed` : ""}
            </div>
          </div>

          <div style={{ background: "var(--surface)", padding: "20px 24px" }}>
            <div style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-dim)" }}>
              Vector Chunks
            </div>
            <div style={{ fontSize: "1.75rem", fontWeight: 700, color: "var(--text)", marginTop: 6 }}>
              {health?.chunks?.toLocaleString() ?? 0}
            </div>
            <div style={{ fontSize: "0.8125rem", color: "var(--text-dim)", marginTop: 4 }}>
              LanceDB local vector index
            </div>
          </div>

          <div style={{ background: "var(--surface)", padding: "20px 24px" }}>
            <div style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-dim)" }}>
              Named Entities
            </div>
            <div style={{ fontSize: "1.75rem", fontWeight: 700, color: "var(--text)", marginTop: 6 }}>
              {health?.entities?.toLocaleString() ?? 0}
            </div>
            <div style={{ fontSize: "0.8125rem", color: "var(--text-dim)", marginTop: 4 }}>
              Equipment, SOPs, sensors
            </div>
          </div>

          <div style={{ background: "var(--surface)", padding: "20px 24px" }}>
            <div style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-dim)" }}>
              Relationships
            </div>
            <div style={{ fontSize: "1.75rem", fontWeight: 700, color: "var(--text)", marginTop: 6 }}>
              {health?.relationships?.toLocaleString() ?? 0}
            </div>
            <div style={{ fontSize: "0.8125rem", color: "var(--text-dim)", marginTop: 4 }}>
              Cross-document links
            </div>
          </div>
        </div>
      </Panel>

      {/* Two Column Layout: Recent Documents & Quick Links */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 24 }}>
        {/* Recent Documents Panel */}
        <Panel
          title="Recent Documents"
          actions={
            <Link href="/console/knowledge/documents" style={{ fontSize: "0.8125rem", color: "var(--accent)" }}>
              View all ({health?.documents ?? 0}) →
            </Link>
          }
        >
          {loading ? (
            <SkeletonRows rows={4} />
          ) : recentDocs.length === 0 ? (
            <EmptyState
              title="No documents uploaded"
              detail="Upload company manuals, P&IDs, SOPs, or inspection logs to populate this workspace."
              action={
                <Link href="/console/knowledge/documents">
                  <Button variant="primary">Ingest Documents</Button>
                </Link>
              }
            />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {recentDocs.map((doc) => (
                <div
                  key={doc.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "10px 14px",
                    borderRadius: 8,
                    background: "rgba(255, 255, 255, 0.02)",
                    border: "1px solid var(--border)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                    <Icon name="doc" size={16} style={{ color: "var(--text-dim)", flexShrink: 0 }} />
                    <div style={{ minWidth: 0 }}>
                      <div
                        style={{
                          fontWeight: 500,
                          fontSize: "0.875rem",
                          color: "var(--text)",
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {doc.filename}
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                        {timeAgo(doc.created_at)}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                    <Tag tone={doc.status === "indexed" ? "ok" : doc.status === "indexing" ? "ai" : doc.status === "failed" ? "crit" : "warn"}>
                      {doc.status}
                    </Tag>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>

        {/* Knowledge Pipeline Info */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <Panel title="On-Device Intelligence">
            <p style={{ fontSize: "0.8125rem", color: "var(--text-dim)", lineHeight: 1.6, margin: "0 0 12px 0" }}>
              Documents are processed 100% locally through your local ingestion pipeline (Docling OCR + Ollama embeddings). No egress, fully confidential.
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: "0.8125rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <StatusDot state="ok" />
                <span style={{ color: "var(--text)" }}>Local LanceDB Vector Store</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <StatusDot state="ok" />
                <span style={{ color: "var(--text)" }}>Ollama Triple Extraction</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <StatusDot state="ok" />
                <span style={{ color: "var(--text)" }}>Audited Document Lineage</span>
              </div>
            </div>
          </Panel>

          <Panel title="Quick Actions">
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <Button variant="ghost" onClick={() => router.push("/console/workspace")} style={{ width: "100%", justifyContent: "flex-start" }}>
                <Icon name="chat" size={14} style={{ marginRight: 8 }} /> Query AI Assistant
              </Button>
              <Button variant="ghost" onClick={() => router.push("/console/knowledge")} style={{ width: "100%", justifyContent: "flex-start" }}>
                <Icon name="graph" size={14} style={{ marginRight: 8 }} /> Open Graph Canvas
              </Button>
              <Button variant="ghost" onClick={() => router.push("/console/knowledge/documents")} style={{ width: "100%", justifyContent: "flex-start" }}>
                <Icon name="upload" size={14} style={{ marginRight: 8 }} /> Manage Ingest Queue
              </Button>
            </div>
          </Panel>
        </div>
      </div>

      {/* Create Workspace Modal */}
      {createModalOpen && (
        <Modal title="Create Knowledge Workspace" onClose={() => setCreateModalOpen(false)}>
          <form onSubmit={handleCreateWorkspace} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <label htmlFor="name-input" style={{ display: "block", fontSize: "0.8125rem", color: "var(--text-dim)", marginBottom: 6 }}>
                Workspace Name
              </label>
              <input
                id="name-input"
                type="text"
                value={newWsName}
                onChange={(e) => setNewWsName(e.target.value)}
                placeholder="e.g. facility_unit_4"
                required
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: 6,
                  border: "1px solid var(--border)",
                  background: "rgba(255, 255, 255, 0.05)",
                  color: "var(--text)",
                  fontSize: "0.875rem",
                }}
              />
            </div>
            <div>
              <label htmlFor="desc-input" style={{ display: "block", fontSize: "0.8125rem", color: "var(--text-dim)", marginBottom: 6 }}>
                Description (optional)
              </label>
              <textarea
                id="desc-input"
                value={newWsDesc}
                onChange={(e) => setNewWsDesc(e.target.value)}
                placeholder="Documents for distillation unit 4 and maintenance history"
                rows={3}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: 6,
                  border: "1px solid var(--border)",
                  background: "rgba(255, 255, 255, 0.05)",
                  color: "var(--text)",
                  fontSize: "0.875rem",
                }}
              />
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 8 }}>
              <Button variant="ghost" onClick={() => setCreateModalOpen(false)}>
                Cancel
              </Button>
              <Button variant="primary" type="submit" disabled={creating || !newWsName.trim()}>
                {creating ? "Creating…" : "Create Workspace"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
