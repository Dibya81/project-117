"""DOCX content specs.

This module builds and validates the *content* of a Word document. It does not
render one, and that separation is deliberate: rendering happens inside the
documents sandbox image via a reviewed generator
(:mod:`backend.deliverables.generators.docx_generator`), reached through the
``create_docx`` tool. A second rendering path in the API process would mean
two places where a document can be produced, only one of which is hashed,
verified and audited.

What this module adds on top of the raw spec schema is the citation
discipline. :func:`document_spec` refuses to emit a report that claims
findings with no evidence attached - it appends an explicit notice instead, so
a reader can never mistake an unsourced document for a verified one.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from backend.deliverables.spec import SpecError, parse_spec

#: Matches the ``Section`` limits in backend.deliverables.spec.
MAX_PARAGRAPHS_PER_SECTION = 40
MAX_BULLETS_PER_SECTION = 40

UNCITED_HEADING = "Evidence status"
UNCITED_TEXT = (
    "No source documents were attached to this document. Its statements are "
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


def bullet(text: str, citations: Iterable[Mapping[str, Any]] = ()) -> dict[str, Any]:
    return {
        "text": str(text),
        "citations": [dict(item) for item in citations],
    }


def section(
    heading: str,
    *,
    level: int = 1,
    paragraphs: Sequence[str] = (),
    bullets: Sequence[Mapping[str, Any]] = (),
    citations: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """One document section, capped to what the renderer accepts."""
    return {
        "heading": str(heading),
        "level": max(1, min(int(level), 4)),
        "paragraphs": [str(item) for item in paragraphs][:MAX_PARAGRAPHS_PER_SECTION],
        "bullets": [dict(item) for item in bullets][:MAX_BULLETS_PER_SECTION],
        "citations": [dict(item) for item in citations],
    }


def document_spec(
    *,
    title: str,
    sections: Sequence[Mapping[str, Any]],
    subtitle: str = "",
    author: str = "Project 117",
    sources: Sequence[Mapping[str, Any]] = (),
    footer: str = "",
    artifact_type: str = "docx",
) -> dict[str, Any]:
    """Build and validate a DOCX (or PDF) content spec.

    ``artifact_type`` accepts ``"pdf"`` because both renderers consume the
    identical section structure; keeping one builder avoids two drifting
    copies of the same shape.
    """
    kind = str(artifact_type or "docx").lower()
    if kind not in ("docx", "pdf"):
        raise SpecError(f"document_spec builds docx or pdf, not '{artifact_type}'")
    body = [dict(item) for item in sections]
    if not body:
        raise SpecError("a document needs at least one section")

    cited = any(
        item.get("citations") or any(b.get("citations") for b in item.get("bullets", []))
        for item in body
    )
    if not cited and not sources:
        body.append(section(UNCITED_HEADING, level=1, paragraphs=[UNCITED_TEXT]))

    payload = {
        "type": kind,
        "title": str(title),
        "subtitle": str(subtitle),
        "author": str(author),
        "sections": body,
        "sources": [dict(item) for item in sources],
        "footer": str(footer),
    }
    parse_spec(payload, expected_type=kind)
    return payload


def from_findings(
    *,
    title: str,
    findings: Sequence[Mapping[str, Any]],
    summary: str = "",
    subtitle: str = "",
    sources: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Turn analysis findings into a document spec.

    Each finding is ``{"heading", "statement", "detail"?, "citations"?}``.
    Findings without citations are still rendered - suppressing them would
    hide the analysis - but they are marked in the text, which is the honest
    behaviour rather than the flattering one.
    """
    sections: list[dict[str, Any]] = []
    if summary:
        sections.append(section("Summary", level=1, paragraphs=[summary]))
    for item in findings:
        citations = [dict(c) for c in item.get("citations") or []]
        paragraphs = [str(item.get("statement", "")).strip()]
        detail = str(item.get("detail", "") or "").strip()
        if detail:
            paragraphs.append(detail)
        if not citations:
            paragraphs.append("Source: not cited - unverified.")
        sections.append(
            section(
                str(item.get("heading") or "Finding"),
                level=2,
                paragraphs=[p for p in paragraphs if p],
                citations=citations,
            )
        )
    return document_spec(
        title=title, subtitle=subtitle, sections=sections, sources=sources
    )


__all__ = [
    "MAX_BULLETS_PER_SECTION",
    "MAX_PARAGRAPHS_PER_SECTION",
    "UNCITED_HEADING",
    "UNCITED_TEXT",
    "bullet",
    "citation",
    "document_spec",
    "from_findings",
    "section",
]
