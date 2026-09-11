"""Job endpoints (Phase 6/12).

The orchestrator runs a job on a background thread once it is spawned
(see api/agents.py and orchestrator/orchestrator.py); this router only
reads and advances that job's persisted state. It never runs a plan step
itself.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.api.src.deps import get_jobs, get_orchestrator, get_principal
from backend.jobs.service import ConcurrentJobUpdate, JobNotFound, JobService
from backend.orchestrator import Orchestrator
from backend.security.rbac import AuthorizationError, Principal, require
from backend.tools.base import Permission

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobApprovalRequest(BaseModel):
    note: str = ""


class JobRejectionRequest(BaseModel):
    reason: str = "rejected by reviewer"


@router.get("")
def list_jobs(
    state: str | None = None,
    limit: int = 50,
    offset: int = 0,
    principal: Principal = Depends(get_principal),
    jobs: JobService = Depends(get_jobs),
) -> dict:
    # Non-admins only ever see their own jobs; an operator's job history is
    # not another operator's business.
    user_filter = None if "admin" in principal.roles else principal.user
    rows = jobs.list(user=user_filter, state=state, limit=limit, offset=offset)
    return {"total": len(rows), "jobs": rows}


@router.get("/{job_id}")
def get_job(job_id: str, jobs: JobService = Depends(get_jobs)) -> dict:
    try:
        return jobs.get(job_id)
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc


@router.get("/{job_id}/events")
def get_job_events(
    job_id: str,
    after: int = Query(default=0),
    limit: int = Query(default=500),
    jobs: JobService = Depends(get_jobs),
) -> dict:
    try:
        events = jobs.events(job_id, after=after, limit=limit)
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    return {"total": len(events), "events": events}


@router.post("/{job_id}/approve")
async def approve_job(
    job_id: str,
    payload: JobApprovalRequest,
    principal: Principal = Depends(get_principal),
    jobs: JobService = Depends(get_jobs),
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> dict:
    # `async` for the same reason as agents.run_agent: `Orchestrator.spawn`
    # calls `asyncio.create_task`, which needs a running loop. When this
    # handler was sync, FastAPI ran it in a worker thread, so approving a
    # parked job raised RuntimeError and the job never resumed.
    #
    # A human approval gate is only meaningful if the approver is actually
    # authorized to approve jobs, not merely authenticated.
    try:
        require(Permission.JOBS_APPROVE, roles=principal.roles)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        result = await asyncio.to_thread(
            jobs.approve, job_id, user=principal.user, note=payload.note
        )
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    except ConcurrentJobUpdate as exc:
        raise HTTPException(status_code=409, detail="job is not awaiting approval") from exc
    # Resume execution from the parked step now that a human has signed off.
    orchestrator.spawn(job_id)
    return result


@router.post("/{job_id}/reject")
def reject_job(
    job_id: str,
    payload: JobRejectionRequest,
    principal: Principal = Depends(get_principal),
    jobs: JobService = Depends(get_jobs),
) -> dict:
    try:
        require(Permission.JOBS_APPROVE, roles=principal.roles)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        return jobs.reject(job_id, user=principal.user, reason=payload.reason)
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    except ConcurrentJobUpdate as exc:
        raise HTTPException(status_code=409, detail="job is not awaiting approval") from exc


@router.post("/{job_id}/cancel")
def cancel_job(
    job_id: str,
    principal: Principal = Depends(get_principal),
    jobs: JobService = Depends(get_jobs),
) -> dict:
    try:
        return jobs.cancel(job_id, reason=f"cancelled by {principal.user}")
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
