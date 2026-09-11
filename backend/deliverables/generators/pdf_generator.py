"""PDF generator - runs *inside* the sandbox, never on the host.

Invoked as::

    python pdf_generator.py --spec inputs/spec.json --out artifacts/report.pdf

Uses ReportLab's Platypus flowables rather than the canvas API so pagination,
wrapping and keep-together behaviour are handled by the library instead of by
arithmetic in this file.

One detail that matters more here than in the other generators: Platypus
``Paragraph`` accepts a small HTML-like markup, so spec text containing ``<``
or ``&`` would either raise or silently change the rendering. ``_escape``
neutralises it. This is the same class of bug as SQL injection - untrusted
text reaching a parser - and the untrusted text here is model output built
from document content.

A missing reportlab exits 3 with an actionable message: the sandbox is
network-denied by policy, so the fix is rebuilding the documents image, not a
runtime install.
"""

from __future__ import annotations

import argparse
import json
import sys

MAX_PARAGRAPH_CHARS = 4000


def _escape(text: str) -> str:
    """Make text safe for Platypus' inline markup parser."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _citation_suffix(citations: list | None) -> str:
    labels = []
    for citation in citations or []:
        document_id = str(citation.get("document_id", "") or "")
        if not document_id:
            continue
        page = citation.get("page")
        labels.append(f"{document_id} p.{page}" if page else document_id)
    if not labels:
        return ""
    return "  [" + "; ".join(labels[:3]) + "]"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render an artifact spec as PDF")
    parser.add_argument("--spec", required=True, help="path to the JSON artifact spec")
    parser.add_argument("--out", required=True, help="path to write the .pdf to")
    args = parser.parse_args(argv)

    try:
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            ListFlowable,
            ListItem,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
        )
    except ImportError:
        print(
            "reportlab is not installed in this sandbox image. The sandbox has no "
            "network access by policy, so it cannot be installed at runtime: rebuild "
            "the documents image (infrastructure/docker/sandbox-documents.Dockerfile) "
            "with reportlab baked in.",
            file=sys.stderr,
        )
        return 3

    with open(args.spec, encoding="utf-8") as handle:
        spec = json.load(handle)

    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "Body117",
        parent=styles["BodyText"],
        alignment=TA_LEFT,
        spaceAfter=6,
        leading=14,
    )
    footer_text = str(spec.get("footer", "") or "")

    def _decorate(canvas, document) -> None:
        """Page footer with the page number.

        Printed reports get walked around a plant; an unnumbered page is a
        page that cannot be referred to.
        """
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        label = f"page {document.page}"
        if footer_text:
            label = f"{footer_text[:120]}  -  {label}"
        canvas.drawString(20 * mm, 12 * mm, label)
        canvas.restoreState()

    flowables = [
        Paragraph(_escape(str(spec.get("title", "Untitled"))[:300]), styles["Title"])
    ]
    subtitle = str(spec.get("subtitle", "") or "")
    if subtitle:
        flowables.append(Paragraph(_escape(subtitle[:300]), styles["Heading3"]))
    flowables.append(Spacer(1, 6 * mm))

    sections = spec.get("sections") or []
    paragraphs = 0
    for section in sections:
        level = int(section.get("level", 1) or 1)
        level = 1 if level < 1 else 4 if level > 4 else level
        flowables.append(
            Paragraph(
                _escape(str(section.get("heading", ""))[:300]),
                styles[f"Heading{level}"],
            )
        )
        for paragraph in section.get("paragraphs") or []:
            text = str(paragraph)[:MAX_PARAGRAPH_CHARS]
            if not text.strip():
                continue
            flowables.append(Paragraph(_escape(text), body))
            paragraphs += 1

        bullets = section.get("bullets") or []
        items = []
        for bullet in bullets:
            text = str(bullet.get("text", ""))[:MAX_PARAGRAPH_CHARS]
            if not text.strip():
                continue
            rendered = _escape(text) + _escape(_citation_suffix(bullet.get("citations")))
            items.append(ListItem(Paragraph(rendered, body)))
            paragraphs += 1
        if items:
            flowables.append(ListFlowable(items, bulletType="bullet", leftIndent=12))

        trailing = _citation_suffix(section.get("citations"))
        if trailing:
            flowables.append(Paragraph(_escape(f"Sources for this section:{trailing}"), body))
        flowables.append(Spacer(1, 3 * mm))

    sources = spec.get("sources") or []
    source_count = 0
    if sources:
        flowables.append(Paragraph("Sources", styles["Heading1"]))
        items = []
        for citation in sources:
            document_id = str(citation.get("document_id", "") or "")
            if not document_id:
                continue
            page = citation.get("page")
            section_label = str(citation.get("section", "") or "")
            line = document_id
            if page:
                line += f", page {page}"
            if section_label:
                line += f" - {section_label}"
            items.append(ListItem(Paragraph(_escape(line), body)))
            source_count += 1
        if items:
            flowables.append(ListFlowable(items, bulletType="1", leftIndent=12))

    document = SimpleDocTemplate(
        args.out,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=str(spec.get("title", "Untitled"))[:300],
        author=str(spec.get("author", "Project 117"))[:120],
    )
    document.build(flowables, onFirstPage=_decorate, onLaterPages=_decorate)

    print(
        json.dumps(
            {
                "artifact": args.out,
                "sections": len(sections),
                "paragraphs": paragraphs,
                "sources": source_count,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
