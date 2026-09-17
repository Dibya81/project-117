"""Entities in the knowledge graph.

The graph exists so an answer can show *how* two things are connected -
C-3 to the bearing signal, the signal to the inspection report, the report to
the SOP. That only works if an entity has one identity everywhere, so ids are
normalised here and nowhere else.

An id is ``"<type>:<identifier>"``. Types are closed: an open type field
produces "equipment", "Equipment" and "asset" nodes for the same compressor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "equipment",
        "signal",
        "document",
        "procedure",
        "work_order",
        "artifact",
        "job",
        "person",
        "site",
        # Added with the operational graph tool: a spare part and a recorded
        # inspection are real records the system holds, and the closed set had
        # no type for either.
        "material",
        "inspection",
    }
)

_ID_CLEAN = re.compile(r"[^A-Za-z0-9._\-]+")


class UnknownEntityType(ValueError):
    """A type outside :data:`ENTITY_TYPES` was used."""


def normalise(identifier: str) -> str:
    """Trim and strip separators so ``"C-3 "`` and ``"c-3"`` are one node."""
    cleaned = _ID_CLEAN.sub("-", str(identifier or "").strip())
    return cleaned.strip("-").lower()


def node_id(entity_type: str, identifier: str) -> str:
    kind = (entity_type or "").strip().lower()
    if kind not in ENTITY_TYPES:
        raise UnknownEntityType(
            f"unknown entity type '{entity_type}'; expected one of {sorted(ENTITY_TYPES)}"
        )
    ident = normalise(identifier)
    if not ident:
        raise ValueError("entity identifier must not be empty")
    return f"{kind}:{ident}"


def split_id(value: str) -> tuple[str, str]:
    kind, _, ident = str(value or "").partition(":")
    return kind, ident


@dataclass(frozen=True)
class Entity:
    """A node. ``label`` is what a human reads; ``id`` is what edges use."""

    id: str
    type: str
    label: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "attributes": dict(self.attributes),
        }


def make(entity_type: str, identifier: str, *, label: str | None = None, **attributes: Any) -> Entity:
    return Entity(
        id=node_id(entity_type, identifier),
        type=entity_type.strip().lower(),
        label=(label or str(identifier)).strip(),
        attributes={k: v for k, v in attributes.items() if v is not None},
    )


def equipment(tag: str, **attributes: Any) -> Entity:
    return make("equipment", tag, label=tag, **attributes)


def document(document_id: str, *, name: str | None = None, **attributes: Any) -> Entity:
    return make("document", document_id, label=name or document_id, **attributes)


def work_order(number: str, **attributes: Any) -> Entity:
    return make("work_order", number, label=number, **attributes)


def signal(name: str, *, equipment_tag: str | None = None, **attributes: Any) -> Entity:
    ident = f"{equipment_tag}-{name}" if equipment_tag else name
    return make("signal", ident, label=name, equipment=equipment_tag, **attributes)


def from_memory_record(record: dict[str, Any]) -> Entity | None:
    """Derive the subject entity of a memory record, if it names one.

    Returns None rather than guessing: a record with no recorded subject does
    not get a node invented for it.
    """
    metadata = record.get("metadata") or {}
    subject = None
    if isinstance(metadata, dict):
        subject = metadata.get("subject") or metadata.get("equipment")
    subject = subject or record.get("key")
    if not subject:
        return None
    text = str(subject).split(":")[0].strip()
    if not text:
        return None
    return equipment(text, source="memory")


__all__ = [
    "ENTITY_TYPES",
    "Entity",
    "UnknownEntityType",
    "document",
    "equipment",
    "from_memory_record",
    "make",
    "node_id",
    "normalise",
    "signal",
    "split_id",
    "work_order",
]
