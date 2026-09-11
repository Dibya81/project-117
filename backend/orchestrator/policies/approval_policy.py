"""Approval policy — which plan steps need a human before they run.

The risk rules themselves live in :mod:`backend.security.approvals` and are
shared with direct tool calls, so a step cannot dodge a gate by going through
the orchestrator instead of the tools API. This module is the plan-shaped view
of that same policy: it walks a plan, resolves each tool step's spec, and
reports which steps are gated and why.

A step is gated when either

* the tool's risk (or an explicit ``always_require`` rule) demands it, or
* the planner marked the step ``requires_approval`` — a plan may ask for more
  scrutiny than policy requires, never less.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from backend.orchestrator.src.plan import Plan, PlanStep
from backend.security.approvals import (
    ApprovalDecision,
    ApprovalPolicy,
)
from backend.security.approvals import (
    policy_from_settings as base_policy_from_settings,
)
from backend.tools.base import ToolSpec


@dataclass(frozen=True)
class StepApproval:
    """Per-step gating outcome, recorded on the job so the UI can show why a
    run is waiting rather than just that it is."""

    step_id: str
    tool: str | None
    required: bool
    reason: str = ""
    basis: str = "risk"
    risk: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stepId": self.step_id,
            "tool": self.tool,
            "required": self.required,
            "reason": self.reason,
            "basis": self.basis,
            "risk": self.risk,
        }


class PlanApprovalPolicy:
    """Apply :class:`ApprovalPolicy` across a whole plan.

    ``tools`` is an optional tool registry. When a tool step names a tool the
    registry does not know, the step is gated: an unresolvable step is never
    auto-approved.
    """

    def __init__(self, policy: ApprovalPolicy | None = None, tools: Any = None) -> None:
        self.policy = policy or ApprovalPolicy()
        self._tools = tools

    # -- helpers -------------------------------------------------------
    def _specs(self) -> dict[str, ToolSpec]:
        if self._tools is None:
            return {}
        try:
            return {spec.name: spec for spec in self._tools.specs()}
        except Exception:  # pragma: no cover - a broken registry is not a grant
            return {}

    @staticmethod
    def _tool_name(step: PlanStep) -> str:
        return step.name or str(step.arguments.get("tool") or "")

    # -- evaluation ----------------------------------------------------
    def evaluate_step(
        self,
        step: PlanStep,
        *,
        already_approved: bool = False,
        specs: dict[str, ToolSpec] | None = None,
    ) -> StepApproval:
        if step.kind != "tool":
            if step.requires_approval and not already_approved:
                return StepApproval(
                    step.id, None, True, "the plan marked this step for review", "policy"
                )
            return StepApproval(step.id, None, False, "no gate for this step kind", "risk")

        name = self._tool_name(step)
        catalogue = self._specs() if specs is None else specs
        spec = catalogue.get(name)
        if spec is None:
            return StepApproval(
                step.id,
                name or None,
                not already_approved,
                f"unknown tool '{name or 'unnamed'}' cannot be auto-approved",
                "tool_rule",
            )

        decision: ApprovalDecision = self.policy.evaluate(
            spec, already_approved=already_approved
        )
        required = decision.required or (step.requires_approval and not already_approved)
        reason = decision.reason
        basis = decision.basis
        if not decision.required and required:
            reason = "the plan marked this step for review"
            basis = "policy"
        return StepApproval(step.id, spec.name, required, reason, basis, spec.risk.value)

    def evaluate_plan(
        self, plan: Plan, *, approved_steps: Iterable[str] = ()
    ) -> list[StepApproval]:
        approved = set(approved_steps or ())
        specs = self._specs()
        return [
            self.evaluate_step(step, already_approved=step.id in approved, specs=specs)
            for step in plan.steps
        ]

    def gated_steps(
        self, plan: Plan, *, approved_steps: Iterable[str] = ()
    ) -> list[StepApproval]:
        return [s for s in self.evaluate_plan(plan, approved_steps=approved_steps) if s.required]

    def requires_approval(self, plan: Plan, *, approved_steps: Iterable[str] = ()) -> bool:
        return bool(self.gated_steps(plan, approved_steps=approved_steps))

    def summary(self) -> dict[str, Any]:
        return self.policy.summary()


def policy_from_settings(settings: Any, tools: Any = None) -> PlanApprovalPolicy:
    """Build the plan-level policy from the same settings the tools API uses."""
    return PlanApprovalPolicy(base_policy_from_settings(settings), tools=tools)


__all__ = [
    "ApprovalDecision",
    "ApprovalPolicy",
    "PlanApprovalPolicy",
    "StepApproval",
    "policy_from_settings",
]
