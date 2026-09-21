"""Workspace endpoints — /api/workspaces.

Workspaces are the top-level containers for a company's knowledge base.
This router handles workspace lifecycle and the knowledge-health dashboard.

GET  /api/workspaces               list all workspaces
POST /api/workspaces               create a workspace
GET  /api/workspaces/default       shortcut: get-or-create the default workspace
GET  /api/workspaces/{id}          get one workspace
DELETE /api/workspaces/{id}        delete workspace (does not delete documents)
GET  /api/workspaces/{id}/health   knowledge health statistics
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.api.src.deps import get_workspaces
from backend.knowledge.workspace_service import WorkspaceNotFound

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str | None = None


@router.get("")
def list_workspaces(request: Request) -> dict:
    svc = get_workspaces(request)
    # Ensure the default workspace always exists so fresh installs have
    # something to show without an explicit create call.
    svc.get_or_create_default()
    return {"workspaces": svc.list()}


@router.post("", status_code=201)
def create_workspace(payload: WorkspaceCreateRequest, request: Request) -> dict:
    svc = get_workspaces(request)
    return svc.create(name=payload.name, description=payload.description)


@router.get("/default")
def get_default_workspace(request: Request) -> dict:
    """Get-or-create the default workspace — safe to call on first run."""
    return get_workspaces(request).get_or_create_default()


@router.get("/{workspace_id}")
def get_workspace(workspace_id: str, request: Request) -> dict:
    try:
        return get_workspaces(request).get(workspace_id)
    except WorkspaceNotFound:
        raise HTTPException(status_code=404, detail=f"workspace '{workspace_id}' not found")


@router.delete("/{workspace_id}", status_code=200)
def delete_workspace(workspace_id: str, request: Request) -> dict:
    svc = get_workspaces(request)
    try:
        svc.delete(workspace_id)
    except WorkspaceNotFound:
        raise HTTPException(status_code=404, detail=f"workspace '{workspace_id}' not found")
    return {"deleted": True, "id": workspace_id}


@router.get("/{workspace_id}/health")
def workspace_health(workspace_id: str, request: Request) -> dict:
    """Return knowledge-base health statistics.

    All counts are computed from the database — no LanceDB round-trip.
    The ``status`` field summarises whether the knowledge base is ready,
    updating, degraded, or empty.
    """
    svc = get_workspaces(request)
    try:
        return svc.health(workspace_id)
    except WorkspaceNotFound:
        raise HTTPException(status_code=404, detail=f"workspace '{workspace_id}' not found")
