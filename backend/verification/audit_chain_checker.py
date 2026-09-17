"""Audit-chain integrity as a verification check (Phase 2).

The audit chain is a checkable property of the system, so it is expressed as a
checker in this package rather than as a second verification concept living
next to it. :class:`~backend.verification.verifier.Verifier` already knows how
to run checkers, attribute a failure, and refuse to call an unrun check a pass;
re-implementing that next to the audit log would have produced two answers to
"is this system verified" that could disagree.

Two deliberate choices:

* **SKIPPED when there is no audit sink.** A payload with no ``audit`` handle
  has nothing to verify against, and the package's rule is that an unrun check
  is never reported as a pass. It is not a failure either — the deployment may
  legitimately not have a durable audit log.
* **Non-blocking by default.** The chain covers the *whole* log, including rows
  written by other jobs, so a single tampered row would otherwise reject every
  unrelated artifact in flight. It is reported as a warning that a caller can
  promote to blocking (``AuditChainChecker(blocking=True)``) where that is the
  right policy.
"""

from __future__ import annotations

from typing import Any

from backend.verification.base import (
    CheckResult,
    CheckStatus,
    VerificationInput,
)


class AuditChainChecker:
    """Walks the durable audit hash chain and reports the first broken link."""

    name = "audit_chain"

    def __init__(self, *, blocking: bool = False) -> None:
        self.blocking = blocking

    async def check(self, payload: VerificationInput) -> CheckResult:
        audit: Any = getattr(payload, "audit", None) or payload.options.get("audit")
        if audit is None or not hasattr(audit, "verify"):
            return CheckResult(
                checker=self.name,
                status=CheckStatus.SKIPPED,
                message=(
                    "no audit sink was supplied, so the hash chain was not walked; "
                    "this is not a statement that the log is intact"
                ),
                blocking=self.blocking,
            )

        try:
            verdict = audit.verify()
            summary = verdict.as_dict()
        except Exception as exc:  # noqa: BLE001 - a broken verifier is a failure
            return CheckResult(
                checker=self.name,
                status=CheckStatus.FAILED,
                message=f"the audit chain verifier raised {type(exc).__name__}: {exc}"[:400],
                blocking=self.blocking,
            )

        if summary.get("error"):
            return CheckResult(
                checker=self.name,
                status=CheckStatus.WARNING,
                message=(
                    "the audit chain could not be verified: "
                    f"{summary['error']} — unverified is not intact"
                ),
                findings=[summary],
                blocking=self.blocking,
            )

        if not summary.get("valid"):
            broken = summary.get("broken_seq")
            return CheckResult(
                checker=self.name,
                status=CheckStatus.FAILED,
                message=(
                    f"audit chain broken at sequence {broken} "
                    f"(event {summary.get('broken_id')}): {summary.get('reason')}"
                ),
                # The finding names the offending row so a reader can go and
                # look at it rather than being told only that something is wrong.
                findings=[summary],
                blocking=self.blocking,
            )

        return CheckResult(
            checker=self.name,
            status=CheckStatus.PASSED,
            message=(
                f"audit chain of {summary.get('events', 0)} event(s) verified; "
                f"head {str(summary.get('last_hash'))[:16]}…"
            ),
            findings=[
                {
                    "events": summary.get("events"),
                    "last_hash": summary.get("last_hash"),
                    "last_seq": summary.get("last_seq"),
                }
            ],
            blocking=self.blocking,
        )


__all__ = ["AuditChainChecker"]
