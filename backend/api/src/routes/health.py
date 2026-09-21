"""``GET /health`` — real checks, no pretend.

Reports: app version, database reachability, local model backend reachability
(degrades gracefully — a dead backend is reported, never fatal),
uploads-directory writability, and registered services.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from fastapi import APIRouter, Request
from sqlalchemy import text

from backend import __version__
from backend.api.src.deps import get_settings
from backend.models.gateway import ModelGateway
from backend.security.network.network_monitor import summary as network_summary

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
        # Measured, not asserted: the console's system-posture panel needs a
        # storage figure, and the alternative to measuring it is inventing one.
        # A fabricated number reads as a real measurement to an operator, which
        # is worse than reporting that the measurement is unavailable.
        "storage": _storage_usage(settings.uploads_dir),
        # The real egress posture: the policy from configuration, and the
        # process-local record of every outbound decision the guard transport
        # made. Until this was wired the monitor was dead code, so any
        # "external calls" figure would have been a false zero.
        "egress": "denied" if settings.egress_default_deny else "allowlist",
        "network": network_summary(recent=5),
        "services": {
            "opensandbox": {"configured": bool(settings.open_sandbox_base_url)},
        },
    }


def _storage_usage(uploads_dir: Path) -> dict:
    """Disk figures for the volume this service actually writes to."""
    target = uploads_dir if uploads_dir.exists() else uploads_dir.parent
    try:
        usage = shutil.disk_usage(target)
    except OSError:  # pragma: no cover - platform dependent
        return {"available": False, "path": str(target)}
    return {
        "available": True,
        "path": str(target),
        "used_gb": round(usage.used / 1024**3, 2),
        "total_gb": round(usage.total / 1024**3, 2),
        "free_gb": round(usage.free / 1024**3, 2),
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
