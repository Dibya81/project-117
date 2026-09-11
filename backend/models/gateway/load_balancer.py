"""Load balancer for multi-instance model backends.

Scope, stated plainly so nobody over-reads this module: it distributes calls
across **several providers already known to serve the same model** (two Ollama
hosts, a vLLM replica pair). It does not probe health — that is
``health_check.py`` — and it does not pick models, which is the router's job.

In the default single-provider deployment this is a pass-through, and
:meth:`LoadBalancer.is_passthrough` says so, so a reader does not assume
balancing is happening where there is nothing to balance.

Not implemented, deliberately: latency-weighted routing and outlier ejection.
Both need a real latency history to be anything other than a guess, and a
plausible-looking guess in a routing layer is worse than an honest
round-robin.
"""

from __future__ import annotations

import itertools
import threading
from contextlib import contextmanager
from typing import Iterator, Sequence

LEAST_IN_FLIGHT = "least_in_flight"
ROUND_ROBIN = "round_robin"
STRATEGIES: tuple[str, ...] = (LEAST_IN_FLIGHT, ROUND_ROBIN)


class NoProviderAvailable(Exception):
    """No candidate provider was offered for the request."""


class LoadBalancer:
    def __init__(self, strategy: str = LEAST_IN_FLIGHT) -> None:
        if strategy not in STRATEGIES:
            raise ValueError(
                f"unknown strategy '{strategy}' (known: {', '.join(STRATEGIES)})"
            )
        self._strategy = strategy
        self._lock = threading.Lock()
        self._in_flight: dict[str, int] = {}
        self._served: dict[str, int] = {}
        self._rr = itertools.count()

    @property
    def strategy(self) -> str:
        return self._strategy

    def is_passthrough(self, candidates: Sequence[str]) -> bool:
        return len(candidates) <= 1

    def choose(self, candidates: Sequence[str]) -> str:
        """Pick a provider name from ``candidates``.

        Ties break on the candidate order given, which keeps the choice
        reproducible for a fixed input instead of depending on dict ordering.
        """
        names = [str(name) for name in candidates if str(name).strip()]
        if not names:
            raise NoProviderAvailable(
                "no provider was offered for this request; the router should "
                "have refused earlier"
            )
        if len(names) == 1:
            return names[0]

        with self._lock:
            if self._strategy == ROUND_ROBIN:
                return names[next(self._rr) % len(names)]
            # least_in_flight
            return min(names, key=lambda name: (self._in_flight.get(name, 0), names.index(name)))

    @contextmanager
    def lease(self, provider_name: str) -> Iterator[str]:
        """Count one in-flight request against ``provider_name``.

        The decrement is in a ``finally`` so a failed request cannot leak a
        permanently "busy" slot — which would eventually starve the provider
        of traffic and look like a mysterious imbalance.
        """
        with self._lock:
            self._in_flight[provider_name] = self._in_flight.get(provider_name, 0) + 1
        try:
            yield provider_name
        finally:
            with self._lock:
                remaining = self._in_flight.get(provider_name, 1) - 1
                if remaining > 0:
                    self._in_flight[provider_name] = remaining
                else:
                    self._in_flight.pop(provider_name, None)
                self._served[provider_name] = self._served.get(provider_name, 0) + 1

    @contextmanager
    def acquire(self, candidates: Sequence[str]) -> Iterator[str]:
        """Choose a provider and hold a lease for the duration of the call."""
        chosen = self.choose(candidates)
        with self.lease(chosen):
            yield chosen

    def in_flight(self) -> dict[str, int]:
        with self._lock:
            return dict(self._in_flight)

    def served_counts(self) -> dict[str, int]:
        with self._lock:
            return dict(self._served)

    def stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "strategy": self._strategy,
                "in_flight": dict(self._in_flight),
                "served": dict(self._served),
                "note": (
                    "counts are per-process; a multi-worker deployment balances "
                    "per worker, not globally"
                ),
            }


__all__ = [
    "LEAST_IN_FLIGHT",
    "ROUND_ROBIN",
    "STRATEGIES",
    "LoadBalancer",
    "NoProviderAvailable",
]
