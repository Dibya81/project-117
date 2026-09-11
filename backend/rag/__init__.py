"""Phase 4 — hybrid retrieval + citations.

Responsibilities (one implementation per responsibility):
- ``adapter.LocalGPTRetriever`` — embedder over the vendored localGPT
  ``MultiVectorRetriever`` (LanceDB vector + FTS legs, RRF fusion) and over
  the vendored rerankers. Retrieval logic belongs to localGPT; this adapter
  only bridges our UUID document ids to the staged basenames localGPT keyed
  the index with.
- ``service.RetrievalService`` — orchestration: filter compilation,
  id-bridging (index → API ids), document resolution for citations,
  auditing. Never talks to LanceDB itself.
- ``errors`` — typed errors whose messages are safe to expose via the API.

Nothing here re-implements retrieval: no second vector store, no second
fusion, no second reranker.
"""

from backend.rag.adapter import LocalGPTRetriever, VendorNotAvailableError
from backend.rag.errors import (
    IndexUnavailableError,
    RerankerUnavailableError,
    RetrievalError,
)
from backend.rag.service import Citation, Evidence, RetrievalService

__all__ = [
    "Citation",
    "Evidence",
    "IndexUnavailableError",
    "LocalGPTRetriever",
    "RetrievalError",
    "RetrievalService",
    "RerankerUnavailableError",
    "VendorNotAvailableError",
]
