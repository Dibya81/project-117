"""Data policy — what a running plan may read, send and record.

Three concerns that all reduce to "data must not leave the boundary it was
given":

1. **Destination** — every outbound URL a step wants to touch is checked
   against the egress policy (default deny). Local model servers and the
   sandbox are reachable; the internet is not.
2. **Scope** — when a caller scopes a task to specific documents, later steps
   cannot silently widen that scope to the whole corpus.
3. **Recording** — arguments written to traces and audit rows go through the
   same redaction the tool registry uses, so a credential passed as a tool
   argument is never persisted in clear text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from backend.security.egress import EgressBlocked, EgressPolicy
from backend.tools.registry import redact_arguments


class DataScopeViolation(RuntimeError):
    """A step tried to read outside the scope the caller granted."""

    reason = "data_scope_violation"


@dataclass(frozen=True)
class DataPolicy:
    """Per-job data constraints. Immutable: a step cannot widen its own scope."""

    egress: EgressPolicy = field(default_factory=EgressPolicy)
    #: When non-empty, retrieval is confined to these document ids.
    document_ids: tuple[str, ...] = ()
    #: Cap on evidence chunks a single step may pull, so one step cannot drag
    #: the entire corpus into the model context.
    max_chunks_per_step: int = 24

    # -- destinations --------------------------------------------------
    def allows_url(self, url: str) -> bool:
        return self.egress.allows(url)

    def check_url(self, url: str) -> None:
        """Raise :class:`~backend.security.egress.EgressBlocked` if refused."""
        self.egress.check(url)

    def check_urls(self, urls: Iterable[str]) -> None:
        for url in urls:
            self.check_url(url)

    # -- scope ---------------------------------------------------------
    def scope_documents(self, requested: Sequence[str] | None) -> list[str]:
        """Narrow a request to the granted scope.

        No scope granted -> the request passes through unchanged. A scope
        granted and a request outside it -> refused, not silently trimmed;
        quietly returning fewer documents would produce an answer that looks
        complete but is not.
        """
        if not self.document_ids:
            return list(requested or [])
        allowed = set(self.document_ids)
        if not requested:
            return list(self.document_ids)
        outside = [doc for doc in requested if doc not in allowed]
        if outside:
            raise DataScopeViolation(
                "documents outside the granted scope: " + ", ".join(sorted(outside))
            )
        return list(requested)

    def cap_chunks(self, requested: int | None) -> int:
        if not requested or requested < 1:
            return self.max_chunks_per_step
        return min(int(requested), self.max_chunks_per_step)

    # -- recording -----------------------------------------------------
    def redact(self, arguments: dict[str, Any] | None) -> dict[str, Any]:
        """Same redaction the tool registry applies before persisting."""
        return redact_arguments(arguments or {})

    def summary(self) -> dict[str, Any]:
        return {
            "egressDefaultDeny": self.egress.default_deny,
            "allowedHosts": sorted(self.egress.allowed_hosts),
            "documentScope": list(self.document_ids),
            "maxChunksPerStep": self.max_chunks_per_step,
        }


def policy_for_job(
    egress: EgressPolicy,
    *,
    document_ids: Sequence[str] | None = None,
    max_chunks_per_step: int = 24,
) -> DataPolicy:
    """Build the per-job policy from the caller's request."""
    return DataPolicy(
        egress=egress,
        document_ids=tuple(document_ids or ()),
        max_chunks_per_step=max(1, int(max_chunks_per_step)),
    )


__all__ = [
    "DataPolicy",
    "DataScopeViolation",
    "EgressBlocked",
    "policy_for_job",
]
