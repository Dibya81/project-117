"""Resolve which tools an agent may actually use.

An agent *declares* the tools it was designed around (``BaseAgent.tool_names``).
What it may use at run time is the intersection of that declaration with:

1. what is registered in this deployment,
2. what the caller's roles permit, and
3. what the deployment's tool policy allows (risk ceiling, allow/deny list).

Resolving this before prompting matters: if the model is told about a tool it
is not allowed to call, it will plan a step that fails at execution time and
the user sees a broken run instead of a narrower but working one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from backend.security.rbac import permissions_for
from backend.tools.base import ToolSpec


@dataclass(frozen=True)
class ToolAvailability:
    """What the agent asked for versus what it got, and why."""

    available: tuple[ToolSpec, ...] = ()
    unregistered: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()

    @property
    def names(self) -> list[str]:
        return [spec.name for spec in self.available]

    @property
    def complete(self) -> bool:
        """True when every declared tool is usable."""
        return not self.unregistered and not self.forbidden

    def notes(self) -> list[str]:
        """Operator-facing notes to attach to a degraded result."""
        out: list[str] = []
        if self.unregistered:
            out.append(
                "tools not registered in this deployment: "
                + ", ".join(sorted(self.unregistered))
            )
        if self.forbidden:
            out.append(
                "tools withheld by policy or permissions: "
                + ", ".join(sorted(self.forbidden))
            )
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.names,
            "unregistered": list(self.unregistered),
            "forbidden": list(self.forbidden),
            "complete": self.complete,
        }


def _catalogue(registry: Any) -> dict[str, ToolSpec]:
    if registry is None:
        return {}
    try:
        return {spec.name: spec for spec in registry.specs()}
    except Exception:  # pragma: no cover - a broken registry grants nothing
        return {}


def resolve(
    declared: Sequence[str],
    *,
    registry: Any = None,
    roles: Iterable[str] | None = None,
    policy: Any = None,
) -> ToolAvailability:
    """Intersect declared tools with registration, permissions and policy.

    ``policy`` is duck-typed: anything exposing ``evaluate(spec, roles=...)``
    with an ``.allowed`` attribute works, which keeps the agents package free
    of an import back into the orchestrator.
    """
    catalogue = _catalogue(registry)
    granted = permissions_for(roles) if roles is not None else None

    available: list[ToolSpec] = []
    unregistered: list[str] = []
    forbidden: list[str] = []

    for name in declared or ():
        spec = catalogue.get(name)
        if spec is None:
            unregistered.append(name)
            continue
        if granted is not None and spec.permission not in granted:
            forbidden.append(name)
            continue
        if policy is not None:
            try:
                decision = policy.evaluate(spec, roles=roles)
            except TypeError:
                decision = policy.evaluate(spec)
            if not getattr(decision, "allowed", True):
                forbidden.append(name)
                continue
        available.append(spec)

    return ToolAvailability(
        available=tuple(available),
        unregistered=tuple(unregistered),
        forbidden=tuple(forbidden),
    )


def describe(specs: Iterable[ToolSpec], *, limit: int = 12) -> str:
    """Compact catalogue for a prompt: name, purpose, risk.

    Kept short deliberately — a long tool dump crowds out the evidence, which
    is what the answer actually has to be grounded in.
    """
    lines: list[str] = []
    for spec in list(specs)[: max(1, limit)]:
        lines.append(f"- {spec.name} ({spec.risk.value}): {spec.description}")
    return "\n".join(lines)


__all__ = ["ToolAvailability", "describe", "resolve"]
