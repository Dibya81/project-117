"""The audit sink the egress path writes to.

The Network Sentinel has two halves, both fed from the *same* decision:

* :mod:`~backend.security.network.network_monitor` — the process-wide counters
  and ring buffer, read by ``/health`` and the Security Events panel.
* :mod:`~backend.security.network.sentinel_stream` — the live SSE stream the
  console subscribes to.

Neither of them is the durable audit log. The brief asks for a network attempt
to reach the audit trail (``record_decision() → audit event → SSE``), and the
durable log lives in :class:`~backend.security.audit.AuditService`, which is
constructed with the database and therefore cannot be imported by a module the
httpx transport imports on a hot path.

This module is the one-way seam between them. The API lifespan registers the
service here once; the egress policy reads it (through this module, never by
importing the API). When no audit service has been registered — a unit test
that only exercises the policy, or the embedded engine's process — the egress
path still records and still streams, and the audit write is simply skipped.
That is deliberate: a missing audit sink must never be able to fail a request
the policy allowed, and it must never be silently replaced by one built from
settings the caller did not choose.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger("backend.security.network.audit_sink")


class AuditSink(Protocol):
    """The one method this seam needs. Matches ``AuditService.record``."""

    def record(self, **kwargs: Any) -> Any:  # pragma: no cover - protocol
        ...


_sink: AuditSink | None = None


def register_audit_sink(sink: AuditSink | None) -> None:
    """Attach (or clear) the process-wide audit sink. Called from the lifespan."""
    global _sink
    _sink = sink


def current_audit_sink() -> AuditSink | None:
    return _sink


def record_network_decision(
    *,
    host: str | None,
    scheme: str | None,
    port: int | None,
    decision: str,
    reason: str | None,
    local: bool,
    agent: str | None,
    task_id: str | None,
) -> None:
    """Persist one egress decision. Never raises.

    Called by :func:`backend.security.network.network_monitor.record_decision`,
    which is the single place every allow/block already passes through, so a
    decision cannot reach the stream but miss the audit log.

    What is written and what is not: the destination **host**, port and scheme
    — never the full URL. A URL's path and query can carry document content or
    a query string, and the audit log is durable; the monitor and the stream
    make the same omission for the same reason.
    """
    sink = _sink
    if sink is None:
        return
    blocked = decision != "allowed"
    try:
        sink.record(
            action="network.egress_decision",
            resource_type="network",
            resource_id=host or "unknown",
            outcome="refused" if blocked else "success",
            agent=agent,
            detail={
                "decision": "BLOCK" if blocked else "ALLOW",
                "host": host,
                "scheme": scheme,
                "port": port,
                "local": bool(local),
                "reason": reason,
                "task_id": task_id,
            },
        )
    except Exception:  # noqa: BLE001 - observability must never break traffic
        logger.debug("egress decision could not be audited", exc_info=True)


__all__ = [
    "AuditSink",
    "current_audit_sink",
    "record_network_decision",
    "register_audit_sink",
]
