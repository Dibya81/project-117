"""Semantic-memory recall.

Semantic records are the only memory kind required to carry evidence, so this
retriever is the one place that may hand memory to an answer as a *sourced*
claim. Everything it returns therefore passes three filters: right kind, has
evidence, not expired.

Recall is lexical by default and deterministic. Embedding rerank is opt-in
via :meth:`rerank`, and when embeddings are unavailable the result is
returned in lexical order with ``rerank: "lexical"`` recorded on it, so a
trace never implies a semantic ranking that did not happen.
"""

from __future__ import annotations

from typing import Any

from backend.memory.semantic import filters
from backend.memory.semantic.embeddings import EmbeddingsUnavailable, rank_by_similarity
from backend.memory.src.memory_retriever import MemoryRetriever
from backend.memory.src.memory_types import KIND_SEMANTIC


class SemanticMemoryRetriever:
    """Evidence-bearing recall over a :class:`MemoryService`."""

    def __init__(self, service: Any, *, router: Any = None) -> None:
        self._retriever = MemoryRetriever(service)
        self._router = router

    @property
    def available(self) -> bool:
        return self._retriever.available

    # -- lexical recall --------------------------------------------------
    def facts(
        self,
        query: str,
        *,
        user: str | None = None,
        session_id: str | None = None,
        limit: int = 5,
        min_confidence: float = 0.0,
    ) -> list[dict[str, Any]]:
        records = self._retriever.recall(
            query, user=user, session_id=session_id, limit=limit * 2, kinds=(KIND_SEMANTIC,)
        )
        predicates = [
            filters.of_kind(KIND_SEMANTIC),
            filters.has_evidence(),
            filters.not_expired(),
        ]
        if min_confidence > 0.0:
            predicates.append(filters.min_confidence(min_confidence))
        kept = filters.apply(records, predicates)
        for record in kept:
            record["rerank"] = "lexical"
        return kept[: max(1, limit)]

    # -- optional embedding rerank ---------------------------------------
    async def rerank(
        self,
        query: str,
        *,
        user: str | None = None,
        session_id: str | None = None,
        limit: int = 5,
    ) -> tuple[list[dict[str, Any]], str]:
        """Recall then optionally rerank by embedding similarity.

        Returns ``(records, mode)`` where mode is ``"embedding"`` or
        ``"lexical"``. The caller shows the mode; a degraded ranking that
        looks identical to a good one is how quality regressions hide.
        """
        candidates = self.facts(query, user=user, session_id=session_id, limit=limit * 3)
        if not candidates or self._router is None:
            return candidates[: max(1, limit)], "lexical"
        texts = [
            f"{record.get('key', '')} {record.get('content', '')}".strip() for record in candidates
        ]
        try:
            ranked = await rank_by_similarity(self._router, query, texts, limit=limit)
        except EmbeddingsUnavailable:
            return candidates[: max(1, limit)], "lexical"
        out: list[dict[str, Any]] = []
        for index, score in ranked:
            record = dict(candidates[index])
            record["similarity"] = round(float(score), 6)
            record["rerank"] = "embedding"
            out.append(record)
        return out, "embedding"

    # -- evidence ---------------------------------------------------------
    @staticmethod
    def evidence_for(record: dict[str, Any]) -> list[dict[str, Any]]:
        """Normalise the stored evidence list into citation shape."""
        out: list[dict[str, Any]] = []
        for item in record.get("evidence") or ():
            if not isinstance(item, dict):
                continue
            out.append(
                {
                    "document_id": item.get("document_id") or item.get("documentId"),
                    "page": item.get("page"),
                    "section": item.get("section"),
                    "chunk_id": item.get("chunk_id") or item.get("chunkId"),
                }
            )
        return out


__all__ = ["SemanticMemoryRetriever"]
