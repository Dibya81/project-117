"""Network egress policy - and, as of Phase 0.5, its actual enforcement.

The default posture of Project 117 is ZERO EXTERNAL DATA EGRESS: document
content never leaves the machine.

Why this file changed
---------------------
The Phase 0 audit found that ``EgressPolicy`` was referenced in exactly four
places: the settings object, the app factory, this module and its own unit
test. No outbound HTTP client ever consulted it. A policy that no code path
checks is documentation, not security - the guarantee was unenforced.

``EgressGuardTransport`` closes that gap. It is an ``httpx`` *transport*
wrapper rather than a helper function, which matters: the check then sits
underneath every request the client makes - including redirects and streaming
responses - and a caller cannot forget to call it. Enforcement is structural,
not a convention.

Scope, stated honestly: this covers HTTP made by *our* process through httpx.
Vendored code that opens its own sockets is not covered and cannot be from
here. Container-level egress control is Phase 9/12 work. This is the first
gate, not the only one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx

from backend.security.network.network_monitor import record_decision

if TYPE_CHECKING:  # pragma: no cover - typing only
    from backend.config import Settings

logger = logging.getLogger(__name__)


class EgressBlocked(RuntimeError):
    """An outbound request was refused by the egress policy.

    Raised from inside the transport, so it surfaces at the call site of
    whatever tried to leave the machine. Providers translate it into a typed
    provider error; everything else should let it propagate loudly.
    """

    reason = "egress_blocked"

    def __init__(self, url: str) -> None:
        host = urlparse(url).hostname or "?"
        super().__init__(
            f"egress to '{host}' is blocked by policy (zero external egress). "
            "If this is an internal service, allow it explicitly with "
            "P117_EGRESS_ALLOWED_HOSTS. Note that 0.0.0.0 is a bind address, "
            "not a destination - use 127.0.0.1."
        )
        self.url = url
        self.host = host


@dataclass(frozen=True)
class EgressPolicy:
    """Allow outbound URLs explicitly; deny everything else by default.

    ``allowed_hosts`` entries are exact hostnames (no wildcards - a wildcard
    allowlist is how zero-egress quietly becomes full egress). ``localhost``,
    ``127.0.0.1`` and ``::1`` are always allowed so the backend can reach
    local model servers (Ollama, vLLM) and OpenSandbox; the point is to block
    *external* destinations, not to make the loopback awkward.
    """

    default_deny: bool = True
    allowed_hosts: frozenset[str] = field(default_factory=frozenset)
    allowed_schemes: frozenset[str] = frozenset({"http", "https"})

    # 0.0.0.0 is deliberately NOT here: it means "all interfaces" as a bind
    # address and is not a meaningful destination. Treating it as loopback was
    # sloppy, and a mis-set base URL should fail visibly.
    _LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

    def allows(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in self.allowed_schemes:
            return False
        host = (parsed.hostname or "").lower()
        if host in self._LOCAL_HOSTS:
            return True
        if self.default_deny:
            return host in self.allowed_hosts
        # Non-deny mode still enforces the scheme allowlist; it only relaxes
        # the host check.
        return True

    def is_local(self, host: str | None) -> bool:
        """True when ``host`` is loopback.

        The distinction matters for reporting, not for policy: ``allows``
        admits loopback so the backend can reach Ollama, vLLM and OpenSandbox,
        but a request to ``127.0.0.1`` has not left the machine and must never
        be counted as an external call. Without this split, "external calls:
        400" would really mean "we talked to our own model server 400 times".
        """
        return (host or "").lower() in self._LOCAL_HOSTS

    def check(self, url: str) -> None:
        """Raise ``EgressBlocked`` unless the URL is permitted."""
        if not self.allows(url):
            raise EgressBlocked(url)

    def with_allowlist(self, *hosts: str) -> "EgressPolicy":
        return EgressPolicy(
            default_deny=self.default_deny,
            allowed_hosts=frozenset({*self.allowed_hosts, *(h.lower() for h in hosts)}),
            allowed_schemes=self.allowed_schemes,
        )


def policy_from_settings(settings: "Settings") -> EgressPolicy:
    """Build the process-wide policy from configuration."""
    return EgressPolicy(
        default_deny=settings.egress_default_deny,
        allowed_hosts=frozenset(host.lower() for host in settings.egress_allowed_hosts),
    )


class EgressGuardTransport(httpx.AsyncBaseTransport):
    """Async httpx transport that refuses requests the policy denies.

    Wrap the transport, not the call: this way the policy is consulted for
    every request the client issues, and adding a new outbound call site
    cannot accidentally skip the check.
    """

    def __init__(
        self,
        policy: EgressPolicy,
        inner: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._policy = policy
        self._inner = inner if inner is not None else httpx.AsyncHTTPTransport()

    @property
    def policy(self) -> EgressPolicy:
        return self._policy

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        host = request.url.host
        # Observation, not policy: the monitor is what turns "zero external
        # egress" from a claim in a docstring into a number an operator can
        # read. It is recorded here, in the one place every outbound call must
        # pass through, so a new call site cannot go uncounted.
        local = self._policy.is_local(host)
        if not self._policy.allows(url):
            # Log the host only. A URL may carry a query, and a query can
            # carry content - that must never reach the log.
            logger.warning(
                "egress blocked: host=%s scheme=%s",
                host,
                request.url.scheme,
            )
            record_decision(
                host=host,
                scheme=request.url.scheme,
                decision="blocked",
                reason="denied by egress policy",
                local=local,
            )
            raise EgressBlocked(url)
        record_decision(
            host=host, scheme=request.url.scheme, decision="allowed", local=local
        )
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


class EgressGuardSyncTransport(httpx.BaseTransport):
    """Sync counterpart of :class:`EgressGuardTransport`."""

    def __init__(
        self,
        policy: EgressPolicy,
        inner: httpx.BaseTransport | None = None,
    ) -> None:
        self._policy = policy
        self._inner = inner if inner is not None else httpx.HTTPTransport()

    @property
    def policy(self) -> EgressPolicy:
        return self._policy

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        host = request.url.host
        local = self._policy.is_local(host)
        if not self._policy.allows(url):
            logger.warning(
                "egress blocked: host=%s scheme=%s",
                host,
                request.url.scheme,
            )
            record_decision(
                host=host,
                scheme=request.url.scheme,
                decision="blocked",
                reason="denied by egress policy",
                local=local,
            )
            raise EgressBlocked(url)
        record_decision(
            host=host, scheme=request.url.scheme, decision="allowed", local=local
        )
        return self._inner.handle_request(request)

    def close(self) -> None:
        self._inner.close()


def guarded_async_client(
    *,
    policy: EgressPolicy,
    base_url: str = "",
    headers: dict[str, str] | None = None,
    timeout: float = 120.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    """The only sanctioned way to build an outbound async client.

    Phase 9+ code (sandbox adapter, enterprise connectors) must use this
    rather than constructing ``httpx.AsyncClient`` directly.
    """
    return httpx.AsyncClient(
        base_url=base_url.rstrip("/"),
        headers=headers or {},
        timeout=timeout,
        transport=EgressGuardTransport(policy, transport),
    )
