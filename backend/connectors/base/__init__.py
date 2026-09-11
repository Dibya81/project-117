"""BASE connector package — implementation in connector.py."""

from backend.connectors.base.connector import (
    BaseConnector,
    ConnectorAuthError,
    ConnectorConfig,
    ConnectorError,
    ConnectorUnavailable,
    logger,
)

__all__ = [
    "BaseConnector",
    "ConnectorAuthError",
    "ConnectorConfig",
    "ConnectorError",
    "ConnectorUnavailable",
    "logger",
]
