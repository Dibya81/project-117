"""Chat request/response contracts.

These live outside the route module so the same definitions can be imported by
the route, by tests, and by the OpenAPI export that the frontend's typed API
client is generated from. ``routes/chat.py`` imports ``ChatRequest`` from here
— there is exactly one definition of the contract, not a copy per layer.
"""

from __future__ import annotations

from typing import Literal

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


class Citation(BaseModel):
    """A pointer back to retrieved evidence. Answers carry these or say they
    could not be grounded; they are never synthesised."""

    document_id: str
    document_name: str | None = None
    chunk_id: str | None = None
    score: float | None = None
    snippet: str | None = None


class ChatStreamEvent(BaseModel):
    """One frame of the SSE stream produced by ``POST /api/chat/stream``."""

    type: Literal["start", "token", "citations", "usage", "done", "error"]
    content: str | None = None
    code: str | None = None
    message: str | None = None
    citations: list[Citation] | None = None
    model: str | None = None
    session_id: str | None = None


class ChatResponse(BaseModel):
    """Non-streaming reply shape."""

    message: str
    session_id: str
    model: str
    role: str
    citations: list[Citation] = Field(default_factory=list)
    grounded: bool = False
    usage: dict | None = None


__all__ = ["ChatRequest", "ChatResponse", "ChatStreamEvent", "Citation"]
