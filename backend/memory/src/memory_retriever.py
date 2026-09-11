"""Read side of organisational memory.

:class:`MemoryService` already does a bounded, scope-aware recall. This adds
the part the orchestrator needs on every turn: deterministic re-ranking, a
kind filter, and a compact rendering that can be pasted into a prompt without
crowding out retrieved evidence.

Memory is context, not evidence. Nothing here is allowed to present a
remembered note as a citation - only :mod:`backend.rag` output carries
document-backed citations.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from backend.memory.src import relevance
from backend.memory.src.memory_types import (
    KIND_EPISODIC,
    KIND_PROCEDURAL,
    KIND_SEMANTIC,
    SCOPE_GLOBAL,
)

#: Hard ceiling on characters injected into a prompt from memory.
MAX_CONTEXT_CHARS = 1200


class MemoryRetriever:
    """Recall helper over a :class:`MemoryService`."""

    def __init__(self, service: Any) -> None:
        self._service = service

    @property
    def available(self) -> bool:
        return self._service is not None

    # -- recall --------------------------------------------------------
    def recall(
        self,
        query: str,
        *,
        user: str | None = None,
        session_id: str | None = None,
        limit: int = 5,
        kinds: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Scope-aware recall, re-ranked and optionally filtered by kind.

        Over-fetches before ranking so a kind filter does not starve the
        result set, then trims back to ``limit``.
        """
        if not self.available or not (query or "").strip():
            return []
        fetch = max(limit * 3, 10)
        try:
            records = self._service.recall(
                query, user=user, session_id=session_id, limit=fetch
            )
        except Exception:
            return []
        if kinds:
            wanted = {k.lower() for k in kinds}
            records = [r for r in records if str(r.get("kind", "")).lower() in wanted]
        return relevance.rank(records, query, limit=limit)

    def facts(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Semantic memory only - the kind that must carry evidence."""
        return self.recall(query, kinds=(KIND_SEMANTIC,), **kwargs)

    def procedures(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        return self.recall(query, kinds=(KIND_PROCEDURAL,), **kwargs)

    def episodes(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        return self.recall(query, kinds=(KIND_EPISODIC,), **kwargs)

    # -- direct lookups -------------------------------------------------
    def by_key(
        self,
        key: str,
        *,
        kind: str | None = None,
        scope: str = SCOPE_GLOBAL,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Exact-key lookup. The service lists by kind/scope, so the key match
        is applied here over a bounded page rather than by scanning."""
        if not self.available or not key:
            return []
        try:
            rows = self._service.list(kind=kind, scope=scope, limit=200)
        except Exception:
            return []
        needle = key.strip().lower()
        return [r for r in rows if str(r.get("key", "")).lower() == needle][:limit]

    # -- prompt rendering ------------------------------------------------
    def context_lines(
        self, records: Iterable[dict[str, Any]], *, max_chars: int = MAX_CONTEXT_CHARS
    ) -> str:
        """Render for a prompt, labelled as memory and hard-capped.

        Each line is prefixed with the kind so the model can weigh a durable
        fact differently from a note about one past conversation.
        """
        lines: list[str] = []
        used = 0
        for record in records or ():
            kind = str(record.get("kind", "note"))
            key = str(record.get("key", "")).strip()
            content = " ".join(str(record.get("content", "")).split())
            if not content:
                continue
            line = f"- [{kind}] {key}: {content}" if key else f"- [{kind}] {content}"
            if used + len(line) > max_chars:
                break
            lines.append(line)
            used += len(line) + 1
        return "\n".join(lines)

    def for_context(
        self,
        query: str,
        *,
        user: str | None = None,
        session_id: str | None = None,
        limit: int = 5,
    ) -> str:
        return self.context_lines(
            self.recall(query, user=user, session_id=session_id, limit=limit)
        )


__all__ = ["MAX_CONTEXT_CHARS", "MemoryRetriever"]
