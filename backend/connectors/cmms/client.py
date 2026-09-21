from __future__ import annotations

from typing import Any

from backend.connectors.base import BaseConnector


class CMMSConnector(BaseConnector):
    """Work order and asset lookups against a computerised maintenance
    management system."""

    def get_work_order(self, work_order_id: str) -> dict[str, Any]:
        response = self._request("GET", f"/api/work-orders/{work_order_id}")
        return response.json()

    def list_work_orders(
        self, *, asset_tag: str | None = None, status: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if asset_tag:
            params["asset"] = asset_tag
        if status:
            params["status"] = status
        response = self._request("GET", "/api/work-orders", params=params)
        return response.json().get("work_orders", [])

    def get_asset(self, asset_tag: str) -> dict[str, Any]:
        response = self._request("GET", f"/api/assets/{asset_tag}")
        return response.json()
