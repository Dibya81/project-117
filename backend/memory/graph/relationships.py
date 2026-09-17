"""Edges in the knowledge graph.

Relation types are closed and typed at both ends. That constraint is the
point: it stops a document being "monitored by" a work order, which is how a
graph stops meaning anything after a few hundred automatic insertions.

Every edge carries the evidence that justified it. An edge with no evidence
is still allowed - operators assert things - but it is marked, and query
results can be restricted to evidenced edges only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.memory.graph.entities import split_id

#: relation -> (allowed source types, allowed target types)
RELATION_TYPES: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "monitored_by": (frozenset({"equipment"}), frozenset({"signal"})),
    "documented_in": (
        frozenset({"equipment", "work_order", "procedure"}),
        frozenset({"document"}),
    ),
    "governed_by": (frozenset({"equipment", "work_order"}), frozenset({"procedure"})),
    "raised_for": (frozenset({"work_order"}), frozenset({"equipment"})),
    "performed_by": (frozenset({"work_order"}), frozenset({"person"})),
    "derived_from": (frozenset({"artifact"}), frozenset({"document", "job"})),
    "produced_by": (frozenset({"artifact"}), frozenset({"job"})),
    "analysed_in": (frozenset({"equipment", "signal"}), frozenset({"job"})),
    "installed_at": (frozenset({"equipment"}), frozenset({"site"})),
    "related_to": (frozenset({"equipment"}), frozenset({"equipment"})),
    # Spares and inspections. Both were added with the operational graph tool:
    # a spare's requirement and an asset's recorded inspection are facts the
    # system already stores, and the closed schema above had no way to say so.
    "requires_spare": (frozenset({"equipment"}), frozenset({"material"})),
    "has_inspection": (frozenset({"equipment"}), frozenset({"inspection"})),
}

#: Reading an edge backwards, for neighbourhood queries.
INVERSE_LABELS: dict[str, str] = {
    "monitored_by": "monitors",
    "documented_in": "documents",
    "governed_by": "governs",
    "raised_for": "has work order",
    "performed_by": "performed",
    "derived_from": "source of",
    "produced_by": "produced",
    "analysed_in": "analysed",
    "installed_at": "hosts",
    "related_to": "related to",
    "requires_spare": "spare for",
    "has_inspection": "inspection of",
}


class InvalidRelationship(ValueError):
    """The relation type is unknown, or the endpoints are the wrong types."""


@dataclass(frozen=True)
class Relationship:
    """A typed, directed, evidenced edge."""

    source: str
    target: str
    type: str
    confidence: float = 0.8
    evidence: list[dict[str, Any]] = field(default_factory=list)

    @property
    def evidenced(self) -> bool:
        return bool(self.evidence)

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.source, self.type, self.target)

    def inverse_label(self) -> str:
        return INVERSE_LABELS.get(self.type, self.type)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "type": self.type,
            "confidence": self.confidence,
            "evidenced": self.evidenced,
            "evidence": list(self.evidence),
        }


def validate(relationship: Relationship) -> None:
    """Raise :class:`InvalidRelationship` if the edge is not well typed."""
    rule = RELATION_TYPES.get(relationship.type)
    if rule is None:
        raise InvalidRelationship(
            f"unknown relation '{relationship.type}'; expected one of {sorted(RELATION_TYPES)}"
        )
    source_types, target_types = rule
    source_kind, source_ident = split_id(relationship.source)
    target_kind, target_ident = split_id(relationship.target)
    if not source_ident or not target_ident:
        raise InvalidRelationship("edge endpoints must be '<type>:<id>' node ids")
    if source_kind not in source_types:
        raise InvalidRelationship(
            f"'{relationship.type}' cannot start at a '{source_kind}' node "
            f"(allowed: {sorted(source_types)})"
        )
    if target_kind not in target_types:
        raise InvalidRelationship(
            f"'{relationship.type}' cannot end at a '{target_kind}' node "
            f"(allowed: {sorted(target_types)})"
        )
    if relationship.source == relationship.target:
        raise InvalidRelationship("an edge must connect two different nodes")


def connect(
    source: str,
    relation: str,
    target: str,
    *,
    confidence: float = 0.8,
    evidence: list[dict[str, Any]] | None = None,
) -> Relationship:
    """Build and validate an edge in one step."""
    edge = Relationship(
        source=source,
        target=target,
        type=relation,
        confidence=confidence,
        evidence=list(evidence or []),
    )
    validate(edge)
    return edge


__all__ = [
    "INVERSE_LABELS",
    "InvalidRelationship",
    "RELATION_TYPES",
    "Relationship",
    "connect",
    "validate",
]
