"""Assemble the knowledge graph from things the system already knows.

The graph is derived, never authored by a model. Nodes and edges come from
records that exist - equipment rows, documents, work orders, memory entries -
so every connection shown in the console can be traced back to something a
person can open. If a source is missing, the edge is simply absent; an
inferred edge would look identical to a real one on screen.

The container is an in-memory adjacency structure. It is rebuilt on demand
rather than persisted, because a stale graph is worse than a slow one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from backend.memory.graph import entities as ent
from backend.memory.graph.entities import Entity
from backend.memory.graph.relationships import (
    InvalidRelationship,
    Relationship,
    connect,
)


@dataclass
class MemoryGraph:
    """Nodes plus typed edges, with adjacency maintained on insert."""

    nodes: dict[str, Entity] = field(default_factory=dict)
    edges: list[Relationship] = field(default_factory=list)
    _adjacency: dict[str, set[int]] = field(default_factory=dict, repr=False)

    # -- mutation ---------------------------------------------------------
    def add_entity(self, entity: Entity) -> Entity:
        """Insert or merge a node. Attributes merge; the first label wins so
        a later, sparser record cannot blank out a good display name."""
        existing = self.nodes.get(entity.id)
        if existing is None:
            self.nodes[entity.id] = entity
            self._adjacency.setdefault(entity.id, set())
            return entity
        merged = Entity(
            id=existing.id,
            type=existing.type,
            label=existing.label or entity.label,
            attributes={**entity.attributes, **existing.attributes},
        )
        self.nodes[existing.id] = merged
        return merged

    def add_edge(self, edge: Relationship) -> bool:
        """Add an edge if both endpoints exist and it is not a duplicate.

        Returns False instead of raising when an endpoint is unknown: graph
        assembly runs over partial data and must not fail a whole build
        because one document was not ingested.
        """
        if edge.source not in self.nodes or edge.target not in self.nodes:
            return False
        if any(existing.key == edge.key for existing in self.edges):
            return False
        index = len(self.edges)
        self.edges.append(edge)
        self._adjacency.setdefault(edge.source, set()).add(index)
        self._adjacency.setdefault(edge.target, set()).add(index)
        return True

    def link(self, source: str, relation: str, target: str, **kwargs: Any) -> bool:
        try:
            return self.add_edge(connect(source, relation, target, **kwargs))
        except InvalidRelationship:
            return False

    # -- access -----------------------------------------------------------
    def edge_indexes(self, node_id: str) -> set[int]:
        return self._adjacency.get(node_id, set())

    def incident(self, node_id: str) -> list[Relationship]:
        return [self.edges[index] for index in sorted(self.edge_indexes(node_id))]

    def by_type(self, entity_type: str) -> list[Entity]:
        return [node for node in self.nodes.values() if node.type == entity_type]

    def stats(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for node in self.nodes.values():
            counts[node.type] = counts.get(node.type, 0) + 1
        evidenced = sum(1 for edge in self.edges if edge.evidenced)
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "nodesByType": counts,
            "evidencedEdges": evidenced,
            "unevidencedEdges": len(self.edges) - evidenced,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
            "stats": self.stats(),
        }


class GraphBuilder:
    """Builds a :class:`MemoryGraph` from operational records."""

    def __init__(self) -> None:
        self.graph = MemoryGraph()

    def build(self) -> MemoryGraph:
        return self.graph

    # -- sources ----------------------------------------------------------
    def add_equipment(self, rows: Iterable[dict[str, Any]]) -> "GraphBuilder":
        for row in rows or ():
            tag = row.get("tag") or row.get("id")
            if not tag:
                continue
            self.graph.add_entity(
                ent.equipment(
                    str(tag),
                    name=row.get("name"),
                    status=row.get("status"),
                    criticality=row.get("criticality"),
                    unit=row.get("unit"),
                )
            )
            unit = row.get("unit")
            if unit:
                self.graph.add_entity(ent.make("site", str(unit), label=str(unit)))
                self.graph.link(
                    ent.node_id("equipment", str(tag)),
                    "installed_at",
                    ent.node_id("site", str(unit)),
                )
        return self

    def add_documents(self, rows: Iterable[dict[str, Any]]) -> "GraphBuilder":
        for row in rows or ():
            doc_id = row.get("id") or row.get("documentId")
            if not doc_id:
                continue
            self.graph.add_entity(
                ent.document(
                    str(doc_id),
                    name=row.get("title") or row.get("name"),
                    kind=row.get("type"),
                )
            )
            for tag in row.get("equipment") or ():
                source = ent.node_id("equipment", str(tag))
                if source in self.graph.nodes:
                    self.graph.link(
                        source,
                        "documented_in",
                        ent.node_id("document", str(doc_id)),
                        evidence=[{"document_id": str(doc_id)}],
                    )
        return self

    def add_work_orders(self, rows: Iterable[dict[str, Any]]) -> "GraphBuilder":
        for row in rows or ():
            number = row.get("id") or row.get("number")
            tag = row.get("equipment") or row.get("equipmentId")
            if not number:
                continue
            self.graph.add_entity(
                ent.work_order(
                    str(number), status=row.get("status"), priority=row.get("priority")
                )
            )
            if tag:
                target = ent.node_id("equipment", str(tag))
                if target in self.graph.nodes:
                    self.graph.link(
                        ent.node_id("work_order", str(number)), "raised_for", target
                    )
        return self

    def add_telemetry(self, series: Iterable[dict[str, Any]]) -> "GraphBuilder":
        for row in series or ():
            tag = row.get("equipment") or row.get("equipmentId")
            name = row.get("signal") or row.get("name")
            if not tag or not name:
                continue
            node = self.graph.add_entity(
                ent.signal(str(name), equipment_tag=str(tag), unit=row.get("unit"))
            )
            source = ent.node_id("equipment", str(tag))
            if source in self.graph.nodes:
                self.graph.link(source, "monitored_by", node.id)
        return self

    def add_memory_records(self, records: Sequence[dict[str, Any]]) -> "GraphBuilder":
        """Attach memory-derived nodes, keeping their evidence on the edge."""
        for record in records or ():
            subject = ent.from_memory_record(record)
            if subject is None:
                continue
            self.graph.add_entity(subject)
            for item in record.get("evidence") or ():
                if not isinstance(item, dict):
                    continue
                doc_id = item.get("document_id") or item.get("documentId")
                if not doc_id:
                    continue
                document = self.graph.add_entity(ent.document(str(doc_id)))
                self.graph.link(
                    subject.id,
                    "documented_in",
                    document.id,
                    confidence=float(record.get("confidence") or 0.5),
                    evidence=[item],
                )
        return self


__all__ = ["GraphBuilder", "MemoryGraph"]
