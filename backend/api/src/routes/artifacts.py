"""Artifact endpoints (PDF/DOCX/PPTX/XLSX generation, Phase 10/12).

``POST /generate`` is a direct, synchronous call for ad-hoc generation from a
validated spec (see ``deliverables/spec.py``); a job's own artifact steps go
through this same :class:`ArtifactService` in-process from
``ExecutionManager``, not through HTTP. Never returns raw model bytes — the
spec is validated, then rendered in the sandbox, then hashed and verified
before this returns.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.src.deps import get_artifacts, get_principal
from backend.deliverables.service import ArtifactError, ArtifactNotFound, ArtifactService
from backend.security.rbac import Principal

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


class ArtifactGenerateRequest(BaseModel):
    kind: str = Field(pattern="^(pdf|docx|pptx|xlsx)$")
    content: dict = Field(default_factory=dict)  # structured ArtifactSpec payload
    filename: str | None = None


@router.post("/generate")
async def generate_artifact(
    payload: ArtifactGenerateRequest,
    principal: Principal = Depends(get_principal),
    artifacts: ArtifactService = Depends(get_artifacts),
) -> dict:
    try:
        return await artifacts.generate(
            spec=payload.content,
            artifact_type=payload.kind,
            user=principal.user,
            filename=payload.filename,
        )
    except ArtifactError as exc:
        # A rejected spec or a failed sandbox render is a 400, not a 500 —
        # the service, not the API layer, already decided this call failed.
        raise HTTPException(status_code=400, detail={"reason": exc.reason, "message": str(exc)}) from exc


@router.get("")
def list_artifacts(
    job_id: str | None = None,
    artifacts: ArtifactService = Depends(get_artifacts),
) -> dict:
    records = artifacts.list(job_id=job_id)
    return {"total": len(records), "artifacts": records}


@router.get("/{artifact_id}")
def get_artifact(
    artifact_id: str,
    artifacts: ArtifactService = Depends(get_artifacts),
) -> dict:
    try:
        return artifacts.get(artifact_id)
    except ArtifactNotFound as exc:
        raise HTTPException(status_code=404, detail="artifact not found") from exc