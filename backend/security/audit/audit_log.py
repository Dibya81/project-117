"""Shaping and redaction for audit events.

Separated from :class:`~backend.security.audit.AuditService` so the rules about
what an audit record may contain are testable without a database. That matters:
the service imports SQLAlchemy, so testing that an API key never reaches a
permanent row would otherwise require a driver.

Two invariants, neither negotiable:

1. Nothing sensitive is written. ``detail`` passes through
   :func:`backend.security.secrets.redact` before serialisation.
2. Approval state and outcome are closed sets. An unknown value raises rather
   than defaulting, because defaulting here means guessing about authorisation.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.security.secrets import redact

logger = logging.getLogger("backend.audit")

APPROVAL_STATES: frozenset[str] = frozenset(
    {"not_required", "pending", "approved", "rejected"}
)

#: The canonical outcome vocabulary.
#:
#: "refused" is distinct from "failure": a policy or permission refusal is the
#: system working correctly, and conflating them makes a denied request look
#: like an outage on the Admin dashboard.
#:
#: "pending" exists because an operation parked at an approval gate has not
#: run. Without it the only honest-looking option is "success", which would
#: record consent and completion that nobody gave.
OUTCOMES: frozenset[str] = frozenset({"success", "failure", "refused", "pending"})

#: Historical spellings accepted and normalised.
#:
#: Callers across the codebase grew three parallel vocabularies before this
#: module existed ("ok"/"error"/"denied" from the tool registry and the
#: deliverables service, "failure" from the API middleware). Normalising here
#: rather than widening OUTCOMES keeps a single set of values in the database,
#: so the Admin dashboard can group by outcome without a translation table.
#: Callers have been migrated to the canonical spellings; this map is the
#: compatibility net, not the intended path.
OUTCOME_ALIASES: dict[str, str] = {
    "ok": "success",
    "error": "failure",
    "denied": "refused",
    "rejected": "refused",
    "awaiting_approval": "pending",
}

#: An audit row records that an action happened; it is not a result store.
MAX_DETAIL_CHARS = 8000


class AuditFieldError(ValueError):
    """An audit event carried a value outside its permitted set."""

    reason = "audit_field_invalid"


def validate_approval(approval: str) -> str:
    if approval not in APPROVAL_STATES:
        raise AuditFieldError(
            f"unknown approval state '{approval}' - expected one of: "
            + ", ".join(sorted(APPROVAL_STATES))
        )
    return approval


def validate_outcome(outcome: str) -> str:
    """Return the canonical spelling of an outcome.

    Known aliases are normalised; anything else raises. Normalising is safe
    because every alias maps to a value with the same meaning - it never
    upgrades a failure into a success.
    """
    if outcome in OUTCOMES:
        return outcome
    normalised = OUTCOME_ALIASES.get(outcome)
    if normalised is not None:
        return normalised
    raise AuditFieldError(
        f"unknown outcome '{outcome}' - expected one of: "
        + ", ".join(sorted(OUTCOMES))
        + " (accepted aliases: "
        + ", ".join(sorted(OUTCOME_ALIASES))
        + ")"
    )


def redact_detail(detail: dict[str, Any] | None) -> dict[str, Any]:
    if not detail:
        return {}
    cleaned = redact(dict(detail))
    return cleaned if isinstance(cleaned, dict) else {"detail": cleaned}


def serialise_detail(detail: dict[str, Any] | None) -> str:
    """Redact, serialise and bound a detail mapping.

    Truncation is reported inside the payload rather than silently applied, so
    a reader can tell "there was nothing more" from "there was more, dropped".
    """
    payload = json.dumps(redact_detail(detail), default=str, sort_keys=True)
    if len(payload) <= MAX_DETAIL_CHARS:
        return payload
    return json.dumps(
        {
            "truncated": True,
            "original_chars": len(payload),
            "limit": MAX_DETAIL_CHARS,
            "head": payload[: MAX_DETAIL_CHARS - 200],
        },
        default=str,
    )


def canonical_event(
    *,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    user: str | None = None,
    outcome: str = "success",
    agent: str | None = None,
    tool: str | None = None,
    model: str | None = None,
    approval: str = "not_required",
    detail: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Validate and normalise one audit event into a plain mapping."""
    if not action or not action.strip():
        raise AuditFieldError("an audit event must name an action")
    return {
        "action": action.strip(),
        "resource_type": resource_type,
        "resource_id": resource_id,
        "user": user,
        "outcome": validate_outcome(outcome),
        "agent": agent,
        "tool": tool,
        "model": model,
        "approval": validate_approval(approval),
        "detail_json": serialise_detail(detail),
        "error": error,
    }


def log_event(event: dict[str, Any]) -> None:
    """Low-cardinality companion log line: identifiers and outcomes only."""
    logger.info(
        "audit %s resource=%s/%s user=%s agent=%s tool=%s approval=%s outcome=%s",
        event.get("action", "-"),
        event.get("resource_type") or "-",
        event.get("resource_id") or "-",
        event.get("user") or "-",
        event.get("agent") or "-",
        event.get("tool") or "-",
        event.get("approval", "-"),
        event.get("outcome", "-"),
    )


__all__ = [
    "APPROVAL_STATES",
    "MAX_DETAIL_CHARS",
    "OUTCOMES",
    "OUTCOME_ALIASES",
    "AuditFieldError",
    "canonical_event",
    "log_event",
    "redact_detail",
    "serialise_detail",
    "validate_approval",
    "validate_outcome",
]
