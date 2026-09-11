"""Maintenance agent (Phase 7).

Answers the question a reliability engineer actually asks: *this machine is
behaving badly - what do the documents say about why, and what should I check
first?*

Two design choices matter more than the prompt wording.

First, the agent ranks **probable** causes and forces each one to carry an
evidence marker. A local model asked "why did the pump fail" will otherwise
produce a fluent, textbook-correct list of causes that has nothing to do with
the uploaded manual - and a plausible list is more dangerous than a short one,
because nothing on its face distinguishes it from a sourced list.

Second, the agent is required to end with what is missing. "The manual does not
state the bearing clearance limit" is a useful output for a maintenance
planner. A number invented to fill that gap is a machine damaged next week.
"""

from __future__ import annotations

from typing import Any

from backend.agents.base import AgentResult, BaseAgent
from backend.models.providers.base import ChatMessage

_SYSTEM = (
    "You are a maintenance and reliability engineer working strictly from the plant's "
    "own documents, inside an air-gapped system.\n\n"
    "Rules:\n"
    "- Use ONLY the numbered evidence provided. Cite the number for every factual claim, "
    "e.g. [2]. If several passages support a claim, cite all of them.\n"
    "- Never invent equipment tags, part numbers, torque values, clearances, set points, "
    "intervals or standard numbers. If a value is not in the evidence, say it is not "
    "stated.\n"
    "- Keep units, tolerances and revision numbers exactly as written in the source.\n"
    "- Distinguish what the document states from what it implies. Mark inference as "
    "inference.\n"
    "- Do not recommend an intervention the documents do not authorise. Recommend the "
    "check or the procedure that the documents do describe.\n\n"
    "Structure the answer with these headings, omitting any that the evidence cannot "
    "support:\n"
    "1. Summary - two or three sentences.\n"
    "2. What the documents state - the observed condition and any recorded history.\n"
    "3. Probable causes - ranked, each with its evidence marker and a one-line reason.\n"
    "4. Recommended checks - in the order a technician should perform them, with the "
    "acceptance criterion from the document where one exists.\n"
    "5. Parts, tools and consumables - only those named in the evidence.\n"
    "6. Not covered by the documents - state plainly what a decision still needs."
)


class MaintenanceAgent(BaseAgent):
    name = "maintenance"
    description = (
        "Diagnoses equipment problems and plans interventions from maintenance manuals, "
        "inspection reports and work-order history, with page-level citations."
    )
    capabilities = (
        "diagnose_failure",
        "rank_probable_causes",
        "plan_inspection",
        "identify_parts",
        "summarise_maintenance_history",
    )
    requires_rag = True
    tool_names = ("search_documents", "read_document", "extract_table")
    model_role = "reasoning"
    temperature = 0.1
    system_prompt = _SYSTEM

    def build_prompt(
        self,
        *,
        task: str,
        context: Any = None,
        arguments: dict[str, Any] | None = None,
    ) -> list[ChatMessage]:
        arguments = dict(arguments or {})
        equipment = str(arguments.get("equipment") or "").strip()
        focus = f"Equipment under investigation: {equipment}\n\n" if equipment else ""
        user = (
            f"{focus}Evidence:\n{self.evidence_text(context)}\n\n"
            f"Maintenance request: {task}"
        )
        return [
            ChatMessage(role="system", content=self.system_prompt),
            ChatMessage(role="user", content=user[:60_000]),
        ]

    async def postprocess(
        self,
        result: AgentResult,
        *,
        task: str,
        context: Any = None,
        arguments: dict[str, Any] | None = None,
    ) -> AgentResult:
        # A note, not a rejection: the citation checker is the component that
        # decides whether an answer may be returned. Two components disagreeing
        # about that would mean neither is authoritative.
        if result.grounded and "[" not in result.answer:
            result.notes.append(
                "the answer carries no evidence markers, so citation checking will reject it"
            )
        return result
