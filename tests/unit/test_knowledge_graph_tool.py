"""The knowledge-graph tool (``query_knowledge_graph``).

The audit finding this closes: ``backend/memory/graph`` was real, bounded and
clearance-aware, but nothing in the request path consumed it. These tests pin
the two things that matter about the new consumer:

* it returns the relationships that actually exist in the stores — sensor,
  work order, spare, inspection, SOP — and never invents one for a source that
  is empty (a missing link is reported in ``absent``); and
* it stays clearance-aware: a restricted document reached by traversal is
  hidden from a viewer and visible to an admin.
"""

from __future__ import annotations

import asyncio

from backend.tools.base import ToolContext
from backend.tools.builtin import DEFAULT_TOOL_CLASSES, DEFAULT_TOOL_NAMES
from backend.tools.builtin.graph import QueryKnowledgeGraphTool, build_operational_graph
from backend.tools.registry import ToolRegistry


class _FakeOperations:
    """The shape ``OperationsStore`` exposes to the graph builder."""

    def __init__(self, *, with_work_order: bool = True, with_document: bool = True) -> None:
        self._with_work_order = with_work_order
        self._with_document = with_document

    def equipment(self) -> list[dict]:
        return [
            {
                "id": "e-P-1001",
                "name": "Crude charge pump",
                "status": "healthy",
                "criticality": "high",
                "unit": "Crude Receiving",
                "tags": ["pump", "area-crude", "P-1001"],
                "lastInspection": "2026-01-15",
                "nextInspection": "2026-07-15",
                "manufacturer": "Sulzer",
                "model": "MSD-4x6",
                "keySignals": [
                    {"signal": "pressure", "unit": "bar"},
                    {"signal": "flow", "unit": "m3/h"},
                ],
            }
        ]

    def work_orders(self) -> list[dict]:
        if not self._with_work_order:
            return []
        return [
            {"id": "WO-2001", "equipmentId": "e-P-1001", "status": "in_progress", "priority": "high"}
        ]

    def documents(self) -> list[dict]:
        if not self._with_document:
            return []
        return [
            {
                "id": "SOP-P1001",
                "title": "Crude charge pump start-up",
                "type": "sop",
                "clearance": "CONFIDENTIAL",
                "equipment": ["P-1001"],
            }
        ]


class _FakeMaterials:
    def requirements(self, *, equipment_id: str | None = None, **_: object) -> list[dict]:
        if equipment_id != "e-P-1001":
            return []
        return [
            {
                "id": "REQ-MECH-SEAL-P1001",
                "item_id": "MECH-SEAL-P1001",
                "item_name": "Mechanical seal kit — crude charge pump",
                "unit": "EA",
                "schedule": "on condition",
                "purpose": "Seal replacement on seal-leak diagnosis",
                "failure_mode": "seal_leak",
            }
        ]


def _graph(ops: _FakeOperations | None = None, materials: object = None):
    return build_operational_graph(ops or _FakeOperations(), materials)


def test_graph_carries_the_real_relationships() -> None:
    graph, absent = _graph(_FakeOperations(), _FakeMaterials())
    edge_types = {edge.type for edge in graph.edges}
    assert {"monitored_by", "raised_for", "requires_spare", "has_inspection", "documented_in"} <= edge_types
    assert absent == [] or all(a["relationship"] != "spare" for a in absent)


def test_graph_reports_absent_sources_rather_than_inventing_edges() -> None:
    graph, absent = _graph(_FakeOperations(with_work_order=False, with_document=False), _FakeMaterials())
    edge_types = {edge.type for edge in graph.edges}
    assert "raised_for" not in edge_types
    assert "documented_in" not in edge_types
    reasons = {a["relationship"] for a in absent}
    assert "work order / maintenance history" in reasons
    assert "document / SOP" in reasons


def test_tool_is_registered_in_the_existing_registry() -> None:
    assert QueryKnowledgeGraphTool in DEFAULT_TOOL_CLASSES
    assert "query_knowledge_graph" in DEFAULT_TOOL_NAMES
    registry = ToolRegistry()
    registry.register(QueryKnowledgeGraphTool())
    assert "query_knowledge_graph" in registry.names()


def _run_tool(
    *, roles: list[str], operations: _FakeOperations, clearance: str | None = None
) -> dict:
    registry = ToolRegistry()
    registry.register(QueryKnowledgeGraphTool())
    context = ToolContext(
        user="tester",
        roles=roles,
        clearance=clearance,
        operations=operations,
        materials=_FakeMaterials(),
    )
    result = asyncio.run(
        registry.execute("query_knowledge_graph", {"asset": "P-1001", "depth": 1}, context)
    )
    return result.output


def test_tool_returns_real_neighbourhood_for_a_tag() -> None:
    output = _run_tool(roles=["admin"], operations=_FakeOperations())
    assert output["found"] is True
    assert output["node_id"] == "equipment:p-1001"
    types = {node["type"] for node in output["nodes"]}
    assert {"equipment", "signal", "work_order", "material", "inspection", "document"} <= types
    assert {edge["type"] for edge in output["edges"]} >= {
        "monitored_by",
        "raised_for",
        "requires_spare",
        "has_inspection",
        "documented_in",
    }


def test_tool_hides_a_restricted_document_from_a_viewer() -> None:
    # An explicit PUBLIC badge on an operator role is the real "contractor with
    # an operator role" configuration, and it must lower the clearance rather
    # than be ignored.
    viewer = _run_tool(roles=["operator"], clearance="PUBLIC", operations=_FakeOperations())
    admin = _run_tool(roles=["admin"], operations=_FakeOperations())
    viewer_types = {node["type"] for node in viewer["nodes"]}
    admin_types = {node["type"] for node in admin["nodes"]}
    assert "document" not in viewer_types
    assert "document" in admin_types
    # The equipment itself is not secret, so the viewer still gets the graph.
    assert "equipment" in viewer_types
