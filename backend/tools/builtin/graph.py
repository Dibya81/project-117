"""Knowledge-graph tool (Phase 8 registry over ``backend/memory/graph``).

``backend/memory/graph`` — the bounded, clearance-aware :class:`GraphQuery`
over :class:`MemoryGraph` — was real and tested but had no consumer in the
request path: no tool, no route. This module is that consumer, and it lives in
the existing tool registry rather than in a second one.

The graph is assembled from records the system already stores, never authored
by a model:

* **equipment** and its **sensors** — the plant dataset, via the operations
  store (``equipment`` → ``monitored_by`` → ``signal``);
* **work orders** — the operations work-order table, which is also the
  maintenance history (``work_order`` → ``raised_for`` → ``equipment``);
* **spares** — the materials store's equipment material requirements
  (``equipment`` → ``requires_spare`` → ``material``);
* **inspections** — the equipment's own recorded ``last_inspection``
  (``equipment`` → ``has_inspection`` → ``inspection``);
* **documents / SOPs** — whatever per-equipment document linkage exists
  (``equipment`` → ``documented_in`` → ``document``).

A source with no backing store contributes *no* edges and is reported in the
result's ``absent`` list. An inferred edge would be indistinguishable from a
real one on screen, so nothing is invented.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.memory.graph import entities as ent
from backend.memory.graph.graph_builder import GraphBuilder, MemoryGraph
from backend.memory.graph.graph_query import MAX_DEPTH, GraphQuery
from backend.security.rbac import Principal, principal_from_roles
from backend.tools.base import (
    Permission,
    ResourceLimits,
    RiskLevel,
    ToolContext,
    ToolResult,
    ToolSpec,
)

#: Reliable per-asset neighbourhood size. The graph query caps traversal at
#: ``MAX_DEPTH`` and ``MAX_NODES`` regardless of what the caller asks for.
DEFAULT_DEPTH = 2


def _tag_of(row: dict[str, Any]) -> str:
    """The human tag of an equipment row.

    The operations store carries the tag in ``tags`` (kind, area, tag); the
    node is keyed by it so ``query_knowledge_graph("P-102")`` resolves the way
    an operator writes it, not by the surrogate ``e-P-1001`` id.
    """
    tags = row.get("tags") or []
    if isinstance(tags, list) and tags:
        return str(tags[-1])
    return str(row.get("tag") or row.get("id") or "")


def build_operational_graph(
    operations: Any, materials: Any = None
) -> tuple[MemoryGraph, list[dict[str, str]]]:
    """Assemble the graph from the live stores.

    Returns ``(graph, absent)`` where ``absent`` names every requested
    relationship whose source store is empty, so a caller can tell "no such
    link" from "nothing links this yet".
    """
    builder = GraphBuilder()
    graph = builder.graph
    absent: list[dict[str, str]] = []

    try:
        equipment_rows = operations.equipment()
    except Exception:  # noqa: BLE001 - a missing store is reported, not raised
        equipment_rows = []

    id_to_tag: dict[str, str] = {}
    telemetry_rows: list[dict[str, Any]] = []
    for row in equipment_rows or []:
        tag = _tag_of(row)
        if not tag:
            continue
        id_to_tag[str(row.get("id") or tag)] = tag
        # Basic node (site + install edge) first, then the richer attributes.
        builder.add_equipment(
            [
                {
                    "tag": tag,
                    "name": row.get("name"),
                    "status": row.get("status"),
                    "criticality": row.get("criticality"),
                    "unit": row.get("unit"),
                }
            ]
        )
        graph.add_entity(
            ent.equipment(
                tag,
                name=row.get("name"),
                last_inspection=row.get("lastInspection"),
                next_inspection=row.get("nextInspection"),
                manufacturer=row.get("manufacturer"),
                model=row.get("model"),
            )
        )
        for signal in row.get("keySignals") or []:
            if signal.get("signal"):
                telemetry_rows.append(
                    {"equipment": tag, "signal": signal.get("signal"), "unit": signal.get("unit")}
                )
        last = row.get("lastInspection")
        if last:
            inspection = graph.add_entity(
                ent.make(
                    "inspection",
                    f"{tag}@{last}",
                    label=f"{tag} inspected {last}",
                    date=last,
                    next_due=row.get("nextInspection"),
                )
            )
            graph.link(
                ent.node_id("equipment", tag),
                "has_inspection",
                inspection.id,
                evidence=[{"source": "equipment.last_inspection", "date": last}],
            )
        if materials is not None:
            try:
                requirements = materials.requirements(equipment_id=str(row.get("id") or tag))
            except Exception:  # noqa: BLE001 - materials are optional
                requirements = []
            for requirement in requirements or []:
                item_id = str(requirement.get("item_id") or "")
                if not item_id:
                    continue
                spare = graph.add_entity(
                    ent.make(
                        "material",
                        item_id,
                        label=requirement.get("item_name") or item_id,
                        unit=requirement.get("unit"),
                        schedule=requirement.get("schedule"),
                        purpose=requirement.get("purpose"),
                        failure_mode=requirement.get("failure_mode"),
                    )
                )
                graph.link(
                    ent.node_id("equipment", tag),
                    "requires_spare",
                    spare.id,
                    evidence=[
                        {
                            "source": "equipment_material_requirements",
                            "requirement_id": requirement.get("id"),
                        }
                    ],
                )

    if telemetry_rows:
        builder.add_telemetry(telemetry_rows)
    else:
        absent.append({"relationship": "sensor", "reason": "no equipment signals in the dataset"})

    try:
        work_orders = operations.work_orders()
    except Exception:  # noqa: BLE001
        work_orders = []
    mapped_orders = []
    for order in work_orders or []:
        equipment_id = str(order.get("equipmentId") or "")
        mapped_orders.append(
            {
                "id": order.get("id") or order.get("number"),
                "equipment": id_to_tag.get(equipment_id, equipment_id),
                "status": order.get("status"),
                "priority": order.get("priority"),
            }
        )
    if mapped_orders:
        builder.add_work_orders(mapped_orders)
    else:
        absent.append(
            {
                "relationship": "work order / maintenance history",
                "reason": "the operations work-order store is empty",
            }
        )

    try:
        documents = operations.documents()
    except Exception:  # noqa: BLE001
        documents = []
    if documents:
        builder.add_documents(documents)
    else:
        absent.append(
            {
                "relationship": "document / SOP",
                "reason": "no per-equipment document linkage exists in the operations store",
            }
        )
    if materials is None:
        absent.append(
            {
                "relationship": "spare",
                "reason": "no materials store is attached to this tool call",
            }
        )
    return graph, absent


class KnowledgeGraphArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: An equipment tag (``P-102``), an equipment id (``e-P-1001``) or a node
    #: label fragment. Resolution goes through :meth:`GraphQuery.search`.
    asset: str = Field(min_length=1, max_length=120)
    depth: int = Field(default=DEFAULT_DEPTH, ge=1, le=MAX_DEPTH)
    #: Optional edge-type filter, e.g. ``["monitored_by", "raised_for"]``.
    relations: list[str] | None = Field(default=None, max_length=16)


class QueryKnowledgeGraphTool:
    """``query_knowledge_graph`` — real relationships around one asset."""

    def __init__(self) -> None:
        self._spec = ToolSpec(
            name="query_knowledge_graph",
            description=(
                "Query the operational knowledge graph around one asset and return its REAL "
                "relationships: monitored_by sensors, raised_for work orders (the maintenance "
                "history), requires_spare materials, has_inspection inspections, and "
                "documented_in SOPs. All of it is assembled from records that already exist; "
                "a relationship with no backing store is absent and is reported in `absent`, "
                "never inferred. Results are clearance-filtered for the caller."
            ),
            permission=Permission.CONNECTORS_READ,
            risk=RiskLevel.READ,
            limits=ResourceLimits(timeout_seconds=30.0),
            capabilities=["knowledge_graph", "query", "topology"],
            latency_class=2,
            cost_class=1,
            input_schema=KnowledgeGraphArguments.model_json_schema(),
            output_schema={
                "type": "object",
                "properties": {
                    "asset": {"type": "string"},
                    "found": {"type": "boolean"},
                    "node_id": {"type": "string"},
                    "nodes": {"type": "array"},
                    "edges": {"type": "array"},
                    "absent": {"type": "array"},
                    "stats": {"type": "object"},
                },
            },
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    @property
    def arguments_model(self) -> type[BaseModel]:
        return KnowledgeGraphArguments

    async def run(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, KnowledgeGraphArguments)
        operations = context.operations
        if operations is None:
            from backend.storage.operations import get_operations_store  # noqa: PLC0415

            operations = get_operations_store()
        graph, absent = build_operational_graph(operations, context.materials)

        # The caller's clearance travels with the query: a node above it is
        # never returned, and an edge with a hidden endpoint is dropped.
        principal: Principal = principal_from_roles(context.user, context.roles)
        if context.clearance:
            principal = replace(
                principal, extra={**(principal.extra or {}), "clearance": context.clearance}
            )
        query = GraphQuery(graph, principal=principal)

        matches = query.search(arguments.asset, limit=10)
        if not matches:
            return ToolResult(
                tool=self._spec.name,
                output={
                    "asset": arguments.asset,
                    "found": False,
                    "node_id": None,
                    "nodes": [],
                    "edges": [],
                    "absent": absent,
                    "stats": graph.stats(),
                },
            )

        node_id = str(matches[0]["id"])
        result = query.neighbours(node_id, depth=arguments.depth, relations=arguments.relations)
        return ToolResult(
            tool=self._spec.name,
            output={
                "asset": arguments.asset,
                "found": bool(result.get("found")),
                "node_id": node_id,
                "depth": result.get("depth", arguments.depth),
                "nodes": result.get("nodes", []),
                "edges": result.get("edges", []),
                "truncated": result.get("truncated", False),
                "absent": absent,
                "stats": graph.stats(),
            },
        )


__all__ = [
    "KnowledgeGraphArguments",
    "QueryKnowledgeGraphTool",
    "build_operational_graph",
]
