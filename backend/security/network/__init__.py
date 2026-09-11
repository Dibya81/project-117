"""Network security: egress policy and the record of what it decided.

Import layout note. :mod:`backend.security.network.network_monitor` is
standard-library only and is re-exported eagerly, because
:mod:`backend.security.egress` imports it on the request path -- an eager
import of the policy here would close that loop into a cycle. The policy
surface is therefore resolved lazily through :pep:`562` ``__getattr__``, so
``from backend.security.network import EgressPolicy`` still works for callers
while the import graph stays acyclic.
"""

# pyright: reportUnsupportedDunderAll=false
# The lazy exports below are real at runtime (PEP 562 __getattr__), but pyright
# cannot see through __getattr__ and reports each name in __all__ as missing.
# The surface is exercised by tests/unit/test_egress*.py, so this is a static
# analysis limitation rather than a broken export.

from __future__ import annotations

from typing import Any

from backend.security.network.network_monitor import (
    MONITOR,
    EgressDecision,
    NetworkMonitor,
    record_decision,
    summary,
)

_LAZY = {
    "EgressBlocked",
    "EgressGuardSyncTransport",
    "EgressGuardTransport",
    "EgressPolicy",
    "check_and_record",
    "guarded_async_client",
    "policy_from_settings",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        from backend.security.network import egress_policy

        return getattr(egress_policy, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | _LAZY)


__all__ = [
    "MONITOR",
    "EgressBlocked",
    "EgressDecision",
    "EgressGuardSyncTransport",
    "EgressGuardTransport",
    "EgressPolicy",
    "NetworkMonitor",
    "check_and_record",
    "guarded_async_client",
    "policy_from_settings",
    "record_decision",
    "summary",
]
