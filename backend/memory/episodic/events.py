"""Episodic memory: what happened, when, and to what.

Episodic records are observations, not conclusions. "Vibration alarm raised on
C-3 at 06:00" is episodic; "C-3 has a bearing problem" is a semantic claim and
must carry evidence. Keeping the two apart is what stops a chain of guesses
from hardening into remembered fact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.memory.src.memory_types import (
    KIND_EPISODIC,
    SCOPE_GLOBAL,
    MemoryCandidate,
)

#: Event vocabulary. Closed on purpose - an open string field turns into six
#: spellings of the same event within a month.
EVENT_KINDS: frozenset[str] = frozenset(
    {
        "alarm_raised",
        "alarm_cleared",
        "inspection_completed",
        "work_order_created",
        "work_order_completed",
        "maintenance_performed",
        "analysis_completed",
        "artifact_generated",
        "approval_granted",
        "approval_rejected",
        "observation",
    }
)


class UnknownEvent(ValueError):
    """An event kind outside :data:`EVENT_KINDS` was supplied."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Event:
    """One observed occurrence."""

    kind: str
    subject: str
    summary: str
    occurred_at: str = field(default_factory=_now)
    job_id: str | None = None
    user: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in EVENT_KINDS:
            raise UnknownEvent(
                f"unknown event kind '{self.kind}'; expected one of {sorted(EVENT_KINDS)}"
            )

    @property
    def key(self) -> str:
        """Stable lookup key: subject first, so all events for a tag group."""
        return f"{self.subject}:{self.kind}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "subject": self.subject,
            "summary": self.summary,
            "occurredAt": self.occurred_at,
            "jobId": self.job_id,
            "user": self.user,
            "details": dict(self.details),
        }

    def to_candidate(self, *, scope: str = SCOPE_GLOBAL) -> MemoryCandidate:
        """Shape for :meth:`MemoryService.remember`."""
        return MemoryCandidate(
            kind=KIND_EPISODIC,
            key=self.key,
            content=f"{self.occurred_at} - {self.summary}",
            scope=scope,
            confidence=0.9,
            metadata={
                "event": self.kind,
                "subject": self.subject,
                "occurredAt": self.occurred_at,
                **{k: v for k, v in self.details.items() if isinstance(v, (str, int, float))},
            },
            job_id=self.job_id,
            user=self.user,
        )


def from_step_outcome(outcome: Any, *, subject: str, job_id: str | None = None) -> Event:
    """Build an event from an orchestrator step outcome.

    Used so a completed analysis leaves a trace in memory without the
    orchestrator having to know the memory schema.
    """
    status = getattr(outcome, "status", "ok")
    name = getattr(outcome, "name", "step")
    return Event(
        kind="analysis_completed",
        subject=subject,
        summary=f"step '{name}' finished with status {status}",
        job_id=job_id,
        details={"status": str(status), "step": str(name)},
    )


__all__ = ["EVENT_KINDS", "Event", "UnknownEvent", "from_step_outcome"]
