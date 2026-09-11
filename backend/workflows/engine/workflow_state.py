"""Run and step state for the workflow engine path.

This module is deliberately pure: it holds no executor, opens no connections
and performs no I/O. It exists so that "what happened during this run" is a
single inspectable object rather than something reconstructed from log lines.

The one distinction worth spelling out is ``skipped`` versus ``succeeded``. A
step whose guard evaluated false produced no output. If it were recorded as
succeeded, a downstream guard reading ``steps.x.status == 'succeeded'`` would
be told a lie, and a downstream step reading ``steps.x.output`` would silently
see an empty dict as if the step had genuinely returned nothing. So skipped is
its own terminal state, and a step that depends on a failed step is
``blocked`` rather than started.

Run status is derived, never assigned by a caller:

* ``succeeded`` - every step reached ``succeeded`` or ``skipped``, and no step
  failed.
* ``partial``  - at least one step failed but was marked ``continue_on_error``,
  and the run reached the end. This is never reported as success.
* ``failed``   - a step failed terminally without ``continue_on_error``, or a
  step was blocked by such a failure.
* ``cancelled``- the caller stopped the run.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

RunStatus = Literal["pending", "running", "succeeded", "partial", "failed", "cancelled"]

StepStatus = Literal["pending", "running", "succeeded", "failed", "skipped", "blocked"]

#: Step states from which no further transition is legal.
TERMINAL_STEP_STATES: frozenset[str] = frozenset({"succeeded", "failed", "skipped", "blocked"})

#: Run states from which no further transition is legal.
TERMINAL_RUN_STATES: frozenset[str] = frozenset({"succeeded", "partial", "failed", "cancelled"})

_ALLOWED_STEP_TRANSITIONS: dict[str, frozenset[str]] = {
    # "failed" is reachable directly from pending because a step can be
    # refused before it ever starts: an approval gate the executor cannot
    # honour, or a guard that cannot be evaluated. Those are genuine step
    # failures. Routing them through "running" first would record an attempt
    # that never happened and start a timer for work that never ran.
    "pending": frozenset({"running", "skipped", "blocked", "failed"}),
    # A running step may end in any terminal state except "blocked": being
    # blocked is decided before a step starts, not after.
    "running": frozenset({"succeeded", "failed", "skipped"}),
    "succeeded": frozenset(),
    "failed": frozenset(),
    "skipped": frozenset(),
    "blocked": frozenset(),
}


class InvalidTransition(RuntimeError):
    """An illegal state change was attempted.

    This is a programming error, not a workflow-authoring error, so it raises
    rather than being recorded as a step failure. Swallowing it would let a
    run report a status that its own step records contradict.
    """

    reason = "invalid_transition"

    def __init__(self, subject: str, current: str, requested: str) -> None:
        super().__init__(f"{subject}: cannot move from '{current}' to '{requested}'")
        self.subject = subject
        self.current = current
        self.requested = requested


@dataclass
class StepRecord:
    """Everything known about one step of one run."""

    step_id: str
    kind: str = ""
    name: str = ""
    status: StepStatus = "pending"
    attempts: int = 0
    #: Output of the successful attempt. Empty for every non-succeeded state -
    #: notably, a failed step's partial output is not retained here, because a
    #: half-written result is not a result.
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    #: Machine-readable classification of ``error`` (see
    #: :mod:`backend.workflows.engine.retry_manager`).
    error_reason: str | None = None
    #: Why the step was skipped or blocked, in the author's terms.
    note: str | None = None
    started_at: float | None = None
    finished_at: float | None = None

    @property
    def duration_ms(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return max(0.0, (end - self.started_at) * 1000.0)

    def context_view(self) -> dict[str, Any]:
        """The shape a guard expression sees as ``steps.<id>``.

        Only these four keys are exposed. Timings and attempt counts are
        deliberately withheld: a workflow whose control flow depends on how
        long a step took, or how many times it was retried, is a workflow that
        behaves differently on a slow day.
        """
        return {
            "status": self.status,
            "output": dict(self.output),
            "error": self.error,
            "skipped": self.status == "skipped",
        }

    def summary(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "kind": self.kind,
            "name": self.name,
            "status": self.status,
            "attempts": self.attempts,
            "duration_ms": round(self.duration_ms, 1),
            "error": self.error,
            "error_reason": self.error_reason,
            "note": self.note,
        }


class WorkflowRunState:
    """Mutable state of a single workflow run.

    Step order is the order the steps were registered, which is the order they
    appear in the definition. Dependencies are tracked separately so that
    readiness is a graph question, not a list-position question.
    """

    def __init__(
        self,
        *,
        workflow: str,
        inputs: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> None:
        self.run_id = run_id or f"wfr-{uuid.uuid4().hex[:12]}"
        self.workflow = workflow
        self.inputs: dict[str, Any] = dict(inputs or {})
        self.status: RunStatus = "pending"
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.error: str | None = None
        self._steps: dict[str, StepRecord] = {}
        self._order: list[str] = []
        self._depends: dict[str, list[str]] = {}

    # -- registration ----------------------------------------------------

    def add_step(
        self,
        step_id: str,
        *,
        kind: str = "",
        name: str = "",
        depends_on: list[str] | None = None,
    ) -> StepRecord:
        if step_id in self._steps:
            raise ValueError(f"step '{step_id}' is already registered on run {self.run_id}")
        depends = [str(dep) for dep in (depends_on or [])]
        unknown = [dep for dep in depends if dep not in self._steps]
        if unknown:
            # Registering in definition order means a forward reference is
            # always an authoring error, and catching it here keeps
            # ready_steps() from having to reason about steps that may never
            # appear.
            raise ValueError(
                f"step '{step_id}' depends on step(s) not yet registered: "
                f"{', '.join(unknown)}"
            )
        record = StepRecord(step_id=step_id, kind=kind, name=name)
        self._steps[step_id] = record
        self._order.append(step_id)
        self._depends[step_id] = depends
        return record

    # -- lookup ----------------------------------------------------------

    def step(self, step_id: str) -> StepRecord:
        try:
            return self._steps[step_id]
        except KeyError as exc:
            raise KeyError(f"run {self.run_id} has no step '{step_id}'") from exc

    def has_step(self, step_id: str) -> bool:
        return step_id in self._steps

    @property
    def steps(self) -> list[StepRecord]:
        return [self._steps[sid] for sid in self._order]

    def depends_on(self, step_id: str) -> list[str]:
        return list(self._depends.get(step_id, []))

    # -- guard context ---------------------------------------------------

    def context(self) -> dict[str, Any]:
        """Context for :func:`backend.workflows.engine.condition_evaluator.evaluate`.

        Every registered step is present, including ones that have not run.
        An unstarted step reads as ``status == 'pending'`` rather than being
        absent, so a guard that looks forward gets a defined answer instead of
        an "unknown step" error.
        """
        return {
            "inputs": dict(self.inputs),
            "steps": {sid: record.context_view() for sid, record in self._steps.items()},
        }

    # -- run transitions -------------------------------------------------

    def start(self) -> None:
        if self.status != "pending":
            raise InvalidTransition(f"run {self.run_id}", self.status, "running")
        self.status = "running"
        self.started_at = time.monotonic()

    def cancel(self, reason: str = "cancelled by caller") -> None:
        if self.status in TERMINAL_RUN_STATES:
            raise InvalidTransition(f"run {self.run_id}", self.status, "cancelled")
        self.status = "cancelled"
        self.error = reason
        self.finished_at = time.monotonic()
        # Steps that never ran are blocked, not skipped: nothing evaluated a
        # guard for them, so "skipped" would misattribute the reason.
        for record in self._steps.values():
            if record.status in ("pending", "running"):
                record.status = "blocked"
                record.note = reason
                if record.finished_at is None and record.started_at is not None:
                    record.finished_at = time.monotonic()

    def finish(self) -> RunStatus:
        """Derive and store the terminal run status."""
        if self.status in TERMINAL_RUN_STATES:
            return self.status
        if self.status != "running":
            raise InvalidTransition(f"run {self.run_id}", self.status, "succeeded")

        failed = [r for r in self._steps.values() if r.status == "failed"]
        blocked = [r for r in self._steps.values() if r.status == "blocked"]
        unfinished = [r for r in self._steps.values() if r.status in ("pending", "running")]

        if unfinished:
            # Reaching finish() with work outstanding means the driver loop
            # exited early without saying why. Calling that success would be
            # the exact failure mode this module exists to prevent.
            self.status = "failed"
            self.error = (
                "run ended with unfinished step(s): "
                + ", ".join(sorted(r.step_id for r in unfinished))
            )
        elif blocked:
            self.status = "failed"
            self.error = self.error or (
                "run ended with blocked step(s): "
                + ", ".join(sorted(r.step_id for r in blocked))
            )
        elif failed:
            # Every failure was tolerated (otherwise the driver would have
            # blocked the rest), so the run completed - but only partly.
            self.status = "partial"
            self.error = self.error or (
                "tolerated failure in step(s): "
                + ", ".join(sorted(r.step_id for r in failed))
            )
        else:
            self.status = "succeeded"
        self.finished_at = time.monotonic()
        return self.status

    def fail(self, error: str) -> None:
        """Terminate the run because of a condition outside any single step."""
        if self.status in TERMINAL_RUN_STATES:
            raise InvalidTransition(f"run {self.run_id}", self.status, "failed")
        self.status = "failed"
        self.error = error
        self.finished_at = time.monotonic()
        for record in self._steps.values():
            if record.status in ("pending", "running"):
                record.status = "blocked"
                record.note = error

    # -- step transitions ------------------------------------------------

    def _transition(self, record: StepRecord, requested: StepStatus) -> None:
        allowed = _ALLOWED_STEP_TRANSITIONS.get(record.status, frozenset())
        if requested not in allowed:
            raise InvalidTransition(
                f"run {self.run_id} step '{record.step_id}'", record.status, requested
            )
        record.status = requested

    def mark_running(self, step_id: str) -> StepRecord:
        record = self.step(step_id)
        self._transition(record, "running")
        record.attempts += 1
        if record.started_at is None:
            record.started_at = time.monotonic()
        return record

    def mark_retrying(self, step_id: str) -> StepRecord:
        """Count another attempt on a step that is already running.

        Attempts are counted here rather than in the runner so the count can
        never disagree with the record.
        """
        record = self.step(step_id)
        if record.status != "running":
            raise InvalidTransition(
                f"run {self.run_id} step '{record.step_id}'", record.status, "running"
            )
        record.attempts += 1
        return record

    def mark_succeeded(self, step_id: str, output: dict[str, Any] | None = None) -> StepRecord:
        record = self.step(step_id)
        self._transition(record, "succeeded")
        record.output = dict(output or {})
        record.error = None
        record.error_reason = None
        record.finished_at = time.monotonic()
        return record

    def mark_failed(self, step_id: str, error: str, *, reason: str | None = None) -> StepRecord:
        record = self.step(step_id)
        self._transition(record, "failed")
        record.error = error
        record.error_reason = reason
        record.output = {}
        record.finished_at = time.monotonic()
        return record

    def mark_skipped(self, step_id: str, note: str) -> StepRecord:
        record = self.step(step_id)
        self._transition(record, "skipped")
        record.note = note
        record.output = {}
        record.finished_at = time.monotonic()
        if record.started_at is None:
            record.started_at = record.finished_at
        return record

    def mark_blocked(self, step_id: str, note: str) -> StepRecord:
        record = self.step(step_id)
        self._transition(record, "blocked")
        record.note = note
        record.output = {}
        record.finished_at = time.monotonic()
        if record.started_at is None:
            record.started_at = record.finished_at
        return record

    # -- scheduling ------------------------------------------------------

    def ready_steps(self) -> list[str]:
        """Pending steps whose dependencies have all succeeded or skipped.

        A skipped dependency does not block: the guard that skipped it made a
        decision about that step, not about everything after it. A *failed* or
        *blocked* dependency does block, and the caller is expected to call
        :meth:`block_unreachable` to record why.
        """
        ready: list[str] = []
        for step_id in self._order:
            record = self._steps[step_id]
            if record.status != "pending":
                continue
            deps = self._depends.get(step_id, [])
            if all(self._steps[dep].status in ("succeeded", "skipped") for dep in deps):
                ready.append(step_id)
        return ready

    def block_unreachable(self) -> list[str]:
        """Mark pending steps that can never run, and say which dependency stopped them.

        Applied repeatedly until stable, so blocking propagates down a chain
        instead of only one level.
        """
        blocked: list[str] = []
        changed = True
        while changed:
            changed = False
            for step_id in self._order:
                record = self._steps[step_id]
                if record.status != "pending":
                    continue
                stoppers = [
                    dep
                    for dep in self._depends.get(step_id, [])
                    if self._steps[dep].status in ("failed", "blocked")
                ]
                if stoppers:
                    self.mark_blocked(
                        step_id,
                        "dependency did not complete: " + ", ".join(sorted(stoppers)),
                    )
                    blocked.append(step_id)
                    changed = True
        return blocked

    # -- reporting -------------------------------------------------------

    @property
    def duration_ms(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return max(0.0, (end - self.started_at) * 1000.0)

    def counts(self) -> dict[str, int]:
        tally: dict[str, int] = {}
        for record in self._steps.values():
            tally[record.status] = tally.get(record.status, 0) + 1
        return tally

    def outputs(self) -> dict[str, dict[str, Any]]:
        """Outputs of succeeded steps only."""
        return {
            sid: dict(record.output)
            for sid, record in self._steps.items()
            if record.status == "succeeded"
        }

    def summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow": self.workflow,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 1),
            "error": self.error,
            "counts": self.counts(),
            "steps": [record.summary() for record in self.steps],
        }


__all__ = [
    "TERMINAL_RUN_STATES",
    "TERMINAL_STEP_STATES",
    "InvalidTransition",
    "RunStatus",
    "StepRecord",
    "StepStatus",
    "WorkflowRunState",
]
