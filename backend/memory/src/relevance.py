"""Relevance scoring for recalled memory.

Deliberately lexical and deterministic: the same query against the same
records always ranks identically, which is what makes a recall trace
reproducible during an audit. Embedding-based recall is a separate, optional
path (:mod:`backend.memory.semantic.retriever`) rather than a silent upgrade
of this one.

The score combines three signals:

* **overlap** - fraction of query words present in the record,
* **confidence** - what the writer claimed, never treated as truth,
* **recency** - exponential decay so a stale note loses to a fresh one.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

_WORD = re.compile(r"[a-z0-9]+")

#: How long it takes for the recency signal to halve.
DEFAULT_HALF_LIFE_DAYS = 30.0


def tokenize(text: str) -> set[str]:
    return set(_WORD.findall((text or "").lower()))


def overlap(query: str, text: str) -> float:
    """Fraction of the query's words that appear in the text (0.0-1.0)."""
    words = tokenize(query)
    if not words:
        return 0.0
    found = words & tokenize(text)
    return len(found) / len(words)


def _parse(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def recency_weight(
    timestamp: Any, *, now: datetime | None = None, half_life_days: float = DEFAULT_HALF_LIFE_DAYS
) -> float:
    """1.0 for something written now, 0.5 after one half-life.

    An unparseable timestamp scores 0.5 rather than 0.0 or 1.0: unknown age
    should neither promote nor bury a record.
    """
    written = _parse(timestamp)
    if written is None:
        return 0.5
    reference = now or datetime.now(timezone.utc)
    age_days = max(0.0, (reference - written).total_seconds() / 86400.0)
    return 0.5 ** (age_days / max(0.1, half_life_days))


def score_record(record: dict[str, Any], query: str, *, now: datetime | None = None) -> float:
    """Weighted score in 0.0-1.0. Text overlap dominates; a high-confidence
    record that does not match the question is still not an answer."""
    text = " ".join(str(record.get(field_name) or "") for field_name in ("key", "content"))
    lexical = overlap(query, text)
    confidence = float(record.get("confidence") or 0.5)
    freshness = recency_weight(
        record.get("updated_at") or record.get("updatedAt") or record.get("created_at"),
        now=now,
    )
    return round(0.65 * lexical + 0.2 * confidence + 0.15 * freshness, 6)


def rank(
    records: Iterable[dict[str, Any]],
    query: str,
    *,
    limit: int = 5,
    min_score: float = 0.05,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Rank records, attaching the score under ``relevance`` for the trace.

    Records below ``min_score`` are dropped rather than padded in: returning
    five unrelated notes to fill a quota is how irrelevant context ends up in
    a prompt.
    """
    scored: list[tuple[float, dict[str, Any]]] = []
    for record in records or ():
        value = score_record(record, query, now=now)
        if value >= min_score:
            enriched = dict(record)
            enriched["relevance"] = value
            scored.append((value, enriched))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[: max(1, limit)]]


def top_terms(records: Sequence[dict[str, Any]], *, limit: int = 8) -> list[str]:
    """Most common content words across records - used to label a cluster."""
    counts: dict[str, int] = {}
    for record in records or ():
        for word in tokenize(str(record.get("content") or "")):
            if len(word) < 4:
                continue
            counts[word] = counts.get(word, 0) + 1
    ordered = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return [word for word, _ in ordered[:limit]]


__all__ = [
    "DEFAULT_HALF_LIFE_DAYS",
    "overlap",
    "rank",
    "recency_weight",
    "score_record",
    "tokenize",
    "top_terms",
]
