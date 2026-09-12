"use client";

/**
 * Command palette — ⌘K. A command system, not a search box.
 * Grouped results with TYPE / STATUS / CONTEXT, full keyboard navigation,
 * agents, workflows, and recent investigations alongside navigation.
 *
 * Everything after the fixed navigation commands is loaded from the real
 * console data adapter — the plant's own equipment, documents, work orders,
 * agents and workflows. The palette previously indexed mock constants, so it
 * would happily navigate to an equipment tag that does not exist.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon, type IconName } from "@/components/ui/Icon";
import { consoleData } from "@/lib/data/console";
import type { AgentDescriptor, DocumentRecord, Equipment, WorkOrder, WorkflowDefinition } from "@/types";
import type { WorkspaceSession } from "@/types/console";

interface Command {
  id: string;
  label: string;
  type: string;
  status?: string;
  context?: string;
  icon: IconName;
  run: () => void;
}

interface Index {
  equipment: Equipment[];
  documents: DocumentRecord[];
  workOrders: WorkOrder[];
  agents: AgentDescriptor[];
  workflows: WorkflowDefinition[];
  sessions: WorkspaceSession[];
}

const EMPTY: Index = {
  equipment: [],
  documents: [],
  workOrders: [],
  agents: [],
  workflows: [],
  sessions: [],
};

export function CommandPalette({
  open,
  onClose,
  onOpenRoster,
}: {
  open: boolean;
  onClose: () => void;
  onOpenRoster?: () => void;
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const [data, setData] = useState<Index>(EMPTY);
  const inputRef = useRef<HTMLInputElement>(null);

  // Load once per open. A source that fails contributes nothing rather than
  // falling back to fixture rows; the palette then simply cannot offer what
  // it could not read.
  useEffect(() => {
    if (!open) return;
    let alive = true;
    const settle = <K extends keyof Index>(key: K) => (v: Index[K]) => {
      if (alive) setData((prev) => ({ ...prev, [key]: v }));
    };
    const ignore = () => {};
    consoleData.equipment.list().then(settle("equipment")).catch(ignore);
    consoleData.documents.list().then(settle("documents")).catch(ignore);
    consoleData.workOrders.list().then(settle("workOrders")).catch(ignore);
    consoleData.agents.list().then(settle("agents")).catch(ignore);
    consoleData.workflows.list().then(settle("workflows")).catch(ignore);
    consoleData.workspace.sessions().then(settle("sessions")).catch(ignore);
    return () => { alive = false; };
  }, [open]);

  const close = useCallback(() => onClose(), [onClose]);

  const commands = useMemo<Command[]>(() => {
    const go = (href: string) => () => {
      router.push(href);
      close();
    };
    return [
      { id: "ask", label: "Ask AI — new investigation", type: "ACTION", status: "ready", context: "AI Workspace", icon: "zap", run: go("/console/workspace") },
      { id: "home", label: "Command Center", type: "PAGE", status: "live", icon: "home", run: go("/console/home") },
      { id: "wo-new", label: "Create work order", type: "ACTION", context: "requires approval if AI-drafted", icon: "plus", run: go("/console/work-orders?new=1") },
      { id: "appr", label: "Approvals", type: "PAGE", icon: "check", run: go("/console/approvals") },
      { id: "insights", label: "Insights", type: "PAGE", icon: "insights", run: go("/console/insights") },
      { id: "admin", label: "Sovereignty control", type: "PAGE", context: "models · audit · perimeter", icon: "admin", run: go("/console/admin") },
      ...data.sessions.map((s) => ({
        id: `session-${s.id}`,
        label: s.title,
        type: "INVESTIGATION",
        status: `${s.task_count} task${s.task_count === 1 ? "" : "s"}`,
        icon: "history" as const,
        run: go("/console/workspace"),
      })),
      ...data.equipment.map((e) => ({
        id: `eq-${e.id}`,
        label: `${e.id} — ${e.name}`,
        type: "EQUIPMENT",
        status: e.status,
        context: e.zone,
        icon: "equipment" as const,
        run: go(`/console/equipment/${e.id}`),
      })),
      ...data.documents.map((d) => ({
        id: `doc-${d.id}`,
        label: d.filename,
        type: "DOCUMENT",
        status: d.status,
        icon: "file" as const,
        run: go(`/console/documents?doc=${d.id}`),
      })),
      ...data.workOrders.map((w) => ({
        id: `wo-${w.id}`,
        label: `${w.id} — ${w.title}`,
        type: "WORK ORDER",
        status: w.status.replace(/_/g, " "),
        context: w.equipment_id,
        icon: "workorder" as const,
        run: go(`/console/work-orders/${w.id}`),
      })),
      ...data.agents.map((a) => ({
        id: `agent-${a.kind}`,
        label: a.name,
        type: "AGENT",
        status: a.status,
        context: `${a.tools.length} tools`,
        icon: "cpu" as const,
        run: () => {
          onOpenRoster?.();
          close();
        },
      })),
      ...data.workflows.map((w) => ({
        id: `wf-${w.name}`,
        label: w.name.replace(/-/g, " "),
        type: "WORKFLOW",
        status: `${w.steps.length} step${w.steps.length === 1 ? "" : "s"}`,
        icon: "workflow" as const,
        run: go("/console/workspace"),
      })),
    ];
  }, [router, close, onOpenRoster, data]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands.slice(0, 10);
    return commands
      .filter((c) => `${c.label} ${c.type} ${c.status ?? ""} ${c.context ?? ""}`.toLowerCase().includes(q))
      .slice(0, 10);
  }, [commands, query]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setIndex(0);
      setTimeout(() => inputRef.current?.focus(), 30);
    }
  }, [open]);

  useEffect(() => setIndex(0), [query]);

  if (!open) return null;

  const statusTone = (s?: string) =>
    s === "critical" || s === "failed" ? "var(--crit)" : s === "warning" || s === "pending" || s === "2 pending" ? "var(--warn)" : s ? "var(--ok)" : "var(--ink-3)";

  return (
    <div className="cs-palette" onClick={onClose}>
      <div className="cs-palette__box" role="dialog" aria-label="Command palette" onClick={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          className="cs-palette__input"
          placeholder="Ask AI, find equipment, documents, work orders, agents, workflows…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setIndex((i) => Math.min(i + 1, filtered.length - 1));
            }
            if (e.key === "ArrowUp") {
              e.preventDefault();
              setIndex((i) => Math.max(i - 1, 0));
            }
            if (e.key === "Enter" && filtered[index]) filtered[index].run();
            if (e.key === "Escape") onClose();
          }}
          aria-label="Command input"
        />
        <div className="cs-palette__list" role="listbox">
          {filtered.map((cmd, i) => (
            <button
              key={cmd.id}
              className={`cs-palette__item${i === index ? " is-active" : ""}`}
              role="option"
              aria-selected={i === index}
              onMouseEnter={() => setIndex(i)}
              onClick={cmd.run}
            >
              <Icon name={cmd.icon} size={14} />
              <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{cmd.label}</span>
              <span className="cs-mono" style={{ marginLeft: "auto", fontSize: 8.5, letterSpacing: "0.18em", color: "var(--ink-3)", flex: "0 0 auto" }}>
                {cmd.type}
              </span>
              {cmd.status && (
                <span className="cs-mono" style={{ fontSize: 9, color: statusTone(cmd.status), flex: "0 0 auto", minWidth: 56, textAlign: "right" }}>
                  {cmd.status}
                </span>
              )}
            </button>
          ))}
          {filtered.length === 0 && (
            <div className="cs-empty" style={{ padding: 20 }}>
              Nothing in the plant matches “{query}”.
            </div>
          )}
        </div>
        <div className="cs-palette__hint">
          <span>↑↓ navigate</span>
          <span>↵ open</span>
          <span>esc close</span>
          <span style={{ marginLeft: "auto" }}>PROJECT 117 · COMMAND</span>
        </div>
      </div>
    </div>
  );
}
