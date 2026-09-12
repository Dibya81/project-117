"""Egress policy surface for the ``security/network`` package.

The implementation lives in :mod:`backend.security.egress`, which is where it
has always been and where the transports that enforce it are defined. This
module exists because the network security surface is addressed as
``backend.security.network`` in the architecture, and a caller looking there
should find the policy rather than a comment pointing elsewhere.

It re-exports explicitly (never ``import *``) and adds one thing of its own:
:func:`check_and_record`, which combines the policy decision with the
:mod:`~backend.security.network.network_monitor` bookkeeping for call sites
that consult the policy directly instead of going through a guarded transport.
"""

from __future__ import annotations

from urllib.parse import urlparse

from backend.security.egress import (
    EgressBlocked,
    EgressGuardSyncTransport,
    EgressGuardTransport,
    EgressPolicy,
    guarded_async_client,
    policy_from_settings,
)
from backend.security.network.network_monitor import record_decision


def check_and_record(policy: EgressPolicy, url: str) -> None:
    """Enforce ``policy`` for ``url`` and record the outcome.

    Raises :class:`EgressBlocked` when the policy denies the URL. Use this
    instead of :meth:`EgressPolicy.check` when the call site is not behind a
    guarded transport, so the decision still shows up in the security view.
    """
    parsed = urlparse(url)
    allowed = policy.allows(url)
    record_decision(
        host=parsed.hostname,
        scheme=parsed.scheme,
        decision="allowed" if allowed else "blocked",
        reason=None if allowed else "denied by egress policy",
        local=policy.is_local(parsed.hostname),
    )
    if not allowed:
        raise EgressBlocked(url)


__all__ = [
    "EgressBlocked",
    "EgressGuardSyncTransport",
    "EgressGuardTransport",
    "EgressPolicy",
    "check_and_record",
    "guarded_async_client",
    "policy_from_settings",
]
