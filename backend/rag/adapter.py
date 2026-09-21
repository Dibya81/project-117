"""localGPT retrieval adapter.

Imports the vendored ``rag_system`` package in place (upstream code is never
modified) and exposes ``MultiVectorRetriever`` — localGPT's hybrid LanceDB
retriever (vector leg + full-text leg fused with reciprocal rank fusion) —
plus the vendored rerankers as one embedder object.

Design points (mirroring the Phase 3 ingestion adapter):

- **Lazy vendor import.** Importing ``rag_system.retrieval.retrievers`` pulls
  torch/transformers (~10s cold). The adapter defers that import until the
  first real retrieval call, so app boot, tests and non-search endpoints
  never pay for it. Construction is serialized behind a lock: the embedder
  load and LanceDB connect are expensive and not thread-safe on first use.
- **Query-side embedder identity.** localGPT's ``select_embedder`` builds an
  ``OllamaEmbedder`` for Ollama tags and a HF ``QwenEmbedder`` for model
  paths. The table marker written at indexing time records the embedding
  model; ``MultiVectorRetriever.retrieve`` re-checks it on every query
  (``EmbedderMismatchError`` is never swallowed) and normalizes the query
  vector for v4+ tables. We pass the same model name the indexer used.
- **Filter DSL stays upstream.** The ``where`` predicate must come from
  ``rag_system.retrieval.filters.compile_filters`` — localGPT refuses to
  compile unvalidated strings, and so do we.
- **Rerankers are opt-in and vendor-owned.** ``CrossEncoderReranker`` (HF
  cross-encoder), ``QwenRerankerScorer`` (causal-LM yes/no scorer — the
  only calibrated 0–1 backend) and the ``rerankers`` lib are all vendored;
  we just construct the configured one lazily and lock its first use.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)

# Repo-relative: backend/rag/adapter.py -> parents[2] is the repo root.
# The vendored tree lives at <repo>/vendor/localGPT (it was an out-of-repo
# sibling before, so retrieval only worked on the author's machine).
_VENDOR_ROOT = Path(__file__).resolve().parents[2] / "vendor" / "localGPT"


class VendorNotAvailableError(RuntimeError):
    """The vendored localGPT tree is missing or its dependencies are absent."""


def _ensure_vendor_on_path() -> None:
    if _VENDOR_ROOT.is_dir() and str(_VENDOR_ROOT) not in sys.path:
        sys.path.insert(0, str(_VENDOR_ROOT))


def ensure_vendor_available() -> None:
    """Raise unless the vendored tree exists; make it importable."""
    if not _VENDOR_ROOT.is_dir():
        raise VendorNotAvailableError(f"vendored localGPT tree not found at {_VENDOR_ROOT}")
    _ensure_vendor_on_path()


class LocalGPTRetriever:
    """Thin embedder over localGPT's ``MultiVectorRetriever`` + rerankers.

    Responsibilities deliberately NOT replicated here (upstream owns them):
    hybrid search, RRF fusion, embedder-mismatch guards, FTS quote-stripping,
    filter compilation, reranker model loading.
    """

    def __init__(
        self,
        *,
        db_path: Path,
        table_name: str,
        embedding_model: str,
        ollama_host: str,
        reranker_model: str = "",
    ) -> None:
        self._db_path = str(db_path)
        self._table_name = table_name
        self._embedding_model = embedding_model
        self._ollama_host = ollama_host
        self._reranker_model = reranker_model
        self._retriever: Any = None
        self._reranker: Any = None
        self._init_lock = threading.Lock()
        self._reranker_init_lock = threading.Lock()

    # --- public API -------------------------------------------------------

    def retrieve(
        self,
        query: str,
        *,
        top_k: int,
        mode: str = "hybrid",
        where: str | None = None,
    ) -> list[dict[str, Any]]:
        """Hybrid/vector/FTS retrieval over the configured table.

        ``where`` must be a compiled LanceDB predicate (the service compiles
        it via localGPT's filter DSL). Rows carry ``document_id`` (the staged
        basename), ``chunk_index``, ``text``, ``score`` and ``metadata``.
        """
        retriever = self._retriever_or_init()
        started = time.perf_counter()
        rows = retriever.retrieve(
            text_query=query,
            table_name=self._table_name,
            k=top_k,
            search_type=mode,
            where=where,
        )
        logger.debug(
            "localGPT retrieval mode=%s k=%d rows=%d in %.2fs",
            mode,
            top_k,
            len(rows),
            time.perf_counter() - started,
        )
        return rows

    def rerank(self, query: str, docs: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
        """Rerank candidate rows; returns a new list ordered by relevance.

        Uses the configured vendored backend. ``QwenRerankerScorer`` yields a
        calibrated 0–1 probability (stored as ``rerank_score``); other
        backends yield raw logits, which are still monotone in relevance.
        A reranker failure raises — the service decides whether to degrade.
        """
        reranker = self._reranker_or_init()
        if reranker is None or not docs:
            return docs
        # Interface shared by every vendored backend: rank(query, docs) →
        # [(score, original_index)] sorted by score, descending.
        scored = reranker.rank(query, [d.get("text", "") for d in docs])
        out: list[dict[str, Any]] = []
        for score, index in scored[:top_k]:
            row = dict(docs[index])
            row["rerank_score"] = float(score)
            out.append(row)
        return out

    def has_table(self) -> bool:
        """Whether the LanceDB table exists (used to map 'nothing indexed')."""
        import lancedb

        from backend.storage.lancedb import has_table

        db = lancedb.connect(self._db_path)
        return has_table(db, self._table_name)

    @property
    def embedding_model(self) -> str:
        return self._embedding_model

    @property
    def table_name(self) -> str:
        return self._table_name

    @property
    def reranker_model(self) -> str:
        return self._reranker_model

    # --- internals ---------------------------------------------------------

    def _retriever_or_init(self) -> Any:
        if self._retriever is not None:
            return self._retriever
        with self._init_lock:
            if self._retriever is None:
                self._retriever = self._build_retriever()
            return self._retriever

    def _build_retriever(self) -> Any:
        if not _VENDOR_ROOT.is_dir():
            raise VendorNotAvailableError(f"vendored localGPT tree not found at {_VENDOR_ROOT}")
        try:
            import lancedb  # noqa: F401
            import torch  # noqa: F401
        except ImportError as exc:
            raise VendorNotAvailableError(
                f"retrieval dependencies missing ({exc}); run `uv sync` in backend/"
            ) from exc

        _ensure_vendor_on_path()
        started = time.perf_counter()
        from rag_system.indexing.embedders import LanceDBManager
        from rag_system.indexing.representations import QwenEmbedder, select_embedder
        from rag_system.retrieval.retrievers import MultiVectorRetriever

        logger.info(
            "initializing localGPT MultiVectorRetriever (embedder=%s, table=%s)",
            self._embedding_model,
            self._table_name,
        )
        # cast: select_embedder returns the QwenEmbedder | OllamaEmbedder union;
        # MultiVectorRetriever annotates the narrower QwenEmbedder, but both
        # satisfy the same EmbeddingModel protocol upstream relies on.
        embedder = cast("QwenEmbedder", select_embedder(self._embedding_model, self._ollama_host))
        retriever = MultiVectorRetriever(
            LanceDBManager(db_path=self._db_path),
            embedder,
        )
        logger.info("localGPT retriever ready in %.1fs", time.perf_counter() - started)
        return retriever

    def _reranker_or_init(self) -> Any:
        if not self._reranker_model:
            return None
        if self._reranker is not None:
            return self._reranker
        with self._reranker_init_lock:
            if self._reranker is None:
                self._reranker = self._build_reranker()
            return self._reranker

    def _build_reranker(self) -> Any:
        if not _VENDOR_ROOT.is_dir():
            raise VendorNotAvailableError(f"vendored localGPT tree not found at {_VENDOR_ROOT}")
        _ensure_vendor_on_path()
        model = self._reranker_model
        # Same routing rule as the vendored RetrievalPipeline._get_ai_reranker:
        # Qwen3-Reranker is a causal-LM yes/no scorer, not a
        # SequenceClassification model — the rerankers lib would load it with
        # a randomly initialised head.
        if "qwen3-reranker" in model.lower():
            from rag_system.rerankers.reranker import QwenRerankerScorer

            return QwenRerankerScorer(model_name=model)
        if "/" not in model:
            # An Ollama-style tag cannot be a HF cross-encoder; refuse loudly
            # instead of downloading something unexpected.
            raise VendorNotAvailableError(
                f"reranker model '{model}' is not usable — configure a Hugging Face "
                "path (e.g. BAAI/bge-reranker-v2-m3 or Qwen/Qwen3-Reranker-0.6B)"
            )
        from rag_system.rerankers.reranker import CrossEncoderReranker

        return CrossEncoderReranker(model_name=model)
