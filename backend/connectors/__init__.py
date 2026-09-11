"""Enterprise integration connectors (Phase 15).

Each connector talks to one external system (SAP, a CMMS, a process
historian, a document management system, or a generic REST API) and is
disabled by default - see :class:`backend.connectors.base.ConnectorConfig`.
A sovereign, air-gapped deployment must opt every one of these in explicitly;
none of them is reachable unless ``enabled=True`` and a ``base_url`` are
configured.

Connectors are read-oriented on purpose. None of the built-in connectors
write back to the source system (no SAP order updates, no CMMS work-order
mutation, no historian setpoints) - that would make an agent an unreviewed
actuator on plant systems, which is out of scope here. If a deployment needs
write-back, it is a deliberate, reviewed addition, not something these
classes grow silently.
"""

from __future__ import annotations

from backend.connectors.base import (
    BaseConnector,
    ConnectorAuthError,
    ConnectorConfig,
    ConnectorError,
    ConnectorUnavailable,
)
from backend.connectors.cmms import CMMSConnector
from backend.connectors.dms import DMSConnector
from backend.connectors.generic import GenericAPIConnector
from backend.connectors.historian import HistorianConnector
from backend.connectors.sap import SAPConnector

__all__ = [
    "BaseConnector",
    "ConnectorConfig",
    "ConnectorError",
    "ConnectorAuthError",
    "ConnectorUnavailable",
    "SAPConnector",
    "CMMSConnector",
    "HistorianConnector",
    "DMSConnector",
    "GenericAPIConnector",
]


def build_connectors(settings: object) -> dict[str, BaseConnector]:
    """Build the connector set from settings. Every connector defaults to
    disabled; this only wires the ones a deployment turned on.

    ``settings`` is read defensively via ``getattr`` so the connector layer
    does not force every deployment to define SAP/CMMS/historian/DMS
    settings it will never use.
    """
    connectors: dict[str, BaseConnector] = {}
    specs = [
        ("sap", SAPConnector),
        ("cmms", CMMSConnector),
        ("historian", HistorianConnector),
        ("dms", DMSConnector),
        ("generic", GenericAPIConnector),
    ]
    for name, cls in specs:
        config = getattr(settings, f"{name}_connector", None)
        if config is None:
            config = ConnectorConfig(name=name)
        connectors[name] = cls(config)
    return connectors
