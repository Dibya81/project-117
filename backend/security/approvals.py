"""Approval policy (Phase 12).

One question, asked before a tool runs: does a human have to say yes first?

The default answer is derived from the tool's declared risk, not from the
tool's opinion of itself and not from the plan:

==========  ==============  ==================================================
Risk        Default         Rationale
==========  ==============  ==================================================
read        auto            Retrieval and document reads change nothing.
compute     auto            Deterministic work on already-approved data.
write       auto            Produces a file inside the job's own workspace.
execute     **gated**       Runs model-authored code. Nobody reviewed it.
external    **gated**       Leaves this machine. Cannot be undone from here.
==========  ==============  ==================================================

The gate is evaluated *before* the handler is invoked, so a parked job has
changed nothing: no container started, no connector called, no file written.
Approval then resumes exactly that step.

Relaxations exist (``P117_APPROVAL_AUTO_EXECUTE`` for an unattended demo box)
and they are deliberately awkward: they are settings on the server, not fields
in a request, and ``always_require`` cannot be overridden by them. A plan, an
agent, or a document that says "no approval needed" has no effect here -
which matters, because plans and documents are partly written by models and
models can be talked into things.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.tools.base import RiskLevel, ToolSpec, risk_rank

#: Risk at or above which approval is required by default.
GATE_AT = risk_rank(RiskLevel.EXECUTE)


@dataclass(frozen=True)
class ApprovalDecision:
    required: bool
    reason: str = ""
    #: Why this decision was reached: ``risk`` | ``policy`` | ``already_approved``
    #: | ``tool_rule``. Recorded on the audit row so a permissive deployment is
    #: visible afterwards.
    basis: str = "risk"

    def as_state(self) -> str:
        """Value for the ``approval`` column on jobs, audit and tool rows."""
        return "pending" if self.required else "not_required"

    def to_dict(self) -> dict[str, Any]:
        return {"required": self.required, "reason": self.reason, "basis": self.basis}


@dataclass(frozen=True)
class ApprovalPolicy:
    #: Allow ``execute`` risk without a human. For an unattended demo only.
    auto_approve_execute: bool = False
    #: Allow ``external`` risk without a human. Strongly discouraged.
    auto_approve_external: bool = False
    #: Tool names that always need approval regardless of risk. Cannot be
    #: relaxed by the flags above.
    always_require: frozenset[str] = field(default_factory=frozenset)

    def evaluate(self, spec: ToolSpec, *, already_approved: bool = False) -> ApprovalDecision:
        if spec.name in self.always_require:
            if already_approved:
                return ApprovalDecision(False, "approved by a reviewer", "already_approved")
            return ApprovalDecision(
                True,
                f"'{spec.name}' always requires approval by configuration",
                "tool_rule",
            )
        if already_approved:
            return ApprovalDecision(False, "approved by a reviewer", "already_approved")

        rank = risk_rank(spec.risk)
        if rank < GATE_AT:
            return ApprovalDecision(False, f"{spec.risk.value} risk is auto-approved", "risk")

        if spec.risk is RiskLevel.EXTERNAL and self.auto_approve_external:
            return ApprovalDecision(
                False, "external risk auto-approved by configuration", "policy"
            )
        if spec.risk is RiskLevel.EXECUTE and self.auto_approve_execute:
            return ApprovalDecision(
                False, "code execution auto-approved by configuration", "policy"
            )
        return ApprovalDecision(
            True,
            f"'{spec.name}' is {spec.risk.value} risk and needs human approval",
            "risk",
        )

    def summary(self) -> dict[str, Any]:
        return {
            "gate_at": RiskLevel.EXECUTE.value,
            "auto_approve_execute": self.auto_approve_execute,
            "auto_approve_external": self.auto_approve_external,
            "always_require": sorted(self.always_require),
        }


def policy_from_settings(settings: Any) -> ApprovalPolicy:
    """Build the policy from application settings.

    Reads ``approval_always_require``, ``approval_auto_execute`` and
    ``approval_auto_external``. Missing attributes fall back to the strict
    default, so an older settings object cannot silently open the gate.
    """
    always = getattr(settings, "approval_always_require", None) or ()
    if isinstance(always, str):
        always = [part.strip() for part in always.split(",") if part.strip()]
    return ApprovalPolicy(
        auto_approve_execute=bool(getattr(settings, "approval_auto_execute", False)),
        auto_approve_external=bool(getattr(settings, "approval_auto_external", False)),
        always_require=frozenset(str(name) for name in always),
    )
