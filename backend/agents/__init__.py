"""Specialised agents (Phase 7).

Five specialisations, one shared base, one registry. The registry is what the
orchestrator's :class:`~backend.orchestrator.src.agent_manager.AgentManager` builds
from, which is how an agent receives the model router, the tool registry and
the assembled context instead of constructing its own.

Why these five, and not one "assistant":

- **maintenance** and **operations** answer the same document with different
  obligations - a diagnosis ranks causes, a procedure must never be reordered.
- **safety** exists because the acceptable failure mode is different. Its
  prompt refuses to complete a procedure that was not retrieved, and its
  temperature is zero.
- **data-analysis** writes Python for the sandbox instead of asserting numbers,
  so figures come from data and can be re-computed by the verifier.
- **documentation** authors the structured content that the deterministic
  generators turn into a deck, report or workbook.

Adding an agent means adding a prompt and a post-processing rule, not a new
model client, retriever or tool path. If a change to an agent requires touching
retrieval or the sandbox, the boundary has been crossed and the change belongs
in those layers instead.
"""

from __future__ import annotations

from backend.agents.base import (
    AgentError,
    AgentModelUnavailable,
    AgentRegistry,
    AgentResult,
    AgentSpec,
    BaseAgent,
)
from backend.agents.data_analysis import DataAnalysisAgent
from backend.agents.documentation import DocumentationAgent
from backend.agents.maintenance import MaintenanceAgent
from backend.agents.operations import OperationsAgent
from backend.agents.safety import SafetyAgent

#: Registration order is also the order ``GET /api/agents`` reports.
DEFAULT_AGENT_CLASSES: tuple[type[BaseAgent], ...] = (
    MaintenanceAgent,
    OperationsAgent,
    DocumentationAgent,
    DataAnalysisAgent,
    SafetyAgent,
)

DEFAULT_AGENT_NAMES: tuple[str, ...] = tuple(cls.name for cls in DEFAULT_AGENT_CLASSES)


def build_agent_registry(
    *,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> AgentRegistry:
    """Build the registry the orchestrator dispatches through.

    ``include``/``exclude`` exist so a deployment can disable an agent it has
    not validated for its site. Disabling one degrades the answer (the agent
    manager falls back to a grounded direct answer) rather than failing the
    job, which is the right behaviour for a plant that wants documentation Q&A
    live before it trusts maintenance diagnosis.
    """
    wanted = set(include) if include else None
    unwanted = set(exclude or ())
    registry = AgentRegistry()
    for agent_cls in DEFAULT_AGENT_CLASSES:
        if wanted is not None and agent_cls.name not in wanted:
            continue
        if agent_cls.name in unwanted:
            continue
        registry.register_agent(agent_cls)
    return registry


__all__ = [
    "AgentError",
    "AgentModelUnavailable",
    "AgentRegistry",
    "AgentResult",
    "AgentSpec",
    "BaseAgent",
    "DEFAULT_AGENT_CLASSES",
    "DEFAULT_AGENT_NAMES",
    "DataAnalysisAgent",
    "DocumentationAgent",
    "MaintenanceAgent",
    "OperationsAgent",
    "SafetyAgent",
    "build_agent_registry",
]
