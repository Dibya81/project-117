"""Maintenance recommendation documents.

Produces the deliverable at the end of the demo story: an engineer asks why
C-3's vibration rose, and the system returns a recommendation that a
maintenance planner could act on.

Two rules are enforced structurally rather than by convention:

* **Recommended actions are separated from observed facts.** They render as
  distinct sections so a reader is never left guessing which sentences are
  measurements and which are proposals.
* **A recommendation with no evidence is labelled unverified** by the shared
  report builder. The system is allowed to be unsure; it is not allowed to
  look confident while being unsure.
"""

from __future__ import annotations

from typing import Any, Sequence

from backend.deliverables.generators.report import (
    build_report_spec,
    bullet,
    citations_from_evidence,
    section,
)

PRIORITIES = ("low", "medium", "high", "urgent")


def build_maintenance_recommendation(
    *,
    equipment_tag: str,
    equipment_name: str = "",
    summary: str,
    findings: Sequence[str] = (),
    actions: Sequence[str] = (),
    priority: str = "medium",
    evidence: Sequence[dict[str, Any]] = (),
    telemetry_notes: Sequence[str] = (),
    artifact_type: str = "pdf",
) -> dict[str, Any]:
    """Assemble a maintenance recommendation spec.

    ``priority`` is validated against :data:`PRIORITIES` rather than passed
    through, because it drives planner triage downstream.
    """
    level = priority.strip().lower()
    if level not in PRIORITIES:
        raise ValueError(f"unknown priority '{priority}'; expected one of {list(PRIORITIES)}")

    sources = citations_from_evidence(evidence)
    label = f"{equipment_tag} - {equipment_name}".strip(" -") or equipment_tag

    sections: list[dict[str, Any]] = [
        section(
            "Summary",
            level=1,
            paragraphs=[summary],
            citations=sources[:6],
        ),
        section(
            "Observed findings",
            paragraphs=[] if findings else ["No findings were recorded for this asset."],
            bullets=[bullet(text, sources[:2]) for text in findings],
        ),
    ]

    if telemetry_notes:
        sections.append(
            section(
                "Telemetry",
                paragraphs=list(telemetry_notes),
            )
        )

    sections.append(
        section(
            "Recommended actions",
            paragraphs=(
                [] if actions else ["No actions are recommended; continue routine monitoring."]
            ),
            bullets=[bullet(text) for text in actions],
        )
    )
    sections.append(
        section(
            "Basis and limitations",
            paragraphs=[
                (
                    "This recommendation was produced by Project 117 from the sources "
                    "listed below using locally hosted models. It is decision support "
                    "for a qualified engineer, not an authorisation to perform work."
                )
            ],
        )
    )

    return build_report_spec(
        title=f"Maintenance recommendation - {label}",
        subtitle=f"Priority: {level.upper()}",
        sections=sections,
        sources=sources,
        artifact_type=artifact_type,
    )


__all__ = ["PRIORITIES", "build_maintenance_recommendation"]
