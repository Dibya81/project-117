"""Search endpoint.

Phase 4: evidence-backed retrieval over the localGPT hybrid index (vector +
full-text fused with reciprocal rank fusion), with optional reranking and
structured citations (document/page/section/chunk).
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from backend.api.src.deps import get_retrieval
from backend.rag.errors import RetrievalError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    document_ids: list[str] | None = None
    top_k: int = Field(default=10, ge=1, le=100)
    mode: str = Field(default="hybrid", pattern="^(hybrid|vector_only|fts_only)$")
    # localGPT metadata filter DSL: {"document_id": {"in": [...]}, "chunk_index": {"gte": 0}}
    filters: dict | None = None
    rerank: bool | None = None  # None = server default


@router.post("")
async def search(payload: SearchRequest, request: Request) -> dict:
    service = get_retrieval(request)
    loop = asyncio.get_running_loop()
    # Retrieval embeds the query (possibly an Ollama round-trip) and can hit
    # LanceDB — run it off the event loop like the other blocking phases.
    return await loop.run_in_executor(
        None,
        lambda: service.search(
            payload.query,
            top_k=payload.top_k,
            mode=payload.mode,
            document_ids=payload.document_ids,
            filters=payload.filters,
            rerank=payload.rerank,
        ),
    )


def retrieval_error_status(exc: RetrievalError) -> int:
    """Map typed retrieval errors to HTTP statuses."""
    from backend.rag.errors import IndexUnavailableError

    if isinstance(exc, IndexUnavailableError):
        return 404 if "not found" in str(exc) else 409
    return 422
