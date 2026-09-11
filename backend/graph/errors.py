"""Typed graph-memory errors.

Messages are safe to expose through the API (they never contain document
content — only ids, model names and storage paths).
"""

from __future__ import annotations


class GraphError(RuntimeError):
    """A graph-memory operation failed; message is safe to expose via API."""

    reason = "graph_failed"


class GraphUnavailableError(GraphError):
    """The graph engine is not configured or its dependencies are absent."""

    reason = "graph_unavailable"


class GraphNotIndexedError(GraphError):
    """The requested document has no graph extraction yet."""

    reason = "graph_not_indexed"
