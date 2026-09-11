"""PPTX content specs.

Slide decks fail in a specific way: too much text per slide, and the renderer
shrinks it until nobody can read it. So the builders here enforce the shape
rather than hoping the caller respects it - bullets per slide are capped, over
long bullets are split across continuation slides instead of being truncated,
and the cap comes from the same constant the artifact checker measures against.

Rendering happens in the sandbox through ``create_pptx``; see
:mod:`backend.tools.office.docx` for why that boundary is where it is.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from backend.deliverables.spec import SpecError, parse_spec
from backend.tools.office.docx import citation

#: Matches ``Slide.bullets`` max_length in backend.deliverables.spec.
MAX_BULLETS_PER_SLIDE = 8

LAYOUTS = ("title", "title_content", "section", "two_content")


def bullet(text: str, citations: Iterable[Mapping[str, Any]] = ()) -> dict[str, Any]:
    return {"text": str(text), "citations": [dict(item) for item in citations]}


def slide(
    title: str,
    *,
    bullets: Sequence[Mapping[str, Any]] = (),
    notes: str = "",
    layout: str = "title_content",
) -> dict[str, Any]:
    chosen = str(layout or "title_content")
    if chosen not in LAYOUTS:
        raise SpecError(f"unknown slide layout '{layout}'; use one of {', '.join(LAYOUTS)}")
    return {
        "title": str(title),
        "bullets": [dict(item) for item in bullets][:MAX_BULLETS_PER_SLIDE],
        "notes": str(notes),
        "layout": chosen,
    }


def paginate(
    title: str,
    bullets: Sequence[Mapping[str, Any]],
    *,
    notes: str = "",
    layout: str = "title_content",
) -> list[dict[str, Any]]:
    """Split a long bullet list into as many slides as it needs.

    Continuation slides are labelled ``(cont.)`` so the reader knows the
    content was split rather than duplicated.
    """
    items = [dict(item) for item in bullets or []]
    if not items:
        return [slide(title, notes=notes, layout=layout)]
    slides: list[dict[str, Any]] = []
    for offset in range(0, len(items), MAX_BULLETS_PER_SLIDE):
        chunk = items[offset : offset + MAX_BULLETS_PER_SLIDE]
        heading = title if offset == 0 else f"{title} (cont.)"
        slides.append(
            slide(heading, bullets=chunk, notes=notes if offset == 0 else "", layout=layout)
        )
    return slides


def deck_spec(
    *,
    title: str,
    slides: Sequence[Mapping[str, Any]],
    subtitle: str = "",
    author: str = "Project 117",
    sources: Sequence[Mapping[str, Any]] = (),
    footer: str = "",
) -> dict[str, Any]:
    """Build and validate a PPTX spec."""
    body = [dict(item) for item in slides or []]
    if not body:
        raise SpecError("a deck needs at least one slide")
    payload = {
        "type": "pptx",
        "title": str(title),
        "subtitle": str(subtitle),
        "author": str(author),
        "slides": body,
        "sources": [dict(item) for item in sources],
        "footer": str(footer),
    }
    parse_spec(payload, expected_type="pptx")
    return payload


def from_findings(
    *,
    title: str,
    findings: Sequence[Mapping[str, Any]],
    subtitle: str = "",
    sources: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Turn analysis findings into a deck: one slide per finding, paginated.

    Each finding is ``{"heading", "points": [...], "citations"?}`` where a
    point is either a string or ``{"text", "citations"}``.
    """
    built: list[dict[str, Any]] = []
    for item in findings or []:
        shared = [dict(c) for c in item.get("citations") or []]
        points: list[dict[str, Any]] = []
        for point in item.get("points") or []:
            if isinstance(point, Mapping):
                points.append(
                    bullet(
                        point.get("text", ""),
                        [dict(c) for c in point.get("citations") or []] or shared,
                    )
                )
            else:
                points.append(bullet(str(point), shared))
        built.extend(paginate(str(item.get("heading") or "Finding"), points))
    return deck_spec(title=title, subtitle=subtitle, slides=built, sources=sources)


__all__ = [
    "LAYOUTS",
    "MAX_BULLETS_PER_SLIDE",
    "bullet",
    "citation",
    "deck_spec",
    "from_findings",
    "paginate",
    "slide",
]
