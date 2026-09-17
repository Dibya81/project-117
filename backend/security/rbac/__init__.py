"""Roles, permissions and the caller identity (Phase 12).

This is the answer to "who is allowed to do this", asked by the tool registry
before any handler runs. It is small on purpose: four roles, a fixed map to
the permissions declared in ``backend.tools.base``, and no way for a request
to grant itself anything.

=========  =====================================================
Role       Can
=========  =====================================================
viewer     read documents, run searches
analyst    + generate artifacts, execute sandboxed code
operator   + upload/delete documents, approve parked jobs
admin      everything
=========  =====================================================

On a single-user on-premise install an unauthenticated request is treated as
``operator``: the machine is the trust boundary and the product would be
unusable otherwise. It is never treated as ``admin``, so the destructive and
external surface still needs a real identity. Setting
``P117_AUTH_REQUIRED=true`` refuses anonymous requests outright, which is what
a shared deployment should do.

What this module deliberately does not do: consult the sandbox, decide
whether an action needs a human, or write audit rows. Those are
``approvals.py``, the registry, and ``audit.py`` respectively - one question
per module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from backend.tools.base import Permission

#: Role name used for a request with no authenticated principal.
DEFAULT_ROLE = "operator"

#: Recorded as the actor for anonymous local calls, so audit rows never show
#: an empty user.
ANONYMOUS_USER = "local"

#: Roles an unauthenticated caller may claim via X-P117-Roles (Phase 12).
#: Admin is deliberately excluded: the destructive and external surface
#: always needs a real, authenticated identity, even on a trusted machine.
ANONYMOUS_MAX_ROLES: frozenset[str] = frozenset({"viewer", "analyst", "operator"})

VIEWER_PERMISSIONS: frozenset[Permission] = frozenset(
    {Permission.DOCUMENTS_READ, Permission.SEARCH_QUERY}
)

ANALYST_PERMISSIONS: frozenset[Permission] = VIEWER_PERMISSIONS | {
    Permission.ARTIFACTS_WRITE,
    Permission.CODE_EXECUTE,
    Permission.CONNECTORS_READ,
}

OPERATOR_PERMISSIONS: frozenset[Permission] = ANALYST_PERMISSIONS | {
    Permission.DOCUMENTS_WRITE,
    Permission.WORK_ORDERS_WRITE,
    Permission.JOBS_APPROVE,
}

#: The role a mobile bearer-token principal acts as. It is ``operator`` plus the
#: connector-write right the ``/api/v1`` boundary gate requires (see
#: ``middleware/permissions.py``). It is a distinct role rather than a widening
#: of ``operator`` so the deliberate separation between advancing a record in
#: *this* system (``WORK_ORDERS_WRITE``) and pushing into an external system of
#: record (``CONNECTORS_WRITE``) is preserved for every console caller. The
#: phone's own vocabulary is finer-grained still and is checked separately by
#: the mobile handlers (see ``security/mobile_roles.py``).
FIELD_PERMISSIONS: frozenset[Permission] = OPERATOR_PERMISSIONS | {
    Permission.CONNECTORS_WRITE,
}

#: Role -> permissions. ``admin`` is derived from the enum so a new permission
#: is never accidentally unreachable.
ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "viewer": VIEWER_PERMISSIONS,
    "analyst": ANALYST_PERMISSIONS,
    "operator": OPERATOR_PERMISSIONS,
    "field": FIELD_PERMISSIONS,
    "admin": frozenset(Permission),
}


class AuthorizationError(PermissionError):
    """The caller may not perform this action. Not approvable, not retryable."""

    reason = "forbidden"

    def __init__(self, message: str, *, permission: Permission | None = None) -> None:
        super().__init__(message)
        self.permission = permission.value if permission else None


@dataclass(frozen=True)
class Principal:
    """The identity a request acts as.

    Immutable: a tool cannot widen the caller's rights midway through a job by
    mutating the context it was handed.
    """

    user: str = ANONYMOUS_USER
    roles: tuple[str, ...] = (DEFAULT_ROLE,)
    authenticated: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def permissions(self) -> frozenset[Permission]:
        return permissions_for(self.roles)

    def has(self, permission: Permission) -> bool:
        return permission in self.permissions

    def to_dict(self) -> dict[str, Any]:
        return {
            "user": self.user,
            "roles": list(self.roles),
            "authenticated": self.authenticated,
            "permissions": sorted(p.value for p in self.permissions),
        }


def permissions_for(roles: Iterable[str]) -> frozenset[Permission]:
    """Union of the permissions of every recognised role.

    Unknown role names contribute nothing. They are ignored rather than
    rejected so a future role in a token cannot lock a user out, but they can
    never grant anything either.
    """
    granted: set[Permission] = set()
    for role in roles or ():
        granted |= ROLE_PERMISSIONS.get(str(role).strip().lower(), frozenset())
    return frozenset(granted)


def principal_from_roles(
    user: str | None,
    roles: Iterable[str] | None,
    *,
    authenticated: bool = False,
) -> Principal:
    resolved = tuple(str(role).strip().lower() for role in (roles or ()) if str(role).strip())
    return Principal(
        user=user or ANONYMOUS_USER,
        roles=resolved or (DEFAULT_ROLE,),
        authenticated=authenticated,
    )


def authorize(permission: Permission, *, roles: Iterable[str] | None) -> bool:
    return permission in permissions_for(roles or (DEFAULT_ROLE,))


def require(permission: Permission, *, roles: Iterable[str] | None) -> None:
    """Raise :class:`AuthorizationError` unless the roles carry ``permission``."""
    if not authorize(permission, roles=roles):
        held = sorted(set(roles or (DEFAULT_ROLE,)))
        raise AuthorizationError(
            f"role(s) {', '.join(held) or 'none'} lack permission '{permission.value}'",
            permission=permission,
        )
