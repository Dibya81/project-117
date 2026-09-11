"""Façade over the two ways a workflow can be run.

There are deliberately two paths, and this module is where the choice is made
explicit instead of being folded into one half-implemented hybrid.

**Plan path (default, production).** :meth:`WorkflowEngine.compile` hands the
definition to :class:`~backend.orchestrator.src.workflow_manager.WorkflowManager`,
which turns it into the same ``Plan`` the planner produces. From there the
orchestrator owns execution: tool permissions, risk gating, plan approval,
retrieval scoping, verification and audit. Nothing about a workflow is special
once it is a plan, which is exactly why this is the default. Use it unless you
have a reason not to.

**Engine path.** :meth:`WorkflowEngine.run` executes the definition directly,
adding the three things a ``Plan`` cannot express: per-step guards (``when``),
per-step retry policy (``retry``), and a queryable run state. It still does not
execute anything itself - it requires an injected executor and delegates every
step to it. Without an executor, :meth:`run` raises rather than pretending.

What this module does **not** do is re-validate what ``WorkflowManager``
already validates (unknown tools, dependency ordering, step-id reuse, input
placeholder resolution, step limits). :meth:`validate` calls into the manager
for that and only adds the engine-specific checks - guard structure, guard
reference ordering, and the approval/tolerance combination.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from backend.workflows.engine.condition_evaluator import validate_expression
from backend.workflows.engine.registry import (
    WorkflowDefinition,
    WorkflowRegistry,
    WorkflowStepSpec,
)
from backend.workflows.engine.retry_manager import RetryManager
from backend.workflows.engine.step_runner import (
    StepRunner,
    executor_handles_approval,
)
from backend.workflows.engine.workflow_state import WorkflowRunState

logger = logging.getLogger(__name__)


class ExecutorRequired(RuntimeError):
    """The engine path was used without an executor.

    Raised instead of falling back to a stub. A workflow that "ran" with no
    executor would report succeeded steps that never happened, which is worse
    than an error.
    """

    reason = "executor_required"

    def __init__(self) -> None:
        super().__init__(
            "WorkflowEngine.run() needs an executor. Construct the engine with "
            "executor=... (in production, the orchestrator's execution adapter), "
            "or use WorkflowEngine.compile() to run the workflow as a plan "
            "through the orchestrator instead."
        )


class ManagerRequired(RuntimeError):
    """The plan path was used without the orchestrator's ``WorkflowManager``.

    The engine cannot compile a plan on its own: plan construction is where
    tool names are checked against the live registry and ``{{inputs.x}}``
    placeholders are resolved. Faking a ``Plan`` here would produce one the
    orchestrator never validated.
    """

    reason = "manager_required"

    def __init__(self) -> None:
        super().__init__(
            "WorkflowEngine.compile() needs the orchestrator's WorkflowManager; "
            "construct the engine with manager=..."
        )


class WorkflowValidationError(ValueError):
    """A definition failed engine-level validation."""

    reason = "workflow_invalid"

    def __init__(self, name: str, problems: list[str]) -> None:
        detail = "; ".join(problems)
        super().__init__(f"workflow '{name}' is invalid: {detail}")
        self.name = name
        self.problems = list(problems)


@dataclass
class WorkflowRunReport:
    """Result of an engine-path run."""

    run_id: str
    workflow: str
    status: str
    error: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: Per-step attempt logs, keyed by step id.
    attempts: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    duration_ms: float = 0.0
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        """True only for a clean run.

        ``partial`` is not success. A caller that wants to accept tolerated
        failures must check ``status`` explicitly and say so.
        """
        return self.status == "succeeded"

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow": self.workflow,
            "status": self.status,
            "succeeded": self.succeeded,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 1),
            "counts": dict(self.counts),
            "steps": list(self.steps),
            "attempts": {k: list(v) for k, v in self.attempts.items()},
        }


class WorkflowEngine:
    """Entry point for listing, validating, compiling and running workflows."""

    def __init__(
        self,
        registry: WorkflowRegistry,
        *,
        manager: Any | None = None,
        executor: Any | None = None,
        retry_manager: RetryManager | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._registry = registry
        # The orchestrator's WorkflowManager. Optional so the engine can be
        # constructed for validation in contexts that have no tool registry.
        self._manager = manager
        self._executor = executor
        self._retry = retry_manager or RetryManager()
        self._sleep = sleep

    # -- introspection ---------------------------------------------------

    @property
    def registry(self) -> WorkflowRegistry:
        return self._registry

    @property
    def has_executor(self) -> bool:
        return self._executor is not None

    @property
    def handles_approval(self) -> bool:
        return executor_handles_approval(self._executor)

    def list_workflows(self) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for definition in self._registry.list():
            steps = list(definition.steps or [])
            summaries.append(
                {
                    "name": definition.name,
                    "description": definition.description,
                    "version": definition.version,
                    "agent": definition.agent,
                    "inputs": list(definition.inputs or []),
                    "steps": len(steps),
                    "source": definition.source,
                    "has_guards": any(step.when for step in steps),
                    "has_retries": any(step.retry for step in steps),
                    "requires_approval": any(step.requires_approval for step in steps),
                }
            )
        return summaries

    def get(self, name: str) -> WorkflowDefinition:
        return self._registry.get(name)

    # -- validation ------------------------------------------------------

    def validate(self, name: str) -> list[str]:
        """Engine-level problems with a definition. Empty means usable.

        Only checks what the orchestrator's ``WorkflowManager`` does not:
        guard structure, guard reference ordering, and the approval/tolerance
        combination. Duplicating the manager's checks here would mean two
        implementations of "is this workflow valid", which is how the two
        disagree.
        """
        definition = self._registry.get(name)
        problems: list[str] = []
        declared_inputs = list(definition.inputs or [])
        seen_ids: list[str] = []

        for index, step in enumerate(definition.steps or []):
            step_id = step.id or f"step{index + 1}"

            problems.extend(
                f"step '{step_id}': {problem}"
                for problem in validate_expression(
                    step.when, inputs=declared_inputs, steps=seen_ids
                )
            )

            if step.requires_approval and step.continue_on_error:
                problems.append(
                    f"step '{step_id}': continue_on_error cannot be combined with "
                    "requires_approval; a rejected or failed approval gate is not "
                    "something a run may tolerate and carry on past"
                )

            if step.requires_approval and self._executor is not None and not self.handles_approval:
                problems.append(
                    f"step '{step_id}': requires approval, but the configured "
                    "executor does not declare handles_approval=True"
                )

            seen_ids.append(step_id)

        return problems

    def validate_all(self) -> dict[str, list[str]]:
        """Validate every registered definition; only failures are included."""
        report: dict[str, list[str]] = {}
        for definition in self._registry.list():
            problems = self.validate(definition.name)
            if problems:
                report[definition.name] = problems
        return report

    # -- plan path (default) ---------------------------------------------

    def compile(
        self,
        name: str,
        *,
        inputs: dict[str, Any] | None = None,
        task: str | None = None,
    ) -> Any:
        """Compile to an orchestrator ``Plan``. This is the production path.

        Returns whatever the injected manager returns (a ``Plan``); typed as
        ``Any`` so this module does not import the orchestrator, which would
        make a cycle - the orchestrator's composition root builds the engine.
        """
        if self._manager is None:
            raise ManagerRequired()
        problems = self.validate(name)
        if problems:
            raise WorkflowValidationError(name, problems)
        return self._manager.compile(name, inputs=inputs, task=task)

    # -- engine path -----------------------------------------------------

    def _prepare_state(
        self, definition: WorkflowDefinition, inputs: dict[str, Any] | None
    ) -> tuple[WorkflowRunState, dict[str, WorkflowStepSpec]]:
        supplied = dict(inputs or {})
        missing = [key for key in (definition.inputs or []) if key not in supplied]
        if missing:
            raise WorkflowValidationError(
                definition.name,
                [f"missing required input(s): {', '.join(missing)}"],
            )

        state = WorkflowRunState(workflow=definition.name, inputs=supplied)
        specs: dict[str, WorkflowStepSpec] = {}
        for index, step in enumerate(definition.steps or []):
            step_id = step.id or f"step{index + 1}"
            state.add_step(
                step_id,
                kind=step.kind,
                name=step.name or "",
                depends_on=list(step.depends_on or []),
            )
            specs[step_id] = step
        return state, specs

    async def run(
        self,
        name: str,
        *,
        inputs: dict[str, Any] | None = None,
    ) -> WorkflowRunReport:
        """Execute a workflow through the injected executor.

        Steps run in dependency order, one at a time. Sequential rather than
        wave-parallel on purpose: a guard may read any earlier step's output,
        so running independent steps concurrently would make the guard context
        depend on completion timing. The plan path is where parallelism lives
        (``Plan.waves``), and it has no guards.
        """
        if self._executor is None:
            raise ExecutorRequired()

        definition = self._registry.get(name)
        problems = self.validate(name)
        if problems:
            raise WorkflowValidationError(name, problems)

        state, specs = self._prepare_state(definition, inputs)
        runner = StepRunner(
            self._executor, retry_manager=self._retry, sleep=self._sleep
        )
        attempts: dict[str, list[dict[str, Any]]] = {}

        state.start()
        logger.info(
            "workflow %s run %s: starting %d step(s)",
            definition.name,
            state.run_id,
            len(specs),
        )

        try:
            while True:
                ready = state.ready_steps()
                if not ready:
                    break
                step_id = ready[0]
                result = await runner.run_step(state, specs[step_id], step_id=step_id)
                if result.attempts:
                    attempts[step_id] = result.attempts
                if result.abort_run:
                    blocked = state.block_unreachable()
                    if blocked:
                        logger.info(
                            "workflow %s run %s: blocked %s after '%s'",
                            definition.name,
                            state.run_id,
                            ", ".join(blocked),
                            step_id,
                        )
                    state.fail(result.abort_reason or f"step '{step_id}' failed")
                    break
                # A tolerated failure still stops anything that depended on it;
                # continue_on_error means "carry on with the rest", not "pretend
                # this step produced output".
                if result.status == "failed":
                    state.block_unreachable()
        except Exception:
            if state.status == "running":
                state.fail("run aborted by an unexpected error")
            raise

        if state.status == "running":
            state.finish()

        report = WorkflowRunReport(
            run_id=state.run_id,
            workflow=state.workflow,
            status=state.status,
            error=state.error,
            steps=[record.summary() for record in state.steps],
            outputs=state.outputs(),
            attempts=attempts,
            duration_ms=state.duration_ms,
            counts=state.counts(),
        )
        logger.info(
            "workflow %s run %s: %s (%s)",
            definition.name,
            state.run_id,
            report.status,
            report.counts,
        )
        return report


__all__ = [
    "ExecutorRequired",
    "ManagerRequired",
    "WorkflowEngine",
    "WorkflowRunReport",
    "WorkflowValidationError",
]
