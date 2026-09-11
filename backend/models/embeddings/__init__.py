"""Retrieval-side model roles: ``embedding`` and ``reranker``.

Both live here because the folder tree has no separate ``reranker`` package
and because they are the same concern — turning a query into an ordering over
documents. Declaring the reranker in a package called ``embeddings`` is a
small naming compromise, recorded here rather than hidden.

Neither role is required. When they are absent, retrieval degrades to lexical
scoring and reports ``rerank: "lexical"`` in its output; it never fabricates
vectors or invents a similarity score.
"""

from backend.models.gateway.model_registry import RoleDescriptor

EMBEDDING = RoleDescriptor(
    role="embedding",
    purpose=(
        "Turning document chunks and queries into vectors for semantic "
        "retrieval over the plant document corpus."
    ),
    setting="P117_EMBEDDING_MODEL",
    modalities=("text",),
    capabilities=("embed_documents", "embed_queries"),
    suggested_models=(
        "nomic-embed-text",
        "bge-m3",
        "mxbai-embed-large",
    ),
    required_for_demo=False,
    notes=(
        "Changing this model invalidates every stored vector: the index must be "
        "rebuilt, because comparing vectors from two different models is "
        "meaningless. Without it, retrieval degrades to lexical search and says so."
    ),
)

RERANKER = RoleDescriptor(
    role="reranker",
    purpose=(
        "Re-scoring a shortlist of retrieved chunks against the query so the "
        "evidence shown to the user is the most relevant, not merely the "
        "nearest in vector space."
    ),
    setting="P117_RERANKER_MODEL",
    modalities=("text",),
    capabilities=("cross_encode", "rerank"),
    suggested_models=(
        "bge-reranker-v2-m3",
        "jina-reranker-v2-base",
    ),
    required_for_demo=False,
    notes=(
        "Purely an ordering improvement. Its absence lowers answer quality but "
        "never blocks a job, and retrieval labels the method actually used."
    ),
)

DESCRIPTORS = (EMBEDDING, RERANKER)

__all__ = ["DESCRIPTORS", "EMBEDDING", "RERANKER"]
