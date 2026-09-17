"""Chat request/response contracts.

These live outside the route module so the same definitions can be imported by
the route, by tests, and by the OpenAPI export that the frontend's typed API
client is generated from.

They describe what the endpoints actually return. The previous revision of this
module declared ``ChatResponse`` as ``{message, session_id, model, role,
citations, grounded, usage}`` while the route returned ``{response, model,
provider, latency_ms, session_id, usage, evidence}``. Nothing imported the old
class, so it was never checked against a live response — a contract that is
declared but not enforced drifts silently, and every consumer that trusted it
read the wrong fields.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """A single turn sent to the local model gateway."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1)
    session_id: str | None = None
    role: str | None = None
    model: str | None = None  # explicit model override (must be served locally)
    # Phase 4: opt-in document grounding. None = server default (off).
    use_rag: bool | None = None
    # Optional scope: only retrieve evidence from these document UUIDs.
    document_ids: list[str] | None = None


class EvidenceCitation(BaseModel):
    """Where a retrieved chunk came from, inside its source document."""

    document_id: str
    chunk_index: int
    page: int | None = None
    heading_path: list[str] = Field(default_factory=list)
    block_type: str


class EvidenceDocument(BaseModel):
    """The source document a chunk belongs to. Present only when known."""

    id: str
    filename: str


class Evidence(BaseModel):
    """One retrieved chunk offered to the model as grounding.

    ``text`` is the verbatim chunk. These are the snippets the answer is
    allowed to rely on, so they are returned to the caller rather than being
    kept server-side: the UI has to be able to show what grounded an answer.
    """

    chunk_id: str
    text: str
    score: float | None = None
    rerank_score: float | None = None
    citation: EvidenceCitation
    document: EvidenceDocument | None = None


class ChatResponse(BaseModel):
    """The non-streaming reply shape returned by ``POST /api/chat``."""

    response: str
    model: str
    provider: str
    latency_ms: float
    session_id: str | None = None
    #: Opaque provider usage metadata. Not ``dict[str, int]``: the
    #: OpenAI-compatible format nests ``prompt_tokens_details``, and the strict
    #: value type rejected every real Ollama reply (a 400 from this contract).
    usage: dict[str, Any] = Field(default_factory=dict)
    #: Populated only when the turn was grounded; empty otherwise.
    evidence: list[Evidence] = Field(default_factory=list)


class ChatStreamEvent(BaseModel):
    """One frame of the SSE stream produced by ``POST /api/chat/stream``.

    A single frame type carries different fields, so everything but ``type`` is
    optional — see ``backend/chat/service.py::stream_turn`` for the emission
    order: start, evidence?, delta*, complete.
    """

    type: Literal["start", "evidence", "delta", "error", "complete"]
    model: str | None = None
    provider: str | None = None
    grounded: bool | None = None
    evidence: list[Evidence] | None = None
    text: str | None = None
    message: str | None = None
    latency_ms: float | None = None


__all__ = [
    "ChatRequest",
    "ChatResponse",
    "ChatStreamEvent",
    "Evidence",
    "EvidenceCitation",
    "EvidenceDocument",
]
