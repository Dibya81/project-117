"""Safety agent (Phase 7).

The agent with the least freedom, on purpose.

A safety question - isolation, permits, interlocks, confined space, hazardous
materials - has a property the others do not: a fluent wrong answer can injure
someone. So this agent does not summarise, paraphrase or "helpfully" complete a
procedure. It quotes the controlled document, preserves every warning, and when
the evidence does not cover the question it says exactly that and stops.

That is also why ``temperature`` is 0.0, why the prompt forbids reordering
steps, and why every answer carries a standing note that the controlled
document governs. The system is an aid to finding the right procedure, never a
substitute for it.
"""

from __future__ import annotations

from typing import Any

from backend.agents.base import AgentResult, BaseAgent
from backend.models.providers.base import ChatMessage

_SYSTEM = (
    "You are a plant safety documentation assistant. You answer ONLY from the numbered "
    "evidence taken from the site's controlled documents.\n\n"
    "Absolute rules:\n"
    "- Never invent, complete, merge, shorten or reorder a safety procedure. If the "
    "evidence contains steps 1-4 and the question needs step 5, say that step 5 was not "
    "retrieved.\n"
    "- Reproduce every warning, caution, prohibition, PPE requirement, permit "
    "requirement, isolation requirement and limit exactly as written, and cite it.\n"
    "- Never soften or omit a warning to make an answer shorter.\n"
    "- Never give a numeric limit, exposure value, pressure, temperature or clearance "
    "that is not in the evidence.\n"
    "- If the evidence does not answer the question, reply that it does not and name the "
    "document or section that should be consulted, if the evidence names one.\n"
    "- Do not rely on general safety knowledge, standards you were trained on, or common "
    "practice. Only these documents.\n\n"
    "Structure the answer as:\n"
    "1. Direct answer - or an explicit statement that the documents do not cover it.\n"
    "2. Requirements from the documents - PPE, permits, isolation, competency, with "
    "citations.\n"
    "3. Procedure as written - quoted steps in their original order, each cited.\n"
    "4. Warnings and prohibitions - quoted verbatim, each cited.\n"
    "5. Not covered - what a person must confirm from the controlled document."
)

#: Appended to every answer's notes. Not a disclaimer for its own sake: an
#: operator reading a retrieved procedure needs to know the retrieval was
#: partial by design.
_STANDING_NOTE = (
    "safety answers are retrieved extracts, not authorisation to work - confirm against "
    "the current controlled document and the site permit system before starting"
)


class SafetyAgent(BaseAgent):
    name = "safety"
    description = (
        "Answers safety, permit, isolation and hazard questions by quoting the controlled "
        "documents verbatim with citations, and refuses to complete a procedure that was "
        "not retrieved."
    )
    capabilities = (
        "locate_safety_requirement",
        "quote_procedure_verbatim",
        "list_ppe_and_permits",
        "identify_missing_safety_information",
    )
    requires_rag = True
    tool_names = ("search_documents", "read_document")
    model_role = "reasoning"
    temperature = 0.0
    system_prompt = _SYSTEM

    def build_prompt(
        self,
        *,
        task: str,
        context: Any = None,
        arguments: dict[str, Any] | None = None,
    ) -> list[ChatMessage]:
        user = (
            f"Evidence:\n{self.evidence_text(context)}\n\n"
            f"Safety question: {task}\n\n"
            "If the evidence is incomplete, say so rather than filling the gap."
        )
        return [
            ChatMessage(role="system", content=self.system_prompt),
            ChatMessage(role="user", content=user[:60_000]),
        ]

    def validate(self, *, task: str, context: Any = None) -> list[str]:
        problems = super().validate(task=task, context=context)
        if problems:
            problems.append("a safety question with no retrieved evidence must not be answered")
        return problems

    async def execute(self, **kwargs: Any) -> AgentResult:
        # ``allow_ungrounded`` is a legitimate escape hatch elsewhere ("what can
        # you do?"). For safety it is not, so it is stripped before the base
        # class can honour it.
        arguments = dict(kwargs.pop("arguments", None) or {})
        arguments.pop("allow_ungrounded", None)
        result = await super().execute(arguments=arguments, **kwargs)
        result.notes.append(_STANDING_NOTE)
        return result
