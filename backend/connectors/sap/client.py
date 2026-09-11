from __future__ import annotations

from typing import Any

from backend.connectors.base import BaseConnector


class SAPConnector(BaseConnector):
    """SAP PM/MM read access: equipment master data, maintenance orders,
    and procurement status. Disabled by default (see ``ConnectorConfig``);
    a sovereign deployment with no SAP tenant configured never attempts an
    outbound call here."""

    def get_equipment(self, tag: str) -> dict[str, Any]:
        response = self._request("GET", f"/api/equipment/{tag}")
        return response.json()

    def get_maintenance_orders(self, tag: str, *, limit: int = 20) -> list[dict[str, Any]]:
        response = self._request(
            "GET", "/api/maintenance-orders", params={"equipment": tag, "limit": limit}
        )
        return response.json().get("orders", [])

    def get_procurement_status(self, order_id: str) -> dict[str, Any]:
        response = self._request("GET", f"/api/procurement/{order_id}")
        return response.json()
