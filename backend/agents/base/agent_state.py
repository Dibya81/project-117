"""Agent run state machine.

The UI shows a task moving through PERCEIVE -> PLAN -> ACT -> VERIFY, so the
backend needs one authoritative definition of those phases and of which
transitions are legal. Without it, "verifying" is whatever string the last
writer happened to emit.

Phases map to the workspace stages as follows:

=============  =====================================================
``perceive``   Retrieving evidence and reading context.
``plan``       Deciding the steps (no side effects yet).
``act``        Running tools / producing output.
``verify``     Checking the output against evidence and policy.
``complete``   Terminal, successful.
``failed``     Terminal, unsuccessful — always carries a reason.
``blocked``    Waiting on a human approval; can resume into ``act``.
=============  =====================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

AgentPhase = Literal[
    "idle",
    "perceive",
    "plan",
    "act",
    "verify",
    "blocked",
    "complete",
    "failed",
]

#: Legal transitions. Terminal phases have no outgoing edges: a completed run
#: cannot be quietly reopened, a new run is started instead.
TRANSITIONS: dict[str, frozenset[str]] = {
    "idle": frozenset({"perceive", "plan", "failed"}),
    "perceive": frozenset({"plan", "act", "failed"}),
    "plan": frozenset({"act", "blocked", "failed"}),
    "act": frozenset({"verify", "blocked", "failed"}),
    "verify": frozenset({"complete", "act", "failed"}),
    "blocked": frozenset({"act", "failed"}),
    "complete": frozenset(),
    "failed": frozenset(),
}

TERMINAL: frozenset[str] = frozenset({"complete", "failed"})


class AgentStateError(RuntimeError):
    """An illegal phase transition was attempted."""

    reason = "invalid_transition"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class AgentRunState:
    """Phase plus the history of how it got there.

    The history is what the workspace timeline renders; it is recorded as the
    run happens rather than reconstructed afterwards.
    """

    agent: str
    phase: AgentPhase = "idle"
    job_id: str | None = None
    error: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)

    # -- queries -------------------------------------------------------
    @property
    def terminal(self) -> bool:
        return self.phase in TERMINAL

    def can_advance(self, phase: str) -> bool:
        return phase in TRANSITIONS.get(self.phase, frozenset())

    # -- transitions ---------------------------------------------------
    def advance(self, phase: AgentPhase, *, detail: str = "") -> "AgentRunState":
        if not self.can_advance(phase):
            allowed = sorted(TRANSITIONS.get(self.phase, frozenset()))
            raise AgentStateError(
                f"cannot move {self.agent} from '{self.phase}' to '{phase}'; "
                f"allowed: {allowed or 'none (terminal)'}"
            )
        self.history.append(
            {"from": self.phase, "to": phase, "at": _now(), "detail": detail}
        )
        self.phase = phase
        return self

    def fail(self, reason: str) -> "AgentRunState":
        """Terminal failure. Always carries a reason — a failed run with no
        explanation is indistinguishable from a bug."""
        if self.phase in TERMINAL:
            raise AgentStateError(f"{self.agent} is already {self.phase}")
        self.history.append(
            {"from": self.phase, "to": "failed", "at": _now(), "detail": reason}
        )
        self.phase = "failed"
        self.error = reason
        return self

    def block(self, reason: str) -> "AgentRunState":
        return self.advance("blocked", detail=reason)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "phase": self.phase,
            "jobId": self.job_id,
            "terminal": self.terminal,
            "error": self.error,
            "history": list(self.history),
        }


__all__ = [
    "TERMINAL",
    "TRANSITIONS",
    "AgentPhase",
    "AgentRunState",
    "AgentStateError",
]
