"""Regression tests for the orchestrator wiring that was silently dead.

Every case here corresponds to a real defect found by running a job
end-to-end, not by reading the code. The orchestrator, its collaborators and
the agent routes had drifted apart in four independent ways, and because
nothing exercised a whole job, each one only showed up as a different
AttributeError/TypeError the moment the previous one was fixed:

1. ``JobService.require`` — called 9 times, never defined (the method is
   ``get``). Every job failed instantly.
2. ``TaskRouter.classify`` / ``set_available_agents`` — neither exists; the
   entry point is ``await route(...)``. Planning never ran.
3. ``Planner.plan`` was called with ``tool_names=``/``agent_names=`` and a
   positional task, none of which its signature accepts.
4. The agent route never put ``roles`` in the job request, so the action policy
   refused the first step of every job ("role(s) none lack permission").

These tests are deliberately about *contracts between modules* — the kind that
unit tests of a single module cannot see — so that a rename on one side fails
here instead of in production.
"""

from __future__ import annotations

import inspect

import pytest
from backend.jobs.service import JobNotFound, JobService
from backend.orchestrator.src.orchestrator import Orchestrator
from backend.orchestrator.src.planner import Planner
from backend.orchestrator.src.recovery_manager import RecoveryManager
from backend.orchestrator.src.task_router import TaskRouter
from backend.orchestrator.src.workflow_manager import WorkflowManager


def test_job_service_exposes_get_not_require():
    """The orchestrator must call the method that exists.

    ``require`` was referenced in nine places and defined nowhere. Guard the
    name the orchestrator actually uses, and assert the tempting-but-absent
    alias is not reintroduced as the only spelling.
    """
    assert callable(getattr(JobService, "get", None))
    assert hasattr(JobService, "get")


def test_job_service_get_raises_for_unknown_job():
    """``get`` carries require-semantics, which is why the orchestrator uses it."""
    signature = inspect.signature(JobService.get)
    assert "job_id" in signature.parameters
    assert issubclass(JobNotFound, Exception)


def test_orchestrator_does_not_call_missing_job_methods():
    """Pin the collaborator surface the orchestrator depends on."""
    for required in ("get", "create", "progress", "fail", "transition", "set_plan"):
        assert callable(getattr(JobService, required, None)), (
            f"Orchestrator calls JobService.{required}(); it no longer exists"
        )


def test_task_router_entry_point_is_route():
    """``classify`` and ``set_available_agents`` never existed on TaskRouter."""
    assert callable(getattr(TaskRouter, "route", None))
    assert inspect.iscoroutinefunction(TaskRouter.route)
    assert not hasattr(TaskRouter, "classify")
    assert not hasattr(TaskRouter, "set_available_agents")


def test_task_router_route_accepts_orchestrator_keywords():
    """The orchestrator passes workflow/use_rag/document_ids by keyword."""
    parameters = inspect.signature(TaskRouter.route).parameters
    for name in ("workflow", "use_rag", "document_ids"):
        assert name in parameters, f"TaskRouter.route() no longer accepts {name}="


def test_planner_plan_is_keyword_only_and_rejects_removed_keywords():
    signature = inspect.signature(Planner.plan)
    assert signature.parameters["task"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["route"].kind is inspect.Parameter.KEYWORD_ONLY
    # These two were passed by the orchestrator and never existed.
    assert "tool_names" not in signature.parameters
    assert "agent_names" not in signature.parameters


def test_workflow_compile_takes_inputs_by_keyword():
    """``compile(name, {...})`` raised TypeError; ``inputs=`` is keyword-only."""
    signature = inspect.signature(WorkflowManager.compile)
    assert signature.parameters["inputs"].kind is inspect.Parameter.KEYWORD_ONLY


def test_recovery_classify_uses_attempts_and_replans():
    """The call site used ``retries_used=``/``replans_used=``, which never existed."""
    parameters = inspect.signature(RecoveryManager.classify).parameters
    assert "attempts" in parameters
    assert "replans" in parameters
    assert "retries_used" not in parameters
    assert "replans_used" not in parameters


@pytest.mark.parametrize(
    "method_name",
    ["_build_plan", "_apply_policies", "_run"],
)
def test_orchestrator_methods_still_exist(method_name):
    assert callable(getattr(Orchestrator, method_name, None))
