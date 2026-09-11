"""Runs one workflow step: guard, approval check, attempts, retries.

This module does not execute anything itself. It takes an **injected executor**
and calls it. In production that executor is backed by the orchestrator's
``ExecutionManager``, which is the only code in the system that knows how to
dispatch a retrieve/agent/tool/verify step, enforce tool permissions, record
audit rows and honour approval gates.

That separation is the whole point. If this module dispatched tools itself it
would be a second execution path, and every guarantee the orchestrator makes -
permission checks, risk gating, audit records, chunk caps - would have to be
re-implemented here and would drift. So the engine adds exactly three things
the orchestrator does not do (guards, retry policy, run-state tracking) and
delegates the rest.

One refusal is worth calling out. If a step declares ``requires_approval`` and
the injected executor does not declare ``handles_approval = True``, the step is
not run. It is not run-and-hope, and it is not silently skipped: it fails, and
the run aborts. Executing a gated step through an executor that has no concept
of approval would be precisely the "fake success" failure this codebase is
meant to avoid.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping, Protocol, runtime_checkable

from backend.workflows.engine.condition_evaluator import ConditionError, evaluate
from backend.workflows.engine.registry import WorkflowStepSpec
from backend.workflows.engine.retry_manager import RetryManager
from backend.workflows.engine.workflow_state import StepRecord, WorkflowRunState

logger = logging.getLogger(__name__)

#: Fallback per-step timeout when a step declares none. Matches the default
#: ``PlanStep.timeout_seconds`` so the two paths time out alike.
DEFAULT_STEP_TIMEOUT_SECONDS = 120.0


class ApprovalNotSupported(RuntimeError):
    """A gated step was handed to an executor that cannot gate."""

    reason = "approval_required"

    def __init__(self, step_id: str) -> None:
        super().__init__(
            f"step '{step_id}' requires approval, but the injected executor does "
            "not declare handles_approval=True; refusing to run it rather than "
            "bypassing the gate"
        )
        self.step_id = step_id


class ExecutorContractError(TypeError):
    """The executor returned something that is not a mapping of outputs."""

    reason = "executor_contract"


@dataclass(frozen=True)
class StepInvocation:
    """Everything an executor is given for one attempt.

    A flat, frozen snapshot rather than the live :class:`WorkflowRunState`, so
    an executor cannot mutate run bookkeeping as a side effect of running a
    step. Note what is absent: no credentials, no session, no registry. The
    executor already holds those; a step never supplies them.
    """

    run_id: str
    workflow: str
    step_id: str
    kind: str
    name: str
    description: str
    arguments: Mapping[str, Any]
    #: 1-based attempt number.
    attempt: int
    requires_approval: bool
    timeout_seconds: float
    #: The run's declared inputs.
    inputs: Mapping[str, Any]
    #: Outputs of steps that have already succeeded, keyed by step id.
    outputs: Mapping[str, Mapping[str, Any]]


@runtime_checkable
class StepExecutor(Protocol):
    """What the engine needs from whoever actually runs steps.

    ``handles_approval`` is a declaration, not a capability probe: an executor
    that returns ``True`` is asserting that it parks gated steps for review.
    The engine takes that assertion at face value and refuses gated steps
    otherwise, which is the safe direction to be wrong in.
    """

    handles_approval: bool

    async def execute(self, invocation: StepInvocation) -> Mapping[str, Any]:
        """Run one attempt and return its outputs."""
        ...


#: Simpler alternative to the protocol for tests and adapters.
ExecutorCallable = Callable[[StepInvocation], Awaitable[Mapping[str, Any]]]


def executor_handles_approval(executor: Any) -> bool:
    """Whether ``executor`` declares that it enforces approval gates.

    Defaults to ``False`` for anything that does not say so explicitly,
    including bare callables.
    """
    return bool(getattr(executor, "handles_approval", False))


async def _invoke(executor: Any, invocation: StepInvocation) -> Mapping[str, Any]:
    """Call either a protocol executor or a plain async callable."""
    execute = getattr(executor, "execute", None)
    if callable(execute):
        result = execute(invocation)
    elif callable(executor):
        result = executor(invocation)
    else:
        raise ExecutorContractError(
            "executor must expose an async execute(invocation) method or be an "
            f"async callable; got {type(executor).__name__}"
        )
    if not isinstance(result, Awaitable):
        raise ExecutorContractError(
            "executor must be asynchronous; "
            f"{type(executor).__name__} returned {type(result).__name__}"
        )
    return await result


@dataclass
class StepResult:
    """Outcome of :meth:`StepRunner.run_step`."""

    record: StepRecord
    #: True when the run must stop. Set for an untolerated failure, a broken
    #: guard, or a refused approval gate.
    abort_run: bool = False
    abort_reason: str | None = None
    #: One entry per attempt, including the retry decision that followed it.
    attempts: list[dict[str, Any]] = field(default_factory=list)

    @property
    def status(self) -> str:
        return self.record.status


class StepRunner:
    """Executes a single :class:`WorkflowStepSpec` against a run state."""

    def __init__(
        self,
        executor: Any,
        *,
        retry_manager: RetryManager | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._executor = executor
        self._retry = retry_manager or RetryManager()
        # Injected so tests do not wait out real backoff. Production passes
        # nothing and gets asyncio.sleep.
        self._sleep = sleep or asyncio.sleep
        self._handles_approval = executor_handles_approval(executor)

    @property
    def handles_approval(self) -> bool:
        return self._handles_approval

    def _invocation(
        self, state: WorkflowRunState, spec: WorkflowStepSpec, step_id: str, attempt: int
    ) -> StepInvocation:
        return StepInvocation(
            run_id=state.run_id,
            workflow=state.workflow,
            step_id=step_id,
            kind=spec.kind,
            name=spec.name or "",
            description=spec.description,
            arguments=dict(spec.arguments),
            attempt=attempt,
            requires_approval=spec.requires_approval,
            timeout_seconds=float(spec.timeout_seconds or DEFAULT_STEP_TIMEOUT_SECONDS),
            inputs=dict(state.inputs),
            outputs=state.outputs(),
        )

    async def run_step(
        self, state: WorkflowRunState, spec: WorkflowStepSpec, *, step_id: str | None = None
    ) -> StepResult:
        resolved_id = step_id or spec.id or ""
        if not state.has_step(resolved_id):
            raise KeyError(
                f"step '{resolved_id}' was not registered on run {state.run_id}"
            )

        # 1. Guard. A guard that cannot be evaluated is an authoring error, and
        #    it aborts the run regardless of continue_on_error: that flag is a
        #    statement about tolerating operational failures, not about running
        #    a workflow whose control flow is undefined.
        try:
            should_run = evaluate(spec.when, state.context())
        except ConditionError as exc:
            record = state.mark_failed(
                resolved_id, f"guard could not be evaluated: {exc}", reason="condition_error"
            )
            return StepResult(
                record=record,
                abort_run=True,
                abort_reason=f"step '{resolved_id}' has an invalid guard: {exc}",
            )

        if not should_run:
            record = state.mark_skipped(
                resolved_id, f"guard evaluated false: {str(spec.when).strip()}"
            )
            logger.info(
                "workflow %s run %s: step '%s' skipped by guard",
                state.workflow,
                state.run_id,
                resolved_id,
            )
            return StepResult(record=record)

        # 2. Approval gate. Checked before the first attempt so a gated step is
        #    never partially executed.
        if spec.requires_approval and not self._handles_approval:
            error = ApprovalNotSupported(resolved_id)
            record = state.mark_failed(resolved_id, str(error), reason=error.reason)
            logger.warning(
                "workflow %s run %s: refusing gated step '%s' (executor cannot gate)",
                state.workflow,
                state.run_id,
                resolved_id,
            )
            return StepResult(record=record, abort_run=True, abort_reason=str(error))

        # 3. Attempts.
        spec_retry = spec.retry
        max_attempts = self._retry.spec_for(spec_retry).max_attempts
        attempt_log: list[dict[str, Any]] = []
        state.mark_running(resolved_id)
        attempt = 1

        while True:
            invocation = self._invocation(state, spec, resolved_id, attempt)
            try:
                output = await asyncio.wait_for(
                    _invoke(self._executor, invocation),
                    timeout=invocation.timeout_seconds,
                )
            except asyncio.CancelledError:
                # Cancellation is not a step failure and must not be absorbed;
                # the caller is shutting the run down.
                raise
            except Exception as exc:  # noqa: BLE001 - classified below
                decision = self._retry.decide(
                    attempt=attempt, error=exc, spec=spec_retry
                )
                attempt_log.append(
                    {
                        "attempt": attempt,
                        "status": "error",
                        "error": str(exc) or type(exc).__name__,
                        "decision": decision.as_dict(),
                    }
                )
                logger.info(
                    "workflow %s run %s: step '%s' attempt %d/%d failed (%s); %s",
                    state.workflow,
                    state.run_id,
                    resolved_id,
                    attempt,
                    max_attempts,
                    decision.error_reason,
                    decision.explanation,
                )
                if decision.retry:
                    if decision.delay_seconds > 0:
                        await self._sleep(decision.delay_seconds)
                    state.mark_retrying(resolved_id)
                    attempt += 1
                    continue

                record = state.mark_failed(
                    resolved_id,
                    str(exc) or type(exc).__name__,
                    reason=decision.error_reason,
                )
                tolerated = bool(spec.continue_on_error)
                if tolerated:
                    # Recorded on the step so a reader of the run report can
                    # see the failure was allowed rather than missed.
                    record.note = "failure tolerated by continue_on_error"
                return StepResult(
                    record=record,
                    abort_run=not tolerated,
                    abort_reason=None if tolerated else f"step '{resolved_id}' failed: {exc}",
                    attempts=attempt_log,
                )

            # Success path: validate the executor honoured its contract before
            # recording anything, so a malformed return cannot become output.
            if output is None:
                output = {}
            if not isinstance(output, Mapping):
                error = ExecutorContractError(
                    f"step '{resolved_id}' executor returned "
                    f"{type(output).__name__}, expected a mapping of outputs"
                )
                record = state.mark_failed(resolved_id, str(error), reason=error.reason)
                return StepResult(
                    record=record,
                    abort_run=True,
                    abort_reason=str(error),
                    attempts=attempt_log,
                )

            attempt_log.append({"attempt": attempt, "status": "ok", "error": None})
            record = state.mark_succeeded(resolved_id, dict(output))
            return StepResult(record=record, attempts=attempt_log)


__all__ = [
    "DEFAULT_STEP_TIMEOUT_SECONDS",
    "ApprovalNotSupported",
    "ExecutorCallable",
    "ExecutorContractError",
    "StepExecutor",
    "StepInvocation",
    "StepResult",
    "StepRunner",
    "executor_handles_approval",
]
