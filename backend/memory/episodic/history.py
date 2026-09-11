"""Operational history: the timeline the console renders.

Reads episodic memory back out in the shapes the UI asks for - by equipment,
by job, or most recent first. Ordering is by observed time, not write time:
an event ingested late still belongs where it happened.
"""

from __future__ import annotations

from typing import Any, Sequence

from backend.memory.episodic.events import Event
from backend.memory.src.memory_types import KIND_EPISODIC


def _occurred_at(record: dict[str, Any]) -> str:
    metadata = record.get("metadata") or {}
    if isinstance(metadata, dict) and metadata.get("occurredAt"):
        return str(metadata["occurredAt"])
    return str(record.get("created_at") or record.get("createdAt") or "")


class EpisodeHistory:
    """Timeline view over episodic memory."""

    def __init__(self, service: Any) -> None:
        self._service = service

    @property
    def available(self) -> bool:
        return self._service is not None

    def record(self, event: Event, *, scope: str = "global") -> dict[str, Any] | None:
        """Persist an observation. Returns None when memory is unavailable,
        because losing a timeline entry must not fail the job that produced
        it."""
        if not self.available:
            return None
        try:
            return self._service.remember(**event.to_candidate(scope=scope).as_kwargs())
        except Exception:
            return None

    def _all(self, limit: int = 200) -> list[dict[str, Any]]:
        if not self.available:
            return []
        try:
            return list(self._service.list(kind=KIND_EPISODIC, limit=limit))
        except Exception:
            return []

    def recent(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._all()
        rows.sort(key=_occurred_at, reverse=True)
        return rows[: max(1, limit)]

    def for_subject(self, subject: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Every recorded event for one equipment tag or document id."""
        needle = (subject or "").strip().lower()
        if not needle:
            return []
        rows = [
            row
            for row in self._all()
            if needle in str(row.get("key", "")).lower()
            or needle in str((row.get("metadata") or {}).get("subject", "")).lower()
        ]
        rows.sort(key=_occurred_at, reverse=True)
        return rows[: max(1, limit)]

    def for_job(self, job_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = [row for row in self._all() if str(row.get("job_id") or "") == job_id]
        rows.sort(key=_occurred_at)
        return rows[: max(1, limit)]

    def timeline(self, records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        """Flatten records into the console timeline shape."""
        out: list[dict[str, Any]] = []
        for record in records or ():
            metadata = record.get("metadata") or {}
            out.append(
                {
                    "id": record.get("id"),
                    "at": _occurred_at(record),
                    "event": metadata.get("event") if isinstance(metadata, dict) else None,
                    "subject": metadata.get("subject") if isinstance(metadata, dict) else None,
                    "summary": record.get("content"),
                    "jobId": record.get("job_id"),
                }
            )
        return out


__all__ = ["EpisodeHistory"]
