"""The context an agent is handed for one task.

Immutable on purpose. An agent receives the evidence, scope and services it
needs, and cannot widen any of them mid-run: narrowing (``scoped``) returns a
new context, and there is no setter that grants a document, a role or a tool
the caller did not already have.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Sequence

from backend.agents.base.agent import BaseAgent


@dataclass(frozen=True)
class AgentContext:
    """Everything an agent may use, and nothing it may not."""

    task: str = ""
    job_id: str | None = None
    step_id: str | None = None
    user: str | None = None
    roles: tuple[str, ...] = ()
    #: Retrieved chunks, already filtered by the data policy.
    evidence: tuple[dict[str, Any], ...] = ()
    #: Scope granted by the caller. Empty means "whole corpus".
    document_ids: tuple[str, ...] = ()
    #: Services. Any of these may be None; an agent must degrade honestly
    #: rather than assume they are present.
    retrieval: Any = None
    tools: Any = None
    memory: Any = None
    router: Any = None
    #: Free-form inputs from the plan step.
    inputs: dict[str, Any] = field(default_factory=dict)

    # -- derived views -------------------------------------------------
    @property
    def evidence_count(self) -> int:
        return len(self.evidence)

    @property
    def grounded(self) -> bool:
        """True when there is evidence to ground an answer in."""
        return bool(self.evidence)

    def evidence_text(self) -> str:
        """Render evidence for a prompt using the agent's own formatter, so
        prompt-side and context-side never drift apart."""
        return BaseAgent.evidence_text(self)

    def citations(self) -> list[dict[str, Any]]:
        """Citation stubs for every evidence chunk, in retrieval order."""
        out: list[dict[str, Any]] = []
        for item in self.evidence:
            if not isinstance(item, dict):
                continue
            out.append(
                {
                    "document_id": item.get("document_id") or item.get("documentId"),
                    "document_name": item.get("document_name") or item.get("filename"),
                    "chunk_id": item.get("chunk_id") or item.get("id"),
                    "score": item.get("score"),
                }
            )
        return out

    # -- narrowing -----------------------------------------------------
    def scoped(self, document_ids: Sequence[str]) -> "AgentContext":
        """Narrow the document scope. Never widens: the result is the
        intersection when a scope was already set."""
        requested = tuple(document_ids or ())
        if self.document_ids:
            allowed = set(self.document_ids)
            requested = tuple(d for d in requested if d in allowed)
        return replace(self, document_ids=requested)

    def with_evidence(self, evidence: Sequence[dict[str, Any]]) -> "AgentContext":
        return replace(self, evidence=tuple(evidence or ()))

    def with_inputs(self, **inputs: Any) -> "AgentContext":
        merged = dict(self.inputs)
        merged.update(inputs)
        return replace(self, inputs=merged)

    # -- serialisation -------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        """Trace-safe view: service handles and raw chunk text are omitted."""
        return {
            "task": self.task,
            "jobId": self.job_id,
            "stepId": self.step_id,
            "user": self.user,
            "roles": list(self.roles),
            "evidenceCount": self.evidence_count,
            "documentScope": list(self.document_ids),
            "hasRetrieval": self.retrieval is not None,
            "hasTools": self.tools is not None,
            "hasMemory": self.memory is not None,
            "inputs": sorted(self.inputs),
        }


__all__ = ["AgentContext"]
