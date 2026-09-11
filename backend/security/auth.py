"""Request identity (Phase 12).

Answers one question — who is this request acting as — before RBAC decides
what that identity may do. On a single-user on-premise install an
unauthenticated request defaults to ``operator`` (see ``rbac.DEFAULT_ROLE``);
this module is what lets a shared deployment turn that default off with
``P117_AUTH_REQUIRED=true``.

Three headers, no sessions, no JWT: this is a machine-to-machine API key
model, matching the rest of the sovereignty posture (nothing calls out,
nothing needs a token service).

===================  ===============================================
Header               Meaning
===================  ===============================================
X-P117-Api-Key       Shared secret. Required when auth is required.
X-P117-User          Caller identity to attribute audit rows to.
X-P117-Roles         Comma-separated roles from ``rbac.ROLE_PERMISSIONS``.
===================  ===============================================

The API key is compared with :func:`hmac.compare_digest` so a timing attack
cannot narrow it down one byte at a time. A wrong key is always rejected, even
when auth is not required — "optional auth" means anonymous is allowed, not
that a bad credential is quietly ignored.
"""

from __future__ import annotations

import hmac
import logging
from typing import Any, Callable

from starlette.requests import Request

from backend.security.rbac import ANONYMOUS_MAX_ROLES, DEFAULT_ROLE, Principal

logger = logging.getLogger(__name__)

USER_HEADER = "X-P117-User"
ROLES_HEADER = "X-P117-Roles"
API_KEY_HEADER = "X-P117-Api-Key"


class AuthenticationError(PermissionError):
    """The request could not be authenticated. Not approvable, not retryable."""

    reason = "unauthenticated"
    status_code = 401

    def __init__(self, message: str = "authentication required") -> None:
        super().__init__(message)
        self.message = message


def _bearer(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return value


def split_roles(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip().lower() for part in value.split(",") if part.strip())


def _settings_of(request: Request, settings: Any = None) -> Any:
    if settings is not None:
        return settings
    return request.app.state.settings


def principal_from_request(request: Request, *, settings: Any = None) -> Principal:
    """Resolve the caller's identity for one request.

    Behaviour, in order:

    1. ``P117_AUTH_REQUIRED=true`` with no ``P117_AUTH_API_KEY`` configured is
       a misconfiguration — refuse every request rather than accept anything,
       which is the failure mode a missing key would otherwise produce.
    2. A caller-supplied key is *always* checked if a key is configured, even
       when auth is not required — a wrong key is refused, not ignored.
    3. No key supplied and auth is not required: anonymous, capped at
       ``ANONYMOUS_MAX_ROLES`` (admin is never reachable anonymously).
    4. No key supplied and auth is required: refused.
    """
    settings = _settings_of(request, settings)
    auth_required = bool(getattr(settings, "auth_required", False))
    configured_key = getattr(settings, "auth_api_key", "") or ""

    if auth_required and not configured_key:
        raise AuthenticationError(
            "P117_AUTH_REQUIRED=true but P117_AUTH_API_KEY is not set; refusing all "
            "requests rather than accepting an unverifiable one"
        )

    supplied = _bearer(request.headers.get(API_KEY_HEADER) or request.headers.get("Authorization"))
    user = request.headers.get(USER_HEADER)
    roles = split_roles(request.headers.get(ROLES_HEADER))

    if supplied:
        if not configured_key or not hmac.compare_digest(supplied, configured_key):
            raise AuthenticationError("the supplied API key is not valid")
        return Principal(
            user=user or "authenticated",
            roles=roles or (DEFAULT_ROLE,),
            authenticated=True,
        )

    if auth_required:
        raise AuthenticationError(f"missing {API_KEY_HEADER} header")

    # Anonymous, local-trust-boundary path. Capped so an anonymous caller can
    # never reach admin even if it claims to.
    anonymous_roles = tuple(role for role in (roles or (DEFAULT_ROLE,)) if role in ANONYMOUS_MAX_ROLES)
    return Principal(
        user=user or "local",
        roles=anonymous_roles or (DEFAULT_ROLE,),
        authenticated=False,
    )


def get_principal(request: Request) -> Principal:
    """Cached per-request resolution, for use as a FastAPI dependency."""
    cached = getattr(request.state, "principal", None)
    if cached is None:
        cached = principal_from_request(request)
        request.state.principal = cached
    return cached


def require_permission(permission: Any) -> Callable[[Request], Principal]:
    """Dependency factory: 401 if unauthenticated-and-required, 403 if unauthorised."""

    def _dependency(request: Request) -> Principal:
        from backend.security.rbac import AuthorizationError, require

        principal = get_principal(request)
        try:
            require(permission, roles=principal.roles)
        except AuthorizationError:
            raise
        return principal

    return _dependency


def describe(settings: Any) -> dict[str, Any]:
    """Diagnostics for ``GET /health``. Never includes the key itself."""
    return {
        "auth_required": bool(getattr(settings, "auth_required", False)),
        "api_key_configured": bool(getattr(settings, "auth_api_key", "")),
    }
