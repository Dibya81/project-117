"""Retry policy for the workflow engine path.

Pure policy: :meth:`RetryManager.decide` takes an attempt number and an error
and returns a decision. It does not sleep, does not call the executor and does
not mutate run state. The runner owns those.

The important half of this module is what it refuses to retry. Retrying is only
reasonable when the same call might plausibly succeed unchanged. Four classes
of error can never satisfy that:

* **permission denied** (``tool_forbidden``) - the caller's roles will not
  change between attempts, so a retry is a guaranteed second denial. Retrying
  also turns one audit record into several, which makes a genuine
  authorisation problem look like an attack.
* **approval required** (``approval_required``) - the run is supposed to stop
  and wait for a human. Retrying would either spin against the gate or, worse,
  eventually be interpreted as progress.
* **argument errors** (``tool_invalid_arguments``) and **unknown tool**
  (``tool_not_found``) - the arguments come from a reviewed YAML file and are
  identical on every attempt. This is an authoring bug; the correct behaviour
  is to surface it immediately.
* **policy refusals** - the action, tool and data policies decide against the
  *plan*, not against the moment. A refusal that changed on retry would mean
  the policy was not deterministic.

Everything else is treated as possibly transient. That includes
``tool_failed``, which is the honest weak point of this taxonomy: the tool
contract does not distinguish "the network blipped" from "this input will
never work", so a deterministic failure will be retried up to the author's
``max_attempts``. The mitigation is that ``max_attempts`` defaults to 1, so a
workflow only retries where its author asked for it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.workflows.engine.registry import RetrySpec

#: Error ``reason`` values that must never be retried. These strings are the
#: ``reason`` class attributes on the exceptions in ``backend.tools.base`` and
#: the orchestrator policies. They are matched as data rather than by importing
#: those modules, so this module stays importable without the tool registry
#: (and cannot introduce an import cycle through it).
NON_RETRYABLE_REASONS: frozenset[str] = frozenset(
    {
        "tool_forbidden",
        "approval_required",
        "tool_invalid_arguments",
        "tool_not_found",
        "policy_refused",
        "action_refused",
        "data_policy_refused",
        "tool_policy_refused",
        "routing_refused",
        "workflow_invalid",
        "workflow_not_found",
        "condition_error",
        "invalid_transition",
        "executor_contract",
        "spec_invalid",
        "cancelled",
    }
)

#: Reasons known to be worth another attempt.
RETRYABLE_REASONS: frozenset[str] = frozenset(
    {
        "tool_timeout",
        "tool_unavailable",
        "tool_failed",
        "provider_unreachable",
        "model_unavailable",
    }
)

#: Exception class names that are non-retryable even without a ``reason``.
#: ``TypeError``/``ValueError`` from an executor mean the call was malformed,
#: which no amount of repetition fixes.
_NON_RETRYABLE_TYPES: frozenset[str] = frozenset(
    {
        "ToolPermissionDenied",
        "ToolApprovalRequired",
        "ToolArgumentError",
        "ToolNotFound",
        "ConditionError",
        "InvalidTransition",
        "ApprovalNotSupported",
        "ExecutorContractError",
        "PermissionError",
        "TypeError",
        "ValueError",
        "KeyError",
        "AttributeError",
        "NotImplementedError",
        "CancelledError",
        "KeyboardInterrupt",
    }
)


def classify(error: BaseException) -> str:
    """Best-effort machine-readable reason for an exception.

    Prefers an explicit ``reason`` attribute (every error in this codebase
    that crosses a module boundary declares one), and falls back to the class
    name so an unexpected exception still classifies as something.
    """
    reason = getattr(error, "reason", None)
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    return type(error).__name__


def is_retryable(error: BaseException) -> bool:
    """Whether ``error`` could plausibly succeed on an identical retry.

    A declared ``reason`` wins over the exception type, so a domain error that
    happens to subclass ``ValueError`` is still classified by what it says it
    is rather than by what it inherits from.
    """
    reason = classify(error)
    if reason in NON_RETRYABLE_REASONS:
        return False
    if reason in RETRYABLE_REASONS:
        return True
    # No recognised reason: fall back to the exception type. Unknown
    # exceptions are treated as transient, because the alternative - refusing
    # to retry anything unrecognised - would make `retry:` useless for exactly
    # the third-party failures it is meant to absorb.
    return type(error).__name__ not in _NON_RETRYABLE_TYPES


@dataclass(frozen=True)
class RetryDecision:
    """The outcome of one policy question."""

    retry: bool
    #: Seconds to wait before the next attempt. Always 0.0 when ``retry`` is false.
    delay_seconds: float
    #: Human-readable justification, recorded on the step so a reader can see
    #: why a failure was or was not retried.
    explanation: str
    #: Machine-readable classification of the error that prompted the question.
    error_reason: str
    #: Attempt number that just failed (1-based).
    attempt: int
    #: Attempts still permitted after this decision.
    attempts_remaining: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "retry": self.retry,
            "delay_seconds": round(self.delay_seconds, 3),
            "explanation": self.explanation,
            "error_reason": self.error_reason,
            "attempt": self.attempt,
            "attempts_remaining": self.attempts_remaining,
        }


class RetryManager:
    """Applies a :class:`RetrySpec` to concrete failures.

    A manager instance is stateless with respect to runs; the attempt number is
    passed in. That keeps one manager safe to share across concurrent steps.
    """

    #: Used when a step declares no ``retry:`` block. One attempt, no waiting.
    DEFAULT_SPEC = RetrySpec(max_attempts=1)

    def __init__(self, *, default: RetrySpec | None = None) -> None:
        self._default = default or self.DEFAULT_SPEC

    def spec_for(self, spec: RetrySpec | None) -> RetrySpec:
        return spec or self._default

    def backoff_for(self, spec: RetrySpec | None, attempt: int) -> float:
        """Delay before attempt ``attempt + 1``.

        Exponential from ``backoff_seconds``, capped at ``max_backoff_seconds``.
        No jitter: these runs are operator-triggered and single-tenant, so the
        thundering-herd problem jitter solves does not exist here. Adding fake
        randomness would only make runs less reproducible.
        """
        resolved = self.spec_for(spec)
        if attempt < 1:
            attempt = 1
        delay = resolved.backoff_seconds * (resolved.backoff_multiplier ** (attempt - 1))
        return float(min(delay, resolved.max_backoff_seconds))

    def decide(
        self,
        *,
        attempt: int,
        error: BaseException,
        spec: RetrySpec | None = None,
    ) -> RetryDecision:
        """Should attempt ``attempt`` be followed by another one?"""
        resolved = self.spec_for(spec)
        reason = classify(error)
        remaining = max(0, resolved.max_attempts - attempt)

        if not is_retryable(error):
            return RetryDecision(
                retry=False,
                delay_seconds=0.0,
                explanation=(
                    f"'{reason}' is not retryable; an identical retry would fail "
                    "the same way"
                ),
                error_reason=reason,
                attempt=attempt,
                attempts_remaining=0,
            )

        if remaining <= 0:
            return RetryDecision(
                retry=False,
                delay_seconds=0.0,
                explanation=(
                    f"exhausted the {resolved.max_attempts} attempt(s) this step declares"
                ),
                error_reason=reason,
                attempt=attempt,
                attempts_remaining=0,
            )

        delay = self.backoff_for(resolved, attempt)
        return RetryDecision(
            retry=True,
            delay_seconds=delay,
            explanation=(
                f"'{reason}' may be transient; retrying after {delay:.1f}s "
                f"({remaining} attempt(s) left)"
            ),
            error_reason=reason,
            attempt=attempt,
            attempts_remaining=remaining,
        )


__all__ = [
    "NON_RETRYABLE_REASONS",
    "RETRYABLE_REASONS",
    "RetryDecision",
    "RetryManager",
    "classify",
    "is_retryable",
]
