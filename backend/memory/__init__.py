"""Organisational memory (Phase 13).

See ``backend.database.memory.MemoryRecord`` for the storage shape and the
four kinds of memory. This module is the only writer of that table: a model
never writes memory directly, it proposes a candidate and
:meth:`MemoryService.remember` decides whether it is admissible.
"""

from __future__ import annotations

from backend.memory.src.memory_manager import (
    MemoryError,
    MemoryRejected,
    MemoryService,
)

__all__ = ["MemoryError", "MemoryRejected", "MemoryService"]
