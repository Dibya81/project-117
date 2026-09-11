"""Workflow endpoints.

``GET /api/workflows`` lists registered workflow definitions (empty until
Phase 15 loads YAMLs). ``POST /api/workflows/run`` is a real route with
explicit 501 until the workflow engine exists.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.api.src.errors import EndpointNotImplemented
from backend.api.src.schemas.workflow import WorkflowRunRequest

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("")
def list_workflows(request: Request) -> dict:
    registry = request.app.state.workflows
    workflows = [w.model_dump() for w in registry.list()]
    return {"total": len(workflows), "workflows": workflows}


@router.post("/run")
def run_workflow(payload: WorkflowRunRequest, request: Request) -> dict:
    raise EndpointNotImplemented(
        "The workflow engine lands in Phase 15 (steps, retries, approval gates)",
        phase=15,
    )