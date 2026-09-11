"""Typed retrieval errors.

Messages are safe to expose through the API (they never contain document
content — only ids, model names and table names).
"""

from __future__ import annotations


class RetrievalError(RuntimeError):
    """Retrieval could not be performed; message is safe to expose via API."""

    reason = "retrieval_failed"


class IndexUnavailableError(RetrievalError):
    """The LanceDB index/table does not exist or cannot be opened."""

    reason = "index_unavailable"


class RerankerUnavailableError(RetrievalError):
    """The configured reranker model is not served by the local backend."""

    reason = "reranker_unavailable"
