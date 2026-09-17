"use client";

/**
 * RelationshipTree — the selected node's neighbours, grouped by the real edge
 * relation and drawn as an indented tree with connector lines.
 *
 * The grouping key is `edge.relation` straight from the graph (`HAS_SENSOR`,
 * `CONTAINS`, `FLOWS_TO`, …). Nothing is summarised into "related" and no node
 * is invented: every row is one edge that exists in the current view. Groups
 * are ordered by size, then name, so a hub reads top-down.
 *
 * Rows are budgeted (a plant hub can have thousands of edges); the group header
 * always reports the true total, and a truncated group says how many rows were
 * not rendered rather than pretending the list is complete.
 */
import { useMemo } from "react";
import { Lucide } from "@/components/ui/LucideIcon";
import { PROVENANCE_TONE, type KEdge, type KNode } from "@/lib/knowledge/types";

export interface Rel {
  edge: KEdge;
  out: boolean;
  other: KNode;
}

/** Upper bound on rendered rows — keeps a 10k-edge hub from stalling the drawer. */
const ROW_BUDGET = 120;

interface Props {
  rels: Rel[];
  selectedEdge: KEdge | null;
  onEdge: (e: KEdge | null) => void;
  /** Open a neighbour: its own deep link when it has one, else select in-graph. */
  onOpen: (node: KNode) => void;
}

export default function RelationshipTree({ rels, selectedEdge, onEdge, onOpen }: Props) {
  const tree = useMemo(() => {
    const byRelation = new Map<string, Rel[]>();
    for (const r of rels) {
      const key = r.edge.relation || "related";
      if (!byRelation.has(key)) byRelation.set(key, []);
      byRelation.get(key)!.push(r);
    }
    const groups = [...byRelation.entries()].sort(
      (a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]),
    );
    let budget = ROW_BUDGET;
    const rendered = groups.map(([relation, list]) => {
      const take = Math.max(0, Math.min(list.length, budget));
      budget -= take;
      return { relation, rows: list.slice(0, take), total: list.length };
    });
    return rendered;
  }, [rels]);

  return (
    <section className="ku-sec">
      <h3>Relationship tree · {rels.length}</h3>
      {rels.length === 0 ? (
        <p className="ku-prov__hint">No relationships in this view.</p>
      ) : (
        <div className="ku-tree">
          {tree.map((g) => (
            <div key={g.relation} className="ku-tree__group">
              <div className="ku-tree__relation">
                <span className="ku-tree__bullet" aria-hidden="true" />
                <span className="ku-tree__relname">{g.relation.replace(/_/g, " ")}</span>
                <b>{g.total}</b>
              </div>
              {g.rows.length > 0 && (
                <ul className="ku-tree__children">
                  {g.rows.map((r) => (
                    <li key={r.edge.id}>
                      <button
                        type="button"
                        className={`ku-rel ku-rel--tree${selectedEdge?.id === r.edge.id ? " is-on" : ""}`}
                        onClick={() => onOpen(r.other)}
                        onContextMenu={(e) => {
                          e.preventDefault();
                          onEdge(r.edge);
                        }}
                        title="Click to navigate · right-click for provenance"
                      >
                        <span className="ku-rel__dir" aria-hidden="true">
                          <Lucide name="arrow" size={10} className={r.out ? undefined : "ku-rel__dir--in"} />
                        </span>
                        <span className="ku-rel__name">{r.other.label}</span>
                        <span className="ku-rel__type">{r.other.type.replace(/_/g, " ")}</span>
                        <span
                          className="ku-rel__prov"
                          style={{ color: PROVENANCE_TONE[r.edge.provenance] }}
                        >
                          {r.edge.provenance}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {g.rows.length < g.total && (
                <p className="ku-tree__more">
                  +{g.total - g.rows.length} more not shown
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
