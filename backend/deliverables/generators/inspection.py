"""Inspection review documents.

Summarises one or more inspection reports for an asset: what was checked,
what was found, and what remains open. Every finding keeps the citation of
the inspection report it came from, so the reviewer can open the source.

Findings without a source document are still included - an inspector's
verbal note is real information - but they are grouped separately under
"Unsourced observations" rather than being blended into the cited list.
"""

from __future__ import annotations

from typing import Any, Sequence

from backend.deliverables.generators.report import (
    build_report_spec,
    bullet,
    citation,
    citations_from_evidence,
    section,
)


def _split_findings(
    findings: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Split findings into cited bullets and unsourced text."""
    cited: list[dict[str, Any]] = []
    unsourced: list[str] = []
    for item in findings or ():
        text = str(item.get("text") or item.get("finding") or "").strip()
        if not text:
            continue
        document_id = item.get("document_id") or item.get("documentId")
        if document_id:
            cited.append(
                bullet(
                    text,
                    [
                        citation(
                            str(document_id),
                            page=item.get("page") if isinstance(item.get("page"), int) else None,
                            section=str(item.get("section") or ""),
                        )
                    ],
                )
            )
        else:
            unsourced.append(text)
    return cited, unsourced


def build_inspection_summary(
    *,
    equipment_tag: str,
    inspection_ids: Sequence[str] = (),
    period: str = "",
    findings: Sequence[dict[str, Any]] = (),
    open_items: Sequence[str] = (),
    evidence: Sequence[dict[str, Any]] = (),
    artifact_type: str = "pdf",
) -> dict[str, Any]:
    """Assemble an inspection review spec."""
    cited, unsourced = _split_findings(findings)
    sources = citations_from_evidence(evidence) or [
        citation(str(identifier)) for identifier in inspection_ids
    ]

    sections: list[dict[str, Any]] = [
        section(
            "Scope",
            level=1,
            paragraphs=[
                f"Asset: {equipment_tag}",
                f"Reports reviewed: {', '.join(inspection_ids) if inspection_ids else 'none recorded'}",
                f"Period: {period}" if period else "Period: not specified",
            ],
        ),
        section(
            "Findings",
            paragraphs=[] if cited else ["No source-backed findings were recorded."],
            bullets=cited,
        ),
    ]

    if unsourced:
        sections.append(
            section(
                "Unsourced observations",
                paragraphs=[
                    "The following were reported without an attached document and "
                    "have not been verified against the record."
                ],
                bullets=[bullet(text) for text in unsourced],
            )
        )

    sections.append(
        section(
            "Open items",
            paragraphs=[] if open_items else ["No open items."],
            bullets=[bullet(text) for text in open_items],
        )
    )

    return build_report_spec(
        title=f"Inspection review - {equipment_tag}",
        subtitle=period,
        sections=sections,
        sources=sources,
        artifact_type=artifact_type,
    )


__all__ = ["build_inspection_summary"]
