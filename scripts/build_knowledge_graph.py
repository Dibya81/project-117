#!/usr/bin/env python3
"""Compile graphify-out/graph.json into the web artifact the Knowledge Universe
renders.

Graphify's raw graph is 4,159 nodes / 9,114 edges — correct for analysis, too
heavy to hand the browser as-is. This emits one compact, self-describing file:

  apps/web/public/knowledge/system-graph.json

containing

  * `communities` — graphify's own 226 clusters (names taken verbatim, never
    renamed or invented) plus the inter-community edge weights, so the initial
    view can render 226 super-nodes instead of 4,159;
  * `nodes` / `links` — the full graph, key-minified, for progressive
    expansion.

Run:  python3 scripts/build_knowledge_graph.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GRAPH = REPO / "graphify-out" / "graph.json"
OUT = REPO / "apps" / "web" / "public" / "knowledge" / "system-graph.json"
OUT_INDEX = REPO / "apps" / "web" / "public" / "knowledge" / "system-index.json"


def kind_of(node: dict) -> str:
    """Coarse semantic type used for colour and filtering in the UI."""
    if node.get("file_type") == "code" and not node.get("_callable") and node.get("label", "").endswith((".tsx", ".ts", ".py", ".md")):
        return "file"
    if node.get("_callable_class"):
        return "class"
    if node.get("_callable"):
        return "function"
    if node.get("file_type") == "doc":
        return "doc"
    return "symbol"


def main() -> int:
    if not GRAPH.exists():
        print(f"missing {GRAPH} — run scripts/graphify-obsidian.sh first", file=sys.stderr)
        return 1

    raw = json.loads(GRAPH.read_text(encoding="utf-8"))
    rnodes = raw.get("nodes") or []
    rlinks = raw.get("links") or raw.get("edges") or []
    print(f"read {len(rnodes)} nodes / {len(rlinks)} edges")

    # ---- communities: names come straight from graphify -------------------
    members: dict[int, list[str]] = defaultdict(list)
    for n in rnodes:
        cid = n.get("community")
        if cid is not None:
            members[cid].append(n["id"])

    degree: Counter[str] = Counter()
    for e in rlinks:
        degree[e["source"]] += 1
        degree[e["target"]] += 1

    comm_name: dict[int, str] = {}
    for n in rnodes:
        cid = n.get("community")
        if cid is not None and cid not in comm_name:
            comm_name[cid] = n.get("community_name") or f"Community {cid}"

    node_comm = {n["id"]: n.get("community") for n in rnodes}

    # ---- inter-community edge weights (for the zoomed-out view) -----------
    pair_weight: Counter[tuple[int, int]] = Counter()
    for e in rlinks:
        a, b = node_comm.get(e["source"]), node_comm.get(e["target"])
        if a is None or b is None or a == b:
            continue
        pair_weight[(min(a, b), max(a, b))] += 1

    communities = []
    for cid, ids in members.items():
        top = sorted(ids, key=lambda i: -degree[i])[:8]
        by_id = {n["id"]: n for n in rnodes}
        communities.append({
            "id": cid,
            "name": comm_name.get(cid, f"Community {cid}"),
            "size": len(ids),
            "degree": sum(degree[i] for i in ids),
            "major": [{"id": i, "label": by_id[i]["label"], "kind": kind_of(by_id[i])} for i in top if i in by_id],
        })
    communities.sort(key=lambda c: -c["size"])

    community_edges = [
        {"a": a, "b": b, "w": w}
        for (a, b), w in pair_weight.most_common()
    ]

    # ---- full graph, key-minified ----------------------------------------
    nodes = [
        {
            "i": n["id"],
            "l": n.get("label") or n["id"],
            "c": n.get("community"),
            "k": kind_of(n),
            "f": n.get("source_file") or "",
            "o": n.get("source_location") or "",
        }
        for n in rnodes
    ]
    links = [
        {
            "s": e["source"],
            "t": e["target"],
            "r": e.get("relation") or "related",
            "c": e.get("confidence") or "EXTRACTED",
            "f": e.get("source_file") or "",
            "o": e.get("source_location") or "",
        }
        for e in rlinks
    ]

    payload = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "graphify-out/graph.json",
        "generator": "graphify 0.9.56",
        "nodeCount": len(nodes),
        "edgeCount": len(links),
        "communityCount": len(communities),
        "relations": dict(Counter(e["r"] for e in links).most_common()),
        "communities": communities,
        "communityEdges": community_edges,
        "nodes": nodes,
        "links": links,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)

    # Two artifacts on purpose. The index is what the page renders first: 226
    # community super-nodes and their inter-cluster edges. The full graph is
    # ~2.3 MB and is fetched only when the user drills into a community or
    # searches across the whole namespace.
    index = {
        "generated": payload["generated"],
        "source": payload["source"],
        "generator": payload["generator"],
        "nodeCount": payload["nodeCount"],
        "edgeCount": payload["edgeCount"],
        "communityCount": payload["communityCount"],
        "relations": payload["relations"],
        "communities": communities,
        "communityEdges": community_edges,
    }
    OUT_INDEX.write_text(json.dumps(index, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    OUT.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

    print(f"wrote {OUT_INDEX.relative_to(REPO)}  {OUT_INDEX.stat().st_size / 1024:.0f} KB  (first paint)")
    print(f"wrote {OUT.relative_to(REPO)}  {OUT.stat().st_size / 1024 / 1024:.2f} MB  (lazy)")
    print(f"  {len(nodes)} nodes, {len(links)} links, {len(communities)} communities, {len(community_edges)} community edges")
    print("  top relations:", list(payload["relations"].items())[:6])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
