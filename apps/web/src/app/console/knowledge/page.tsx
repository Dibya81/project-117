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
 *
 * This file owns the chrome only: the data wiring, the graph assembly and the
 * layout maths are untouched. The sidebar filters are glass segmented controls
 * with a shared-element glider, the search box is a live autocomplete whose
 * active row drives the graph's existing selection highlight, and the drawer is
 * the EntityInspector (metadata cards + relationship tree + deep-link actions).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Lucide } from "@/components/ui/LucideIcon";
import GraphCanvas, { type GraphHandle } from "@/components/knowledge/GraphCanvas";
import SegmentedControl, { type SegmentOption } from "@/components/knowledge/SegmentedControl";
import SearchAutocomplete from "@/components/knowledge/SearchAutocomplete";
import EntityInspector from "@/components/knowledge/EntityInspector";
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
import { forceLayout, layoutCommunityMembers, layoutPlant, layoutSystemOverview, type Pt } from "@/lib/knowledge/layout";
import { api } from "@/lib/api";
import {
  colorOf,
  indexGraph,
  neighborhood,
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

const LENSES: { id: Lens; label: string; types: string[]; icon: Parameters<typeof Lucide>[0]["name"] }[] = [
  { id: "all", label: "All knowledge", types: [], icon: "graph" },
  { id: "investigations", label: "Recent investigations", types: ["anomaly", "event", "rule"], icon: "insights" },
  { id: "equipment", label: "Equipment", types: ["equipment", "plant", "area"], icon: "equipment" },
  { id: "sensor", label: "Sensors", types: ["sensor"], icon: "gauge" },
  { id: "document", label: "Documents", types: ["document"], icon: "doc" },
  { id: "anomaly", label: "Anomalies", types: ["anomaly"], icon: "alert" },
  { id: "work_order", label: "Work orders", types: ["work_order"], icon: "workorder" },
  { id: "rule", label: "Learned rules", types: ["rule"], icon: "check" },
];

/**
 * The lenses grouped into the filter families the sidebar shows. The order
 * inside each group preserves the flat list's original order, so nothing moves
 * hidden behind a visual separator.
 */
const LENS_GROUPS: { id: string; label: string; lenses: Lens[] }[] = [
  { id: "scope", label: "Scope", lenses: ["all", "investigations"] },
  { id: "assets", label: "Assets", lenses: ["equipment", "sensor"] },
  { id: "records", label: "Records", lenses: ["document", "anomaly", "work_order", "rule"] },
];

/**
 * The asset the guided trace starts from, discovered from the graph rather than
 * named. It used to be the hardcoded `equipment:C-3`, an asset from the retired
 * demo data: the "Trace the C-3 story" button set its path endpoints to a node
 * that does not exist, so pressing it did nothing at all. The anchor is now the
 * best-connected real asset, preferring one that reaches a document.
 */
function chooseTraceAnchor(graph: KGraph): string | null {
  const equipment = graph.nodes.filter((n) => n.type === "equipment");
  if (!equipment.length) return null;
  const degree = new Map<string, number>();
  const reachesDocument = new Set<string>();
  for (const e of graph.edges) {
    degree.set(e.from, (degree.get(e.from) ?? 0) + 1);
    degree.set(e.to, (degree.get(e.to) ?? 0) + 1);
    const from = graph.nodes.find((n) => n.id === e.from);
    const to = graph.nodes.find((n) => n.id === e.to);
    if (to?.type === "document" && from?.type === "equipment") reachesDocument.add(from.id);
    if (from?.type === "document" && to?.type === "equipment") reachesDocument.add(to.id);
  }
  const scored = [...equipment].sort((a, b) => {
    const doc = Number(reachesDocument.has(b.id)) - Number(reachesDocument.has(a.id));
    if (doc) return doc;
    return (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0);
  });
  const top = scored[0];
  return (degree.get(top.id) ?? 0) > 0 ? top.id : null;
}

export default function KnowledgeUniverse() {
  const router = useRouter();
  const graphRef = useRef<GraphHandle>(null);

  const [ns, setNs] = useState<Namespace>("plant");
  const [lens, setLens] = useState<Lens>("all");
  const [plant, setPlant] = useState<KGraph | null>(null);
  const [companyGraph, setCompanyGraph] = useState<KGraph | null>(null);
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
  const loadCompanyGraph = useCallback(async () => {
    try {
      const res = await api.knowledgeHub.graph();
      const nodes: KNode[] = res.nodes.map((n) => ({
        id: n.id,
        label: n.label,
        type: n.type.toLowerCase(),
        group: n.type,
        status: "verified",
        source: `docs: ${n.document_ids?.length || 0}`,
        facts: {
          "Entity Type": n.type,
          Confidence: `${Math.round((n.confidence ?? 0.8) * 100)}%`,
          "Linked Docs": n.document_ids?.length ? `${n.document_ids.length} documents` : "1 document",
        },
        href: n.document_ids?.[0] ? `/console/knowledge/documents` : undefined,
      }));
      const edges: KEdge[] = res.edges.map((e) => ({
        id: e.id,
        from: e.source,
        to: e.target,
        relation: (e.label || "RELATES_TO").toUpperCase(),
        provenance: "EXTRACTED",
        confidence: e.confidence ?? 0.85,
      }));
      const g: KGraph = {
        namespace: "company",
        nodes,
        edges,
        communities: [],
        stats: summarize(nodes, edges, []),
      };
      setCompanyGraph(g);
    } catch (e) {
      console.error("Failed to load company graph", e);
    }
  }, []);

  useEffect(() => {
    if (ns === "company") {
      void loadCompanyGraph();
    }
  }, [ns, loadCompanyGraph]);

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
        // Open on the discovered anchor rather than the whole refinery at once.
        const anchor = chooseTraceAnchor(g);
        if (anchor) setSelected(anchor);
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

  const full = ns === "plant" ? plant : ns === "company" ? companyGraph : sysGraph;

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
    if (ns === "company") return forceLayout(graph);
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
   * The autocomplete's active row drives the graph highlight through the
   * existing selection state: `GraphCanvas` already fades everything outside the
   * selection's neighbourhood and frames it, so no new highlight prop is needed
   * (and none was available). The camera follows the active row so the
   * highlighted node is actually on screen.
   */
  const previewHit = useCallback(
    (node: KNode) => {
      setSelected(node.id);
      setSelectedEdge(null);
      graphRef.current?.focusNode(node.id);
    },
    [],
  );

  const pickHit = useCallback(
    (node: KNode) => {
      if (ns === "system" && node.type === "community") void expand(node.id);
      setSelected(node.id);
      setSelectedEdge(null);
      graphRef.current?.focusNode(node.id);
      setQuery("");
    },
    [ns, expand],
  );

  /** The anchor the guided trace walks from, or null when the graph is empty. */
  const traceAnchor = useMemo(() => (plant ? chooseTraceAnchor(plant) : null), [plant]);

  /**
   * Walk from the anchor to whatever the graph actually connects it to: an
   * anomaly, then a work order raised against it, then the agent that raised
   * that. The route is discovered from the edges, never hardcoded, and if a
   * link is missing the path is simply shorter — nothing is invented to
   * lengthen it. With no anomalies or work orders in the store (the current
   * state) this resolves to anchor → its documents, which is a real path.
   */
  const traceStory = useCallback(() => {
    if (!plant || !traceAnchor) return;
    setNs("plant");
    setLens("all");
    const touches = (id: string) =>
      plant.edges.some(
        (e) => (e.from === id && e.to === traceAnchor) || (e.to === id && e.from === traceAnchor),
      );
    const anomaly = plant.nodes.find((n) => n.type === "anomaly" && touches(n.id));
    // work order → equipment is `FOR_EQUIPMENT`, so the edge runs from the
    // work order to the asset, not the other way round.
    const wo = plant.nodes.find(
      (n) =>
        n.type === "work_order" &&
        plant.edges.some((e) => e.from === n.id && e.to === traceAnchor),
    );
    const agent = plant.nodes.find(
      (n) => n.type === "agent" && wo != null && plant.edges.some((e) => e.from === n.id && e.to === wo.id),
    );
    const document = plant.nodes.find(
      (n) =>
        n.type === "document" &&
        plant.edges.some(
          (e) =>
            (e.from === traceAnchor && e.to === n.id) ||
            (e.to === traceAnchor && e.from === n.id),
        ),
    );
    const from = anomaly?.id ?? traceAnchor;
    const to = (agent ?? wo ?? document)?.id ?? traceAnchor;
    setPathFrom(from);
    setPathTo(to === from ? null : to);
    setSelected(traceAnchor);
    graphRef.current?.focusNode(traceAnchor);
  }, [plant, traceAnchor]);

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

  /** Real per-lens counts (plant namespace only, where every type is loaded). */
  const lensSegments = useCallback(
    (ids: Lens[]): SegmentOption[] =>
      ids.flatMap((lid) => {
        const l = LENSES.find((x) => x.id === lid);
        if (!l) return [];
        return [
          {
            id: l.id,
            label: l.label,
            icon: l.icon,
            tone: l.types[0] ? colorOf(l.types[0]) : undefined,
            count:
              ns === "plant" && stats && l.types.length > 0
                ? (full?.nodes.filter((n) => l.types.includes(n.type)).length ?? 0)
                : undefined,
            disabled: ns === "system" && l.id !== "all",
          },
        ];
      }),
    [ns, stats, full],
  );

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

        <SegmentedControl
          className="ku-ns"
          layoutId="ku-namespace"
          ariaLabel="Graph namespace"
          variant="tabs"
          value={ns}
          onChange={(id) => {
            setNs(id as Namespace);
            setLens("all");
            setSelected(null);
            setPathFrom(null);
            setPathTo(null);
          }}
          options={[
            { id: "plant", label: "Plant Knowledge" },
            { id: "company", label: "Company Docs" },
            { id: "system", label: "System Knowledge" },
          ]}
        />
      </header>

      {error && (
        <div className="ku-error" role="alert">
          <b>Graph unavailable.</b> {error}
        </div>
      )}

      <div className="ku-body">
        {/* ---------------- left navigation ---------------- */}
        <nav className="ku-nav" aria-label="Graph navigation">
          <SearchAutocomplete
            query={query}
            onQueryChange={setQuery}
            hits={hits}
            selectedId={selected}
            onActive={previewHit}
            onPick={pickHit}
            onSubmit={() => { if (ns === "system") void runSystemSearch(); }}
            placeholder={ns === "plant" ? "Search equipment, docs…" : "Search symbols, files…"}
            busy={loadingFull}
            showSearchAll={ns === "system"}
          />

          <div className="ku-nav__scroll">
            <p className="ku-nav__label">Views</p>
            {LENS_GROUPS.map((g) => (
              <div className="ku-filter" key={g.id}>
                <p className="ku-filter__label">{g.label}</p>
                <SegmentedControl
                  className="ku-nav__seg"
                  chipClassName="ku-nav__item"
                  layoutId={`ku-lens-${g.id}`}
                  ariaLabel={`${g.label} filters`}
                  orientation="vertical"
                  variant="radio"
                  value={lens}
                  onChange={(id) => { setLens(id as Lens); setSelected(null); }}
                  options={lensSegments(g.lenses)}
                />
              </div>
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
              <Lucide name="play" size={12} />{' '}
              {traceAnchor
                ? `Trace ${traceAnchor.replace(/^equipment:/, "")}`
                : "Trace (no plant data)"}
            </button>
          </div>
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
              <span>
                Try <b>{traceAnchor ? traceAnchor.replace(/^equipment:/, "") : "an equipment tag"}</b> — or run the
                guided trace.
              </span>
            </div>
          )}
        </section>

        {/* ---------------- detail (contextual overlay) ---------------- */}
        <aside className={`ku-detail${selectedNode ? " is-open" : ""}`} aria-label="Entity detail" aria-hidden={!selectedNode}>
          {selectedNode && (
            <button className="ku-detail__close" onClick={() => { select(null); setSelectedEdge(null); }} aria-label="Close detail panel">
              <Lucide name="x" size={14} />
            </button>
          )}
          {/* The content is keyed, not cross-faded: the inspector previews every
              active autocomplete row, so an enter/exit pair (especially
              `AnimatePresence mode="wait"`) parks the panel at opacity 0 while
              the user arrows through results. The drawer itself still slides in
              via the existing `.ku-detail` CSS transition; the card swaps
              instantly so it is always readable. */}
          {selectedNode && (
            <div key={selectedNode.id} className="ku-detail__body">
              <EntityInspector
                node={selectedNode}
                rels={rels}
                selectedEdge={selectedEdge}
                onEdge={setSelectedEdge}
                onSelectNode={(id) => { select(id); graphRef.current?.focusNode(id); }}
                onOpenHref={(href) => router.push(href)}
                onPathFrom={() => setPathFrom(selectedNode.id)}
                onPathTo={() => setPathTo(selectedNode.id)}
                pathFrom={pathFrom}
                pathTo={pathTo}
              />
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
