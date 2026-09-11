"""Execution policies applied to a plan before and during a run.

Four concerns, deliberately kept apart because they fail for different
reasons and a deployment tunes them independently:

===================  ======================================================
``action_policy``    Does this caller hold the permission the step needs?
``tool_policy``      Is this tool available in this deployment at all
                     (allow/deny list, risk ceiling, call budget)?
``approval_policy``  Does this step need a human before it runs?
``data_policy``      What may the step read, where may it send, what is
                     safe to record?
===================  ======================================================

The risk rules behind ``approval_policy`` and the egress rules behind
``data_policy`` are the same objects used by the direct tools API, so a step
cannot dodge a gate by routing through the orchestrator.
"""

from backend.orchestrator.policies.action_policy import (
    STEP_PERMISSIONS,
    ActionDecision,
    ActionPolicy,
)
from backend.orchestrator.policies.approval_policy import (
    PlanApprovalPolicy,
    StepApproval,
)
from backend.orchestrator.policies.approval_policy import (
    policy_from_settings as approval_policy_from_settings,
)
from backend.orchestrator.policies.data_policy import (
    DataPolicy,
    DataScopeViolation,
    policy_for_job,
)
from backend.orchestrator.policies.tool_policy import ToolDecision, ToolPolicy
from backend.orchestrator.policies.tool_policy import (
    policy_from_settings as tool_policy_from_settings,
)

__all__ = [
    "STEP_PERMISSIONS",
    "ActionDecision",
    "ActionPolicy",
    "DataPolicy",
    "DataScopeViolation",
    "PlanApprovalPolicy",
    "StepApproval",
    "ToolDecision",
    "ToolPolicy",
    "approval_policy_from_settings",
    "policy_for_job",
    "tool_policy_from_settings",
]
