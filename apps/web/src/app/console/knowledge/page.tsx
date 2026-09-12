"use client";

/**
 * Knowledge Universe — /console/knowledge
 *
 * One interface over two real graphs:
 *
 *   Plant Knowledge   the refinery, assembled from the simulation dataset and
 *                     the console's own records (documents, work orders,
 *                     anomalies, history, learned rules).
 *   System Knowledge  Project 117's source graph, compiled by graphify
 *                     (4,159 nodes / 9,114 edges / 226 communities).
 *
 * Obsidian reads the same concepts through scripts/graphify-obsidian.sh; the
 * ids used here (`equipment:C-3`, `document:d-1`) are the stable join keys.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/ui/Icon";
import { Tag } from "@/components/ui/primitives";
import GraphCanvas, { type GraphHandle } from "@/components/knowledge/GraphCanvas";
import { buildPlantGraph } from "@/lib/knowledge/plant";
import {
  expandCommunity,
  loadSystemFull,
  loadSystemIndex,
  searchSystem,
  systemOverview,
  type SystemFull,
  type SystemIndex,
} from "@/lib/knowledge/system";
import { layoutCommunityMembers, layoutPlant, layoutSystemOverview, type Pt } from "@/lib/knowledge/layout";
import {
  colorOf,
  indexGraph,
  neighborhood,
  PROVENANCE_TONE,
  shortestPath,
  summarize,
  type KEdge,
  type KGraph,
  type KNode,
  type Namespace,
} from "@/lib/knowledge/types";

import "@/styles/knowledge.css";

type Lens =
  | "all" | "investigations" | "equipment" | "document"
  | "anomaly" | "work_order" | "rule" | "sensor";

const LENSES: { id: Lens; label: string; types: string[]; icon: Parameters<typeof Icon>[0]["name"] }[] = [
  { id: "all", label: "All knowledge", types: [], icon: "graph" },
  { id: "investigations", label: "Recent investigations", types: ["anomaly", "event", "rule"], icon: "insights" },
  { id: "equipment", label: "Equipment", types: ["equipment", "plant", "area"], icon: "equipment" },
  { id: "sensor", label: "Sensors", types: ["sensor"], icon: "gauge" },
  { id: "document", label: "Documents", types: ["document"], icon: "doc" },
  { id: "anomaly", label: "Anomalies", types: ["anomaly"], icon: "alert" },
  { id: "work_order", label: "Work orders", types: ["work_order"], icon: "workorder" },
  { id: "rule", label: "Learned rules", types: ["rule"], icon: "check" },
];

/** The asset the golden demo starts from. */
const C3 = "equipment:C-3";

export default function KnowledgeUniverse() {
  const router = useRouter();
  const graphRef = useRef<GraphHandle>(null);

  const [ns, setNs] = useState<Namespace>("plant");
  const [lens, setLens] = useState<Lens>("all");
  const [plant, setPlant] = useState<KGraph | null>(null);
  const [sysIndex, setSysIndex] = useState<SystemIndex | null>(null);
  const [sysFull, setSysFull] = useState<SystemFull | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [selected, setSelected] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<KEdge | null>(null);
  const [pathFrom, setPathFrom] = useState<string | null>(null);
  const [pathTo, setPathTo] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loadingFull, setLoadingFull] = useState(false);

  /* ---------------- load ---------------- */
  useEffect(() => {
    buildPlantGraph()
      .then((g) => {
        setPlant(g);
        // Deep link: ?entity=C-3 (or a full node id) selects that node, so
        // other pages can hand off into the graph.
        const param = new URLSearchParams(window.location.search).get("entity");
        const wanted = param
          ? g.nodes.find((n) => n.id === param)?.id ??
            g.nodes.find((n) => n.id === `equipment:${param}`)?.id ??
            null
          : null;
        if (wanted) {
          setSelected(wanted);
          return;
        }
        // Default focus is the C-3 story, so the page opens on something
        // meaningful instead of the whole refinery at once.
        if (g.nodes.some((n) => n.id === C3)) setSelected(C3);
      })
      .catch((e) => setError(String(e.message ?? e)));
    loadSystemIndex().then(setSysIndex).catch((e) => setError(String(e.message ?? e)));
  }, []);

  const ensureFull = useCallback(async (): Promise<SystemFull | null> => {
    if (sysFull) return sysFull;
    setLoadingFull(true);
    try {
      const f = await loadSystemFull();
      setSysFull(f);
      return f;
    } catch (e) {
      setError(String((e as Error).message ?? e));
      return null;
    } finally {
      setLoadingFull(false);
    }
  }, [sysFull]);

  /* ---------------- assemble the active graph ---------------- */
  const sysGraph = useMemo<KGraph | null>(() => {
    if (!sysIndex) return null;
    const base = systemOverview(sysIndex);
    if (!sysFull || expanded.size === 0) return base;
    const nodes = [...base.nodes];
    const edges = [...base.edges];
    const seen = new Set(nodes.map((n) => n.id));
    for (const cid of expanded) {
      const part = expandCommunity(sysFull, cid);
      for (const n of part.nodes) if (!seen.has(n.id)) { nodes.push(n); seen.add(n.id); }
      edges.push(...part.edges);
    }
    return { ...base, nodes, edges, stats: summarize(nodes, edges, base.communities) };
  }, [sysIndex, sysFull, expanded]);

  const full = ns === "plant" ? plant : sysGraph;

  /** Lens filter — keeps the lens nodes plus their direct neighbours so the
   *  result stays a connected picture rather than a scatter of orphans. */
  const graph = useMemo<KGraph | null>(() => {
    if (!full) return null;
    const types = LENSES.find((l) => l.id === lens)?.types ?? [];
    if (!types.length || ns === "system") return full;
    const keep = new Set(full.nodes.filter((n) => types.includes(n.type)).map((n) => n.id));
    for (const e of full.edges) {
      if (keep.has(e.from)) keep.add(e.to);
      if (keep.has(e.to)) keep.add(e.from);
    }
    const nodes = full.nodes.filter((n) => keep.has(n.id));
    const ids = new Set(nodes.map((n) => n.id));
    const edges = full.edges.filter((e) => ids.has(e.from) && ids.has(e.to));
    return { ...full, nodes, edges, stats: summarize(nodes, edges, full.communities) };
  }, [full, lens, ns]);

  const positions = useMemo<Map<string, Pt>>(() => {
    if (!graph) return new Map();
    if (ns === "plant") return layoutPlant(graph);
    const base = layoutSystemOverview(graph);
    if (sysFull && expanded.size) {
      for (const cid of expanded) {
        const center = base.get(`community:${cid}`);
        if (!center) continue;
        const members = graph.nodes.filter((n) => n.type !== "community" && n.group === String(cid));
        for (const [id, p] of layoutCommunityMembers(members, center)) base.set(id, p);
      }
    }
    return base;
  }, [graph, ns, sysFull, expanded]);

  const { adjacency } = useMemo(
    () => (graph ? indexGraph(graph) : { adjacency: new Map() }),
    [graph],
  );

  const highlight = useMemo(
    () => (selected ? neighborhood(adjacency, selected, 1) : new Set<string>()),
    [adjacency, selected],
  );

  const path = useMemo(() => {
    if (!pathFrom || !pathTo) return [];
    return shortestPath(adjacency, pathFrom, pathTo) ?? [];
  }, [adjacency, pathFrom, pathTo]);

  const selectedNode = useMemo(
    () => graph?.nodes.find((n) => n.id === selected) ?? null,
    [graph, selected],
  );

  const rels = useMemo(() => {
    if (!graph || !selected) return [] as { edge: KEdge; out: boolean; other: KNode }[];
    const byId = new Map(graph.nodes.map((n) => [n.id, n]));
    const out: { edge: KEdge; out: boolean; other: KNode }[] = [];
    for (const e of graph.edges) {
      if (e.from !== selected && e.to !== selected) continue;
      const other = byId.get(e.from === selected ? e.to : e.from);
      if (!other) continue;
      out.push({ edge: e, out: e.from === selected, other });
    }
    return out;
  }, [graph, selected]);

  const hits = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q || !graph) return [];
    return graph.nodes
      .filter((n) => `${n.label} ${n.id} ${n.type} ${n.group ?? ""}`.toLowerCase().includes(q))
      .slice(0, 30);
  }, [graph, query]);

  /* ---------------- actions ---------------- */
  const select = useCallback((id: string | null) => {
    setSelected(id);
    setSelectedEdge(null);
  }, []);

  const expand = useCallback(
    async (id: string) => {
      if (ns !== "system") return;
      const m = /^community:(\d+)$/.exec(id);
      if (m) {
        setExpanded((s) => new Set(s).add(Number(m[1])));
        await ensureFull();
      }
    },
    [ns, ensureFull],
  );

  const loadCommunity = useCallback(
    async (cid: number) => {
      setNs("system");
      setLens("all");
      setExpanded((s) => new Set(s).add(cid));
      await ensureFull();
    },
    [ensureFull],
  );

  const runSystemSearch = useCallback(async () => {
    const q = query.trim();
    if (!q) return;
    const f = await ensureFull();
    if (!f) return;
    const found = searchSystem(f, q, 60);
    if (!found.length) return;
    const comms = new Set(found.map((n) => Number(n.group)).filter((n) => !Number.isNaN(n)));
    setNs("system");
    setExpanded((s) => new Set([...s, ...comms]));
    setSelected(found[0].id);
  }, [query, ensureFull]);

  /**
   * Walk the golden path. The route is discovered from the graph, not
   * hardcoded: an anomaly on C-3 → C-3 → its work order → the approval that
   * governs it → the agent that raised it. If a link is missing from the data
   * the path is simply shorter — nothing is fabricated to lengthen it.
   */
  const traceStory = useCallback(() => {
    if (!plant) return;
    setNs("plant");
    setLens("all");
    const touchesC3 = (id: string) =>
      plant.edges.some(
        (e) => (e.from === id && e.to === C3) || (e.to === id && e.from === C3),
      );
    const anomaly = plant.nodes.find((n) => n.type === "anomaly" && touchesC3(n.id));
    // work order → equipment is `FOR_EQUIPMENT`, so the edge runs from the
    // work order to the asset, not the other way round.
    const wo = plant.nodes.find(
      (n) => n.type === "work_order" && plant.edges.some((e) => e.from === n.id && e.to === C3),
    );
    const agent = plant.nodes.find(
      (n) => n.type === "agent" && wo != null && plant.edges.some((e) => e.from === n.id && e.to === wo.id),
    );
    setPathFrom(anomaly?.id ?? C3);
    setPathTo((agent ?? wo)?.id ?? C3);
    setSelected(C3);
    graphRef.current?.focusNode(C3);
  }, [plant]);

  /* ---------------- keyboard ---------------- */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        const el = document.getElementById("ku-search") as HTMLInputElement | null;
        el?.focus();
        el?.select();
      }
      if (e.key === "Escape") { setSelected(null); setSelectedEdge(null); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const stats = graph?.stats;

  return (
    <div className="ku">
      <header className="ku-head">
        <div className="ku-head__title">
          <span className="ku-kicker">Project 117 · Knowledge Universe</span>
          <h1>Knowledge Universe</h1>
          {ns === "system" && sysIndex && (
            // The system graph is a compiled artifact, not a live view. Saying
            // when it was built — and from what — is the difference between a
            // current picture of the codebase and a stale one presented as
            // current. `graphify-out/` is not committed, so the age is the only
            // honest signal available at runtime.
            <span className="ku-meta" style={{ display: "block", marginTop: 4, fontSize: 10.5, letterSpacing: "0.06em", color: "var(--ink-3)" }}>
              {sysIndex.nodeCount.toLocaleString()} nodes · {sysIndex.edgeCount.toLocaleString()} edges ·
              compiled {new Date(sysIndex.generated).toLocaleDateString()} by {sysIndex.generator}
            </span>
          )}
        </div>

        <div className="ku-ns" role="tablist" aria-label="Graph namespace">
          {(["plant", "system"] as Namespace[]).map((n) => (
            <button
              key={n}
              role="tab"
              aria-selected={ns === n}
              className={ns === n ? "is-active" : undefined}
              onClick={() => { setNs(n); setLens("all"); setSelected(null); setPathFrom(null); setPathTo(null); }}
            >
              {n === "plant" ? "Plant Knowledge" : "System Knowledge"}
            </button>
          ))}
        </div>

        <div className="ku-search">
          <Icon name="search" size={13} />
          <input
            id="ku-search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && ns === "system") void runSystemSearch(); }}
            placeholder={ns === "plant" ? "Search equipment, documents, events, agents…" : "Search symbols, files, communities…"}
            aria-label="Search the knowledge graph"
          />
          {query && <button className="ku-search__x" onClick={() => setQuery("")} aria-label="Clear search">×</button>}
          {ns === "system" && (
            <button className="ku-search__go" onClick={() => void runSystemSearch()} disabled={loadingFull}>
              {loadingFull ? "…" : "Search all"}
            </button>
          )}
          <kbd>⌘K</kbd>
        </div>
      </header>

      {error && (
        <div className="ku-error" role="alert">
          <b>Graph unavailable.</b> {error}
        </div>
      )}

      <div className="ku-body">
        {/* ---------------- left navigation ---------------- */}
        <nav className="ku-nav" aria-label="Graph navigation">
          <p className="ku-nav__label">Views</p>
          {LENSES.map((l) => (
            <button
              key={l.id}
              className={`ku-nav__item${lens === l.id ? " is-active" : ""}`}
              onClick={() => { setLens(l.id); setSelected(null); }}
              disabled={ns === "system" && l.id !== "all"}
            >
              <span className="ku-nav__dot" style={{ background: l.types[0] ? colorOf(l.types[0]) : "var(--ink-3)" }} />
              {l.label}
              {stats && l.types.length > 0 && ns === "plant" && (
                <em>{full?.nodes.filter((n) => l.types.includes(n.type)).length ?? 0}</em>
              )}
            </button>
          ))}

          <p className="ku-nav__label" style={{ marginTop: 16 }}>
            {ns === "system" ? `Communities (${sysIndex?.communityCount ?? "…"})` : "Areas"}
          </p>
          <div className="ku-nav__list">
            {ns === "system"
              ? sysIndex?.communities.slice(0, 40).map((c) => (
                  <button key={c.id} className="ku-nav__comm" onClick={() => void loadCommunity(c.id)}>
                    <span>{c.name}</span>
                    <em>{c.size}</em>
                  </button>
                ))
              : plant?.communities.map((c) => (
                  <button key={c.id} className="ku-nav__comm" onClick={() => { setLens("all"); }}>
                    <span>{c.name}</span>
                    <em>{c.size}</em>
                  </button>
                ))}
          </div>

          <button className="ku-trace" onClick={traceStory}>
            <Icon name="play" size={12} /> Trace the C-3 story
          </button>
        </nav>

        {/* ---------------- graph ---------------- */}
        <section className="ku-stage" aria-label="Graph viewport">
          <div className="ku-controls" role="toolbar" aria-label="Graph controls">
            <button onClick={() => graphRef.current?.zoomIn()} title="Zoom in" aria-label="Zoom in">＋</button>
            <button onClick={() => graphRef.current?.zoomOut()} title="Zoom out" aria-label="Zoom out">－</button>
            <button onClick={() => graphRef.current?.fit()} title="Fit to view" aria-label="Fit to view">⤢</button>
            <button
              onClick={() => selected && graphRef.current?.focusNode(selected)}
              title="Focus selection"
              aria-label="Focus selection"
              disabled={!selected}
            >◎</button>
            <button onClick={() => graphRef.current?.reset()} title="Reset camera" aria-label="Reset camera">↺</button>
            <button onClick={() => graphRef.current?.fullscreen()} title="Fullscreen" aria-label="Fullscreen">⛶</button>
          </div>

          {(pathFrom || pathTo) && (
            <div className="ku-pathbar">
              <span className="cs-mono">PATH</span>
              <b>{pathFrom?.replace(/^[a-z_]+:/, "") ?? "—"}</b>
              <span>→</span>
              <b>{pathTo?.replace(/^[a-z_]+:/, "") ?? "—"}</b>
              {path.length > 1 ? (
                <span className="ku-pathbar__ok">{path.length - 1} hops · {path.map((p) => p.replace(/^[a-z_]+:/, "")).join(" → ")}</span>
              ) : (
                <span className="ku-pathbar__bad">no path within 8 hops</span>
              )}
              <button onClick={() => { setPathFrom(null); setPathTo(null); }} aria-label="Clear path">×</button>
            </div>
          )}

          {!graph ? (
            <div className="ku-loading"><i /> Compiling knowledge universe…</div>
          ) : (
            <GraphCanvas
              ref={graphRef}
              graph={graph}
              positions={positions}
              selected={selected}
              highlight={highlight}
              path={path}
              onSelect={select}
              onExpand={(id) => void expand(id)}
              expandable={ns === "system" ? new Set((sysGraph?.nodes ?? []).filter((n) => n.type === "community").map((n) => n.id)) : undefined}
            />
          )}

          {stats && (
            <div className="ku-stats">
              <span><b>{stats.nodes.toLocaleString()}</b> nodes</span>
              <span><b>{stats.edges.toLocaleString()}</b> relationships</span>
              <span><b>{stats.communities}</b> communities</span>
              <span className="ku-stats__hint">
                {ns === "plant"
                  ? "Real plant geometry · scroll to zoom · drag to pan · double-click a unit"
                  : "Graphify community view · double-click a community to expand"}
              </span>
            </div>
          )}

          {!selected && graph && (
            <div className="ku-hint">
              <b>Select an entity</b>
              <span>Click a node to inspect it. Everything outside its neighbourhood recedes, and every
                relationship is listed with the source it was read from.</span>
              <span>Try <b>C-3</b> — or run <b>Trace the C-3 story</b>.</span>
            </div>
          )}

          {hits.length > 0 && (
            <div className="ku-hits" role="listbox" aria-label="Search results">
              {hits.map((n) => (
                <button
                  key={n.id}
                  role="option"
                  aria-selected={n.id === selected}
                  onClick={() => {
                    if (ns === "system" && n.type === "community") void expand(n.id);
                    select(n.id);
                    graphRef.current?.focusNode(n.id);
                    setQuery("");
                  }}
                >
                  <span className="ku-hits__dot" style={{ background: colorOf(n.type) }} />
                  <span className="ku-hits__label">{n.label}</span>
                  <span className="ku-hits__type">{n.type}</span>
                </button>
              ))}
            </div>
          )}
        </section>

        {/* ---------------- detail (contextual overlay) ---------------- */}
        <aside className={`ku-detail${selectedNode ? " is-open" : ""}`} aria-label="Entity detail" aria-hidden={!selectedNode}>
          {selectedNode && (
            <button className="ku-detail__close" onClick={() => { select(null); setSelectedEdge(null); }} aria-label="Close detail panel">×</button>
          )}
          {selectedNode && (
            <EntityDetail
              node={selectedNode}
              rels={rels}
              selectedEdge={selectedEdge}
              onEdge={setSelectedEdge}
              onNavigate={(id) => { select(id); graphRef.current?.focusNode(id); }}
              onPathFrom={() => setPathFrom(selectedNode.id)}
              onPathTo={() => setPathTo(selectedNode.id)}
              pathFrom={pathFrom}
              pathTo={pathTo}
              router={router}
            />
          )}
        </aside>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function EntityDetail({
  node,
  rels,
  selectedEdge,
  onEdge,
  onNavigate,
  onPathFrom,
  onPathTo,
  pathFrom,
  pathTo,
  router,
}: {
  node: KNode;
  rels: { edge: KEdge; out: boolean; other: KNode }[];
  selectedEdge: KEdge | null;
  onEdge: (e: KEdge | null) => void;
  onNavigate: (id: string) => void;
  onPathFrom: () => void;
  onPathTo: () => void;
  pathFrom: string | null;
  pathTo: string | null;
  router: ReturnType<typeof useRouter>;
}) {
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

  return (
    <div className="ku-entity">
      <div className="ku-entity__head">
        <span className="ku-entity__dot" style={{ background: colorOf(node.type) }} />
        <div>
          <h2>{node.label}</h2>
          <p>
            <Tag>{node.type.replace(/_/g, " ")}</Tag>
            {node.status && <span className="ku-status">{node.status}</span>}
          </p>
        </div>
      </div>

      <dl className="ku-facts">
        <div><dt>Entity</dt><dd>{node.id}</dd></div>
        {node.group && <div><dt>Group</dt><dd>{node.group}</dd></div>}
        {node.source && <div><dt>Source</dt><dd>{node.source}</dd></div>}
        {Object.entries(node.facts ?? {}).map(([k, v]) =>
          v === undefined || v === "" ? null : (
            <div key={k}>
              <dt>{k.replace(/_/g, " ")}</dt>
              <dd>{String(v)}</dd>
            </div>
          ),
        )}
        <div><dt>Relationships</dt><dd>{rels.length}</dd></div>
      </dl>

      <div className="ku-actions">
        {node.href && (
          <button className="ku-btn ku-btn--primary" onClick={() => router.push(node.href!)}>
            <Icon name="chevron" size={12} /> Open {labelForHref(node.href)}
          </button>
        )}
        {node.type === "equipment" && (
          <button className="ku-btn" onClick={() => router.push(`/console/simulation/builder?focus=${encodeURIComponent(node.id.replace(/^equipment:/, ""))}`)}>
            <Icon name="gauge" size={12} /> Open in simulation
          </button>
        )}
        <button className="ku-btn" onClick={() => router.push(`/console/workspace?entity=${encodeURIComponent(node.label)}`)}>
          <Icon name="chat" size={12} /> Ask AI about this
        </button>
        <div className="ku-actions__pair">
          <button className={`ku-btn${pathFrom === node.id ? " is-on" : ""}`} onClick={onPathFrom}>Set path start</button>
          <button className={`ku-btn${pathTo === node.id ? " is-on" : ""}`} onClick={onPathTo}>Set path end</button>
        </div>
      </div>

      {evidence.length > 0 && (
        <section className="ku-sec">
          <h3>Evidence · {evidence.length} document{evidence.length === 1 ? "" : "s"}</h3>
          {evidence.map((r) => (
            <button key={r.other.id} className="ku-rel" onClick={() => (r.other.href ? router.push(r.other.href) : onNavigate(r.other.id))}>
              <span className="ku-rel__rel">{r.edge.relation.replace(/_/g, " ")}</span>
              <span className="ku-rel__name">{r.other.label}</span>
              <span className="ku-rel__prov" style={{ color: PROVENANCE_TONE[r.edge.provenance] }}>{r.edge.provenance}</span>
            </button>
          ))}
        </section>
      )}

      {workOrders.length > 0 && (
        <section className="ku-sec">
          <h3>Work orders</h3>
          {workOrders.map((r) => (
            <button key={r.other.id} className="ku-rel" onClick={() => r.other.href && router.push(r.other.href)}>
              <span className="ku-rel__rel">{r.edge.relation.replace(/_/g, " ")}</span>
              <span className="ku-rel__name">{r.other.label}</span>
              <span className="ku-rel__prov" style={{ color: PROVENANCE_TONE[r.edge.provenance] }}>{r.edge.provenance}</span>
            </button>
          ))}
        </section>
      )}

      <section className="ku-sec">
        <h3>All relationships · {rels.length}</h3>
        <div className="ku-rels">
          {rels.slice(0, 60).map((r) => (
            <button
              key={r.edge.id}
              className={`ku-rel${selectedEdge?.id === r.edge.id ? " is-on" : ""}`}
              onClick={() => { if (r.other.href) router.push(r.other.href); else onNavigate(r.other.id); }}
              onContextMenu={(e) => { e.preventDefault(); onEdge(r.edge); }}
              title="Click to navigate · right-click for provenance"
            >
              <span className="ku-rel__rel">{r.out ? "" : "← "}{r.edge.relation.replace(/_/g, " ")}</span>
              <span className="ku-rel__name">{r.other.label}</span>
              <span className="ku-rel__prov" style={{ color: PROVENANCE_TONE[r.edge.provenance] }}>{r.edge.provenance}</span>
            </button>
          ))}
        </div>
        {rels.length > 60 && <p className="ku-more">+{rels.length - 60} more</p>}
      </section>

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
              <div><dt>Classification</dt><dd style={{ color: PROVENANCE_TONE[selectedEdge.provenance] }}>{selectedEdge.provenance}</dd></div>
              {selectedEdge.source && <div><dt>Source</dt><dd>{selectedEdge.source}</dd></div>}
              {selectedEdge.confidence != null && <div><dt>Confidence</dt><dd>{selectedEdge.confidence.toFixed(2)}</dd></div>}
            </dl>
          </div>
        )}
      </section>

      {byType.size > 0 && (
        <section className="ku-sec">
          <h3>Neighbourhood by type</h3>
          <div className="ku-chips">
            {[...byType.entries()].sort((a, b) => b[1].length - a[1].length).map(([t, list]) => (
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

function labelForHref(href: string): string {
  if (href.startsWith("/console/equipment/")) return "digital twin";
  if (href.startsWith("/console/work-orders/")) return "work order";
  if (href.startsWith("/console/documents")) return "document";
  if (href.startsWith("/console/history")) return "history";
  if (href.startsWith("/console/approvals")) return "approval";
  if (href.startsWith("/console/workspace")) return "AI workspace";
  return "record";
}
