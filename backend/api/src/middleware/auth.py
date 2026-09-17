"""Identity middleware.

``security/auth.py`` resolves and caches the caller's identity, and the route
handlers depend on it via ``deps.get_principal``. That works, but it had one
rough edge: an invalid API key raised :class:`AuthenticationError` inside a
dependency and nothing converted that into a clean ``401`` — the caller saw a
``500``.

This middleware resolves identity at the boundary instead, so:

* a missing or wrong credential answers ``401`` with a stable error body,
* the resolved principal is attached to ``request.state`` once per request,
* unauthenticated *access* is still allowed when ``P117_AUTH_REQUIRED`` is
  false — anonymous is a supported mode on a single-user install, a bad
  credential is not.

It does not decide *what* the caller may do. That is RBAC's job, enforced in
the handlers (and, as defence in depth, in ``permissions.py``).
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.security.auth import AuthenticationError, principal_from_request

logger = logging.getLogger(__name__)

#: Paths that must stay reachable without any credential: liveness checks and
#: the API description a client needs before it can authenticate at all.
#:
#: The four ``/api/v1`` entries are the mobile client's pre-authentication
#: surface. A phone cannot present a token before it has logged in, so
#: enrolment, login and refresh must be reachable, and the mobile health probe
#: is a liveness check like ``/health``. Everything else under ``/api/v1``
#: requires a verified bearer token (see ``requires_mobile_token``).
PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/docs/oauth2-redirect",
        "/api/v1/health",
        "/api/v1/auth/enroll",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
    }
)

#: Prefix of the person-authenticated mobile surface.
MOBILE_API_PREFIX = "/api/v1/"


def is_public(path: str) -> bool:
    return path in PUBLIC_PATHS


def requires_mobile_token(path: str) -> bool:
    """True for a ``/api/v1`` path that is not in ``PUBLIC_PATHS``.

    The console may run with ``P117_AUTH_REQUIRED=false``, where an anonymous
    caller is a valid ``operator``. That local-trust mode must not leak onto the
    mobile surface: it is reachable from a handset, so an unauthenticated call
    there is always refused, independently of the deployment-wide setting.
    """
    return path.startswith(MOBILE_API_PREFIX)


class PrincipalMiddleware(BaseHTTPMiddleware):
    """Resolve identity once per request; reject bad credentials with 401."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if is_public(request.url.path):
            return await call_next(request)
        try:
            principal = principal_from_request(request)
        except AuthenticationError as exc:
            logger.info("rejected unauthenticated request to %s: %s", request.url.path, exc.message)
            self._record_rejection(request, exc)
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": {"code": exc.reason, "message": exc.message}},
                headers={"WWW-Authenticate": "X-P117-Api-Key"},
            )
        # Cached for the handlers and for the audit/permission middleware, so
        # identity is resolved exactly once per request.
        request.state.principal = principal
        if not principal.authenticated and requires_mobile_token(request.url.path):
            # 401 *before* the permission layer, so a missing token reads as
            # "authenticate" rather than "forbidden". Raised here rather than
            # in a handler so it applies uniformly to every /api/v1 route,
            # including ones added later.
            exc = AuthenticationError("a valid mobile bearer token is required")
            self._record_rejection(request, exc)
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": {"code": exc.reason, "message": exc.message}},
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)

    @staticmethod
    def _record_rejection(request: Request, exc: AuthenticationError) -> None:
        """Audit the refusal here: this layer is outermost, so the audit
        middleware below it never sees a rejected credential."""
        audit = getattr(request.app.state, "audit", None)
        if audit is None:
            return
        try:
            audit.record(
                action="auth.rejected",
                resource_type="endpoint",
                resource_id=request.url.path,
                user="unknown",
                # A rejected credential is a refusal, not an outage - the
                # docstring above already calls it one.
                outcome="refused",
                detail={
                    "method": request.method,
                    "clientAddress": request.client.host if request.client else None,
                },
                error=exc.message,
            )
        except Exception:  # pragma: no cover - auditing must not mask the 401
            logger.warning("audit write failed for rejected request", exc_info=True)


__all__ = ["MOBILE_API_PREFIX", "PUBLIC_PATHS", "PrincipalMiddleware", "is_public", "requires_mobile_token"]
