"""Chat service.

Orchestrates one turn: resolve the model role via the router, attach session
history, call the provider, persist the turn, and audit it (metadata only —
never message content). Streaming shares the same path and emits typed events
for the SSE consumer.

Phase 4 adds **opt-in document grounding**: with ``use_rag`` (or a server
default) the turn first retrieves evidence through the RetrievalService and
the model is instructed to answer strictly from it. Evidence is returned in
the response payload (and as SSE events) so clients can render citations.
Grounding is best-effort: when nothing is indexed, or retrieval fails, the
turn proceeds without evidence rather than failing.
"""

from __future__ import annotations

import logging
import time
from typing import Any, AsyncIterator

from pydantic import BaseModel, Field

from backend.chat.sessions import ChatSessionStore
from backend.models.providers.base import ChatMessage
from backend.models.router import ModelRouter
from backend.rag.errors import RetrievalError
from backend.rag.service import Evidence, RetrievalService
from backend.security.audit import AuditService
from backend.security.rbac import Principal

logger = logging.getLogger(__name__)

DEFAULT_ROLE = "reasoning"
_SYSTEM_PROMPT = (
    "You are Project 117, a sovereign, local industrial AI assistant for "
    "manufacturing operations. Answer factually and concisely. You have no "
    "internet access and must never claim to know specific document contents "
    "unless evidence-backed retrieval supplies them."
)

# The grounding prompt keeps localGPT's synthesis-grounding rules (snippets
# are the only source; numbers are copied character-for-character; a missing
# answer is stated, never invented) adapted to the chat envelope.
_GROUNDED_SYSTEM_PROMPT = (
    "You are Project 117, a sovereign, local industrial AI assistant for "
    "manufacturing operations.\n\n"
    "Answer the user's question using ONLY the evidence snippets provided "
    "below. Hard rules:\n"
    "1. Use ONLY information stated in the snippets. Your own knowledge, "
    "however confident, must not appear in the answer.\n"
    "2. Copy every number, identifier, code and quoted phrase "
    "character-for-character from a snippet.\n"
    "3. Cite the snippet you used, in the form [S<n>] where n is the snippet "
    "number given before its text.\n"
    "4. If the snippets do not contain the needed information, say exactly "
    "that you could not find it in the provided documents — do not answer "
    "from general knowledge.\n"
    "5. If snippets contradict one another, state the contradiction "
    "explicitly.\n\n"
    "–––––  Evidence snippets  –––––\n{evidence}\n––––––––––––––––––––––––––––––"
)


def _render_evidence(evidence: list[Evidence]) -> str:
    """Format evidence chunks as numbered snippets for the system prompt."""
    parts: list[str] = []
    for i, item in enumerate(evidence, start=1):
        citation = item.citation
        source = item.document_filename or citation.document_id
        where = f"p. {citation.page}" if citation.page is not None else "page unknown"
        heading = " > ".join(citation.heading_path) if citation.heading_path else ""
        header = f"[S{i}] {source} — {where}"
        if heading:
            header += f" — {heading}"
        parts.append(f"{header}\n{item.text}")
    return "\n\n".join(parts)


class ChatTurnResult(BaseModel):
    response: str
    model: str
    provider: str
    latency_ms: float
    session_id: str | None = None
    # ``usage`` is opaque provider metadata, not a fixed integer schema: the
    # OpenAI-compatible wire format includes nested objects such as
    # ``prompt_tokens_details``, and typing this as ``dict[str, int]`` made
    # every Ollama reply fail validation - inside this model, so the whole turn
    # surfaced as a 400. It mirrors ``ChatResult.usage`` (providers/base.py).
    usage: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict] = Field(default_factory=list)  # populated when grounded


class ChatService:
    def __init__(
        self,
        router: ModelRouter,
        sessions: ChatSessionStore,
        audit: AuditService,
        retrieval: RetrievalService | None = None,
        default_use_rag: bool = False,
        evidence_top_k: int = 5,
    ) -> None:
        self._router = router
        self._sessions = sessions
        self._audit = audit
        self._retrieval = retrieval
        self._default_use_rag = default_use_rag
        self._evidence_top_k = evidence_top_k

    async def run_turn(
        self,
        *,
        message: str,
        session_id: str | None = None,
        role: str = DEFAULT_ROLE,
        model_override: str | None = None,
        system_prompt: str | None = None,
        user: str | None = None,
        use_rag: bool | None = None,
        require_grounding: bool = False,
        document_ids: list[str] | None = None,
        principal: Principal | None = None,
    ) -> ChatTurnResult:
        evidence = self._gather_evidence(
            message,
            use_rag=use_rag,
            document_ids=document_ids,
            user=user,
            principal=principal,
        )

        resolved = await self._router.resolve(role, model_override=model_override)

        # Insufficient evidence abstention: if caller requires grounding and no evidence was retrieved
        if require_grounding and not evidence:
            abstention_msg = (
                "Insufficient evidence in indexed documents to answer the question factually. "
                "No matching chunks met the relevance threshold."
            )
            self._persist_turn(session_id, message, abstention_msg)
            self._audit.record(
                action="chat.abstained",
                resource_type="chat",
                resource_id=session_id,
                user=user,
                detail={
                    "model": resolved.model,
                    "provider": resolved.provider_name,
                    "reason": "insufficient_evidence",
                    "grounded": False,
                    "evidence_count": 0,
                },
            )
            return ChatTurnResult(
                response=abstention_msg,
                model=resolved.model,
                provider=resolved.provider_name,
                latency_ms=0.0,
                session_id=session_id,
                evidence=[],
            )

        system_prompt = system_prompt or self._grounded_prompt(evidence)
        messages = self._messages_for(session_id, message, system_prompt)

        started = time.perf_counter()
        result = await resolved.provider.chat(
            model=resolved.model, messages=messages, temperature=0.2
        )
        latency_ms = (time.perf_counter() - started) * 1000

        self._persist_turn(session_id, message, result.content)
        self._audit.record(
            action="chat.completed",
            resource_type="chat",
            resource_id=session_id,
            user=user,
            detail={
                "model": resolved.model,
                "provider": resolved.provider_name,
                "latency_ms": round(latency_ms, 1),
                "grounded": bool(evidence),
                "evidence_count": len(evidence),
            },
        )
        return ChatTurnResult(
            response=result.content,
            model=result.model,
            provider=resolved.provider_name,
            latency_ms=round(latency_ms, 1),
            session_id=session_id,
            usage=result.usage,
            evidence=[e.to_dict() for e in evidence],
        )

    async def stream_turn(
        self,
        *,
        message: str,
        session_id: str | None = None,
        role: str = DEFAULT_ROLE,
        model_override: str | None = None,
        system_prompt: str | None = None,
        user: str | None = None,
        use_rag: bool | None = None,
        document_ids: list[str] | None = None,
        principal: Principal | None = None,
    ) -> AsyncIterator[dict]:
        """Yields typed events: {"type": "start"|"evidence"|"delta"|"complete"|"error"}."""
        evidence = self._gather_evidence(
            message,
            use_rag=use_rag,
            document_ids=document_ids,
            user=user,
            principal=principal,
        )
        system_prompt = system_prompt or self._grounded_prompt(evidence)
        resolved = await self._router.resolve(role, model_override=model_override)
        messages = self._messages_for(session_id, message, system_prompt)

        yield {
            "type": "start",
            "model": resolved.model,
            "provider": resolved.provider_name,
            "grounded": bool(evidence),
        }
        if evidence:
            yield {
                "type": "evidence",
                "evidence": [e.to_dict() for e in evidence],
            }

        started = time.perf_counter()
        parts: list[str] = []
        try:
            async for token in resolved.provider.chat_stream(
                model=resolved.model, messages=messages, temperature=0.2
            ):
                parts.append(token)
                yield {"type": "delta", "text": token}
        except Exception as exc:
            yield {"type": "error", "message": str(exc)}
            raise
        latency_ms = (time.perf_counter() - started) * 1000

        answer = "".join(parts)
        self._persist_turn(session_id, message, answer)
        self._audit.record(
            action="chat.stream_completed",
            resource_type="chat",
            resource_id=session_id,
            user=user,
            detail={
                "model": resolved.model,
                "provider": resolved.provider_name,
                "latency_ms": round(latency_ms, 1),
                "tokens": len(parts),
                "grounded": bool(evidence),
                "evidence_count": len(evidence),
            },
        )
        yield {
            "type": "complete",
            "model": resolved.model,
            "provider": resolved.provider_name,
            "latency_ms": round(latency_ms, 1),
        }

    # --- internals -------------------------------------------------------

    def _gather_evidence(
        self,
        message: str,
        *,
        use_rag: bool | None,
        document_ids: list[str] | None,
        user: str | None,
        principal: Principal | None = None,
    ) -> list[Evidence]:
        """Retrieve grounding evidence when requested.

        Best-effort: retrieval problems are logged and the turn proceeds
        ungrounded — a search outage must not take chat down with it. Note
        the retrieval service is synchronous; both entry points run the model
        call afterwards, so the (fast) hybrid query is acceptable inline here.
        """
        if not (use_rag if use_rag is not None else self._default_use_rag):
            return []
        if self._retrieval is None:
            return []
        try:
            return self._retrieval.evidence_for_chat(
                message,
                top_k=self._evidence_top_k,
                document_ids=document_ids,
                user=user,
                # Grounding is where retrieval meets the model, so the caller's
                # clearance travels with the query: unauthorized chunks are
                # filtered before the evidence list - and therefore before the
                # prompt - is built.
                principal=principal,
            )
        except RetrievalError as exc:
            logger.warning("chat grounding skipped: %s", exc)
            return []

    def _grounded_prompt(self, evidence: list[Evidence]) -> str | None:
        if not evidence:
            return None
        return _GROUNDED_SYSTEM_PROMPT.format(evidence=_render_evidence(evidence))

    def _messages_for(
        self, session_id: str | None, message: str, system_prompt: str | None
    ) -> list[ChatMessage]:
        history = self._sessions.get(session_id) if session_id else []
        messages = [ChatMessage(role="system", content=system_prompt or _SYSTEM_PROMPT)]
        messages.extend(history)
        messages.append(ChatMessage(role="user", content=message))
        return messages

    def _persist_turn(self, session_id: str | None, user_msg: str, answer: str) -> None:
        if not session_id:
            return
        self._sessions.append(session_id, ChatMessage(role="user", content=user_msg))
        self._sessions.append(session_id, ChatMessage(role="assistant", content=answer))
