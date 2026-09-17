"""The ``/api/v1`` mobile field API.

One router, one prefix, four cohesive sub-surfaces: authentication, field
operations, workflow (tasks/approvals/notifications) and knowledge. The path
matches the Android client's configured base URL exactly
(``http://<host>:8000/api/v1/``), so no query, path or payload has to change on
the phone.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.api.src.routes.health import health as _console_health
from backend.api.src.routes.mobile import auth, field, knowledge, workflow

router = APIRouter(prefix="/api/v1", tags=["mobile"])
router.include_router(auth.router)
router.include_router(field.router)
router.include_router(workflow.router)
router.include_router(knowledge.router)


@router.get("/health")
async def health(request: Request) -> dict:
    """Liveness for the mobile client, delegating to the console health check.

    The client only reads ``status`` (``HealthResponse``). Running the same
    check the console runs — database, model backend, uploads writability —
    means the phone and the operator are never told two different stories about
    whether the backend is healthy.
    """
    result = await _console_health(request)
    return {"status": result.get("status", "unknown")}


__all__ = ["router"]
