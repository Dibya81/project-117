"""Route permission middleware (defence in depth).

The route handlers are the primary enforcement point — every one of them calls
``require(...)`` with the permission it needs. This middleware is a second,
independent check at the boundary so that a handler added later without an
authorization call still cannot expose an operations write to a viewer.

The table below is the single declarative statement of "what does this path
cost". It is deliberately conservative: only paths listed here are gated, and
the permissions match what the handlers already require, so this layer can
never *widen* access and cannot silently diverge into blocking something the
handler would have allowed.
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.api.src.middleware.auth import is_public
from backend.security.rbac import DEFAULT_ROLE, Principal, permissions_for
from backend.tools.base import Permission

logger = logging.getLogger(__name__)

READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

#: path prefix -> (permission for reads, permission for writes)
#: ``None`` means "this layer does not gate that method" — the handler still does.
ROUTE_PERMISSIONS: tuple[tuple[str, Permission | None, Permission | None], ...] = (
    # The mobile field API. Reads need connector read, writes need connector
    # write, as this layer requires for the operations surfaces; the mobile
    # bearer token resolves to the RBAC ``field`` role, which carries the write
    # right (security/rbac.py). The finer-grained mobile grants
    # (work_orders:update, approvals:decide, …) are enforced in the handlers
    # because they do not exist in the backend's role matrix.
    ("/api/v1", Permission.CONNECTORS_READ, Permission.CONNECTORS_WRITE),
    ("/api/equipment", Permission.CONNECTORS_READ, Permission.CONNECTORS_WRITE),
    ("/api/work-orders", Permission.CONNECTORS_READ, Permission.WORK_ORDERS_WRITE),
    ("/api/analytics", Permission.CONNECTORS_READ, None),
    ("/api/approvals", Permission.CONNECTORS_READ, Permission.JOBS_APPROVE),
    ("/api/documents", Permission.DOCUMENTS_READ, Permission.DOCUMENTS_WRITE),
    ("/api/search", Permission.SEARCH_QUERY, Permission.SEARCH_QUERY),
    ("/api/knowledge", Permission.SEARCH_QUERY, Permission.SEARCH_QUERY),
    ("/api/artifacts", Permission.DOCUMENTS_READ, Permission.ARTIFACTS_WRITE),
    # Materials: reading the domain needs connector read; the only write-shaped
    # calls are seeding demo data and raising a procurement approval, both of
    # which need the operational-record permission. No materials call can place
    # an order — procurement is a request for a human decision.
    ("/api/materials", Permission.CONNECTORS_READ, Permission.WORK_ORDERS_WRITE),
)


def required_permission(method: str, path: str) -> Permission | None:
    """The permission this layer requires for ``method path``, if any.

    Exposed as a plain function so it is unit-testable without a running app
    and so an admin screen can explain why a call was refused.
    """
    for prefix, read_permission, write_permission in ROUTE_PERMISSIONS:
        if path == prefix or path.startswith(prefix + "/"):
            return read_permission if method.upper() in READ_METHODS else write_permission
    return None


class RoutePermissionMiddleware(BaseHTTPMiddleware):
    """Refuse a request whose path needs a permission the caller lacks."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if is_public(path):
            return await call_next(request)
        permission = required_permission(request.method, path)
        if permission is None:
            return await call_next(request)
        principal: Principal | None = getattr(request.state, "principal", None)
        roles = principal.roles if principal else (DEFAULT_ROLE,)
        if permission not in permissions_for(roles):
            logger.info(
                "refused %s %s: role(s) %s lack %s",
                request.method,
                path,
                ",".join(roles) or "none",
                permission.value,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "forbidden",
                        "message": (
                            f"role(s) {', '.join(roles) or 'none'} lack permission "
                            f"'{permission.value}'"
                        ),
                        "permission": permission.value,
                    }
                },
            )
        return await call_next(request)


__all__ = [
    "READ_METHODS",
    "ROUTE_PERMISSIONS",
    "RoutePermissionMiddleware",
    "required_permission",
]
