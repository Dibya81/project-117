"""Write side of organisational memory.

Every write goes through :meth:`MemoryService.remember`, which decides what is
admissible. This module supplies the intent-shaped entry points - record a
fact, record what happened, record how something is done - so callers do not
assemble raw kwargs and accidentally file an unsourced claim as a durable
fact.

:meth:`propose` exists for model-suggested memory. It never raises on
rejection; it returns the reason, because "the model wanted to remember
something inadmissible" is normal operation, not an error.
"""

from __future__ import annotations

from typing import Any, Sequence

from backend.memory.src.memory_manager import MemoryRejected
from backend.memory.src.memory_types import (
    KIND_EPISODIC,
    KIND_ORGANISATIONAL,
    KIND_PROCEDURAL,
    KIND_SEMANTIC,
    SCOPE_GLOBAL,
    SOURCE_MODEL_PROPOSED,
    SOURCE_SYSTEM,
    MemoryCandidate,
    check,
)


class MemoryWriter:
    """Intent-shaped writes over a :class:`MemoryService`."""

    def __init__(self, service: Any) -> None:
        self._service = service

    @property
    def available(self) -> bool:
        return self._service is not None

    # -- internals -------------------------------------------------------
    def _write(self, candidate: MemoryCandidate) -> dict[str, Any]:
        if not self.available:
            raise MemoryRejected("memory service is not configured")
        admissible, reason = check(candidate)
        if not admissible:
            raise MemoryRejected(reason)
        return self._service.remember(**candidate.as_kwargs())

    # -- intents ---------------------------------------------------------
    def record_fact(
        self,
        key: str,
        content: str,
        *,
        evidence: Sequence[dict[str, Any]],
        scope: str = SCOPE_GLOBAL,
        confidence: float = 0.6,
        job_id: str | None = None,
        user: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """A durable claim about the plant. Evidence is mandatory."""
        return self._write(
            MemoryCandidate(
                kind=KIND_SEMANTIC,
                key=key,
                content=content,
                scope=scope,
                evidence=list(evidence or []),
                confidence=confidence,
                metadata=dict(metadata or {}),
                job_id=job_id,
                user=user,
            )
        )

    def record_event(
        self,
        key: str,
        content: str,
        *,
        scope: str = SCOPE_GLOBAL,
        job_id: str | None = None,
        user: str | None = None,
        metadata: dict[str, Any] | None = None,
        confidence: float = 0.9,
    ) -> dict[str, Any]:
        """Something that happened. High confidence because it is observed,
        not inferred."""
        return self._write(
            MemoryCandidate(
                kind=KIND_EPISODIC,
                key=key,
                content=content,
                scope=scope,
                confidence=confidence,
                metadata=dict(metadata or {}),
                job_id=job_id,
                user=user,
            )
        )

    def record_procedure(
        self,
        key: str,
        content: str,
        *,
        evidence: Sequence[dict[str, Any]] = (),
        scope: str = SCOPE_GLOBAL,
        confidence: float = 0.7,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """How something is done here - an SOP step order, a checklist."""
        return self._write(
            MemoryCandidate(
                kind=KIND_PROCEDURAL,
                key=key,
                content=content,
                scope=scope,
                evidence=list(evidence or []),
                confidence=confidence,
                metadata=dict(metadata or {}),
            )
        )

    def record_preference(
        self,
        key: str,
        content: str,
        *,
        user: str | None = None,
        scope: str = SCOPE_GLOBAL,
        confidence: float = 0.5,
    ) -> dict[str, Any]:
        """A team convention or reporting preference."""
        return self._write(
            MemoryCandidate(
                kind=KIND_ORGANISATIONAL,
                key=key,
                content=content,
                scope=scope,
                confidence=confidence,
                user=user,
            )
        )

    # -- model-proposed --------------------------------------------------
    def propose(
        self, candidate: MemoryCandidate
    ) -> tuple[dict[str, Any] | None, str]:
        """Admit a model-proposed record, or explain why not.

        Returns ``(record, "")`` on success and ``(None, reason)`` on refusal.
        The source is forced to ``model_proposed`` so a trace can always tell
        who wanted this remembered.
        """
        forced = MemoryCandidate(
            kind=candidate.kind,
            key=candidate.key,
            content=candidate.content,
            scope=candidate.scope,
            evidence=list(candidate.evidence),
            confidence=min(float(candidate.confidence), 0.6),
            metadata=dict(candidate.metadata),
            ttl_hours=candidate.ttl_hours,
            source=SOURCE_MODEL_PROPOSED,
            job_id=candidate.job_id,
            user=candidate.user,
        )
        try:
            return self._write(forced), ""
        except MemoryRejected as exc:
            return None, str(exc)
        except Exception as exc:  # pragma: no cover - storage failure
            return None, f"memory write failed: {exc}"

    # -- removal ----------------------------------------------------------
    def forget(self, memory_id: str, *, user: str | None = None) -> bool:
        if not self.available:
            return False
        try:
            self._service.forget(memory_id, user=user)
            return True
        except Exception:
            return False

    def expire_stale(self) -> int:
        if not self.available:
            return 0
        try:
            return int(self._service.expire_stale())
        except Exception:
            return 0


__all__ = ["MemoryWriter", "SOURCE_SYSTEM"]
