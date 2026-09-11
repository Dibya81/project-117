"""Shared vocabulary for organisational memory.

Kinds, scopes and the candidate shape live in one place so the service, the
writer, the retriever and the API all mean the same thing by "session-scoped
procedural memory". :class:`~backend.memory.src.memory_manager.MemoryService`
remains the authority on what is admissible; this module gives callers the
same rules early enough to produce a useful error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.memory.src.memory_manager import (
    DEFAULT_SESSION_TTL_HOURS,
    MAX_CONTENT_CHARS,
    MAX_KEY_CHARS,
    MEMORY_KINDS,
    SOURCE_MODEL_PROPOSED,
    SOURCE_SYSTEM,
)

KIND_SEMANTIC = "semantic"
KIND_EPISODIC = "episodic"
KIND_PROCEDURAL = "procedural"
KIND_ORGANISATIONAL = "organisational"

SCOPE_GLOBAL = "global"


def user_scope(user: str) -> str:
    return f"user:{user}"


def session_scope(session_id: str) -> str:
    return f"session:{session_id}"


def document_scope(document_id: str) -> str:
    return f"document:{document_id}"


def parse_scope(scope: str) -> tuple[str, str | None]:
    """Split ``"user:alice"`` into ``("user", "alice")``; global has no id."""
    text = (scope or SCOPE_GLOBAL).strip()
    if text == SCOPE_GLOBAL:
        return SCOPE_GLOBAL, None
    prefix, _, ident = text.partition(":")
    return prefix, ident or None


def default_ttl_hours(scope: str) -> float | None:
    """Session notes expire; anything wider is kept until explicitly forgotten.

    An unbounded pile of one-conversation notes is not memory, it is debris.
    """
    kind, _ = parse_scope(scope)
    return float(DEFAULT_SESSION_TTL_HOURS) if kind == "session" else None


@dataclass(frozen=True)
class MemoryCandidate:
    """A proposed record, before the service decides whether to admit it."""

    kind: str
    key: str
    content: str
    scope: str = SCOPE_GLOBAL
    evidence: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)
    ttl_hours: float | None = None
    source: str = SOURCE_SYSTEM
    job_id: str | None = None
    user: str | None = None

    def as_kwargs(self) -> dict[str, Any]:
        """Keyword arguments for :meth:`MemoryService.remember`."""
        return {
            "kind": self.kind,
            "key": self.key,
            "content": self.content,
            "scope": self.scope,
            "evidence": list(self.evidence),
            "source": self.source,
            "job_id": self.job_id,
            "user": self.user,
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
            "ttl_hours": (
                self.ttl_hours if self.ttl_hours is not None else default_ttl_hours(self.scope)
            ),
        }


def check(candidate: MemoryCandidate) -> tuple[bool, str]:
    """Pre-flight check mirroring the service's admission rules.

    Returns ``(admissible, reason)``. This is a courtesy so a caller can fail
    fast with a clear message; the service re-checks everything, because a
    pre-flight check that is the only check is not a check at all.
    """
    if candidate.kind not in MEMORY_KINDS:
        return False, f"unknown kind '{candidate.kind}'; expected one of {sorted(MEMORY_KINDS)}"
    if not (candidate.key or "").strip():
        return False, "key must not be empty"
    if len(candidate.key) > MAX_KEY_CHARS:
        return False, f"key exceeds {MAX_KEY_CHARS} characters"
    if not (candidate.content or "").strip():
        return False, "content must not be empty"
    if len(candidate.content) > MAX_CONTENT_CHARS:
        return False, f"content exceeds {MAX_CONTENT_CHARS} characters"
    if candidate.kind == KIND_SEMANTIC and not candidate.evidence:
        return False, "semantic memory requires evidence; a durable fact needs a source"
    if not 0.0 <= float(candidate.confidence) <= 1.0:
        return False, "confidence must be between 0.0 and 1.0"
    return True, ""


__all__ = [
    "KIND_EPISODIC",
    "KIND_ORGANISATIONAL",
    "KIND_PROCEDURAL",
    "KIND_SEMANTIC",
    "MEMORY_KINDS",
    "MemoryCandidate",
    "SCOPE_GLOBAL",
    "SOURCE_MODEL_PROPOSED",
    "SOURCE_SYSTEM",
    "check",
    "default_ttl_hours",
    "document_scope",
    "parse_scope",
    "session_scope",
    "user_scope",
]
