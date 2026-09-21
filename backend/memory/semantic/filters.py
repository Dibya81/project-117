"""Filters applied to recalled memory before it reaches a prompt.

Small, composable predicates rather than one clever query, so a caller can
say exactly what it will accept - and so an audit can show which filter
dropped a record.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Sequence

Predicate = Callable[[dict[str, Any]], bool]


def of_kind(*kinds: str) -> Predicate:
    wanted = {k.lower() for k in kinds}
    return lambda record: str(record.get("kind", "")).lower() in wanted


def in_scope(*scopes: str) -> Predicate:
    wanted = set(scopes)
    return lambda record: str(record.get("scope", "")) in wanted


def min_confidence(threshold: float) -> Predicate:
    return lambda record: float(record.get("confidence") or 0.0) >= threshold


def has_evidence() -> Predicate:
    """Keep only records that can point at a document."""
    return lambda record: bool(record.get("evidence"))


def not_expired(now: datetime | None = None) -> Predicate:
    reference = now or datetime.now(timezone.utc)

    def predicate(record: dict[str, Any]) -> bool:
        raw = record.get("expires_at") or record.get("expiresAt")
        if not raw:
            return True
        try:
            expires = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            # An unparseable expiry is treated as expired: the safe reading of
            # "we do not know if this is still true" is to leave it out.
            return False
        if not expires.tzinfo:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires > reference

    return predicate


def written_by(*sources: str) -> Predicate:
    wanted = set(sources)
    return lambda record: str(record.get("source", "")) in wanted


def mentions(term: str) -> Predicate:
    needle = (term or "").strip().lower()

    def predicate(record: dict[str, Any]) -> bool:
        if not needle:
            return True
        haystack = f"{record.get('key', '')} {record.get('content', '')}".lower()
        return needle in haystack

    return predicate


def apply(
    records: Iterable[dict[str, Any]], predicates: Sequence[Predicate]
) -> list[dict[str, Any]]:
    """Keep records satisfying every predicate."""
    out: list[dict[str, Any]] = []
    for record in records or ():
        if all(predicate(record) for predicate in predicates):
            out.append(record)
    return out


def explain(record: dict[str, Any], predicates: Sequence[tuple[str, Predicate]]) -> list[str]:
    """Names of the predicates this record failed - for the recall trace."""
    return [name for name, predicate in predicates if not predicate(record)]


__all__ = [
    "Predicate",
    "apply",
    "explain",
    "has_evidence",
    "in_scope",
    "mentions",
    "min_confidence",
    "not_expired",
    "of_kind",
    "written_by",
]
