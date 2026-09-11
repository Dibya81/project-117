"""Embedding access for semantic memory.

Thin, honest wrapper over the model router. Two rules:

* **Never fabricate a vector.** If no embedding model is configured or the
  local backend is down, this raises :class:`EmbeddingsUnavailable` so the
  caller falls back to lexical recall *and says so*. A hash-based pseudo
  vector would silently produce confident nonsense rankings.
* **Never reach outside the boundary.** Embeddings resolve through the same
  router and provider as every other model call, which is where the egress
  guard lives.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

from backend.models.router.model_router import ModelUnavailableError

#: Router role that serves embeddings (see ``ModelRouter.known_roles``).
EMBEDDING_ROLE = "embedding"


class EmbeddingsUnavailable(RuntimeError):
    """No usable embedding model. Callers should degrade, not invent."""

    reason = "embeddings_unavailable"


async def embed_texts(
    router: Any, texts: Sequence[str], *, model: str | None = None
) -> list[list[float]]:
    """Embed texts with the configured embedding model.

    Raises :class:`EmbeddingsUnavailable` rather than returning empty or
    zero vectors, because a caller cannot distinguish "no similarity" from
    "no model" once the failure is flattened into data.
    """
    if router is None:
        raise EmbeddingsUnavailable("no model router is configured")
    cleaned = [str(text) for text in (texts or ()) if str(text or "").strip()]
    if not cleaned:
        return []
    try:
        resolved = await router.resolve(EMBEDDING_ROLE, model_override=model)
    except ModelUnavailableError as exc:
        raise EmbeddingsUnavailable(str(exc)) from exc
    except ValueError as exc:  # unknown role - a wiring bug, surfaced plainly
        raise EmbeddingsUnavailable(str(exc)) from exc

    vectors = await resolved.provider.embed(model=resolved.model, texts=cleaned)
    if len(vectors) != len(cleaned):
        raise EmbeddingsUnavailable(
            f"embedding provider returned {len(vectors)} vectors for {len(cleaned)} inputs"
        )
    return [[float(value) for value in vector] for vector in vectors]


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    """Cosine similarity, 0.0 when either vector has no magnitude."""
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if norm_left == 0.0 or norm_right == 0.0:
        return 0.0
    return dot / (norm_left * norm_right)


async def rank_by_similarity(
    router: Any,
    query: str,
    candidates: Sequence[str],
    *,
    limit: int = 5,
    model: str | None = None,
) -> list[tuple[int, float]]:
    """Rank candidate texts against a query.

    Returns ``(index, score)`` pairs so the caller keeps ownership of the
    original records rather than receiving reshaped copies.
    """
    if not candidates:
        return []
    vectors = await embed_texts(router, [query, *candidates], model=model)
    query_vector, candidate_vectors = vectors[0], vectors[1:]
    scored = [
        (index, cosine(query_vector, vector)) for index, vector in enumerate(candidate_vectors)
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[: max(1, limit)]


__all__ = [
    "EMBEDDING_ROLE",
    "EmbeddingsUnavailable",
    "cosine",
    "embed_texts",
    "rank_by_similarity",
]
