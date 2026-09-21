"""Operations agent (Phase 7).

Owns the shift-floor questions: how is this unit started, what does this alarm
mean, what are the limits for this mode, which SOP applies.

The distinguishing rule is order. A procedure is not a set of facts, it is a
sequence, and a model that helpfully reorders or compresses steps has produced
something that reads like an SOP and is not one. So this agent reproduces steps
in document order, keeps their numbering, and marks any gap in the retrieved
sequence instead of bridging it.

Operations questions also drag safety content along - an alarm response often
contains an isolation requirement. Rather than duplicating the safety agent's
judgement, this agent is required to carry every warning it retrieves through
to the answer verbatim; the policy checker independently fails an answer that
drops one.
"""

from __future__ import annotations

from typing import Any

from backend.agents.base import AgentResult, BaseAgent
from backend.models.providers.base import ChatMessage

_SYSTEM = (
    "You are a plant operations assistant working strictly from the site's own "
    "procedures, operating manuals and alarm documentation, inside an air-gapped "
    "system.\n\n"
    "Rules:\n"
    "- Use ONLY the numbered evidence. Cite the number for every step, limit and "
    "instruction, e.g. [3].\n"
    "- Reproduce procedure steps in the order and numbering used by the document. Never "
    "reorder, merge or summarise a step into a shorter instruction.\n"
    "- If the retrieved steps are incomplete (they start at step 4, or stop mid-"
    "procedure), say so explicitly and do not invent the missing steps.\n"
    "- Carry every warning, caution, PPE requirement, permit requirement and operating "
    "limit into the answer exactly as written, with its citation. Never drop one for "
    "brevity.\n"
    "- Never invent set points, alarm thresholds, ramp rates, hold times, valve line-ups "
    "or tag numbers.\n"
    "- Keep units and tolerances exactly as written.\n\n"
    "Structure the answer as:\n"
    "1. Applicable document - name, section and revision if the evidence gives them.\n"
    "2. Preconditions - plant state, permits, isolations required before starting.\n"
    "3. Steps - in document order, each cited, with acceptance criteria where stated.\n"
    "4. Limits and alarms - values exactly as written, each cited.\n"
    "5. Warnings - quoted verbatim, each cited.\n"
    "6. Gaps - which parts of the procedure were not retrieved."
)


class OperationsAgent(BaseAgent):
    name = "operations"
    description = (
        "Answers operating, start-up, shutdown, alarm-response and SOP questions from "
        "controlled procedures, preserving step order, limits and warnings with citations."
    )
    capabilities = (
        "locate_procedure",
        "reproduce_steps_in_order",
        "explain_alarm_response",
        "state_operating_limits",
        "identify_procedure_gaps",
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
        unit = str(arguments.get("unit") or arguments.get("equipment") or "").strip()
        header = f"Unit or system in question: {unit}\n\n" if unit else ""
        user = f"{header}Evidence:\n{self.evidence_text(context)}\n\nOperations request: {task}"
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
        if result.grounded and "[" not in result.answer:
            result.notes.append(
                "the answer carries no evidence markers, so citation checking will reject it"
            )
        return result
