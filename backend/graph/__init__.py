"""Graph memory errors.

The package previously shipped a single mis-named ``__init__data.py``, which
meant ``backend.graph`` was not importable at all. Errors now live in
``errors.py`` and are re-exported here.
"""

from backend.graph.errors import (
    GraphError,
    GraphNotIndexedError,
    GraphUnavailableError,
)

__all__ = ["GraphError", "GraphNotIndexedError", "GraphUnavailableError"]
