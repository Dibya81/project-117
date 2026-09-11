"""Documentation agent (Phase 7).

Two jobs, one prompt discipline.

**Answering and summarising.** Questions about what a document says, section
summaries, "what does this manual cover". Ordinary grounded Q&A with citations.

**Authoring artifact specifications.** This is the interesting one, and it is
the reason the Phase 19 demo can work at all. The agent does *not* write a
PowerPoint file. It writes a JSON :class:`~backend.deliverables.spec.ArtifactSpec`
- titles, bullets, and a citation on every bullet - and a deterministic
generator turns that into a file inside the sandbox. A language model asked to
emit a .pptx produces corrupt XML; asked to emit structured content it produces
something a validator can reject before anyone opens it.

The spec is validated *here*, with the same ``parse_spec`` the tool uses, and
the model gets exactly one chance to repair it with the validator's own error
message. That is deliberate:

- validating early means a malformed spec never reaches the sandbox;
- one repair attempt fixes the common failure (a missing citation, a ninth
  bullet, prose where a list belongs) without turning a wrong answer into an
  expensive retry loop;
- if the second attempt also fails, the agent returns a degraded result that
  names the validation error instead of emitting a spec that will fail again
  downstream.

Citations are mandatory on every bullet. The generators render them, the
citation checker verifies they point at retrieved chunks, and the artifact
checker refuses a deck whose claims cite pages that were never retrieved. An
uncited bullet is therefore not a stylistic lapse - it is the thing that makes
the whole chain refuse the deliverable.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.agents.base import AgentResult, BaseAgent
from backend.deliverables.spec import SpecError, parse_spec
from backend.models.providers.base import ChatMessage

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are an industrial documentation analyst working strictly from the numbered "
    "evidence provided, inside an air-gapped system.\n\n"
    "Rules:\n"
    "- Use ONLY the evidence. Cite the number for every factual claim, e.g. [4].\n"
    "- Never invent page numbers, section names, part numbers, values, dates or standard "
    "numbers. If the evidence does not contain something, say what is missing.\n"
    "- Keep units, tolerances and revision identifiers exactly as written.\n"
    "- Prefer the document's own terminology over a paraphrase.\n"
    "- When the request asks for a summary, cover what the document actually emphasises, "
    "not what a document of that kind usually contains."
)

#: Artifact mode. The schema is spelled out because a local model cannot be
#: assumed to know our field names, and an invalid spec costs a round trip.
_ARTIFACT_SYSTEM = (
    "You are an industrial documentation analyst that produces STRUCTURED CONTENT for a "
    "document generator. You never write the file itself.\n\n"
    "Reply with a single JSON object and nothing else. No prose before or after, no "
    "markdown fence around it.\n\n"
    "Schema:\n"
    "{\n"
    '  "type": "pptx" | "docx" | "pdf" | "xlsx",\n'
    '  "title": string,\n'
    '  "subtitle": string (optional),\n'
    '  "slides": [            // pptx only\n'
    '    {"title": string,\n'
    '     "layout": "title" | "title_content" | "section" | "two_content",\n'
    '     "bullets": [{"text": string,\n'
    '                  "citations": [{"document_id": string, "page": integer,\n'
    '                                 "section": string, "chunk_id": string}]}],\n'
    '     "notes": string (optional speaker notes)}\n'
    "  ],\n"
    '  "sections": [          // docx and pdf only\n'
    '    {"heading": string, "level": 1-4, "paragraphs": [string],\n'
    '     "bullets": [{"text": string, "citations": [...]}]}\n'
    "  ],\n"
    '  "sheets": [            // xlsx only\n'
    '    {"name": string, "columns": [string], "rows": [[value, ...]]}\n'
    "  ],\n"
    '  "sources": [{"document_id": string, "page": integer, "section": string}]\n'
    "}\n\n"
    "Hard requirements:\n"
    "- EVERY bullet must carry at least one citation. Take document_id, page, section "
    "and chunk_id from the evidence block header - never guess them, never renumber "
    "pages, never cite a page that is not in the evidence.\n"
    "- At most 8 bullets per slide, and keep each bullet under about 200 characters so it "
    "fits on the slide.\n"
    "- Content must come from the evidence. If the evidence cannot support the requested "
    "number of slides or sections, produce fewer and add a final slide or section titled "
    "'Gaps in the source material' listing what was missing.\n"
    "- Use only the fields listed above. Unknown fields are rejected.\n"
    "- xlsx rows must be plain values (string, number, boolean or null) and every row "
    "must have exactly as many cells as there are columns. No formulas."
)


class DocumentationAgent(BaseAgent):
    name = "documentation"
    description = (
        "Answers questions and writes summaries from indexed documents, and authors the "
        "structured content (with citations) that the deck, report and spreadsheet "
        "generators turn into files."
    )
    capabilities = (
        "answer_from_documents",
        "summarise_document",
        "author_artifact_specification",
        "extract_structured_content",
        "identify_source_gaps",
    )
    requires_rag = True
    tool_names = (
        "search_documents",
        "read_document",
        "extract_table",
        "create_pptx",
        "create_docx",
        "create_pdf",
        "create_xlsx",
    )
    model_role = "reasoning"
    temperature = 0.2
    system_prompt = _SYSTEM

    #: Artifact types this agent will author content for.
    ARTIFACT_TYPES = ("pptx", "docx", "pdf", "xlsx")

    # --- mode selection ---------------------------------------------------

    @staticmethod
    def _artifact_type(arguments: dict[str, Any]) -> str | None:
        candidate = str(
            arguments.get("artifact_type") or arguments.get("artifact") or ""
        ).strip().lower()
        return candidate if candidate in DocumentationAgent.ARTIFACT_TYPES else None

    def plan(self, *, task: str, context: Any = None) -> list[dict[str, Any]]:
        return [
            {"kind": "agent", "name": self.name, "description": "author the content"},
            {
                "kind": "tool",
                "name": "create_pptx",
                "description": "render the authored spec deterministically",
            },
        ]

    # --- prompting --------------------------------------------------------

    def build_prompt(
        self,
        *,
        task: str,
        context: Any = None,
        arguments: dict[str, Any] | None = None,
    ) -> list[ChatMessage]:
        arguments = dict(arguments or {})
        artifact_type = self._artifact_type(arguments)
        evidence_text = self.evidence_text(context)

        if artifact_type is None:
            user = f"Evidence:\n{evidence_text}\n\nRequest: {task}"
            return [
                ChatMessage(role="system", content=self.system_prompt),
                ChatMessage(role="user", content=user[:60_000]),
            ]

        units = arguments.get("requested_units")
        unit_word = {"pptx": "slides", "xlsx": "sheets"}.get(artifact_type, "sections")
        size_line = (
            f"Produce {int(units)} {unit_word} unless the evidence cannot support that many.\n"
            if isinstance(units, int) and units > 0
            else ""
        )
        user = (
            f"Evidence:\n{evidence_text}\n\n"
            f"Deliverable: {artifact_type}\n{size_line}"
            f"Request: {task}\n\n"
            "Return only the JSON object."
        )
        return [
            ChatMessage(role="system", content=_ARTIFACT_SYSTEM),
            ChatMessage(role="user", content=user[:60_000]),
        ]

    # --- post-processing --------------------------------------------------

    async def postprocess(
        self,
        result: AgentResult,
        *,
        task: str,
        context: Any = None,
        arguments: dict[str, Any] | None = None,
    ) -> AgentResult:
        arguments = dict(arguments or {})
        artifact_type = self._artifact_type(arguments)
        if artifact_type is None:
            if result.grounded and "[" not in result.answer:
                result.notes.append(
                    "the answer carries no evidence markers, so citation checking will "
                    "reject it"
                )
            return result

        spec, error = self._validate(result.answer, artifact_type)
        if spec is None:
            repaired, repair_error = await self._repair(
                task=task,
                context=context,
                arguments=arguments,
                artifact_type=artifact_type,
                previous=result.answer,
                error=error or "the reply was not a JSON object",
            )
            if repaired is None:
                result.degraded = True
                result.notes.append(
                    f"the artifact specification could not be validated: {repair_error}"
                )
                return result
            spec = repaired

        # ``spec`` is the validated model dumped back to JSON-safe primitives:
        # the tool re-validates it, so passing the raw reply would just mean
        # validating twice and trusting the second result.
        result.spec = spec.model_dump(mode="json")
        summary = spec.summary()
        result.answer = (
            f"Authored a {artifact_type} specification: \"{spec.title}\" with "
            f"{spec.content_units()} {('slides' if artifact_type == 'pptx' else 'sheets' if artifact_type == 'xlsx' else 'sections')} "
            f"and {len(spec.all_citations())} citation(s). "
            "The file itself is produced by the generator, not by the model."
        )
        # Filename is deliberately left unset: the artifact service derives a
        # safe one from the title, and two places inventing filenames is one
        # place too many.
        if not spec.all_citations():
            result.degraded = True
            result.notes.append(
                "the specification contains no citations, so verification will reject the "
                "artifact"
            )
        uncited = self._uncited_bullets(spec)
        if uncited:
            result.notes.append(f"{uncited} bullet(s) carry no citation")
        requested = arguments.get("requested_units")
        if isinstance(requested, int) and requested > 0 and spec.content_units() != requested:
            result.notes.append(
                f"{spec.content_units()} unit(s) authored against {requested} requested"
            )
        logger.info("documentation agent authored spec: %s", summary)
        return result

    # --- validation helpers -----------------------------------------------

    def _validate(self, text: str, artifact_type: str) -> tuple[Any | None, str | None]:
        payload = self._json_object(text)
        if payload is None:
            return None, "the reply did not contain a JSON object"
        try:
            return parse_spec(payload, expected_type=artifact_type), None
        except SpecError as exc:
            return None, str(exc)

    async def _repair(
        self,
        *,
        task: str,
        context: Any,
        arguments: dict[str, Any],
        artifact_type: str,
        previous: str,
        error: str,
    ) -> tuple[Any | None, str | None]:
        """One corrective round trip, carrying the validator's own message."""
        messages = [
            ChatMessage(role="system", content=_ARTIFACT_SYSTEM),
            ChatMessage(
                role="user",
                content=(
                    f"Evidence:\n{self.evidence_text(context)}\n\n"
                    f"Deliverable: {artifact_type}\nRequest: {task}\n\n"
                    "Return only the JSON object."
                )[:60_000],
            ),
            ChatMessage(role="assistant", content=previous[:20_000]),
            ChatMessage(
                role="user",
                content=(
                    f"That was rejected by the validator: {error}\n\n"
                    "Return the corrected JSON object only. Do not explain the change. "
                    "Keep every citation you had, and add the missing ones from the "
                    "evidence headers."
                ),
            ),
        ]
        try:
            reply, _model, _usage = await self._complete(messages)
        except Exception as exc:
            return None, f"the repair attempt could not reach the model ({exc})"
        spec, repair_error = self._validate(reply, artifact_type)
        if spec is None:
            return None, repair_error or "the corrected reply was still invalid"
        return spec, None

    @staticmethod
    def _json_object(text: str) -> dict[str, Any] | None:
        """Extract one JSON object from a model reply.

        Fenced first (local models fence even when told not to), then a brace
        scan for the outermost object. Anything else returns ``None`` rather
        than a partially-parsed guess.
        """
        if not text:
            return None
        candidates: list[str] = []
        fenced = BaseAgent.extract_fenced(text, "json")
        if fenced:
            candidates.append(fenced)
        stripped = text.strip()
        candidates.append(stripped)
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end > start:
            candidates.append(stripped[start : end + 1])
        for candidate in candidates:
            try:
                loaded = json.loads(candidate)
            except (ValueError, TypeError):
                continue
            if isinstance(loaded, dict):
                return loaded
        return None

    @staticmethod
    def _uncited_bullets(spec: Any) -> int:
        count = 0
        for slide in getattr(spec, "slides", []) or []:
            count += sum(1 for bullet in slide.bullets if not bullet.citations)
        for section in getattr(spec, "sections", []) or []:
            if section.citations:
                continue
            count += sum(1 for bullet in section.bullets if not bullet.citations)
        return count
