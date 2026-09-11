"""Agent result construction helpers.

:class:`AgentResult` itself is defined once in ``agent.py`` and re-exported
here — two definitions of a result shape is how a "grounded" flag ends up
meaning two different things. What lives here are the constructors, so every
agent reports success, degradation and failure the same way.

The rule these enforce: an answer produced without evidence is never marked
grounded, and an agent that could not do its job says so in ``degraded`` plus
a note, rather than returning a confident-looking empty answer.
"""

from __future__ import annotations

from typing import Any, Sequence

from backend.agents.base.agent import AgentResult


def ok(
    answer: str,
    *,
    agent: str,
    model: str | None = None,
    evidence_count: int = 0,
    grounded: bool | None = None,
    notes: Sequence[str] = (),
    usage: dict[str, int] | None = None,
) -> AgentResult:
    """A normal answer. ``grounded`` defaults to "only if evidence was used"."""
    return AgentResult(
        answer=answer,
        agent=agent,
        model=model,
        grounded=bool(evidence_count > 0) if grounded is None else bool(grounded),
        evidence_count=int(evidence_count),
        notes=list(notes),
        usage=dict(usage or {}),
    )


def degraded(
    answer: str,
    *,
    agent: str,
    note: str,
    model: str | None = None,
    evidence_count: int = 0,
    notes: Sequence[str] = (),
) -> AgentResult:
    """The agent answered, but something was missing and the caller must know."""
    collected = [note, *notes]
    return AgentResult(
        answer=answer,
        agent=agent,
        model=model,
        grounded=evidence_count > 0,
        degraded=True,
        evidence_count=int(evidence_count),
        notes=collected,
    )


def ungrounded(agent: str, *, task: str = "", model: str | None = None) -> AgentResult:
    """No evidence was retrievable. Refuse rather than answer from priors."""
    subject = f" for: {task}" if task else ""
    return AgentResult(
        answer=(
            "No supporting evidence was found in the indexed corpus"
            f"{subject}. Answering would mean inventing the basis for it."
        ),
        agent=agent,
        model=model,
        grounded=False,
        degraded=True,
        evidence_count=0,
        notes=["no evidence retrieved; refused to answer unsupported"],
    )


def with_code(result: AgentResult, code: str, *, filename: str | None = None) -> AgentResult:
    """Attach generated code for a following ``run_python`` step."""
    result.code = code
    if filename:
        result.filename = filename
    return result


def with_spec(
    result: AgentResult, spec: dict[str, Any], *, filename: str | None = None
) -> AgentResult:
    """Attach an artifact specification for a following generator step."""
    result.spec = spec
    if filename:
        result.filename = filename
    return result


def add_note(result: AgentResult, note: str) -> AgentResult:
    if note and note not in result.notes:
        result.notes.append(note)
    return result


__all__ = [
    "AgentResult",
    "add_note",
    "degraded",
    "ok",
    "ungrounded",
    "with_code",
    "with_spec",
]
