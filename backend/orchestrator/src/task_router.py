"""Intent classification and routing (Phase 6).

The first decision the orchestrator makes: what kind of request is this, which
agent should own it, does it need retrieval, code execution or a file?

This is deliberately a **deterministic keyword router with an optional model
fallback**, not a model call. Three reasons:

1. Routing is on the critical path of every request. A local 9B model costs
   seconds to answer "is this a question or a document request".
2. A keyword router is testable. ``"create a 10-slide deck"`` must route to
   documentation with ``artifact_type="pptx"`` on every run, and a test can
   assert that.
3. When routing is wrong the failure should be boring and inspectable, not
   emergent.

The model fallback exists for genuinely ambiguous requests and is used only
when the heuristics find nothing. Its answer is constrained to the same enum,
so an unexpected reply degrades to ``GENERAL`` rather than inventing a route.

Routing never decides *permissions*. It may conclude "this needs code
execution"; whether the caller may execute code is settled later by the tool
registry, which is the only component that can enforce it.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    """What the user is asking for, not which agent answers it."""

    #: A question expected to be answered from the documents.
    QUESTION = "question"
    #: "Summarise this manual", "what does section 7 cover".
    SUMMARY = "summary"
    #: Produce a file: deck, report, spreadsheet.
    ARTIFACT = "artifact"
    #: Compute something from data: trends, rates, totals.
    ANALYSIS = "analysis"
    #: Diagnose a failure, plan an intervention.
    INVESTIGATION = "investigation"
    #: Named deterministic workflow.
    WORKFLOW = "workflow"
    #: Chat with no retrieval need ("what can you do").
    GENERAL = "general"


#: Intent -> which specialised agent owns it (Phase 7 names).
_AGENT_FOR_INTENT = {
    Intent.QUESTION: "documentation",
    Intent.SUMMARY: "documentation",
    Intent.ARTIFACT: "documentation",
    Intent.ANALYSIS: "data-analysis",
    Intent.INVESTIGATION: "maintenance",
    Intent.WORKFLOW: "operations",
    Intent.GENERAL: "documentation",
}

#: Safety questions outrank the rest: a question about an interlock, a permit
#: or an isolation procedure must reach the agent whose prompt refuses to
#: guess, whatever else the sentence is about.
_SAFETY_TERMS = (
    "safety",
    "hazard",
    "lockout",
    "tagout",
    "loto",
    "permit",
    "interlock",
    "isolation",
    "toxic",
    "explosion",
    "relief valve",
    "psv",
    "emergency",
    "evacuat",
)

_ARTIFACT_TERMS = {
    "pptx": (
        "powerpoint",
        "power point",
        "ppt",
        "pptx",
        "slide",
        "slides",
        "deck",
        "presentation",
    ),
    "xlsx": ("excel", "xlsx", "spreadsheet", "workbook", "csv export"),
    "docx": ("word document", "docx", "word file"),
    "pdf": ("pdf",),
}

_ANALYSIS_TERMS = (
    "calculate",
    "compute",
    "trend",
    "average",
    "mean ",
    "correlat",
    "distribution",
    "histogram",
    "regression",
    "mtbf",
    "mttr",
    "failure rate",
    "downtime",
    "how many",
    "how much",
    "plot",
    "chart",
    "statistic",
)

_INVESTIGATION_TERMS = (
    "root cause",
    "rca",
    "why did",
    "why is",
    "diagnose",
    "troubleshoot",
    "fault",
    "failure of",
    "vibration",
    "breakdown",
    "tripped",
    "alarm",
    "leak",
    "overheat",
)

_SUMMARY_TERMS = (
    "summar",
    "overview",
    "key points",
    "tl;dr",
    "brief me",
    "what does this document",
    "outline",
)

_GENERAL_TERMS = (
    "who are you",
    "what can you do",
    "hello",
    "hi ",
    "help me understand how you",
    "your capabilities",
)

_DOC_REFERENCE_TERMS = (
    "document",
    "manual",
    "sop",
    "procedure",
    "drawing",
    "p&id",
    "datasheet",
    "report",
    "page",
    "section",
    "clause",
    "spec",
)

_SLIDE_COUNT = re.compile(r"(\d{1,2})\s*(?:-|\s)?\s*(?:slide|page|section)s?", re.IGNORECASE)


@dataclass(frozen=True)
class Route:
    intent: Intent
    agent: str
    use_rag: bool = True
    needs_code: bool = False
    needs_artifact: bool = False
    artifact_type: str | None = None
    requested_units: int | None = None
    #: Model role for the reasoning step; the router never names a model.
    model_role: str = "reasoning"
    confidence: float = 0.5
    reason: str = ""
    matched: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.value,
            "agent": self.agent,
            "use_rag": self.use_rag,
            "needs_code": self.needs_code,
            "needs_artifact": self.needs_artifact,
            "artifact_type": self.artifact_type,
            "requested_units": self.requested_units,
            "model_role": self.model_role,
            "confidence": round(self.confidence, 2),
            "reason": self.reason,
            "matched": list(self.matched),
        }


def _matches(text: str, terms: tuple[str, ...] | tuple[str, ...]) -> list[str]:
    return [term.strip() for term in terms if term in text]


def _detect_artifact(text: str) -> tuple[str | None, list[str]]:
    for artifact_type, terms in _ARTIFACT_TERMS.items():
        found = [term for term in terms if term in text]
        if found:
            return artifact_type, found
    return None, []


class TaskRouter:
    def __init__(self, *, model_router: Any = None, gateway: Any = None) -> None:
        # Both optional: routing works without a model, and must, because the
        # health of the model backend is not known at request time.
        self._model_router = model_router
        self._gateway = gateway

    async def route(
        self,
        task: str,
        *,
        workflow: str | None = None,
        use_rag: bool | None = None,
        document_ids: list[str] | None = None,
    ) -> Route:
        text = f" {(task or '').lower().strip()} "

        if workflow:
            return Route(
                intent=Intent.WORKFLOW,
                agent=_AGENT_FOR_INTENT[Intent.WORKFLOW],
                use_rag=True if use_rag is None else use_rag,
                confidence=1.0,
                reason=f"caller named workflow '{workflow}'",
            )

        artifact_type, artifact_terms = _detect_artifact(text)
        analysis_terms = _matches(text, _ANALYSIS_TERMS)
        investigation_terms = _matches(text, _INVESTIGATION_TERMS)
        summary_terms = _matches(text, _SUMMARY_TERMS)
        safety_terms = _matches(text, _SAFETY_TERMS)
        general_terms = _matches(text, _GENERAL_TERMS)
        doc_terms = _matches(text, _DOC_REFERENCE_TERMS)

        units = None
        found_units = _SLIDE_COUNT.search(text)
        if found_units:
            try:
                units = int(found_units.group(1))
            except ValueError:  # pragma: no cover - regex guarantees digits
                units = None

        # An artifact request is the most specific thing a user can ask for,
        # so it wins even when the sentence also contains analysis words.
        if artifact_type:
            return Route(
                intent=Intent.ARTIFACT,
                agent=_AGENT_FOR_INTENT[Intent.ARTIFACT],
                use_rag=True if use_rag is None else use_rag,
                needs_code=True,  # generation runs in the sandbox
                needs_artifact=True,
                artifact_type=artifact_type,
                requested_units=units,
                confidence=0.9,
                reason=f"request names a {artifact_type} deliverable",
                matched=tuple(artifact_terms),
            )

        if safety_terms:
            return Route(
                intent=Intent.QUESTION,
                agent="safety",
                use_rag=True if use_rag is None else use_rag,
                confidence=0.85,
                reason="safety-relevant terms present; routed to the safety agent",
                matched=tuple(safety_terms),
            )

        if investigation_terms:
            return Route(
                intent=Intent.INVESTIGATION,
                agent=_AGENT_FOR_INTENT[Intent.INVESTIGATION],
                use_rag=True if use_rag is None else use_rag,
                confidence=0.8,
                reason="diagnostic phrasing",
                matched=tuple(investigation_terms),
            )

        if analysis_terms:
            return Route(
                intent=Intent.ANALYSIS,
                agent=_AGENT_FOR_INTENT[Intent.ANALYSIS],
                use_rag=True if use_rag is None else use_rag,
                needs_code=True,
                confidence=0.8,
                reason="quantitative request; numbers are computed, not written by the model",
                matched=tuple(analysis_terms),
                model_role="reasoning",
            )

        if summary_terms:
            return Route(
                intent=Intent.SUMMARY,
                agent=_AGENT_FOR_INTENT[Intent.SUMMARY],
                use_rag=True if use_rag is None else use_rag,
                requested_units=units,
                confidence=0.8,
                reason="summarisation request",
                matched=tuple(summary_terms),
            )

        if general_terms and not doc_terms:
            return Route(
                intent=Intent.GENERAL,
                agent=_AGENT_FOR_INTENT[Intent.GENERAL],
                use_rag=False if use_rag is None else use_rag,
                confidence=0.7,
                reason="conversational request with no document reference",
                matched=tuple(general_terms),
            )

        # Nothing matched. A question mark, a document reference, or an
        # explicit document filter all mean "go and look it up".
        looks_like_question = "?" in (task or "") or bool(doc_terms) or bool(document_ids)
        fallback = await self._model_fallback(task) if not looks_like_question else None
        if fallback is not None:
            return fallback

        return Route(
            intent=Intent.QUESTION,
            agent=_AGENT_FOR_INTENT[Intent.QUESTION],
            use_rag=True if use_rag is None else use_rag,
            confidence=0.45 if looks_like_question else 0.3,
            reason=(
                "defaulted to a document-grounded question"
                if looks_like_question
                else "no signal found; defaulted to retrieval rather than guessing"
            ),
            matched=tuple(doc_terms),
        )

    async def _model_fallback(self, task: str) -> Route | None:
        """Ask the local model to pick an intent. Best-effort only.

        Returns ``None`` on any problem - unconfigured model, unreachable
        backend, unparseable answer. Routing must never be the reason a
        request fails.
        """
        if self._model_router is None or self._gateway is None:
            return None
        options = ", ".join(intent.value for intent in Intent)
        prompt = (
            "Classify the user request into exactly one label from this list: "
            f"{options}. Reply with the label only.\n\nRequest: {task}"
        )
        try:
            resolved = await self._model_router.resolve("reasoning")
            reply = await self._gateway.chat(
                model=resolved,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            logger.debug("router model fallback unavailable: %s", exc)
            return None

        answer = str(getattr(reply, "content", reply) or "").strip().lower()
        for intent in Intent:
            if intent.value in answer:
                return Route(
                    intent=intent,
                    agent=_AGENT_FOR_INTENT[intent],
                    use_rag=intent is not Intent.GENERAL,
                    needs_code=intent is Intent.ANALYSIS,
                    confidence=0.6,
                    reason="classified by the local reasoning model",
                )
        return None
