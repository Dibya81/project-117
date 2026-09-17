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
from backend.security.clearance import Clearance, entity_clearance, principal_clearance
from backend.security.rbac import Principal

MAX_DEPTH = 4
MAX_NODES = 120


class GraphQuery:
    """Bounded traversals over a :class:`MemoryGraph`.

    Every traversal is clearance-aware when a ``principal`` is supplied. Two
    rules, both enforced in one place (:meth:`_visible`):

    * a node above the caller's clearance is never returned, and
    * an edge with a hidden endpoint is dropped, because an edge names both of
      its endpoints — keeping it would disclose the existence and identity of a
      node the caller may not read.

    With ``principal=None`` the query is unscoped (the caller is a maintenance
    script or a test asserting graph shape). Every API surface passes a real
    principal; nothing in the request path relies on the default.
    """

    def __init__(self, graph: MemoryGraph, *, principal: Principal | None = None) -> None:
        self._graph = graph
        self._principal = principal
        self._held: Clearance = principal_clearance(principal)

    @property
    def graph(self) -> MemoryGraph:
        return self._graph

    @property
    def principal(self) -> Principal | None:
        return self._principal

    # -- clearance ---------------------------------------------------------
    def _clearance_of(self, node: Entity) -> Clearance:
        return entity_clearance(node.attributes)

    def _visible(self, node_id: str) -> bool:
        node = self._graph.nodes.get(node_id)
        if node is None:
            return False
        return self._held >= self._clearance_of(node)

    def _visible_edge(self, edge: Relationship) -> bool:
        return self._visible(edge.source) and self._visible(edge.target)

    def _visible_nodes(self, identifiers: Sequence[str]) -> list[Entity]:
        return [self._graph.nodes[i] for i in identifiers if self._visible(i)]

    # -- lookups -----------------------------------------------------------
    def node(self, node_id: str) -> Entity | None:
        """One node, or None — including when it exists but is above the
        caller's clearance, which is the same answer as "no such node"."""
        return self._graph.nodes.get(node_id) if self._visible(node_id) else None

    def by_type(self, entity_type: str) -> list[dict[str, Any]]:
        return [node.to_dict() for node in self._graph.by_type(entity_type) if self._visible(node.id)]

    def search(self, term: str, *, limit: int = 20) -> list[dict[str, Any]]:
        needle = (term or "").strip().lower()
        if not needle:
            return []
        out = [
            node.to_dict()
            for node in self._graph.nodes.values()
            if self._visible(node.id)
            and (needle in node.label.lower() or needle in node.id.lower())
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
        """Breadth-first neighbourhood, returned as nodes plus edges.

        A root the caller may not read answers ``found: False`` rather than
        ``found: True`` with an empty neighbourhood, so the response does not
        distinguish "hidden" from "absent".
        """
        if node_id not in self._graph.nodes or not self._visible(node_id):
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
                if not self._visible_edge(edge):
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
            "nodes": [node.to_dict() for node in self._visible_nodes(list(seen))],
            "edges": [edge.to_dict() for edge in collected_edges],
            "truncated": len(seen) >= limit,
        }

    def path(self, source: str, target: str, *, max_depth: int = MAX_DEPTH) -> dict[str, Any]:
        """Shortest path, with the edges that justify each hop.

        ``found: false`` means no connection within ``max_depth`` — stated
        plainly rather than returned as an empty path that reads like
        "unrelated". Edges with a hidden endpoint are not traversable, so a
        restricted document cannot be used as a bridge to a permitted one and
        cannot be disclosed by being named in a path.
        """
        if source not in self._graph.nodes or target not in self._graph.nodes:
            return {"found": False, "reason": "unknown node", "nodes": [], "edges": []}
        if not self._visible(source) or not self._visible(target):
            # Same shape as "unknown node": the caller learns nothing about
            # whether the node exists.
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
                if not self._visible_edge(edge):
                    continue
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
        """Induced subgraph over the given nodes, minus anything hidden.

        The requested set is intersected with what the caller may see *before*
        edges are selected, so a hidden node cannot be inferred from an edge
        that appears because someone asked for it by id.
        """
        wanted = {identifier for identifier in node_ids if self._visible(identifier)}
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
