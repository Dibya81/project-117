"""Security: audit, egress policy/enforcement, and (from Phase 12) auth/RBAC/secrets.

Default philosophy: zero external data egress. Nothing here sends document
content anywhere, and as of Phase 0.5 that is enforced in the HTTP transport
layer rather than merely asserted in prose.
"""

from backend.security.egress import (
    EgressBlocked,
    EgressGuardSyncTransport,
    EgressGuardTransport,
    EgressPolicy,
    guarded_async_client,
    policy_from_settings,
)

__all__ = [
    "EgressBlocked",
    "EgressGuardSyncTransport",
    "EgressGuardTransport",
    "EgressPolicy",
    "guarded_async_client",
    "policy_from_settings",
]
