from __future__ import annotations

from typing import Any

from backend.connectors.base import BaseConnector


class DMSConnector(BaseConnector):
    """Search and fetch metadata from an external document management
    system, distinct from this backend's own document storage/ingestion
    (``backend.storage`` / ``backend.ingestion``). Content fetched here still
    goes through the normal ingestion pipeline before it is used as
    evidence - a connector is a source, not a shortcut around validation."""

    def search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        response = self._request("GET", "/api/documents/search", params={"q": query, "limit": limit})
        return response.json().get("results", [])

    def get_document_metadata(self, document_id: str) -> dict[str, Any]:
        response = self._request("GET", f"/api/documents/{document_id}")
        return response.json()
