"""Tool execution endpoint (Phase 8 registry, Phase 9 sandbox, Phase 12 auth).

This is a direct, synchronous call into :meth:`ToolRegistry.execute` for
ad-hoc/manual invocation (e.g. an operator testing a tool from a console).
The orchestrator does not use this route — it calls the same registry
in-process from ``ExecutionManager`` as part of a job's plan, where a
tool call is one step among many and its result feeds the next step.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.api.src.deps import (
    get_artifacts,
    get_materials,
    get_operations,
    get_principal,
    get_retrieval,
    get_sandbox,
    get_tools,
)
from backend.deliverables.service import ArtifactService
from backend.rag.service import RetrievalService
from backend.sandbox.service import SandboxService
from backend.security.rbac import Principal
from backend.storage.materials import MaterialsStore
from backend.storage.operations import OperationsStore
from backend.tools.base import ToolContext
from backend.tools.registry import ToolRegistry

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolExecuteRequest(BaseModel):
    tool: str
    arguments: dict = Field(default_factory=dict)
    document_ids: list[str] | None = None


@router.get("")
def list_tools(tools: ToolRegistry = Depends(get_tools)) -> dict:
    specs = tools.list()
    return {"total": len(specs), "tools": specs}


@router.post("/execute")
async def execute_tool(
    payload: ToolExecuteRequest,
    principal: Principal = Depends(get_principal),
    tools: ToolRegistry = Depends(get_tools),
    retrieval: RetrievalService = Depends(get_retrieval),
    sandbox: SandboxService = Depends(get_sandbox),
    artifacts: ArtifactService = Depends(get_artifacts),
    materials: MaterialsStore = Depends(get_materials),
    operations: OperationsStore = Depends(get_operations),
) -> dict:
    context = ToolContext(
        job_id=None,
        user=principal.user,
        roles=list(principal.roles),
        document_ids=payload.document_ids,
        retrieval=retrieval,
        sandbox=sandbox,
        artifacts=artifacts,
        materials=materials,
        operations=operations,
    )
    # `approved=False`: a manual call from this endpoint can never carry a
    # prior human approval, so any execute-or-above risk tool correctly
    # raises ToolApprovalRequired here rather than running. Approving and
    # re-running an execute-risk tool is only possible through the job
    # approval flow (`POST /api/jobs/{id}/approve`), which is what attaches
    # `approved=True` on retry.
    result = await tools.execute(payload.tool, payload.arguments, context)
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)
