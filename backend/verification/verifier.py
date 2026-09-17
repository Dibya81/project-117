"""The verifier (Phase 11).

Runs the checkers and aggregates their results. Three properties are the
reason this is a separate object rather than a loop inside the orchestrator.

**Checkers are independent, so they run concurrently.** None of them feeds
another, so a slow one (artifact inspection, which starts a container) does
not serialise behind the fast textual ones.

**A checker that breaks does not silently pass.** An exception or a timeout
becomes a ``FAILED`` result attributed to that checker. This is the opposite
of the usual defensive instinct - swallow the error and carry on - and it is
deliberate: a verification stage that degrades to "no objections" whenever it
malfunctions is worse than having no verification stage, because it produces
the *appearance* of checking. The one thing that must never happen is a job
reaching ``COMPLETED`` with a green report that nothing actually looked at.

**The verifier never asks a model anything.** It has no model router and no
gateway, by construction, so a future change cannot quietly turn verification
into "ask the LLM if it is happy with its own answer".

Each checker gets its own timeout. The budget is per checker rather than
global so that one slow checker cannot consume the whole allowance and leave
the rest unrun - unrun checks are indistinguishable from passed checks in a
global-timeout design, which is exactly the failure this stage exists to
prevent.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import replace
from typing import Any

from backend.verification.artifact_checker import ArtifactChecker
from backend.verification.audit_chain_checker import AuditChainChecker
from backend.verification.base import (
    Checker,
    CheckResult,
    CheckStatus,
    VerificationInput,
    VerificationReport,
)
from backend.verification.calculation_checker import CalculationChecker
from backend.verification.citation_checker import CitationChecker
from backend.verification.evidence_checker import EvidenceChecker
from backend.verification.hallucination_checker import HallucinationChecker
from backend.verification.policy_checker import PolicyChecker

logger = logging.getLogger(__name__)

#: Per-checker budget. Textual checkers finish in milliseconds; the artifact
#: checker may start a sandbox, hence the generous default.
DEFAULT_CHECK_TIMEOUT_SECONDS = 120.0


def default_checkers() -> list[Checker]:
    """The standard set, ordered by how early they catch the worst problems.

    ``AuditChainChecker`` is in the default set because a system that signs and
    verifies its own output while its audit log can be rewritten by hand has
    verified the wrong thing. It is non-blocking: the chain spans every job,
    so one tampered row elsewhere must not reject unrelated work in flight.
    """
    return [
        EvidenceChecker(),
        CitationChecker(),
        CalculationChecker(),
        HallucinationChecker(),
        PolicyChecker(),
        ArtifactChecker(),
        AuditChainChecker(),
    ]


class Verifier:
    def __init__(
        self,
        *,
        checkers: list[Checker] | None = None,
        sandbox: Any = None,
        timeout_seconds: float = DEFAULT_CHECK_TIMEOUT_SECONDS,
    ) -> None:
        self._checkers = list(checkers) if checkers is not None else default_checkers()
        self._sandbox = sandbox
        self._timeout = timeout_seconds

    @property
    def checker_names(self) -> list[str]:
        return [getattr(checker, "name", type(checker).__name__) for checker in self._checkers]

    def describe(self) -> dict[str, Any]:
        return {
            "checkers": self.checker_names,
            "timeout_seconds": self._timeout,
            "artifact_inspection": self._sandbox is not None,
        }

    async def verify(self, payload: VerificationInput) -> VerificationReport:
        if payload.sandbox is None and self._sandbox is not None:
            # VerificationInput is a dataclass, not a pydantic model, so this
            # is dataclasses.replace rather than model_copy. Copying instead
            # of mutating matters: the caller's payload must not gain a
            # sandbox handle as a side effect of being verified.
            payload = replace(payload, sandbox=self._sandbox)

        report = VerificationReport()
        if not self._checkers:
            report.add(
                CheckResult(
                    checker="verifier",
                    status=CheckStatus.FAILED,
                    message=(
                        "no checkers are registered, so nothing was verified; "
                        "completion is blocked rather than assumed"
                    ),
                )
            )
            return report

        results = await asyncio.gather(
            *(self._run(checker, payload) for checker in self._checkers),
            return_exceptions=False,
        )
        for result in results:
            report.add(result)
        return report

    async def _run(self, checker: Checker, payload: VerificationInput) -> CheckResult:
        name = getattr(checker, "name", type(checker).__name__)
        started = time.perf_counter()
        try:
            result = await asyncio.wait_for(checker.check(payload), timeout=self._timeout)
        except asyncio.TimeoutError:
            logger.warning("verification checker '%s' timed out", name)
            return CheckResult(
                checker=name,
                status=CheckStatus.FAILED,
                message=(
                    f"checker '{name}' did not finish within {self._timeout:.0f}s, so its "
                    "result is unknown and treated as blocking"
                ),
                duration_ms=(time.perf_counter() - started) * 1000,
            )
        except Exception as exc:
            logger.warning("verification checker '%s' failed", name, exc_info=True)
            return CheckResult(
                checker=name,
                status=CheckStatus.FAILED,
                message=f"checker '{name}' raised {type(exc).__name__}: {exc}"[:400],
                duration_ms=(time.perf_counter() - started) * 1000,
            )

        if not result.duration_ms:
            result = replace(result, duration_ms=(time.perf_counter() - started) * 1000)
        return result
