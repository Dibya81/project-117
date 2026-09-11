"""Failure classification and recovery (Phase 6).

When a step fails, something has to decide between four options: retry,
replan, park for a human, or fail the job. Getting this wrong is expensive in
both directions - retrying a permission error wastes a minute and produces the
same error, while failing a transient connection blip throws away a
thirty-second retrieval.

The decision is made from the **error class**, not the error message, because
messages change and this logic has to stay predictable:

=========================  ===========  ============================================
Failure                    Action       Why
=========================  ===========  ============================================
timeout                    RETRY (1x)   Often load; a second attempt is cheap.
provider unreachable       RETRY        Ollama restarting is the common case.
provider HTTP 5xx          RETRY        Server-side and usually transient.
model not configured       FAIL         Retrying cannot configure a model.
index unavailable          FAIL         Needs an operator, not another attempt.
invalid tool arguments     REPLAN       The planner produced them; it can fix them.
artifact spec invalid      REPLAN       Same - the model can correct the spec.
verification rejected      REPLAN       Try once more with the failures as input.
permission denied          FAIL         Authorisation does not change on retry.
approval required          PARK         Waiting for a human is not a failure.
sandbox unavailable        FAIL         Operator action required.
sandbox policy violation   FAIL         A refusal, not a fault. Never retried.
cancelled                  CANCEL       The user asked; stop.
=========================  ===========  ============================================

One rule stated explicitly because it is the tempting thing to get wrong:
**a policy refusal is never retried and never replanned.** If the sandbox
policy or the RBAC layer said no, trying again with a slightly different
shape is exactly the behaviour an attacker would want.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

#: A step gets one retry by default. More than that turns a slow failure into
#: a very slow failure.
DEFAULT_MAX_ATTEMPTS = 2

#: Replans are limited too: two failed plans mean the problem is not the plan.
DEFAULT_MAX_REPLANS = 1


class RecoveryAction(str, Enum):
    RETRY = "retry"
    REPLAN = "replan"
    PARK = "park"
    FAIL = "fail"
    CANCEL = "cancel"


@dataclass(frozen=True)
class RecoveryDecision:
    action: RecoveryAction
    reason: str
    #: Seconds to wait before a retry. Small and fixed; this is a local
    #: machine, not a rate-limited cloud API.
    delay_seconds: float = 0.0
    #: Surfaced to the user when the job ends. Plain language, no stack trace.
    user_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "reason": self.reason,
            "delay_seconds": self.delay_seconds,
            "user_message": self.user_message,
        }


#: Exception ``reason`` attributes (every error class in this backend carries
#: one) mapped to an action. Matching on ``reason`` rather than on the class
#: keeps this module free of imports from every other package.
_ACTION_BY_REASON: dict[str, tuple[RecoveryAction, str]] = {
    # transient
    "provider_unreachable": (RecoveryAction.RETRY, "the local model backend was unreachable"),
    "provider_http_error": (RecoveryAction.RETRY, "the local model backend returned an error"),
    "tool_timeout": (RecoveryAction.RETRY, "the step exceeded its time limit"),
    # configuration / operator
    "model_unavailable": (RecoveryAction.FAIL, "no local model is configured for this role"),
    "index_unavailable": (RecoveryAction.FAIL, "the document index is not available"),
    "reranker_unavailable": (RecoveryAction.FAIL, "the reranker is not available"),
    "graph_unavailable": (RecoveryAction.FAIL, "the knowledge graph is not available"),
    "sandbox_unavailable": (RecoveryAction.FAIL, "the sandbox service is not available"),
    "tool_unavailable": (RecoveryAction.FAIL, "a required tool is not available"),
    # model produced something wrong - it can try again with feedback
    "tool_arguments_invalid": (RecoveryAction.REPLAN, "the plan produced invalid arguments"),
    "artifact_spec_invalid": (RecoveryAction.REPLAN, "the artifact specification was rejected"),
    "verification_rejected": (RecoveryAction.REPLAN, "verification rejected the result"),
    "invalid_job_transition": (RecoveryAction.FAIL, "internal state error"),
    # refusals - never retried
    "forbidden": (RecoveryAction.FAIL, "the caller is not permitted to perform this action"),
    "tool_permission_denied": (RecoveryAction.FAIL, "the caller lacks permission for this tool"),
    "sandbox_policy_violation": (RecoveryAction.FAIL, "the sandbox policy refused this action"),
    "egress_blocked": (RecoveryAction.FAIL, "an outbound connection was blocked by policy"),
    # human in the loop
    "approval_required": (RecoveryAction.PARK, "a human must approve this step"),
    # user action
    "job_cancelled": (RecoveryAction.CANCEL, "the job was cancelled"),
}


class RecoveryManager:
    def __init__(
        self,
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        max_replans: int = DEFAULT_MAX_REPLANS,
        retry_delay_seconds: float = 1.0,
    ) -> None:
        self._max_attempts = max(1, max_attempts)
        self._max_replans = max(0, max_replans)
        self._retry_delay = max(0.0, retry_delay_seconds)

    def classify(
        self,
        error: BaseException,
        *,
        attempts: int = 1,
        replans: int = 0,
    ) -> RecoveryDecision:
        reason = str(getattr(error, "reason", "") or "")
        action, explanation = _ACTION_BY_REASON.get(
            reason,
            # Include the message. "unhandled ToolArgumentError" alone told an
            # operator nothing; the exception text names the missing argument.
            (RecoveryAction.FAIL, f"{type(error).__name__}: {error}"),
        )

        if action is RecoveryAction.RETRY and attempts >= self._max_attempts:
            return RecoveryDecision(
                RecoveryAction.FAIL,
                f"{explanation}; {attempts} attempt(s) made",
                user_message=(
                    f"{explanation.capitalize()}. Tried {attempts} times and stopped rather "
                    "than looping."
                ),
            )

        if action is RecoveryAction.REPLAN and replans >= self._max_replans:
            return RecoveryDecision(
                RecoveryAction.FAIL,
                f"{explanation}; already replanned {replans} time(s)",
                user_message=(
                    f"{explanation.capitalize()}. Replanning did not help, so the job was "
                    "stopped instead of producing an unverified result."
                ),
            )

        if action is RecoveryAction.RETRY:
            return RecoveryDecision(
                action,
                explanation,
                delay_seconds=self._retry_delay,
                user_message=f"{explanation.capitalize()}. Retrying once.",
            )

        return RecoveryDecision(
            action,
            explanation,
            user_message=explanation.capitalize() + ".",
        )

    def describe(self) -> dict[str, Any]:
        return {
            "max_attempts": self._max_attempts,
            "max_replans": self._max_replans,
            "retry_delay_seconds": self._retry_delay,
        }
