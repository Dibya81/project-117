"""Condense memory and job history into something short enough to prompt with.

Extractive and deterministic on purpose. A model-written summary of memory
would be a second, unsourced layer of claims sitting on top of the first, and
nothing downstream could tell which sentence came from a document and which
was invented while compressing. So this picks existing sentences by signal
strength and never composes new ones.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Sequence

from backend.memory.src.relevance import tokenize, top_terms

_SENTENCE = re.compile(r"(?<=[.!?])\s+")

MAX_SUMMARY_CHARS = 900


def split_sentences(text: str) -> list[str]:
    parts = [part.strip() for part in _SENTENCE.split((text or "").strip()) if part.strip()]
    return parts


def summarise_text(text: str, *, max_chars: int = 400, query: str = "") -> str:
    """Pick whole sentences until the budget is spent.

    With a query, sentences that share words with it come first; without one,
    original order is kept, because reordering unrelated prose changes what it
    appears to say.
    """
    sentences = split_sentences(text)
    if not sentences:
        return ""
    if query:
        wanted = tokenize(query)
        ordered = sorted(
            enumerate(sentences),
            key=lambda pair: (-len(wanted & tokenize(pair[1])), pair[0]),
        )
        sentences = [sentence for _, sentence in ordered]
    out: list[str] = []
    used = 0
    for sentence in sentences:
        if used + len(sentence) > max_chars and out:
            break
        out.append(sentence)
        used += len(sentence) + 1
    return " ".join(out)


def summarise_records(
    records: Sequence[dict[str, Any]],
    *,
    query: str = "",
    max_chars: int = MAX_SUMMARY_CHARS,
) -> str:
    """One bullet per record, grouped by kind, hard-capped in total length."""
    if not records:
        return ""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record.get("kind", "note")), []).append(record)

    lines: list[str] = []
    used = 0
    budget_per_line = max(80, max_chars // max(4, len(records)))
    for kind in sorted(grouped):
        header = f"{kind}:"
        if used + len(header) > max_chars:
            break
        lines.append(header)
        used += len(header) + 1
        for record in grouped[kind]:
            body = summarise_text(
                str(record.get("content", "")), max_chars=budget_per_line, query=query
            )
            if not body:
                continue
            key = str(record.get("key", "")).strip()
            line = f"  - {key}: {body}" if key else f"  - {body}"
            if used + len(line) > max_chars:
                return "\n".join(lines)
            lines.append(line)
            used += len(line) + 1
    return "\n".join(lines)


def digest(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Machine-readable shape of the same condensation, for the API."""
    counts: dict[str, int] = {}
    for record in records or ():
        kind = str(record.get("kind", "note"))
        counts[kind] = counts.get(kind, 0) + 1
    return {
        "count": len(records or ()),
        "byKind": counts,
        "themes": top_terms(records or (), limit=6),
        "summary": summarise_records(records or ()),
    }


def merge_notes(notes: Iterable[str], *, limit: int = 8) -> list[str]:
    """De-duplicate operator notes while preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for note in notes or ():
        cleaned = " ".join(str(note).split())
        if not cleaned:
            continue
        fingerprint = cleaned.lower()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        out.append(cleaned)
        if len(out) >= limit:
            break
    return out


__all__ = [
    "MAX_SUMMARY_CHARS",
    "digest",
    "merge_notes",
    "split_sentences",
    "summarise_records",
    "summarise_text",
]
