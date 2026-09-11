"""Agent endpoints.

``GET /api/agents`` lists registered agents from the registry. ``POST
/api/agents/run`` (Phase 12) creates a job and hands it to the orchestrator,
which drives it as a background asyncio task; the caller polls ``GET
/api/jobs/{id}`` (or streams ``/api/jobs/{id}/events``) for progress instead
of blocking on this request.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from backend.api.src.deps import get_jobs, get_orchestrator, get_principal
from backend.jobs.service import JobService
from backend.orchestrator import Orchestrator
from backend.security.rbac import Principal

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentRunRequest(BaseModel):
    agent: str
    task: str = Field(min_length=1)
    document_ids: list[str] | None = None


@router.get("")
def list_agents(request: Request) -> dict:
    registry = request.app.state.agents
    agents = [spec.model_dump() for spec in registry.list()]
    return {"total": len(agents), "agents": agents}


@router.post("/run")
async def run_agent(
    payload: AgentRunRequest,
    principal: Principal = Depends(get_principal),
    jobs: JobService = Depends(get_jobs),
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> dict:
    # This handler must be `async` so it executes on the event loop.
    # `Orchestrator.spawn` schedules the run with `asyncio.create_task`, which
    # raises RuntimeError("no running event loop") inside a sync handler
    # (FastAPI runs those in a worker thread), so every run request 500'd.
    #
    # Job creation and the orchestrator hand-off are separate steps on
    # purpose: `create` persists the QUEUED row (so `GET /api/jobs/{id}`
    # works even if the process restarts before the task starts), then
    # `spawn` does the actual planning/execution/verification loop. SQLite
    # writes are blocking, so they are pushed off the loop.
    #
    # `roles` is carried in the request, not on the row, because that is where
    # the orchestrator reads it from (`request.get("roles")`). It was missing
    # entirely, so every job ran with no roles and the action policy refused
    # its first step ("role(s) none lack permission 'search:query'") — the job
    # could never get past retrieval. The approved-resume path re-reads the
    # same stored request, so it inherits these roles.
    #
    # `agent` is recorded for the audit trail, but it does not select the
    # worker: the orchestrator routes on task text via TaskRouter, which is
    # what decides `route.agent`. Naming an agent here does not override that.
    job = await asyncio.to_thread(
        jobs.create,
        task=payload.task,
        kind="agent",
        user=principal.user,
        request={
            "agent": payload.agent,
            "document_ids": payload.document_ids or [],
            "roles": list(principal.roles),
        },
    )
    orchestrator.spawn(job["id"])
    return job