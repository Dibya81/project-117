"""HTTP middleware layers, applied at the API boundary.

Order matters. They are added in ``create_app`` so that the effective
request path is:

1. :class:`~backend.api.src.middleware.rate_limit.RateLimitMiddleware` — shed
   load before doing any work (only active when configured).
2. :class:`~backend.api.src.middleware.auth.PrincipalMiddleware` — resolve
   identity, reject bad credentials with 401.
3. :class:`~backend.api.src.middleware.permissions.RoutePermissionMiddleware`
   — refuse paths the caller's roles do not carry (defence in depth; the
   handlers still enforce their own permission).
4. :class:`~backend.api.src.middleware.audit.RequestAuditMiddleware` — record
   mutating requests, including refusals and crashes.

Metrics are recorded by ``backend.observability.metrics.RequestMetricsMiddleware``.
"""

from backend.api.src.middleware.audit import RequestAuditMiddleware
from backend.api.src.middleware.auth import PUBLIC_PATHS, PrincipalMiddleware, is_public
from backend.api.src.middleware.permissions import (
    ROUTE_PERMISSIONS,
    RoutePermissionMiddleware,
    required_permission,
)
from backend.api.src.middleware.rate_limit import RateLimitMiddleware, TokenBucket

__all__ = [
    "PUBLIC_PATHS",
    "ROUTE_PERMISSIONS",
    "PrincipalMiddleware",
    "RateLimitMiddleware",
    "RequestAuditMiddleware",
    "RoutePermissionMiddleware",
    "TokenBucket",
    "is_public",
    "required_permission",
]
