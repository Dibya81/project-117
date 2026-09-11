"""Boundary audit middleware.

Handlers already write rich, domain-level audit rows ("work_order.created",
"approval.approved"). Those are the useful records. This middleware adds the
complementary one: an HTTP-level trail of every *state-changing* request that
reached the API, including the ones that were refused (401/403/429) and the
ones that crashed — exactly the events a handler-level audit can never write,
because the handler never ran.

Read-only requests are not recorded here; they would drown the log and are
covered by metrics instead.

Set ``P117_AUDIT_HTTP=false`` to disable.
"""

from __future__ import annotations

import logging
import os
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backend.security.rbac import ANONYMOUS_USER

logger = logging.getLogger(__name__)

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: Statuses that mean "the system declined", not "the system broke".
#: 401 unauthenticated, 403 unauthorised, 429 rate limited. Auditing these as
#: failures would make a burst of permission denials indistinguishable from an
#: outage on the Admin dashboard, which is the reason the audit vocabulary
#: separates "refused" from "failure" in the first place.
REFUSAL_STATUSES = frozenset({401, 403, 429})


def _outcome_for(status: int) -> str:
    """Map an HTTP status onto the canonical audit outcome vocabulary."""
    if 200 <= status < 400:
        return "success"
    if status in REFUSAL_STATUSES:
        return "refused"
    return "failure"


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


class RequestAuditMiddleware(BaseHTTPMiddleware):
    """Record every mutating HTTP request, including refusals and failures."""

    def __init__(self, app, *, enabled: bool | None = None) -> None:
        super().__init__(app)
        self.enabled = enabled if enabled is not None else _bool_env("P117_AUDIT_HTTP", True)

    def _audit(self, request: Request):
        return getattr(request.app.state, "audit", None)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self.enabled or request.method.upper() not in MUTATING_METHODS:
            return await call_next(request)
        started = time.monotonic()
        status = 500
        error: str | None = None
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        except Exception as exc:  # noqa: BLE001 - re-raised below after recording
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            audit = self._audit(request)
            if audit is not None:
                principal = getattr(request.state, "principal", None)
                try:
                    audit.record(
                        action=f"http.{request.method.lower()}",
                        resource_type="endpoint",
                        resource_id=request.url.path,
                        user=getattr(principal, "user", ANONYMOUS_USER),
                        outcome=_outcome_for(status),
                        detail={
                            "status": status,
                            "method": request.method,
                            "durationMs": round((time.monotonic() - started) * 1000, 2),
                            "authenticated": bool(getattr(principal, "authenticated", False)),
                            "roles": list(getattr(principal, "roles", ()) or ()),
                        },
                        error=error,
                    )
                except Exception:  # pragma: no cover - auditing must never break a request
                    logger.warning("boundary audit write failed", exc_info=True)


__all__ = ["MUTATING_METHODS", "REFUSAL_STATUSES", "RequestAuditMiddleware"]
