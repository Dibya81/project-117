"""Job state machine (Phase 6).

A request to this backend is not a chat completion. "Read this 600-page
manual and build a deck with cited pages" is a job that plans, retrieves,
executes tools in a sandbox, and gets verified - tens of seconds at best. A
single in-flight boolean cannot describe that, and a client that can only see
"pending" or "done" cannot show progress or ask for approval.

So state is explicit and the legal moves are declared here, in one table, for
both the API and the orchestrator to share.

    QUEUED -> PLANNING -> [RETRIEVING] -> EXECUTING -> VERIFYING -> COMPLETED

Two invariants are worth stating because the rest of the system leans on them:

**COMPLETED is only reachable from VERIFYING.** An answer or artifact cannot
become a success without passing the checkers. That is a property of this
table, not of orchestrator etiquette.

**NEEDS_APPROVAL is reachable from every working state, and resumes.** A job
parks *before* the side effect it needs permission for, so a parked job has
changed nothing.

Aborts (FAILED, CANCELLED, TIMEOUT) are reachable from every non-terminal
state, otherwise a wedged job would be unkillable.
"""

from __future__ import annotations

from enum import Enum


class JobState(str, Enum):
    """The lifecycle of one unit of work. Stored as text in ``jobs.state``."""

    QUEUED = "queued"
    PLANNING = "planning"
    RETRIEVING = "retrieving"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    NEEDS_APPROVAL = "needs_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


#: States from which nothing further can happen.
TERMINAL_STATES = frozenset(
    {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED, JobState.TIMEOUT}
)

#: Terminal states that are not a success. Used by the API to pick a status
#: code and by the orchestrator to decide whether to attempt recovery.
FAILURE_STATES = frozenset({JobState.FAILED, JobState.CANCELLED, JobState.TIMEOUT})

#: States a job can be interrupted into from anywhere non-terminal. Cancelling
#: and timing out must always be reachable, otherwise a stuck job is
#: unkillable.
_ABORTS = frozenset({JobState.FAILED, JobState.CANCELLED, JobState.TIMEOUT})

#: Legal forward edges. Aborts are added to every non-terminal state below.
_FORWARD: dict[JobState, frozenset[JobState]] = {
    JobState.QUEUED: frozenset({JobState.PLANNING}),
    # A plan may need no retrieval (pure computation, artifact from supplied
    # data), so PLANNING -> EXECUTING is legal. A high-risk first step parks
    # the job for a human before anything runs.
    JobState.PLANNING: frozenset(
        {JobState.RETRIEVING, JobState.EXECUTING, JobState.NEEDS_APPROVAL}
    ),
    # Retrieval-only questions ("what does the manual say about X") go
    # straight to verification: the answer is the retrieved evidence.
    JobState.RETRIEVING: frozenset(
        {JobState.EXECUTING, JobState.VERIFYING, JobState.NEEDS_APPROVAL}
    ),
    # EXECUTING -> EXECUTING covers a retried step and multi-step plans.
    # EXECUTING -> RETRIEVING covers a plan that re-queries after computing
    # (e.g. the analysis revealed the equipment id it actually needs).
    JobState.EXECUTING: frozenset(
        {
            JobState.EXECUTING,
            JobState.RETRIEVING,
            JobState.VERIFYING,
            JobState.NEEDS_APPROVAL,
        }
    ),
    # Verification may send work back: a failed artifact check can be retried
    # once with a corrected spec before the job is failed for good.
    JobState.VERIFYING: frozenset({JobState.COMPLETED, JobState.EXECUTING}),
    # Approved resumes where it was parked; rejected is a CANCELLED abort.
    JobState.NEEDS_APPROVAL: frozenset({JobState.EXECUTING, JobState.RETRIEVING}),
}

#: The complete transition table, aborts included.
LEGAL_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    **{state: targets | _ABORTS for state, targets in _FORWARD.items()},
    **{state: frozenset() for state in TERMINAL_STATES},
}


class InvalidTransition(RuntimeError):
    """An illegal state move was attempted. This is a bug, not user error."""

    reason = "invalid_job_transition"

    def __init__(self, current: JobState, target: JobState) -> None:
        allowed = sorted(s.value for s in LEGAL_TRANSITIONS.get(current, frozenset()))
        detail = ", ".join(allowed) if allowed else "none (terminal state)"
        super().__init__(
            f"illegal job transition {current.value} -> {target.value}; "
            f"allowed from {current.value}: {detail}"
        )
        self.current = current
        self.target = target


def can_transition(current: JobState, target: JobState) -> bool:
    return target in LEGAL_TRANSITIONS.get(current, frozenset())


def assert_transition(current: JobState, target: JobState) -> None:
    """Raise :class:`InvalidTransition` unless the move is legal."""
    if not can_transition(current, target):
        raise InvalidTransition(current, target)


def is_terminal(state: JobState) -> bool:
    return state in TERMINAL_STATES


def parse_state(value: str) -> JobState:
    """Parse a state name from the database or an API query string."""
    try:
        return JobState(value)
    except ValueError as exc:
        allowed = ", ".join(s.value for s in JobState)
        raise ValueError(f"unknown job state '{value}' - expected one of: {allowed}") from exc
