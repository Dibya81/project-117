from __future__ import annotations

from typing import Any

from backend.connectors.base import BaseConnector


class HistorianConnector(BaseConnector):
    """Read-only access to a process historian: point telemetry and trend
    windows. Never issues writes - a historian connector that could write
    setpoints back would turn a read tool into an unreviewed control-system
    actuator, which is out of scope for this workbench."""

    def get_latest_value(self, tag: str) -> dict[str, Any]:
        response = self._request("GET", f"/api/points/{tag}/latest")
        return response.json()

    def get_trend(
        self, tag: str, *, start: str, end: str, interval_seconds: int = 60
    ) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            f"/api/points/{tag}/trend",
            params={"start": start, "end": end, "interval_seconds": interval_seconds},
        )
        return response.json().get("samples", [])
