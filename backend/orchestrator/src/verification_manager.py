"""Verification stage wiring (Phase 6 + Phase 11).

The orchestrator does not call checkers directly. It calls this manager, which
assembles a :class:`~backend.verification.base.VerificationInput` and hands it
to the verifier.

The reason for the indirection is the property the review asked for: the thing
that decides whether a job succeeded must not be the thing that produced the
answer. The generator has an interest in its own output; the verifier is given
only the artefacts and the retrieved evidence, and its verdict is what the job
state machine consults.

This manager takes plain fields rather than an ``ExecutionState``. Verification
is meant to see the result, not the machinery that produced it - and keeping
the dependency pointing one way means the verification side cannot start
reaching into execution internals later.

Three behaviours worth being explicit about:

**No verifier means "not verified", never "verified".** If no verifier is wired
the report contains a single skipped, non-blocking check, which makes
:attr:`VerificationReport.status` report ``unverified``. It is never silently
upgraded.

**Verification failing is not verification passing.** If the verifier itself
raises, that becomes a blocking failure. A crash in the component whose job is
to catch problems cannot be the reason a problem gets through.

**Only blocking failures stop a job.** Warnings travel with the result so the
caller sees them; they do not silently discard work. That distinction is what
keeps verification useful rather than something operators learn to route
around.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from backend.verification.base import (
    CheckResult,
    CheckStatus,
    VerificationInput,
    VerificationReport,
)

logger = logging.getLogger(__name__)


class VerificationManager:
    def __init__(
        self, *, verifier: Any = None, sandbox: Any = None, audit: Any = None
    ) -> None:
        self._verifier = verifier
        self._sandbox = sandbox
        # Optional durable audit sink. Supplied so the audit-chain checker can
        # run against the same log the orchestrator writes to; when it is None
        # that checker reports SKIPPED rather than passing.
        self._audit = audit

    @property
    def enabled(self) -> bool:
        return self._verifier is not None

    def describe(self) -> dict[str, Any]:
        """What verification is actually able to do in this deployment.

        Exposed so ``/api/jobs`` and the audit record can state which checkers
        were available, rather than leaving a reader to assume the full set ran.
        """
        if self._verifier is None:
            return {"enabled": False, "checkers": []}
        describe = getattr(self._verifier, "describe", None)
        if callable(describe):
            detail = describe()
            if isinstance(detail, dict):
                return {"enabled": True, **detail}
        return {
            "enabled": True,
            "checkers": list(getattr(self._verifier, "checker_names", [])),
        }

    async def verify(
        self,
        *,
        task: str = "",
        answer: str = "",
        evidence: list[dict[str, Any]] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        job_id: str | None = None,
        user: str | None = None,
    ) -> VerificationReport:
        payload = VerificationInput(
            task=task,
            answer=answer or "",
            evidence=list(evidence or []),
            artifacts=list(artifacts or []),
            sandbox=self._sandbox,
            audit=self._audit,
            job_id=job_id,
            user=user,
        )

        if self._verifier is None:
            report = VerificationReport()
            report.add(
                CheckResult(
                    checker="verifier",
                    status=CheckStatus.SKIPPED,
                    message=(
                        "no verifier is wired; this result has not been checked and must "
                        "not be presented as verified"
                    ),
                    blocking=False,
                )
            )
            return report

        started = time.perf_counter()
        try:
            return await self._verifier.verify(payload)
        except Exception as exc:
            logger.warning("verification raised; treating as a failure", exc_info=True)
            report = VerificationReport()
            report.add(
                CheckResult(
                    checker="verifier",
                    status=CheckStatus.FAILED,
                    message=(
                        f"verification could not complete: {type(exc).__name__}: {exc}"
                    )[:400],
                    duration_ms=(time.perf_counter() - started) * 1000,
                )
            )
            return report

    def may_complete(self, report: VerificationReport) -> tuple[bool, str | None]:
        """Whether the job may reach ``COMPLETED``, and why not if it may not.

        The reason is built from the checkers that objected, so the failure the
        caller sees names the specific problem ("citations: page 143 was never
        retrieved") instead of a bare "verification failed".
        """
        blocking = report.blocking_failures
        if not blocking:
            return True, None
        detail = "; ".join(
            f"{check.checker}: {check.message}" for check in blocking[:3] if check.message
        )
        names = ", ".join(check.checker for check in blocking)
        reason = f"verification rejected the result [{names}]"
        if detail:
            reason = f"{reason} - {detail}"
        return False, reason[:600]
