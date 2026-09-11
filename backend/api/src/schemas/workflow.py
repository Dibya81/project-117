"""Workflow request/response contracts.

One definition, imported by ``routes/workflows.py``, by tests, and by the
OpenAPI export the frontend client is generated from.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: Terminal and non-terminal states a workflow run can report. Mirrors the
#: job state machine in ``backend/jobs/state.py``.
RunStatus = Literal[
    "queued",
    "running",
    "awaiting_approval",
    "succeeded",
    "failed",
    "cancelled",
]


class WorkflowRunRequest(BaseModel):
    """Start a named workflow with a set of typed inputs."""

    model_config = ConfigDict(extra="forbid")

    workflow: str
    inputs: dict = Field(default_factory=dict)


class WorkflowStepView(BaseModel):
    """A single step as reported back to a client."""

    id: str
    name: str
    type: str
    status: RunStatus | Literal["pending", "skipped"] = "pending"
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    requires_approval: bool = False


class WorkflowRunView(BaseModel):
    """Run summary. ``job_id`` links to the job that owns execution, so a
    client polls one place for progress regardless of how the run started."""

    run_id: str
    workflow: str
    status: RunStatus
    job_id: str | None = None
    steps: list[WorkflowStepView] = Field(default_factory=list)
    outputs: dict = Field(default_factory=dict)
    error: str | None = None


__all__ = [
    "RunStatus",
    "WorkflowRunRequest",
    "WorkflowRunView",
    "WorkflowStepView",
]
