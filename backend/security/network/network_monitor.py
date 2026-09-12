"""In-process record of outbound network decisions.

The egress policy decides; this module remembers. Without it, "zero external
egress" is a claim that can only be checked by reading code, which is exactly
the kind of unverifiable assertion this project is supposed to avoid. With it,
the Admin security view and the ``/api/health`` payload can show what the
process has actually tried to reach.

Deliberately small and dependency-free:

* Standard library only, so importing it can never fail because ``httpx`` or
  a driver is missing. The egress transport imports it on a hot path.
* Bounded memory. A ring buffer of the most recent decisions plus per-host
  counters, so a retry storm cannot exhaust the heap.
* Hosts and schemes only. A URL's path and query can carry document content,
  so neither is ever recorded.

This is process-local, like the rate limiter. Across replicas the numbers are
per-process, and that is stated wherever they are surfaced.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Literal

Decision = Literal["allowed", "blocked"]

#: How many individual decisions to keep. Enough to explain a failure that
#: just happened; not enough to matter to memory.
DEFAULT_HISTORY = 200


@dataclass(frozen=True)
class EgressDecision:
    """One allow/deny outcome. Host and scheme only, never a full URL."""

    host: str
    scheme: str
    decision: Decision
    at: float
    reason: str | None = None
    #: True when the destination was loopback. A local model server is not
    #: "external", and conflating the two inflates the very number that proves
    #: the sovereignty claim.
    local: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "scheme": self.scheme,
            "decision": self.decision,
            "at": self.at,
            "reason": self.reason,
            "local": self.local,
        }


class NetworkMonitor:
    """Thread-safe counters and recent history for egress decisions."""

    def __init__(self, *, history: int = DEFAULT_HISTORY) -> None:
        if history < 1:
            raise ValueError("history must be at least 1")
        self._lock = threading.Lock()
        self._history: deque[EgressDecision] = deque(maxlen=history)
        self._allowed: dict[str, int] = {}
        self._blocked: dict[str, int] = {}
        # Four counters rather than two: the security view must be able to say
        # "how much tried to leave" separately from "how much did not leave but
        # still had to be stopped".
        self._external_allowed = 0
        self._external_blocked = 0
        self._local_allowed = 0
        self._local_blocked = 0
        self._started = time.time()

    def record(
        self,
        *,
        host: str | None,
        scheme: str | None,
        decision: Decision,
        reason: str | None = None,
        local: bool = False,
    ) -> EgressDecision:
        entry = EgressDecision(
            host=(host or "?").lower(),
            scheme=(scheme or "?").lower(),
            decision=decision,
            at=time.time(),
            reason=reason,
            local=local,
        )
        with self._lock:
            self._history.append(entry)
            target = self._allowed if decision == "allowed" else self._blocked
            target[entry.host] = target.get(entry.host, 0) + 1
            if local:
                if decision == "allowed":
                    self._local_allowed += 1
                else:
                    self._local_blocked += 1
            elif decision == "allowed":
                self._external_allowed += 1
            else:
                self._external_blocked += 1
        return entry

    def allowed(self, host: str | None, scheme: str | None = None, *, local: bool = False) -> EgressDecision:
        return self.record(host=host, scheme=scheme, decision="allowed", local=local)

    def blocked(
        self,
        host: str | None,
        scheme: str | None = None,
        reason: str | None = None,
        *,
        local: bool = False,
    ) -> EgressDecision:
        return self.record(
            host=host,
            scheme=scheme,
            decision="blocked",
            reason=reason or "denied by egress policy",
            local=local,
        )

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Most recent decisions, newest first."""
        with self._lock:
            items = list(self._history)
        return [entry.as_dict() for entry in reversed(items)][: max(0, limit)]

    def counts(self) -> dict[str, dict[str, int]]:
        with self._lock:
            return {
                "allowed": dict(self._allowed),
                "blocked": dict(self._blocked),
            }

    def totals(self) -> dict[str, int]:
        with self._lock:
            return {
                "allowed": sum(self._allowed.values()),
                "blocked": sum(self._blocked.values()),
                "external_allowed": self._external_allowed,
                "external_blocked": self._external_blocked,
                "local_allowed": self._local_allowed,
                "local_blocked": self._local_blocked,
            }

    def summary(self, *, recent: int = 10) -> dict[str, Any]:
        totals = self.totals()
        counts = self.counts()
        return {
            "since": self._started,
            "scope": "this process only",
            "totals": totals,
            # The figure the console reports as "external calls": destinations
            # off this machine that were actually reached. Blocked attempts are
            # reported separately, because a guard that stopped something is
            # evidence the guard works, not evidence of a leak.
            "external_allowed": totals["external_allowed"],
            "external_blocked": totals["external_blocked"],
            "blocked_hosts": sorted(counts["blocked"]),
            "allowed_hosts": sorted(counts["allowed"]),
            "recent": self.recent(recent),
        }

    def reset(self) -> None:
        """Clear all state. For tests; not exposed through the API."""
        with self._lock:
            self._history.clear()
            self._allowed.clear()
            self._blocked.clear()
            self._external_allowed = 0
            self._external_blocked = 0
            self._local_allowed = 0
            self._local_blocked = 0
            self._started = time.time()


#: Process-wide monitor. The egress transport writes here; the API reads it.
#: A module-level singleton rather than an injected dependency because the
#: transport is constructed in several places and threading a monitor through
#: all of them would make it easy to forget one - and a forgotten one is an
#: unobserved egress path.
MONITOR = NetworkMonitor()


def record_decision(
    *,
    host: str | None,
    scheme: str | None,
    decision: Decision,
    reason: str | None = None,
    local: bool = False,
) -> None:
    """Record against the process-wide monitor. Never raises.

    Bookkeeping must not be able to fail a request that the policy allowed,
    so every error here is swallowed deliberately.
    """
    try:
        MONITOR.record(
            host=host, scheme=scheme, decision=decision, reason=reason, local=local
        )
    except Exception:  # noqa: BLE001 - observability must never break traffic
        pass


def summary(*, recent: int = 10) -> dict[str, Any]:
    return MONITOR.summary(recent=recent)


__all__ = [
    "DEFAULT_HISTORY",
    "MONITOR",
    "Decision",
    "EgressDecision",
    "NetworkMonitor",
    "record_decision",
    "summary",
]
