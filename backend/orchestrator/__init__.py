"""Orchestrator - the central brain (Phase 6).

One request enters, one job is tracked, and every capability is reached through
a named manager rather than by an agent reaching sideways into a subsystem:

``TaskRouter``
    What is being asked for (question, summary, artifact, analysis,
    investigation, workflow, general) and which agent owns it. Keyword rules
    first, a model only as a tie-breaker.
``TaskDecomposer``
    Whether the request is actually several asks, and in what order. Fully
    deterministic - see the module docstring for why a model is not used here.
``Planner``
    Builds a validated ``Plan``. Deterministic templates per intent; a model
    may improve a plan but can never make it invalid, and cannot remove the
    verification step.
``ContextManager``
    Assembles the evidence pack under a token budget, and is the only thing
    that talks to retrieval. Agents receive context; they never fetch it.
``ExecutionManager``
    Runs the plan's dependency waves, dispatching ``retrieve``/``agent``/
    ``tool`` steps, raising ``ApprovalInterrupt`` when a step needs a human
    and ``JobCancelled`` when the job was cancelled.
``AgentManager``
    Instantiates a specialised agent with injected dependencies, and answers
    from context directly when no agent is registered.
``ToolRegistry`` (``backend.tools``)
    The only path to a tool, with permission, approval, timeout and limits
    enforced on every call.
``VerificationManager``
    Runs the checkers after execution and decides whether the job may report
    success. It never asks a model whether the answer is right.
``RecoveryManager``
    Decides retry / replan / gate / fail from the error *reason*, never from
    the message. Policy refusals are never retried.
``WorkflowManager``
    Loads a deterministic YAML workflow into a plan, and may only add
    approval gates, never remove them.

The ordering rule that holds all of it together: the model reasons and writes
content, retrieval supplies evidence, tools do deterministic work, the sandbox
isolates execution, and verification decides what the caller is allowed to see.
"""

from __future__ import annotations

from backend.orchestrator.src.agent_manager import AgentManager
from backend.orchestrator.src.base import EvidenceItem, OrchestratorResult
from backend.orchestrator.src.context_manager import (
    DEFAULT_EVIDENCE_TOKENS,
    MAX_CHUNK_TOKENS,
    ContextManager,
    ContextPack,
)
from backend.orchestrator.src.execution_manager import (
    ApprovalInterrupt,
    ExecutionManager,
    ExecutionState,
    JobCancelled,
)
from backend.orchestrator.src.orchestrator import Orchestrator
from backend.orchestrator.src.plan import (
    MAX_STEP_TIMEOUT_SECONDS,
    MAX_STEPS,
    Plan,
    PlanStep,
    StepOutcome,
)
from backend.orchestrator.src.planner import PLANNER_ROLE, Planner, intent_model_role
from backend.orchestrator.src.recovery_manager import (
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_MAX_REPLANS,
    RecoveryAction,
    RecoveryDecision,
    RecoveryManager,
)
from backend.orchestrator.src.task_decomposer import (
    MAX_SUBTASKS,
    Decomposition,
    SubTask,
    TaskDecomposer,
    decompose,
)
from backend.orchestrator.src.task_router import Intent, Route, TaskRouter
from backend.orchestrator.src.verification_manager import VerificationManager
from backend.orchestrator.src.workflow_manager import (
    WorkflowError,
    WorkflowManager,
    WorkflowNotFound,
)

__all__ = [
    "AgentManager",
    "ApprovalInterrupt",
    "ContextManager",
    "ContextPack",
    "DEFAULT_EVIDENCE_TOKENS",
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_MAX_REPLANS",
    "Decomposition",
    "EvidenceItem",
    "ExecutionManager",
    "ExecutionState",
    "Intent",
    "JobCancelled",
    "MAX_CHUNK_TOKENS",
    "MAX_STEPS",
    "MAX_STEP_TIMEOUT_SECONDS",
    "MAX_SUBTASKS",
    "Orchestrator",
    "OrchestratorResult",
    "PLANNER_ROLE",
    "Plan",
    "PlanStep",
    "Planner",
    "RecoveryAction",
    "RecoveryDecision",
    "RecoveryManager",
    "Route",
    "StepOutcome",
    "SubTask",
    "TaskDecomposer",
    "TaskRouter",
    "VerificationManager",
    "WorkflowError",
    "WorkflowManager",
    "WorkflowNotFound",
    "decompose",
    "intent_model_role",
]
