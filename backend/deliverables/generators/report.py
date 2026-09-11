"""Generic report spec builder.

The shared foundation for every content builder. Its job is to make the
citation discipline structural rather than optional:

* :func:`citation` normalises evidence into the spec's citation shape.
* :func:`build_report_spec` refuses to silently emit an uncited report - if
  no sources are supplied it appends an explicit notice section, so a reader
  can never mistake an unsourced document for a verified one.

Output is a plain dict validated by
:func:`backend.deliverables.spec.parse_spec`, so a malformed report fails here
rather than inside the sandbox renderer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

from backend.deliverables.spec import parse_spec

UNCITED_HEADING = "Evidence status"
UNCITED_TEXT = (
    "No source documents were attached to this report. Its statements are "
    "unverified and must not be treated as evidence-backed findings."
)


def citation(
    document_id: str,
    *,
    page: int | None = None,
    section: str = "",
    chunk_id: str = "",
) -> dict[str, Any]:
    """Normalise one piece of evidence into the spec's citation shape."""
    entry: dict[str, Any] = {"document_id": str(document_id)[:128]}
    if page is not None and int(page) >= 1:
        entry["page"] = int(page)
    if section:
        entry["section"] = str(section)[:300]
    if chunk_id:
        entry["chunk_id"] = str(chunk_id)[:128]
    return entry


def citations_from_evidence(evidence: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert retrieval/memory evidence into citations, de-duplicated.

    Accepts both snake_case and camelCase keys because evidence reaches this
    point from the retrieval layer, the memory layer and the API, and the
    three do not agree on casing.
    """
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, Any, str]] = set()
    for item in evidence or ():
        if not isinstance(item, dict):
            continue
        document_id = (
            item.get("document_id") or item.get("documentId") or item.get("id")
        )
        if not document_id:
            continue
        page = item.get("page")
        section = str(item.get("section") or item.get("heading") or "")
        key = (str(document_id), page, section)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            citation(
                str(document_id),
                page=page if isinstance(page, int) else None,
                section=section,
                chunk_id=str(item.get("chunk_id") or item.get("chunkId") or ""),
            )
        )
    return out


def uncited_notice() -> dict[str, Any]:
    """The section appended when a report carries no sources."""
    return {"heading": UNCITED_HEADING, "level": 2, "paragraphs": [UNCITED_TEXT]}


def generated_footer(*, generated_at: str | None = None) -> str:
    stamp = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    return f"Project 117 - generated {stamp} - local models, no external calls"


def build_report_spec(
    *,
    title: str,
    sections: Sequence[dict[str, Any]],
    subtitle: str = "",
    artifact_type: str = "pdf",
    sources: Sequence[dict[str, Any]] = (),
    author: str = "Project 117",
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build and validate a report spec.

    Raises :class:`~backend.deliverables.spec.SpecError` (via ``parse_spec``)
    if the assembled document is not renderable.
    """
    body = [dict(section) for section in sections if section]
    citation_list = [dict(item) for item in sources]
    if not citation_list:
        body.append(uncited_notice())
    payload: dict[str, Any] = {
        "type": artifact_type,
        "title": title,
        "subtitle": subtitle,
        "author": author,
        "sections": body,
        "sources": citation_list,
        "footer": generated_footer(generated_at=generated_at),
    }
    parse_spec(payload, expected_type=artifact_type)
    return payload


def section(
    heading: str,
    *,
    level: int = 2,
    paragraphs: Sequence[str] = (),
    bullets: Sequence[dict[str, Any]] = (),
    citations: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Small helper so builders read as documents, not dict literals."""
    return {
        "heading": heading,
        "level": level,
        "paragraphs": [str(text) for text in paragraphs if str(text).strip()],
        "bullets": [dict(bullet) for bullet in bullets],
        "citations": [dict(item) for item in citations],
    }


def bullet(text: str, citations: Sequence[dict[str, Any]] = ()) -> dict[str, Any]:
    return {"text": str(text), "citations": [dict(item) for item in citations][:6]}


__all__ = [
    "UNCITED_HEADING",
    "UNCITED_TEXT",
    "build_report_spec",
    "bullet",
    "citation",
    "citations_from_evidence",
    "generated_footer",
    "section",
    "uncited_notice",
]
