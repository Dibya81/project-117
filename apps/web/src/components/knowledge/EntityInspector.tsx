"use client";

/**
 * EntityInspector — the right-hand entity drawer for a selected graph node.
 *
 * Everything rendered here is read from the real node and its real edges:
 * the type/status header, the fact grid, the relationship tree, the evidence
 * and work-order lists, and the provenance of the inspected edge. When a value
 * is absent the row is simply not drawn (or the empty state is honest), never
 * padded with a placeholder count.
 *
 * Quick actions reuse the deep links the rest of the console already exposes:
 *   Open Digital Twin  → the node's own `href` when it points at
 *                        `/console/equipment/<tag>` (the twin route); disabled,
 *                        with an explanatory tooltip, for every node without one.
 *   Ask AI             → `/console/workspace?entity=<label>`, the exact
 *                        mechanism the workspace page reads for its prompt.
 */
import { useMemo } from "react";
import { motion } from "framer-motion";
import { Lucide } from "@/components/ui/LucideIcon";
import { Tag } from "@/components/ui/primitives";
import { SPRING } from "@/lib/ui/motion";
import { colorOf, PROVENANCE_TONE, type KEdge, type KNode } from "@/lib/knowledge/types";
import RelationshipTree, { type Rel } from "@/components/knowledge/RelationshipTree";

interface Props {
  node: KNode;
  rels: Rel[];
  selectedEdge: KEdge | null;
  onEdge: (e: KEdge | null) => void;
  onSelectNode: (id: string) => void;
  onOpenHref: (href: string) => void;
  onPathFrom: () => void;
  onPathTo: () => void;
  pathFrom: string | null;
  pathTo: string | null;
}

/** Semantic glyph per entity type — presentation only, never data. */
function iconForType(type: string): string {
  const t = type.toLowerCase();
  if (t === "equipment" || t === "plant" || t === "area") return "equipment";
  if (t === "sensor") return "gauge";
  if (t === "document" || t === "file" || t === "doc") return "doc";
  if (t === "work_order") return "workorder";
  if (t === "anomaly" || t === "failure_mode") return "alert";
  if (t === "rule") return "check";
  if (t === "scenario") return "play";
  if (t === "approval") return "shield";
  if (t === "agent" || t === "class") return "cpu";
  if (t === "function") return "workflow";
  if (t === "symbol") return "terminal";
  if (t === "event") return "pulse";
  if (t === "community") return "layers";
  return "graph";
}

/** Colour the real status word by meaning (contract: emerald/amber/red). */
function statusTone(status?: string): string {
  const t = (status ?? "").toLowerCase();
  if (/(crit|alarm|fault|fail|open|danger|trip)/.test(t)) return "#dc2626";
  if (/(warn|degrad|pending|attention|maintenance|overdue)/.test(t)) return "#f59e0b";
  if (/(ok|normal|healthy|verified|active|running|online|closed|resolved|stable)/.test(t)) return "#10b981";
  return "#64748b";
}

function labelForHref(href: string): string {
  if (href.startsWith("/console/equipment/")) return "digital twin";
  if (href.startsWith("/console/work-orders/")) return "work order";
  if (href.startsWith("/console/documents")) return "document";
  if (href.startsWith("/console/history")) return "history";
  if (href.startsWith("/console/approvals")) return "approval";
  if (href.startsWith("/console/workspace")) return "AI workspace";
  return "record";
}

export default function EntityInspector({
  node,
  rels,
  selectedEdge,
  onEdge,
  onSelectNode,
  onOpenHref,
  onPathFrom,
  onPathTo,
  pathFrom,
  pathTo,
}: Props) {
  const byType = useMemo(() => {
    const m = new Map<string, KNode[]>();
    for (const r of rels) {
      if (!m.has(r.other.type)) m.set(r.other.type, []);
      m.get(r.other.type)!.push(r.other);
    }
    return m;
  }, [rels]);

  const evidence = rels.filter((r) => r.other.type === "document");
  const workOrders = rels.filter((r) => r.other.type === "work_order");
  const facts = Object.entries(node.facts ?? {}).filter(([, v]) => v !== undefined && v !== "");

  const tone = colorOf(node.type);
  const sTone = statusTone(node.status);
  /** The equipment twin route this node already carries, if any. */
  const twinHref = node.href?.startsWith("/console/equipment/") ? node.href : null;
  const recordHref = node.href && !twinHref ? node.href : null;

  const open = (n: KNode) => (n.href ? onOpenHref(n.href) : onSelectNode(n.id));
  const askAI = () => onOpenHref(`/console/workspace?entity=${encodeURIComponent(node.label)}`);

  return (
    <div className="ku-entity">
      <header className="ku-entity__head">
        <span
          className="ku-entity__dot ku-entity__tile"
          style={{ background: `${tone}14`, borderColor: `${tone}40`, color: tone }}
          aria-hidden="true"
        >
          <Lucide name={iconForType(node.type)} size={15} />
        </span>
        <div className="ku-entity__ident">
          <div className="ku-entity__eyebrow">
            <Tag>{node.type.replace(/_/g, " ")}</Tag>
            {node.status && (
              <span
                className="ku-status"
                style={{ color: sTone, borderColor: `${sTone}40`, background: `${sTone}12` }}
              >
                {node.status}
              </span>
            )}
          </div>
          <h2>{node.label}</h2>
          <p className="ku-entity__id cs-mono">{node.id}</p>
        </div>
      </header>

      <dl className="ku-facts">
        {node.group && <div><dt>Group</dt><dd>{node.group}</dd></div>}
        {node.source && <div><dt>Source</dt><dd>{node.source}</dd></div>}
        {facts.map(([k, v]) => (
          <div key={k}>
            <dt>{k.replace(/_/g, " ")}</dt>
            <dd>{String(v)}</dd>
          </div>
        ))}
        <div><dt>Relationships</dt><dd>{rels.length}</dd></div>
      </dl>

      <div className="ku-actions">
        <div className="ku-actions__quick">
          {twinHref ? (
            <motion.button
              type="button"
              whileHover={{ y: -1 }}
              whileTap={{ scale: 0.98 }}
              transition={SPRING.micro}
              className="ku-btn ku-btn--twin"
              onClick={() => onOpenHref(twinHref)}
              title={`Open the digital twin for ${node.label}`}
            >
              <Lucide name="equipment" size={12} /> Open Digital Twin
            </motion.button>
          ) : (
            // A disabled button swallows the hover event that shows a native
            // tooltip, so the title lives on the wrapper and the button is inert.
            <span
              className="ku-btn-tip"
              title={`No digital twin exists for this ${node.type.replace(/_/g, " ")} entity`}
            >
              <button type="button" className="ku-btn" disabled aria-disabled="true">
                <Lucide name="equipment" size={12} /> Open Digital Twin
              </button>
            </span>
          )}
          <motion.button
            type="button"
            whileHover={{ y: -1 }}
            whileTap={{ scale: 0.98 }}
            transition={SPRING.micro}
            className="ku-btn ku-btn--ai"
            onClick={askAI}
            title={`Ask the AI workspace about ${node.label}`}
          >
            <Lucide name="chat" size={12} /> Ask AI
          </motion.button>
        </div>

        {recordHref && (
          <button type="button" className="ku-btn" onClick={() => onOpenHref(recordHref)}>
            <Lucide name="chevron" size={12} /> Open {labelForHref(recordHref)}
          </button>
        )}
        {node.type === "equipment" && (
          <button
            type="button"
            className="ku-btn"
            onClick={() =>
              onOpenHref(
                `/console/simulation/builder?focus=${encodeURIComponent(node.id.replace(/^equipment:/, ""))}`,
              )
            }
          >
            <Lucide name="gauge" size={12} /> Open in simulation
          </button>
        )}
        <div className="ku-actions__pair">
          <button type="button" className={`ku-btn${pathFrom === node.id ? " is-on" : ""}`} onClick={onPathFrom}>
            Set path start
          </button>
          <button type="button" className={`ku-btn${pathTo === node.id ? " is-on" : ""}`} onClick={onPathTo}>
            Set path end
          </button>
        </div>
      </div>

      {evidence.length > 0 && (
        <section className="ku-sec">
          <h3>Evidence · {evidence.length} document{evidence.length === 1 ? "" : "s"}</h3>
          {evidence.map((r) => (
            <button key={r.other.id} type="button" className="ku-rel" onClick={() => open(r.other)}>
              <span className="ku-rel__rel">{r.edge.relation.replace(/_/g, " ")}</span>
              <span className="ku-rel__name">{r.other.label}</span>
              <span className="ku-rel__prov" style={{ color: PROVENANCE_TONE[r.edge.provenance] }}>
                {r.edge.provenance}
              </span>
            </button>
          ))}
        </section>
      )}

      {workOrders.length > 0 && (
        <section className="ku-sec">
          <h3>Work orders</h3>
          {workOrders.map((r) => (
            <button
              key={r.other.id}
              type="button"
              className="ku-rel"
              onClick={() => r.other.href && onOpenHref(r.other.href)}
            >
              <span className="ku-rel__rel">{r.edge.relation.replace(/_/g, " ")}</span>
              <span className="ku-rel__name">{r.other.label}</span>
              <span className="ku-rel__prov" style={{ color: PROVENANCE_TONE[r.edge.provenance] }}>
                {r.edge.provenance}
              </span>
            </button>
          ))}
        </section>
      )}

      <RelationshipTree rels={rels} selectedEdge={selectedEdge} onEdge={onEdge} onOpen={open} />

      {/* provenance of the last inspected edge */}
      <section className="ku-sec">
        <h3>Relationship provenance</h3>
        {!selectedEdge ? (
          <p className="ku-prov__hint">Right-click any relationship above to inspect where it came from.</p>
        ) : (
          <div className="ku-prov">
            <div className="ku-prov__row">
              <span>{selectedEdge.from.replace(/^[a-z_]+:/, "")}</span>
              <b style={{ color: PROVENANCE_TONE[selectedEdge.provenance] }}>{selectedEdge.relation}</b>
              <span>{selectedEdge.to.replace(/^[a-z_]+:/, "")}</span>
            </div>
            <dl className="ku-facts">
              <div>
                <dt>Classification</dt>
                <dd style={{ color: PROVENANCE_TONE[selectedEdge.provenance] }}>{selectedEdge.provenance}</dd>
              </div>
              {selectedEdge.source && <div><dt>Source</dt><dd>{selectedEdge.source}</dd></div>}
              {selectedEdge.confidence != null && (
                <div><dt>Confidence</dt><dd>{selectedEdge.confidence.toFixed(2)}</dd></div>
              )}
            </dl>
          </div>
        )}
      </section>

      {byType.size > 0 && (
        <section className="ku-sec">
          <h3>Neighbourhood by type</h3>
          <div className="ku-chips">
            {[...byType.entries()]
              .sort((a, b) => b[1].length - a[1].length)
              .map(([t, list]) => (
                <span key={t} className="ku-chip" style={{ borderColor: `${colorOf(t)}66` }}>
                  <i style={{ background: colorOf(t) }} />
                  {t.replace(/_/g, " ")} <b>{list.length}</b>
                </span>
              ))}
          </div>
        </section>
      )}
    </div>
  );
}
