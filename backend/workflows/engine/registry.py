"""Workflow registry (Phase 14).

Holds the workflow definitions loaded from YAML by :mod:`backend.workflows.engine.loader`.
The registry itself does no validation beyond shape - the real compile-time
checks (unknown tools, cyclic dependencies, unresolved inputs) live in
:class:`backend.orchestrator.src.workflow_manager.WorkflowManager`, which is what
turns a definition into an executable :class:`~backend.orchestrator.src.plan.Plan`.
Keeping that logic in one place means a workflow is validated exactly once,
not once at load time and again differently at run time.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RetrySpec(BaseModel):
    """Per-step retry declaration.

    Only consumed by :mod:`backend.workflows.engine.workflow_engine`. The
    orchestrator's ``Plan`` deliberately does not carry retry data: for
    model-generated plans, recovery is the recovery manager's decision, not
    something a plan can demand.
    """

    model_config = ConfigDict(extra="forbid")

    max_attempts: int = Field(default=1, ge=1, le=10)
    backoff_seconds: float = Field(default=1.0, ge=0.0, le=60.0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    max_backoff_seconds: float = Field(default=30.0, ge=0.0, le=300.0)


class WorkflowStepSpec(BaseModel):
    """One step in a workflow YAML file. Mirrors
    :class:`backend.orchestrator.src.plan.PlanStep` loosely - the actual
    ``PlanStep`` is constructed (and validated) by ``WorkflowManager``."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    kind: str
    name: str | None = None
    description: str = ""
    arguments: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    timeout_seconds: float | None = None
    requires_approval: bool = False

    #: Optional guard expression, evaluated by
    #: :mod:`backend.workflows.engine.condition_evaluator`. A step whose guard
    #: is false is recorded as ``skipped`` - never as ``succeeded``, because a
    #: skipped step produced no output and downstream steps must be able to
    #: tell the difference.
    when: str | None = None

    #: Optional retry declaration. Absent means "attempt once".
    retry: RetrySpec | None = None

    #: If true, a terminal failure of this step does not abort the run. The
    #: run is still reported as ``partial``, never ``succeeded``.
    continue_on_error: bool = False

    # NOTE: `when`, `retry` and `continue_on_error` are engine-level concerns.
    # ``WorkflowManager._compile_step`` reads only the fields it maps onto
    # ``PlanStep`` and ignores these, so adding them here cannot change how a
    # workflow compiles for the orchestrator path.


class WorkflowDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    version: str = "1"
    #: Named agent this workflow prefers, if any (informational; execution
    #: still dispatches per-step).
    agent: str | None = None
    #: Input keys the caller must supply; referenced in steps as
    #: ``{{inputs.<key>}}``.
    inputs: list[str] = Field(default_factory=list)
    steps: list[WorkflowStepSpec] = Field(default_factory=list)
    #: Where this definition came from, for diagnostics ("built-in" or a
    #: file path). Not part of the YAML itself.
    source: str = "unknown"


class WorkflowRegistry:
    """In-memory store of loaded workflow definitions."""

    def __init__(self) -> None:
        self._workflows: dict[str, WorkflowDefinition] = {}

    def register(self, definition: WorkflowDefinition, *, replace: bool = True) -> None:
        if not replace and definition.name in self._workflows:
            raise ValueError(f"workflow '{definition.name}' is already registered")
        self._workflows[definition.name] = definition

    def list(self) -> list[WorkflowDefinition]:
        return list(self._workflows.values())

    def get(self, name: str) -> WorkflowDefinition:
        return self._workflows[name]

    def names(self) -> list[str]:
        return sorted(self._workflows)

    def __contains__(self, name: object) -> bool:
        return name in self._workflows

    def __len__(self) -> int:
        return len(self._workflows)


__all__ = [
    "RetrySpec",
    "WorkflowDefinition",
    "WorkflowRegistry",
    "WorkflowStepSpec",
]
