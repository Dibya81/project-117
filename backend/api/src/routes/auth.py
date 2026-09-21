"""Identity endpoints (Phase 12 surface).

This deployment uses a header-based, machine-to-machine identity model (see
``backend/security/auth.py``): a shared API key plus caller identity and roles
headers. There is no token service, no session store and no external identity
provider — that is a sovereignty decision, not an omission.

So these endpoints are deliberately narrow and honest:

* ``GET /api/auth/me`` — who the backend thinks you are, and exactly what that
  identity may do. The frontend uses this to drive role-aware UI instead of
  guessing client-side.
* ``GET /api/auth/roles`` — the role → permission matrix the backend actually
  enforces, so an admin screen can render capabilities without hardcoding them.
* ``POST /api/auth/session`` — validates a candidate identity (key + requested
  roles) and returns the exact headers to send. It does **not** mint a token;
  it tells you whether those credentials would be accepted and what they grant.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.api.src.deps import get_principal, get_settings
from backend.config import Settings
from backend.security.auth import API_KEY_HEADER, ROLES_HEADER, USER_HEADER
from backend.security.rbac import (
    ANONYMOUS_MAX_ROLES,
    DEFAULT_ROLE,
    ROLE_PERMISSIONS,
    Principal,
    permissions_for,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roles: list[str] = Field(default_factory=list, description="roles the caller wants to act with")


def _headers_doc() -> dict:
    return {
        "apiKey": API_KEY_HEADER,
        "user": USER_HEADER,
        "roles": ROLES_HEADER,
    }


@router.get("/me")
def whoami(
    principal: Principal = Depends(get_principal),
    settings: Settings = Depends(get_settings),
) -> dict:
    return {
        "user": principal.user,
        "roles": list(principal.roles),
        "authenticated": principal.authenticated,
        "permissions": sorted(p.value for p in principal.permissions),
        "authRequired": bool(settings.auth_required),
        "defaultRole": DEFAULT_ROLE,
        "headers": _headers_doc(),
    }


@router.get("/roles")
def roles(principal: Principal = Depends(get_principal)) -> dict:
    """The matrix the handlers enforce — read straight out of RBAC, not a copy."""
    return {
        "roles": {role: sorted(p.value for p in perms) for role, perms in ROLE_PERMISSIONS.items()},
        "defaultRole": DEFAULT_ROLE,
        "anonymousMaxRoles": sorted(ANONYMOUS_MAX_ROLES),
        "callerRoles": list(principal.roles),
    }


@router.post("/session")
def check_session(
    payload: SessionRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Validate credentials and report what they grant. No token is issued.

    Reaching this handler already means authentication passed: an invalid API
    key is rejected in ``get_principal`` before the body is read.
    """
    requested = tuple(r.strip().lower() for r in payload.roles if r.strip())
    unknown = [role for role in requested if role not in ROLE_PERMISSIONS]
    if principal.authenticated:
        granted = requested or tuple(principal.roles)
    else:
        # An anonymous caller cannot self-elevate past the anonymous ceiling.
        granted = tuple(
            role for role in (requested or principal.roles) if role in ANONYMOUS_MAX_ROLES
        )
    effective = tuple(role for role in granted if role in ROLE_PERMISSIONS)
    return {
        "accepted": True,
        "tokenIssued": False,
        "model": "header_api_key",
        "user": principal.user,
        "authenticated": principal.authenticated,
        "requestedRoles": list(requested),
        "unknownRoles": unknown,
        "effectiveRoles": list(effective),
        "permissions": sorted(p.value for p in permissions_for(effective)),
        "authRequired": bool(settings.auth_required),
        "sendHeaders": {
            API_KEY_HEADER: "<your api key>" if settings.auth_required else "<optional>",
            USER_HEADER: principal.user,
            ROLES_HEADER: ",".join(effective) or DEFAULT_ROLE,
        },
        "clientAddress": request.client.host if request.client else None,
    }
