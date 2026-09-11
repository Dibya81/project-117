"""Deterministic workflow engine.

A workflow is a plan somebody wrote down and reviewed, instead of one a model
produced at request time. This package holds the pieces:

* :mod:`registry` - the definition schema (``WorkflowDefinition``,
  ``WorkflowStepSpec``, ``RetrySpec``) and the in-memory store.
* :mod:`loader` - YAML loading, including the built-in definition pack under
  ``definitions/`` and the deployment overlay.
* :mod:`condition_evaluator` - ``when:`` guards, evaluated with a hand-written
  AST allowlist rather than ``eval``.
* :mod:`retry_manager` - ``retry:`` policy, including the errors that must
  never be retried (permission denied, approval required, argument errors,
  policy refusals).
* :mod:`workflow_state` - run and step state, where ``skipped`` is a distinct
  outcome from ``succeeded``.
* :mod:`step_runner` - one step: guard, approval check, attempts, retries.
  Delegates the actual work to an injected executor.
* :mod:`workflow_engine` - the facade, and the place the two execution paths
  are documented.

The two paths, briefly. ``WorkflowEngine.compile()`` turns a definition into
the orchestrator's ``Plan`` and is the production path - the orchestrator then
owns permissions, approvals, verification and audit. ``WorkflowEngine.run()``
is the engine path, which adds guards, retries and run state, and still
delegates every step to an injected executor. Neither path executes tools
directly from this package.
"""

from backend.workflows.engine.condition_evaluator import (
    ALLOWED_ROOTS,
    ConditionError,
    evaluate,
    referenced_steps,
    validate_expression,
)
from backend.workflows.engine.loader import (
    BUILTIN_DEFINITIONS_DIR,
    WorkflowLoadError,
    load_builtin_definitions,
    load_registry,
    load_workflow_file,
    load_workflows_dir,
)
from backend.workflows.engine.registry import (
    RetrySpec,
    WorkflowDefinition,
    WorkflowRegistry,
    WorkflowStepSpec,
)
from backend.workflows.engine.retry_manager import (
    NON_RETRYABLE_REASONS,
    RETRYABLE_REASONS,
    RetryDecision,
    RetryManager,
    classify,
    is_retryable,
)
from backend.workflows.engine.step_runner import (
    DEFAULT_STEP_TIMEOUT_SECONDS,
    ApprovalNotSupported,
    ExecutorContractError,
    StepExecutor,
    StepInvocation,
    StepResult,
    StepRunner,
    executor_handles_approval,
)
from backend.workflows.engine.workflow_engine import (
    ExecutorRequired,
    ManagerRequired,
    WorkflowEngine,
    WorkflowRunReport,
    WorkflowValidationError,
)
from backend.workflows.engine.workflow_state import (
    InvalidTransition,
    StepRecord,
    WorkflowRunState,
)

__all__ = [
    "ALLOWED_ROOTS",
    "BUILTIN_DEFINITIONS_DIR",
    "DEFAULT_STEP_TIMEOUT_SECONDS",
    "NON_RETRYABLE_REASONS",
    "RETRYABLE_REASONS",
    "ApprovalNotSupported",
    "ConditionError",
    "ExecutorContractError",
    "ExecutorRequired",
    "InvalidTransition",
    "ManagerRequired",
    "RetryDecision",
    "RetryManager",
    "RetrySpec",
    "StepExecutor",
    "StepInvocation",
    "StepRecord",
    "StepResult",
    "StepRunner",
    "WorkflowDefinition",
    "WorkflowEngine",
    "WorkflowLoadError",
    "WorkflowRegistry",
    "WorkflowRunReport",
    "WorkflowRunState",
    "WorkflowStepSpec",
    "WorkflowValidationError",
    "classify",
    "evaluate",
    "executor_handles_approval",
    "is_retryable",
    "load_builtin_definitions",
    "load_registry",
    "load_workflow_file",
    "load_workflows_dir",
    "referenced_steps",
    "validate_expression",
]
