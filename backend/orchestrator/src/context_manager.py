"""Context assembly (Phase 6).

Decides what the model is allowed to see, and how much of it.

The honest problem this solves: a 600-page manual produces thousands of
chunks, a local 9B model has a few thousand usable tokens, and quietly
truncating a prompt in the middle of an evidence block is how citations start
pointing at text the model never read. So the budget is explicit, the
truncation happens at chunk boundaries, and what was dropped is recorded.

Two rules that make the rest of the system honest:

**Evidence in, evidence out.** The pack keeps the full :class:`Evidence`
objects, not just their text. The citation checker later compares the claims
in the answer against exactly these chunks - if the evidence were flattened
into a prompt string, verification would have nothing to check against.

**Retrieval failure is not silence.** ``RetrievalService.evidence_for_chat``
is best-effort by design, so an empty pack is a real state, recorded as
``degraded``. The prompt then tells the model there is no evidence, which is
what produces "I cannot find this in the indexed documents" instead of a
fluent guess.

Token counting is ``len(text) / 4``. That is an approximation and is labelled
as one; the alternative is shipping a tokeniser per model family, which buys
precision this decision does not need.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

#: Rough characters per token for English technical prose. Deliberately an
#: estimate - see the module docstring.
_CHARS_PER_TOKEN = 4

#: Default budget for retrieved evidence. Leaves room for the system prompt,
#: the plan, the question and the answer inside a typical local 8k window.
DEFAULT_EVIDENCE_TOKENS = 3000

#: Never send a single chunk larger than this; a runaway chunk would eat the
#: whole budget and starve the rest of the evidence.
MAX_CHUNK_TOKENS = 900


@dataclass
class ContextPack:
    """Everything the model may see for one step, plus what was left out."""

    query: str
    evidence: list[Any] = field(default_factory=list)
    #: Evidence retrieved but dropped for budget. Kept so the answer can say
    #: "based on the 12 most relevant of 47 passages".
    dropped: int = 0
    tokens_used: int = 0
    token_budget: int = DEFAULT_EVIDENCE_TOKENS
    document_ids: list[str] = field(default_factory=list)
    memory: list[dict[str, Any]] = field(default_factory=list)
    #: ok | degraded | disabled
    status: str = "ok"
    note: str = ""

    @property
    def has_evidence(self) -> bool:
        return bool(self.evidence)

    def prompt_text(self) -> str:
        """Render evidence for a prompt, one labelled block per chunk.

        The label carries document, page and section because the model is
        being asked to cite them. A model cannot cite metadata it was never
        shown.
        """
        if not self.evidence:
            return "No evidence was retrieved from the indexed documents for this request."
        blocks = []
        for index, item in enumerate(self.evidence, start=1):
            citation = getattr(item, "citation", None)
            document_id = getattr(citation, "document_id", "unknown")
            page = getattr(citation, "page", None)
            headings = getattr(citation, "heading_path", None) or []
            filename = getattr(item, "document_filename", None) or document_id
            location = f"page {page}" if page else "page unknown"
            section = " > ".join(str(part) for part in headings) if headings else ""
            header = f"[{index}] {filename} - {location}"
            if section:
                header += f" - {section}"
            header += f" (document_id={document_id}, chunk_id={getattr(item, 'chunk_id', '')})"
            blocks.append(f"{header}\n{getattr(item, 'text', '')}")
        return "\n\n".join(blocks)

    def evidence_dicts(self) -> list[dict[str, Any]]:
        """Evidence in the response/verification shape."""
        items = []
        for item in self.evidence:
            if hasattr(item, "to_dict"):
                items.append(item.to_dict())
                continue
            citation = getattr(item, "citation", None)
            items.append(
                {
                    "chunk_id": getattr(item, "chunk_id", ""),
                    "document_id": getattr(citation, "document_id", ""),
                    "page": getattr(citation, "page", None),
                    "heading_path": list(getattr(citation, "heading_path", []) or []),
                    "score": getattr(item, "score", None),
                }
            )
        return items

    def summary(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "evidence": len(self.evidence),
            "dropped": self.dropped,
            "tokens_used": self.tokens_used,
            "token_budget": self.token_budget,
            "documents": sorted(
                {
                    getattr(getattr(item, "citation", None), "document_id", "")
                    for item in self.evidence
                }
                - {""}
            ),
            "memory": len(self.memory),
            "note": self.note,
        }


def _estimate_tokens(text: str) -> int:
    return max(1, len(text or "") // _CHARS_PER_TOKEN)


class ContextManager:
    def __init__(
        self,
        *,
        retrieval: Any = None,
        memory: Any = None,
        token_budget: int = DEFAULT_EVIDENCE_TOKENS,
        top_k: int = 12,
    ) -> None:
        self._retrieval = retrieval
        self._memory = memory
        self._token_budget = max(200, token_budget)
        self._top_k = max(1, top_k)

    async def build(
        self,
        *,
        query: str,
        use_rag: bool = True,
        document_ids: list[str] | None = None,
        top_k: int | None = None,
        token_budget: int | None = None,
        user: str | None = None,
        session_id: str | None = None,
    ) -> ContextPack:
        budget = max(200, token_budget or self._token_budget)
        pack = ContextPack(
            query=query,
            token_budget=budget,
            document_ids=list(document_ids or []),
        )

        if not use_rag:
            pack.status = "disabled"
            pack.note = "retrieval was not requested for this step"
        elif self._retrieval is None:
            pack.status = "degraded"
            pack.note = "no retrieval service is wired"
        else:
            import asyncio

            try:
                # RetrievalService is synchronous (it drives the vendored
                # localGPT pipeline). Off the event loop it goes.
                found = await asyncio.to_thread(
                    self._retrieval.evidence_for_chat,
                    query,
                    top_k=top_k or self._top_k,
                    document_ids=document_ids or None,
                    user=user,
                )
            except Exception as exc:
                # evidence_for_chat is best-effort for chat, but a scoping
                # error is a real client error and must not be hidden here.
                if getattr(exc, "reason", "") in {"index_unavailable", "retrieval_failed"}:
                    pack.status = "degraded"
                    pack.note = f"retrieval unavailable: {exc}"
                    found = []
                else:
                    raise
            pack.evidence, pack.dropped, pack.tokens_used = self._fit(found, budget)
            if not pack.evidence:
                pack.status = "degraded"
                pack.note = pack.note or "nothing relevant was found in the indexed documents"

        if self._memory is not None:
            try:
                pack.memory = await self._recall(query, user=user, session_id=session_id)
            except Exception as exc:  # memory is an optimisation, never a blocker
                logger.debug("memory recall failed: %s", exc)
                pack.memory = []

        return pack

    def _fit(self, found: list[Any], budget: int) -> tuple[list[Any], int, int]:
        """Take evidence in rank order until the budget runs out.

        Truncation happens between chunks, never inside one: half a chunk
        would still be cited as if the whole passage had been read.
        """
        kept: list[Any] = []
        used = 0
        dropped = 0
        for item in found or []:
            tokens = min(_estimate_tokens(getattr(item, "text", "")), MAX_CHUNK_TOKENS)
            if used + tokens > budget:
                dropped += 1
                continue
            kept.append(item)
            used += tokens
        return kept, dropped, used

    async def _recall(
        self,
        query: str,
        *,
        user: str | None,
        session_id: str | None,
    ) -> list[dict[str, Any]]:
        import asyncio

        recall = getattr(self._memory, "recall", None)
        if recall is None:
            return []
        result = recall(query, user=user, session_id=session_id)
        if asyncio.iscoroutine(result):
            return await result
        return result or []
