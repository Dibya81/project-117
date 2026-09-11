"""SOP-backed procedural memory.

Stores parsed procedures and hands them back for a tag or a task. The rule
enforced here: a procedure without a source document is never returned as
authoritative. It is still retrievable - operators write useful notes - but
it is flagged so the answer can say where it came from.
"""

from __future__ import annotations

from typing import Any

from backend.memory.procedural.procedures import Procedure
from backend.memory.src.memory_types import KIND_PROCEDURAL
from backend.memory.src.relevance import rank


class SopMemory:
    """Procedural memory over a :class:`MemoryService`."""

    def __init__(self, service: Any) -> None:
        self._service = service

    @property
    def available(self) -> bool:
        return self._service is not None

    def remember(self, procedure: Procedure, *, scope: str = "global") -> dict[str, Any] | None:
        if not self.available:
            return None
        if not procedure.steps:
            # An empty procedure is a parsing failure, not knowledge.
            return None
        try:
            return self._service.remember(**procedure.to_candidate(scope=scope).as_kwargs())
        except Exception:
            return None

    def _rows(self, limit: int = 200) -> list[dict[str, Any]]:
        if not self.available:
            return []
        try:
            return list(self._service.list(kind=KIND_PROCEDURAL, limit=limit))
        except Exception:
            return []

    def lookup(self, name: str) -> dict[str, Any] | None:
        needle = (name or "").strip().lower()
        if not needle:
            return None
        for row in self._rows():
            if str(row.get("key", "")).lower() == needle:
                return self._annotate(row)
        return None

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        return [self._annotate(row) for row in rank(self._rows(), query, limit=limit)]

    def for_equipment(self, tag: str, *, limit: int = 10) -> list[dict[str, Any]]:
        needle = (tag or "").strip().lower()
        if not needle:
            return []
        out: list[dict[str, Any]] = []
        for row in self._rows():
            metadata = row.get("metadata") or {}
            equipment = metadata.get("equipment") if isinstance(metadata, dict) else None
            haystack = " ".join(
                [str(row.get("key", "")), str(row.get("content", "")), str(equipment or "")]
            ).lower()
            if needle in haystack:
                out.append(self._annotate(row))
            if len(out) >= limit:
                break
        return out

    @staticmethod
    def _annotate(row: dict[str, Any]) -> dict[str, Any]:
        """Mark whether the stored procedure carries a document source."""
        enriched = dict(row)
        evidence = row.get("evidence") or []
        enriched["authoritative"] = bool(evidence)
        if not evidence:
            enriched["caveat"] = "no source document recorded; treat as an operator note"
        return enriched


__all__ = ["SopMemory"]
