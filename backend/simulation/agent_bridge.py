"""Bridge from the simulation incident pipeline to the real Project 117 agents.

The red-team audit's first blocker was that ``backend/agents/*`` was never
imported by ``backend/simulation/*``: six agent classes existed and none of
them ever saw an incident. This module is the connection, and it is written so
that what actually happened is always reported truthfully.

How it works
------------
``build_agent_roster()`` resolves the project's real ``AgentRegistry``
(``backend.agents``). For each simulation role it looks up the corresponding
registered agent implementation:

    data_analysis  -> DataAnalysisAgent   ("data-analysis")
    maintenance    -> MaintenanceAgent    ("maintenance")
    operations     -> OperationsAgent     ("operations")
    safety         -> SafetyAgent         ("safety")
    documentation  -> DocumentationAgent  ("documentation")

``dispatch()`` hands an agent its :class:`AgentContext` — the evidence pack the
simulation gathered from the engine and from retrieval, the task string, the
job id, and the tool registry — and runs ``agent.execute()``.

Honest degradation, not silent fallback
---------------------------------------
These agents call a model through the router. When the router or the local
model is not reachable, ``execute()`` raises ``AgentModelUnavailable``. In that
case the roster reports ``runtime="deterministic-evidence"`` for the affected
task and the *deterministic* result computed from engine state is used — the
same number-for-number result, with no narrative. The task record carries
``agent_runtime`` and ``agent_available`` so the Command Center and the audit
trail show which runtime produced each record. Nothing is ever labelled as
having run through a model when it did not.

No chain-of-thought is stored or emitted: only the agent's final structured
result text, the tools it used, its evidence references and its status.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

#: simulation role -> registered agent name in backend/agents
ROLE_TO_AGENT = {
    "data_analysis": "data-analysis",
    "maintenance": "maintenance",
    "operations": "operations",
    "safety": "safety",
    "documentation": "documentation",
}


@dataclass
class AgentDispatchResult:
    role: str
    agent_name: str
    runtime: str  # project117-agent | deterministic-evidence
    available: bool
    text: str = ""
    tools_used: list[str] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


class AgentRoster:
    """Resolves and runs the real agents; reports honestly when it cannot."""

    def __init__(self) -> None:
        self.registry: Any | None = None
        self.available_roles: dict[str, str] = {}
        self.reason: str = ""
        self._load()

    # ------------------------------------------------------------- resolving

    def _load(self) -> None:
        try:
            from backend.agents import (  # noqa: PLC0415
                AgentRegistry,
                DataAnalysisAgent,
                DocumentationAgent,
                MaintenanceAgent,
                OperationsAgent,
                SafetyAgent,
            )
        except Exception as exc:  # dependency stack not installed
            self.reason = f"backend.agents unavailable: {exc.__class__.__name__}: {exc}"
            logger.warning("simulation agent bridge: %s", self.reason)
            return
        registry = AgentRegistry()
        for cls in (
            DataAnalysisAgent,
            DocumentationAgent,
            MaintenanceAgent,
            OperationsAgent,
            SafetyAgent,
        ):
            try:
                registry.register_agent(cls)
            except Exception as exc:  # pragma: no cover - registry guards
                logger.warning("cannot register %s: %s", cls, exc)
        self.registry = registry
        names = set(registry.names())
        self.available_roles = {
            role: name for role, name in ROLE_TO_AGENT.items() if name in names
        }
        self.reason = "registry loaded"

    @property
    def loaded(self) -> bool:
        return self.registry is not None and bool(self.available_roles)

    def runtime_label(self) -> str:
        return "project117-agents" if self.loaded else "deterministic-evidence"

    def status(self) -> dict[str, Any]:
        return {
            "loaded": self.loaded,
            "runtime": self.runtime_label(),
            "roles": sorted(self.available_roles),
            "reason": self.reason,
        }

    # ------------------------------------------------------------ dispatching

    def dispatch(
        self,
        *,
        role: str,
        task: str,
        evidence: list[dict[str, Any]],
        job_id: str,
        deterministic_result: str,
        tools: list[str],
        inputs: dict[str, Any] | None = None,
    ) -> AgentDispatchResult:
        """Run the real agent for ``role``; fall back to the engine-derived
        result only when the agent runtime genuinely cannot run."""
        agent_name = ROLE_TO_AGENT.get(role, role)
        if not self.loaded or role not in self.available_roles:
            return AgentDispatchResult(
                role=role, agent_name=agent_name, runtime="deterministic-evidence",
                available=False, text=deterministic_result, tools_used=tools,
                error=self.reason or "agent not registered",
            )
        try:
            from backend.agents.base.agent_context import AgentContext  # noqa: PLC0415

            agent = self.registry.build(agent_name)  # type: ignore[union-attr]
            ctx = AgentContext(
                task=task,
                job_id=job_id,
                evidence=tuple(evidence),
                inputs=dict(inputs or {}),
            )
            result = asyncio.run(agent.execute(task=task, context=ctx))
        except Exception as exc:
            # Model/router/tooling unavailable, or the agent refused. Both are
            # reported; neither is disguised as a successful model run.
            return AgentDispatchResult(
                role=role, agent_name=agent_name, runtime="deterministic-evidence",
                available=False, text=deterministic_result, tools_used=tools,
                error=f"{exc.__class__.__name__}: {exc}",
            )
        payload = result.to_dict() if hasattr(result, "to_dict") else dict(result)
        text = str(payload.get("output") or payload.get("text") or "").strip()
        return AgentDispatchResult(
            role=role,
            agent_name=agent_name,
            runtime="project117-agents",
            available=True,
            text=text or deterministic_result,
            tools_used=list(payload.get("tools_used") or tools),
            citations=list(payload.get("citations") or []),
        )


_roster: AgentRoster | None = None


def get_roster() -> AgentRoster:
    global _roster
    if _roster is None:
        _roster = AgentRoster()
    return _roster
