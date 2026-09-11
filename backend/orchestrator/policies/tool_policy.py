"""Tool policy — which tools a plan may use, and how many times.

Separate from :mod:`action_policy` (which asks "does this caller hold the
permission?") because the two fail for different reasons and a deployment
wants to tune them independently: an operator may hold ``code:execute`` while
this deployment still refuses to run ``execute``-risk tools unattended.

Three independent gates, all deny-by-default in spirit:

1. **Allow/deny lists** — an explicit ``allowed`` set means "only these".
2. **Risk ceiling** — refuse tools above ``max_risk`` outright.
3. **Call budget** — a plan cannot call tools an unbounded number of times.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from backend.security.rbac import permissions_for
from backend.tools.base import RiskLevel, ToolPermissionDenied, ToolSpec, risk_rank


@dataclass(frozen=True)
class ToolDecision:
    tool: str
    allowed: bool
    reason: str = ""
    risk: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "allowed": self.allowed,
            "reason": self.reason,
            "risk": self.risk,
        }


@dataclass(frozen=True)
class ToolPolicy:
    """Deployment-level constraints on tool use."""

    #: Highest risk level this deployment will run at all. Anything above is
    #: refused even with approval — approval gates *risk*, this gates *reach*.
    max_risk: RiskLevel = RiskLevel.EXECUTE
    #: Tool names that are never available.
    denied: frozenset[str] = field(default_factory=frozenset)
    #: If non-empty, an exclusive allowlist.
    allowed: frozenset[str] = field(default_factory=frozenset)
    #: Ceiling on tool invocations in a single plan/job.
    max_calls_per_plan: int = 32

    # -- evaluation ----------------------------------------------------
    def evaluate(self, spec: ToolSpec, *, roles: Iterable[str] | None = None) -> ToolDecision:
        if spec.name in self.denied:
            return ToolDecision(spec.name, False, "tool is denied by policy", spec.risk.value)
        if self.allowed and spec.name not in self.allowed:
            return ToolDecision(
                spec.name, False, "tool is not in this deployment's allowlist", spec.risk.value
            )
        if risk_rank(spec.risk) > risk_rank(self.max_risk):
            return ToolDecision(
                spec.name,
                False,
                f"risk '{spec.risk.value}' exceeds the deployment ceiling '{self.max_risk.value}'",
                spec.risk.value,
            )
        if roles is not None and spec.permission not in permissions_for(roles):
            held = ", ".join(sorted(set(roles))) or "none"
            return ToolDecision(
                spec.name,
                False,
                f"role(s) {held} lack permission '{spec.permission.value}'",
                spec.risk.value,
            )
        return ToolDecision(spec.name, True, "permitted", spec.risk.value)

    def check(self, spec: ToolSpec, *, roles: Iterable[str] | None = None) -> ToolDecision:
        """Raise :class:`ToolPermissionDenied` unless the tool may be used."""
        decision = self.evaluate(spec, roles=roles)
        if not decision.allowed:
            raise ToolPermissionDenied(f"{spec.name}: {decision.reason}")
        return decision

    def permitted(
        self, specs: Iterable[ToolSpec], *, roles: Iterable[str] | None = None
    ) -> list[ToolSpec]:
        """The subset a caller may actually use — used to build the tool list
        shown to the planner, so it cannot plan a step it may not run."""
        return [spec for spec in specs if self.evaluate(spec, roles=roles).allowed]

    def check_budget(self, call_count: int) -> None:
        if call_count > self.max_calls_per_plan:
            raise ToolPermissionDenied(
                f"plan requests {call_count} tool calls; ceiling is {self.max_calls_per_plan}"
            )

    def summary(self) -> dict[str, Any]:
        return {
            "maxRisk": self.max_risk.value,
            "denied": sorted(self.denied),
            "allowed": sorted(self.allowed),
            "maxCallsPerPlan": self.max_calls_per_plan,
        }


def policy_from_settings(settings: Any) -> ToolPolicy:
    """Build from settings, falling back to the conservative defaults above."""
    raw_risk = str(getattr(settings, "tool_max_risk", "") or "").strip().lower()
    try:
        max_risk = RiskLevel(raw_risk) if raw_risk else RiskLevel.EXECUTE
    except ValueError:
        max_risk = RiskLevel.EXECUTE
    denied = frozenset(getattr(settings, "tool_denylist", ()) or ())
    allowed = frozenset(getattr(settings, "tool_allowlist", ()) or ())
    budget = int(getattr(settings, "tool_max_calls_per_plan", 32) or 32)
    return ToolPolicy(
        max_risk=max_risk,
        denied=denied,
        allowed=allowed,
        max_calls_per_plan=max(1, budget),
    )


__all__ = ["ToolDecision", "ToolPolicy", "policy_from_settings"]
