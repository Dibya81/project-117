"""Caller identity: who is making this request.

Identity and authorisation are separated on purpose. This package answers
"who is this"; :mod:`backend.security.rbac` answers "may they do it". Keeping
them apart means a change to role arithmetic cannot quietly change how a
principal is established from a request.

The implementations live in :mod:`backend.security.auth` (HTTP request ->
principal) and :mod:`backend.security.rbac` (roles -> permissions). This
module re-exports them explicitly so the identity surface is addressable at
the location the architecture names, and adds :func:`describe_identity`, a
non-sensitive summary used by the Admin view.

Re-exports are explicit rather than ``import *`` so that removing a symbol
upstream breaks here loudly instead of silently shrinking the surface.
"""

from __future__ import annotations

from typing import Any

from backend.security.auth import (
    API_KEY_HEADER,
    ROLES_HEADER,
    USER_HEADER,
    AuthenticationError,
    get_principal,
    principal_from_request,
    require_permission,
    split_roles,
)
from backend.security.rbac import (
    ANONYMOUS_USER,
    DEFAULT_ROLE,
    AuthorizationError,
    Principal,
    permissions_for,
    principal_from_roles,
)


def describe_identity(principal: Principal) -> dict[str, Any]:
    """Non-sensitive summary of a principal.

    Permissions are returned as sorted names so the response is stable
    between calls; an unordered set would make the Admin view flicker and
    would make a response impossible to diff in a test.
    """
    return {
        "user": principal.user,
        "roles": sorted(principal.roles),
        "permissions": sorted(str(p) for p in permissions_for(principal.roles)),
        "anonymous": principal.user == ANONYMOUS_USER,
    }


__all__ = [
    "ANONYMOUS_USER",
    "API_KEY_HEADER",
    "DEFAULT_ROLE",
    "ROLES_HEADER",
    "USER_HEADER",
    "AuthenticationError",
    "AuthorizationError",
    "Principal",
    "describe_identity",
    "get_principal",
    "permissions_for",
    "principal_from_request",
    "principal_from_roles",
    "require_permission",
    "split_roles",
]
