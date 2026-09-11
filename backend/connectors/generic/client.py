from __future__ import annotations

from typing import Any

from backend.connectors.base import BaseConnector


class GenericAPIConnector(BaseConnector):
    """A configurable REST connector for enterprise systems with no
    dedicated adapter yet. Exposes raw verbs rather than domain methods -
    callers are expected to know the target API's shape; this exists so a
    new integration does not require a code change to try a read-only
    GET/POST against a configured system."""

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        response = self._request("GET", path, params=params)
        return response.json()

    def post(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        response = self._request("POST", path, json=json)
        return response.json()
