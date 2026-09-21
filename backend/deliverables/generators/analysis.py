"""Data-analysis deliverables.

Turns computed telemetry statistics into a document. The numbers must arrive
already computed - this module formats them, it never derives them, so a
figure in a report always traces back to the analysis step that produced it
rather than to formatting-time arithmetic that nothing verified.

Supports a tabular output (XLSX) as well as prose, because "give me the
numbers" and "explain the numbers" are different requests.
"""

from __future__ import annotations

from typing import Any, Sequence

from backend.deliverables.generators.report import (
    build_report_spec,
    bullet,
    citations_from_evidence,
    generated_footer,
    section,
)
from backend.deliverables.spec import parse_spec


def _format_metric(metric: dict[str, Any]) -> str:
    name = str(metric.get("name") or metric.get("signal") or "metric")
    value = metric.get("value")
    unit = str(metric.get("unit") or "")
    baseline = metric.get("baseline")
    text = f"{name}: {value}{(' ' + unit) if unit else ''}"
    if baseline is not None:
        text += f" (baseline {baseline}{(' ' + unit) if unit else ''})"
    change = metric.get("change_pct")
    if change is not None:
        text += f", change {change}%"
    return text


def build_analysis_report(
    *,
    title: str,
    equipment_tag: str = "",
    method: str = "",
    metrics: Sequence[dict[str, Any]] = (),
    observations: Sequence[str] = (),
    conclusions: Sequence[str] = (),
    evidence: Sequence[dict[str, Any]] = (),
    artifact_type: str = "pdf",
) -> dict[str, Any]:
    """Assemble an analysis report spec."""
    sources = citations_from_evidence(evidence)
    sections: list[dict[str, Any]] = []

    if equipment_tag:
        sections.append(section("Asset", level=1, paragraphs=[equipment_tag]))
    sections.append(
        section(
            "Method",
            paragraphs=[method or "Method not recorded."],
        )
    )
    sections.append(
        section(
            "Measurements",
            paragraphs=[] if metrics else ["No measurements were supplied."],
            bullets=[bullet(_format_metric(metric)) for metric in metrics],
        )
    )
    if observations:
        sections.append(
            section("Observations", bullets=[bullet(text, sources[:2]) for text in observations])
        )
    sections.append(
        section(
            "Conclusions",
            paragraphs=(
                [] if conclusions else ["The analysis did not produce a supported conclusion."]
            ),
            bullets=[bullet(text, sources[:2]) for text in conclusions],
        )
    )

    return build_report_spec(
        title=title,
        subtitle=equipment_tag,
        sections=sections,
        sources=sources,
        artifact_type=artifact_type,
    )


def build_metrics_workbook(
    *,
    title: str,
    sheet_name: str,
    columns: Sequence[str],
    rows: Sequence[Sequence[Any]],
    sources: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Build a validated XLSX spec for tabular results."""
    if not columns:
        raise ValueError("a workbook needs at least one column")
    payload: dict[str, Any] = {
        "type": "xlsx",
        "title": title,
        "sheets": [
            {
                "name": sheet_name[:31] or "Data",
                "columns": [str(column) for column in columns],
                "rows": [list(row) for row in rows],
                "freeze_header": True,
            }
        ],
        "sources": [dict(item) for item in sources],
        "footer": generated_footer(),
    }
    parse_spec(payload, expected_type="xlsx")
    return payload


__all__ = ["build_analysis_report", "build_metrics_workbook"]
