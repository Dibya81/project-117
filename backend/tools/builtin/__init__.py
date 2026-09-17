"""The built-in tool set (Phase 8).

One place where every tool the system ships with is registered, so "what can
this backend actually do?" has a single answer that cannot drift from what is
callable.

The set is deliberately small. Each entry is a capability the backend really
has end to end - retrieval with provenance, sandboxed execution, artifact
generation with verification. Nothing here is a stub that returns a plausible
shape, because a planner cannot tell the difference between a tool that works
and a tool that pretends to, and it will happily build a five-step plan on top
of the pretence.

``convert_document`` from the original tool list is **not** registered: no
converter is wired yet. It will appear when there is something behind it.
Similarly the enterprise connector tools (SAP, CMMS, historian) arrive with
Phase 13, as ``external`` risk, which the approval gate blocks by default.
"""

from __future__ import annotations

from typing import Any

from backend.tools.builtin.artifacts import (
    CreateDocxTool,
    CreatePdfTool,
    CreatePptxTool,
    CreateXlsxTool,
)
from backend.tools.builtin.code import AnalyzeCsvTool, RunPythonTool
from backend.tools.builtin.documents import (
    ExtractTableTool,
    ReadDocumentTool,
    SearchDocumentsTool,
)
from backend.tools.builtin.graph import QueryKnowledgeGraphTool
from backend.tools.materials import MATERIALS_TOOL_CLASSES
from backend.tools.registry import ToolRegistry

#: Registration order is also catalogue order: read, compute, then produce.
DEFAULT_TOOL_CLASSES: tuple[type[Any], ...] = (
    SearchDocumentsTool,
    ReadDocumentTool,
    ExtractTableTool,
    QueryKnowledgeGraphTool,
    AnalyzeCsvTool,
    RunPythonTool,
    CreatePptxTool,
    CreateDocxTool,
    CreateXlsxTool,
    CreatePdfTool,
    *MATERIALS_TOOL_CLASSES,
)

DEFAULT_TOOL_NAMES: tuple[str, ...] = (
    "search_documents",
    "read_document",
    "extract_table",
    # The operational knowledge graph, assembled from real records (see
    # backend/tools/builtin/graph.py). Read-only and clearance-aware.
    "query_knowledge_graph",
    "analyze_csv",
    "run_python",
    # Materials / inventory / business intelligence. Read-only: they expose the
    # domain's computed values to the agent without giving it a way to change
    # stock, order anything or approve its own proposal.
    "get_material",
    "get_inventory_status",
    "get_material_movements",
    "get_production_output",
    "get_equipment_material_requirements",
    "get_maintenance_requirements",
    "search_price_history",
    "calculate_material_requirement",
    "forecast_inventory",
    "generate_procurement_recommendation",
    "create_pptx",
    "create_docx",
    "create_xlsx",
    "create_pdf",
)


def build_default_registry(
    *,
    session_factory: Any = None,
    audit: Any = None,
    approval_policy: Any = None,
    metrics: Any = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> ToolRegistry:
    """Build a registry with the built-in tools.

    ``include``/``exclude`` exist for tests and for deployments that genuinely
    do not want a capability - a site that forbids code execution outright
    removes ``run_python`` here rather than relying on the approval gate never
    being relaxed. Both filters are validated: naming a tool that does not
    exist raises instead of silently registering a smaller set, because a
    typo in a deployment config should not quietly disable retrieval.
    """
    registry = ToolRegistry(
        session_factory=session_factory,
        audit=audit,
        approval_policy=approval_policy,
        metrics=metrics,
    )

    known = set(DEFAULT_TOOL_NAMES)
    for label, names in (("include", include), ("exclude", exclude)):
        unknown = sorted(set(names or ()) - known)
        if unknown:
            raise ValueError(
                f"{label} names tools that do not exist: {', '.join(unknown)}; "
                f"available: {', '.join(sorted(known))}"
            )

    wanted = set(include) if include else set(known)
    wanted -= set(exclude or ())

    for tool_class in DEFAULT_TOOL_CLASSES:
        tool = tool_class()
        if tool.spec.name in wanted:
            registry.register(tool)
    return registry


__all__ = [
    "DEFAULT_TOOL_CLASSES",
    "DEFAULT_TOOL_NAMES",
    "AnalyzeCsvTool",
    "CreateDocxTool",
    "CreatePdfTool",
    "CreatePptxTool",
    "CreateXlsxTool",
    "ExtractTableTool",
    "QueryKnowledgeGraphTool",
    "ReadDocumentTool",
    "RunPythonTool",
    "SearchDocumentsTool",
    "build_default_registry",
]
