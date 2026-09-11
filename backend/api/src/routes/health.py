"""``GET /health`` — real checks, no pretend.

Reports: app version, database reachability, local model backend reachability
(degrades gracefully — a dead backend is reported, never fatal),
uploads-directory writability, and registered services.
"""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Request
from sqlalchemy import text

from backend import __version__
from backend.api.src.deps import get_settings
from backend.models.gateway import ModelGateway

router = APIRouter(tags=["health"])

_UPTIME_STARTED = time.monotonic()


@router.get("/health")
async def health(request: Request) -> dict:
    settings = get_settings(request)

    database = "ok"
    try:
        session = request.app.state.session_factory()
        try:
            session.execute(text("SELECT 1"))
        finally:
            session.close()
    except Exception as exc:  # pragma: no cover - defensive
        database = f"error: {exc.__class__.__name__}"

    llm = await _check_llm(request.app.state.gateway)
    uploads_writable = _check_uploads_writable(settings.uploads_dir)

    return {
        "status": "ok",
        "version": __version__,
        "environment": settings.environment,
        "uptime_seconds": round(time.monotonic() - _UPTIME_STARTED, 1),
        "database": database,
        "llm": llm,
        "uploads_writable": uploads_writable,
        "services": {
            "opensandbox": {"configured": bool(settings.open_sandbox_base_url)},
        },
    }


async def _check_llm(gateway: ModelGateway) -> dict:
    backend = gateway.names()[0] if gateway.names() else None
    health = await gateway.health()
    running = bool(health.get("running"))
    models: list[str] = []
    if running:
        try:
            by_provider = await gateway.list_models()
            models = sorted({info.id for infos in by_provider.values() for info in infos})
        except Exception:  # pragma: no cover - defensive
            models = []
    return {
        "backend": backend,
        "running": running,
        "models": models,
        "providers": health.get("providers", {}),
    }


def _check_uploads_writable(uploads_dir: Path) -> bool:
    try:
        uploads_dir.mkdir(parents=True, exist_ok=True)
        probe = uploads_dir / ".write_probe"
        probe.write_text("ok")
        probe.unlink()
        return True
    except Exception:
        return False