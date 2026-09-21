"""Verification contracts (Phase 11).

Verification is a separate stage with its own inputs, not a self-assessment
bolted onto generation. The generator does not get to grade itself, and
"the model said the answer looks right" is not a check - every checker in
this package either recomputes something, opens something, or compares a
claim against retrieved evidence.

The important field is :attr:`CheckResult.blocking`. A blocking failure means
the job may not reach ``COMPLETED``; the caller gets the work plus an explicit
rejection instead of a confident answer that nobody validated. Non-blocking
failures are warnings: worth surfacing, not worth failing a job over.

``VerificationReport.may_complete`` is the single question the orchestrator
asks. It is computed from the checks, so nobody can "pass" verification by
setting a flag.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class CheckStatus(str, Enum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    #: The check could not run (missing dependency, nothing to check). Never
    #: reported as a pass - an unrun check is not a satisfied requirement.
    SKIPPED = "skipped"


@dataclass
class CheckResult:
    checker: str
    status: CheckStatus
    message: str = ""
    #: Per-item detail: which claim, which citation, which slide. Kept short
    #: and free of document text so reports stay loggable.
    findings: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: float = 0.0
    #: When True, a FAILED result prevents job success.
    blocking: bool = True

    @property
    def failed(self) -> bool:
        return self.status is CheckStatus.FAILED

    def to_dict(self) -> dict[str, Any]:
        return {
            "checker": self.checker,
            "status": self.status.value,
            "message": self.message,
            "findings": self.findings[:50],
            "duration_ms": round(self.duration_ms, 1),
            "blocking": self.blocking,
        }


@dataclass
class VerificationInput:
    """Everything the checkers are allowed to look at.

    ``evidence`` is the retrieved set - the only source a claim may be
    grounded in. ``artifacts`` are records produced this job, each carrying a
    storage path and sha256 so the artifact checker verifies the exact bytes
    that will be handed to the user.
    """

    task: str = ""
    answer: str = ""
    evidence: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    #: Sandbox service, when available, so calculation checks can recompute
    #: arithmetic in isolation instead of trusting the model's mental maths.
    sandbox: Any = None
    #: Durable audit sink, when available. The audit-chain checker walks its
    #: hash chain; without it that check is SKIPPED, never passed.
    audit: Any = None
    job_id: str | None = None
    user: str | None = None
    #: Extra per-check context (expected slide count, tolerance, policy).
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationReport:
    checks: list[CheckResult] = field(default_factory=list)

    def add(self, result: CheckResult) -> CheckResult:
        self.checks.append(result)
        return result

    @property
    def blocking_failures(self) -> list[CheckResult]:
        return [check for check in self.checks if check.failed and check.blocking]

    @property
    def warnings(self) -> list[CheckResult]:
        return [
            check
            for check in self.checks
            if check.status is CheckStatus.WARNING or (check.failed and not check.blocking)
        ]

    @property
    def skipped(self) -> list[CheckResult]:
        return [check for check in self.checks if check.status is CheckStatus.SKIPPED]

    @property
    def ran(self) -> list[CheckResult]:
        """Checks that actually reached a verdict."""
        return [check for check in self.checks if check.status is not CheckStatus.SKIPPED]

    @property
    def may_complete(self) -> bool:
        """The only question the orchestrator asks before COMPLETED."""
        return not self.blocking_failures

    @property
    def status(self) -> str:
        """``verified`` | ``verified_with_warnings`` | ``unverified`` | ``rejected``.

        ``unverified`` exists because of the one collapse this package must
        never allow: if every check skipped - no verifier wired, no evidence to
        check against, no artifact to open - then nothing objected, but nothing
        was examined either. Returning ``verified`` there would put the word
        "verified" on work no checker ever looked at, which is precisely the
        false assurance this stage was built to prevent.
        """
        if self.blocking_failures:
            return "rejected"
        if not self.ran:
            return "unverified"
        if self.warnings:
            return "verified_with_warnings"
        return "verified"

    def summary(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "may_complete": self.may_complete,
            # How many checks reached a verdict, so a reader can tell a green
            # report apart from an empty one.
            "checks_ran": len(self.ran),
            "checks": [check.to_dict() for check in self.checks],
            "blocking_failures": [check.checker for check in self.blocking_failures],
            "counts": {
                status.value: sum(1 for c in self.checks if c.status is status)
                for status in CheckStatus
            },
        }


@runtime_checkable
class Checker(Protocol):
    """A single verification concern.

    Checkers are async because some of them execute code in the sandbox. They
    must not raise: an exception inside a checker is itself a verification
    failure, and the verifier converts it into one.
    """

    @property
    def name(self) -> str: ...

    async def check(self, payload: VerificationInput) -> CheckResult: ...
