"""Job lifecycle: state machine, persistence, and the progress event bus.

The API accepts work and returns a job id; the orchestrator moves that job
through :class:`JobState`. Both sides share the transition table in
``state.py`` so "can this job be approved right now?" has one answer.
"""

from backend.jobs.bus import JobEventBus
from backend.jobs.service import ConcurrentJobUpdate, JobNotFound, JobService
from backend.jobs.state import (
    FAILURE_STATES,
    LEGAL_TRANSITIONS,
    TERMINAL_STATES,
    InvalidTransition,
    JobState,
    assert_transition,
    can_transition,
    is_terminal,
    parse_state,
)

__all__ = [
    "ConcurrentJobUpdate",
    "FAILURE_STATES",
    "InvalidTransition",
    "JobEventBus",
    "JobNotFound",
    "JobService",
    "JobState",
    "LEGAL_TRANSITIONS",
    "TERMINAL_STATES",
    "assert_transition",
    "can_transition",
    "is_terminal",
    "parse_state",
]
