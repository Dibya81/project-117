from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ConnectorError(RuntimeError):
    reason = "connector_error"


class ConnectorAuthError(ConnectorError):
    reason = "connector_auth_error"


class ConnectorUnavailable(ConnectorError):
    """The remote system could not be reached. A connector must raise this
    (not swallow it) so the tool layer's normal error handling, retries and
    audit logging apply - a connector is a tool dependency, not a bypass."""

    reason = "connector_unavailable"


@dataclass
class ConnectorConfig:
    """Shared configuration for enterprise connectors (SAP, CMMS, historian,
    DMS, or a generic REST system).

    Every connector is opt-in and off by default (``enabled=False``): a
    sovereign, air-gapped deployment must not silently try to reach an
    enterprise system that was never configured. Enabling one is an explicit
    settings change, not a code default.
    """

    name: str
    enabled: bool = False
    base_url: str = ""
    api_key: str | None = None
    username: str | None = None
    password: str | None = None
    timeout_seconds: float = 30.0
    verify_tls: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


class BaseConnector:
    """Common request plumbing for enterprise connectors.

    Subclasses (SAP, CMMS, historian, DMS, generic) implement their own
    domain methods on top of :meth:`_request`. All outbound calls go through
    the shared ``httpx`` client here so timeouts, TLS verification and error
    mapping are consistent, and so the egress policy transport used
    elsewhere in the backend can be attached the same way if a deployment
    decides an enterprise system is in-bounds for the egress allowlist.
    """

    def __init__(self, config: ConnectorConfig, *, client: httpx.Client | None = None) -> None:
        self.config = config
        self._client = client

    @property
    def enabled(self) -> bool:
        return self.config.enabled and bool(self.config.base_url)

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise ConnectorUnavailable(
                f"connector '{self.config.name}' is not enabled or has no base_url configured"
            )

    def _client_for_request(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        auth = None
        if self.config.username and self.config.password:
            auth = (self.config.username, self.config.password)
        self._client = httpx.Client(
            base_url=self.config.base_url,
            timeout=self.config.timeout_seconds,
            verify=self.config.verify_tls,
            headers=headers or None,
            auth=auth,
        )
        return self._client

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        self._require_enabled()
        client = self._client_for_request()
        try:
            response = client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ConnectorUnavailable(
                f"connector '{self.config.name}' request to {path} failed: {exc}"
            ) from exc
        if response.status_code in (401, 403):
            raise ConnectorAuthError(
                f"connector '{self.config.name}' rejected credentials (HTTP {response.status_code})"
            )
        if response.status_code >= 400:
            raise ConnectorError(
                f"connector '{self.config.name}' returned HTTP {response.status_code} for {path}: "
                f"{response.text[:300]}"
            )
        return response

    def health_check(self) -> dict[str, Any]:
        """Best-effort reachability check. Never raises - callers (e.g. an
        admin status endpoint) want a status dict, not an exception."""
        if not self.enabled:
            return {"name": self.config.name, "enabled": False, "status": "disabled"}
        try:
            self._request("GET", "/")
            return {"name": self.config.name, "enabled": True, "status": "ok"}
        except ConnectorError as exc:
            return {
                "name": self.config.name,
                "enabled": True,
                "status": "unreachable",
                "error": str(exc),
            }

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
