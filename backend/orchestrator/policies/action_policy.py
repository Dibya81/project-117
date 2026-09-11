"""Action policy — may this plan step run at all, for this caller?

The orchestrator asks this *before* execution, so a plan that a caller is not
entitled to run is refused as a whole rather than half-executed and then
blocked at the third step.

This layer answers one question per step: "which permission does running this
step require, and do the caller's roles carry it?". It deliberately does not
decide risk gating (``approval_policy``), tool eligibility (``tool_policy``)
or data scope (``data_policy``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from backend.orchestrator.src.plan import Plan, PlanStep
from backend.security.rbac import AuthorizationError, permissions_for
from backend.tools.base import Permission, ToolSpec

#: Permission required by a step kind that is not a tool call. Tool steps get
#: their permission from the tool's own spec, which is the authoritative one.
STEP_PERMISSIONS: dict[str, Permission | None] = {
    "retrieve": Permission.SEARCH_QUERY,
    "agent": Permission.SEARCH_QUERY,
    # Verification only reads what the plan already produced; gating it again
    # would let a caller run work it cannot have checked.
    "verify": None,
    "tool": None,
}


@dataclass(frozen=True)
class ActionDecision:
    """Why a step was allowed or refused. Recorded on the job trace."""

    step_id: str
    kind: str
    allowed: bool
    permission: str | None = None
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "stepId": self.step_id,
            "kind": self.kind,
            "allowed": self.allowed,
            "permission": self.permission,
            "reason": self.reason,
        }


class ActionPolicy:
    """Resolve and check the permission each plan step needs.

    ``tools`` is an optional :class:`~backend.tools.registry.ToolRegistry`. If
    it is missing, tool steps are refused rather than waved through: an
    unknown tool is not a safe tool.
    """

    def __init__(self, tools=None) -> None:
        self._tools = tools

    # -- introspection -------------------------------------------------
    def _specs(self) -> dict[str, ToolSpec]:
        if self._tools is None:
            return {}
        try:
            return {spec.name: spec for spec in self._tools.specs()}
        except Exception:  # pragma: no cover - a broken registry is not a grant
            return {}

    def required_permission(self, step: PlanStep) -> tuple[Permission | None, str]:
        """Return ``(permission, reason)``; ``reason`` explains an unresolvable step."""
        if step.kind != "tool":
            return STEP_PERMISSIONS.get(step.kind), ""
        name = step.name or str(step.arguments.get("tool") or "")
        if not name:
            return None, "tool step does not name a tool"
        spec = self._specs().get(name)
        if spec is None:
            return None, f"unknown tool '{name}'"
        return spec.permission, ""

    # -- evaluation ----------------------------------------------------
    def evaluate(self, step: PlanStep, *, roles: Iterable[str] | None) -> ActionDecision:
        permission, problem = self.required_permission(step)
        if problem:
            return ActionDecision(step.id, step.kind, False, None, problem)
        if permission is None:
            return ActionDecision(step.id, step.kind, True, None, "no permission required")
        granted = permissions_for(roles or ())
        if permission in granted:
            return ActionDecision(step.id, step.kind, True, permission.value, "granted")
        held = ", ".join(sorted(set(roles or ()))) or "none"
        return ActionDecision(
            step.id,
            step.kind,
            False,
            permission.value,
            f"role(s) {held} lack permission '{permission.value}'",
        )

    def evaluate_plan(
        self, plan: Plan, *, roles: Iterable[str] | None
    ) -> list[ActionDecision]:
        return [self.evaluate(step, roles=roles) for step in plan.steps]

    def enforce(self, plan: Plan, *, roles: Iterable[str] | None) -> Sequence[ActionDecision]:
        """Raise :class:`AuthorizationError` on the first refused step.

        Fails before any step runs, so a partially executed plan can never be
        the result of a permission problem.
        """
        decisions = self.evaluate_plan(plan, roles=roles)
        for decision in decisions:
            if not decision.allowed:
                raise AuthorizationError(
                    f"step '{decision.step_id}' refused: {decision.reason}"
                )
        return decisions


__all__ = ["STEP_PERMISSIONS", "ActionDecision", "ActionPolicy"]
