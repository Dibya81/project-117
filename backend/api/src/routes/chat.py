"""Chat endpoints.

Phase 2: real single-turn and streaming chat through the model router/gateway
(no RAG yet — document-grounded answers arrive in Phase 4). History is kept
per session in memory; persistence lands in Phase 17.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.api.src.errors import BadRequest, ServiceUnavailable
from backend.api.src.schemas.chat import ChatRequest
from backend.models.providers.base import ProviderUnreachable
from backend.models.router import ModelUnavailableError

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("")
async def chat(payload: ChatRequest, request: Request) -> dict:
    role = payload.role or "reasoning"
    _validate_role(role)
    service = request.app.state.chat
    try:
        result = await service.run_turn(
            message=payload.message,
            session_id=payload.session_id,
            role=role,
            model_override=payload.model,
            use_rag=payload.use_rag,
            document_ids=payload.document_ids,
        )
    except ModelUnavailableError as exc:
        raise ServiceUnavailable(
            exc.message,
            code="model_unavailable",
            detail={"available_models": exc.available_models},
        ) from exc
    except ProviderUnreachable as exc:
        raise ServiceUnavailable(
            f"local model backend unreachable: {exc.message}",
            code="provider_unreachable",
        ) from exc
    return result.model_dump()


@router.post("/stream")
async def chat_stream(payload: ChatRequest, request: Request) -> StreamingResponse:
    role = payload.role or "reasoning"
    _validate_role(role)
    service = request.app.state.chat

    async def event_source():
        try:
            async for event in service.stream_turn(
                message=payload.message,
                session_id=payload.session_id,
                role=role,
                model_override=payload.model,
                use_rag=payload.use_rag,
                document_ids=payload.document_ids,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except ModelUnavailableError as exc:
            yield _error_event("model_unavailable", exc.message, exc.available_models)
        except ProviderUnreachable as exc:
            yield _error_event("provider_unreachable", f"local model backend unreachable: {exc.message}")
        except Exception as exc:  # stream died mid-way; report, don't hang
            yield _error_event("stream_error", exc.__class__.__name__)
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")


def _validate_role(role: str) -> None:
    if role not in ("reasoning", "vision", "embedding", "reranker", "coding", "domain"):
        raise BadRequest(
            f"unknown model role '{role}' — expected one of: "
            "reasoning, vision, embedding, reranker, coding, domain"
        )


def _error_event(code: str, message: str, available_models: list[str] | None = None) -> str:
    event: dict = {"type": "error", "code": code, "message": message}
    if available_models:
        event["available_models"] = available_models
    return f"data: {json.dumps(event)}\n\n"