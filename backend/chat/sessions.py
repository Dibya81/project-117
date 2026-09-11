"""In-memory chat session store.

Bounded (session count + turns per session) and thread-safe. Sessions are
ephemeral across restarts until Phase 17 persists them to the database.
"""

from __future__ import annotations

import threading
from collections import deque

from backend.models.providers.base import ChatMessage

_MAX_SESSIONS = 200
_MAX_TURNS = 40


class ChatSessionStore:
    def __init__(self, max_sessions: int = _MAX_SESSIONS, max_turns: int = _MAX_TURNS) -> None:
        self._max_sessions = max_sessions
        self._max_turns = max_turns
        self._sessions: dict[str, deque[ChatMessage]] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str) -> list[ChatMessage]:
        with self._lock:
            return list(self._sessions.get(session_id, ()))

    def append(self, session_id: str, message: ChatMessage) -> None:
        with self._lock:
            history = self._sessions.setdefault(session_id, deque(maxlen=self._max_turns * 2))
            history.append(message)
            self._evict_locked()

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def list(self) -> list[str]:
        with self._lock:
            return list(self._sessions)

    def _evict_locked(self) -> None:
        # deque already bounds turns; bound session count (oldest first).
        while len(self._sessions) > self._max_sessions:
            oldest = next(iter(self._sessions))
            del self._sessions[oldest]