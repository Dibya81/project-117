"""``GET /api/models`` — what the local backend serves and how roles resolve.

Real endpoint backed by the model gateway/router. The future frontend uses it
to show users which models are available and which role maps to which model.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.api.src.errors import ServiceUnavailable

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
async def list_models(request: Request) -> dict:
    gateway = request.app.state.gateway
    router = request.app.state.router
    try:
        by_provider = await gateway.list_models()
    except Exception as exc:
        raise ServiceUnavailable(
            f"model backend unreachable: {exc.__class__.__name__}",
            code="provider_unreachable",
        ) from exc

    models: dict[str, list[str]] = {
        provider: [info.id for info in infos] for provider, infos in by_provider.items()
    }
    return {
        "backend": {
            "name": gateway.names()[0] if gateway.names() else None,
            "providers": gateway.names(),
        },
        "models": models,
        "roles": router.role_mapping(),
    }