"""Read queries over the knowledge graph.

What the console actually asks: what is next to this node, how are these two
things connected, and give me a subgraph small enough to draw. Traversals are
depth- and size-bounded so a dense area of the graph cannot return a payload
that freezes the browser.

Paths are returned with the edges that make them, so the UI can explain a
connection rather than merely assert one.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Sequence

from backend.memory.graph.entities import Entity
from backend.memory.graph.graph_builder import MemoryGraph
from backend.memory.graph.relationships import Relationship

MAX_DEPTH = 4
MAX_NODES = 120


class GraphQuery:
    """Bounded traversals over a :class:`MemoryGraph`."""

    def __init__(self, graph: MemoryGraph) -> None:
        self._graph = graph

    @property
    def graph(self) -> MemoryGraph:
        return self._graph

    # -- lookups -----------------------------------------------------------
    def node(self, node_id: str) -> Entity | None:
        return self._graph.nodes.get(node_id)

    def by_type(self, entity_type: str) -> list[dict[str, Any]]:
        return [node.to_dict() for node in self._graph.by_type(entity_type)]

    def search(self, term: str, *, limit: int = 20) -> list[dict[str, Any]]:
        needle = (term or "").strip().lower()
        if not needle:
            return []
        out = [
            node.to_dict()
            for node in self._graph.nodes.values()
            if needle in node.label.lower() or needle in node.id.lower()
        ]
        return out[: max(1, limit)]

    # -- traversal ---------------------------------------------------------
    def neighbours(
        self,
        node_id: str,
        *,
        depth: int = 1,
        relations: Sequence[str] | None = None,
        evidenced_only: bool = False,
        limit: int = MAX_NODES,
    ) -> dict[str, Any]:
        """Breadth-first neighbourhood, returned as nodes plus edges."""
        if node_id not in self._graph.nodes:
            return {"root": node_id, "found": False, "nodes": [], "edges": []}
        wanted = {r.lower() for r in relations} if relations else None
        seen = {node_id}
        collected_edges: list[Relationship] = []
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])
        while queue:
            current, level = queue.popleft()
            if level >= min(depth, MAX_DEPTH):
                continue
            for edge in self._graph.incident(current):
                if wanted is not None and edge.type.lower() not in wanted:
                    continue
                if evidenced_only and not edge.evidenced:
                    continue
                other = edge.target if edge.source == current else edge.source
                if edge not in collected_edges:
                    collected_edges.append(edge)
                if other not in seen and len(seen) < limit:
                    seen.add(other)
                    queue.append((other, level + 1))
        return {
            "root": node_id,
            "found": True,
            "depth": min(depth, MAX_DEPTH),
            "nodes": [
                self._graph.nodes[identifier].to_dict()
                for identifier in seen
                if identifier in self._graph.nodes
            ],
            "edges": [edge.to_dict() for edge in collected_edges],
            "truncated": len(seen) >= limit,
        }

    def path(self, source: str, target: str, *, max_depth: int = MAX_DEPTH) -> dict[str, Any]:
        """Shortest path, with the edges that justify each hop.

        ``found: false`` means no connection within ``max_depth`` - stated
        plainly rather than returned as an empty path that reads like
        "unrelated".
        """
        if source not in self._graph.nodes or target not in self._graph.nodes:
            return {"found": False, "reason": "unknown node", "nodes": [], "edges": []}
        if source == target:
            return {"found": True, "nodes": [self._graph.nodes[source].to_dict()], "edges": []}

        previous: dict[str, tuple[str, Relationship]] = {}
        queue: deque[tuple[str, int]] = deque([(source, 0)])
        visited = {source}
        while queue:
            current, level = queue.popleft()
            if level >= max_depth:
                continue
            for edge in self._graph.incident(current):
                other = edge.target if edge.source == current else edge.source
                if other in visited:
                    continue
                visited.add(other)
                previous[other] = (current, edge)
                if other == target:
                    return self._reconstruct(source, target, previous)
                queue.append((other, level + 1))
        return {
            "found": False,
            "reason": f"no connection within {max_depth} hops",
            "nodes": [],
            "edges": [],
        }

    def _reconstruct(
        self, source: str, target: str, previous: dict[str, tuple[str, Relationship]]
    ) -> dict[str, Any]:
        chain: list[str] = [target]
        edges: list[Relationship] = []
        cursor = target
        while cursor != source:
            parent, edge = previous[cursor]
            edges.append(edge)
            chain.append(parent)
            cursor = parent
        chain.reverse()
        edges.reverse()
        return {
            "found": True,
            "hops": len(edges),
            "nodes": [self._graph.nodes[identifier].to_dict() for identifier in chain],
            "edges": [edge.to_dict() for edge in edges],
        }

    def subgraph(self, node_ids: Sequence[str]) -> dict[str, Any]:
        """Induced subgraph over the given nodes."""
        wanted = {identifier for identifier in node_ids if identifier in self._graph.nodes}
        edges = [
            edge
            for edge in self._graph.edges
            if edge.source in wanted and edge.target in wanted
        ]
        return {
            "nodes": [self._graph.nodes[identifier].to_dict() for identifier in wanted],
            "edges": [edge.to_dict() for edge in edges],
        }


__all__ = ["GraphQuery", "MAX_DEPTH", "MAX_NODES"]
