"""localGPT adapter.

Imports the vendored ``rag_system`` package in place (upstream code is never
modified) and exposes the ``IndexingPipeline`` as an embedder. The vendored
tree is prepended to ``sys.path`` once; its import-time side effects are
harmless (logging config + optional HF token login).

Lazy-loading note: importing ``rag_system.pipelines.indexing_pipeline`` pulls
in torch/transformers/docling (~10s cold). The adapter defers that import
until the first real indexing call, so app boot, tests and non-ingestion
endpoints never pay for it. Construction itself is serialized behind a lock:
docling's converter init and HF tokenizer load are expensive and not
thread-safe on first use; concurrent reindexes queue instead of racing.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from importlib import metadata
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

logger = logging.getLogger(__name__)

# Repo-relative: backend/ingestion/adapter.py -> parents[2] is the repo root.
# The vendored tree lives at <repo>/vendor/localGPT (was an out-of-repo sibling
# before, which made a clean checkout unable to ingest anything).
_VENDOR_ROOT = Path(__file__).resolve().parents[2] / "vendor" / "localGPT"
# Root-relative module path the vendored package exposes.
_VENDOR_PACKAGE = "rag_system"


class VendorNotAvailableError(RuntimeError):
    """The vendored localGPT tree is missing or its dependencies are absent."""


def _ensure_vendor_on_path() -> None:
    if _VENDOR_ROOT.is_dir() and str(_VENDOR_ROOT) not in sys.path:
        sys.path.insert(0, str(_VENDOR_ROOT))


def _vendor_version() -> str | None:
    try:
        return metadata.version("docling")
    except metadata.PackageNotFoundError:
        return None


class LocalGPTIndexer:
    """Thin embedder over localGPT's ``IndexingPipeline``.

    Responsibilities deliberately NOT replicated here (upstream owns them):
    document conversion (docling), OCR fallback logic, chunking, embedding,
    LanceDB storage, FTS index creation, dedup on reindex.
    """

    def __init__(
        self,
        *,
        db_path: Path,
        table_name: str,
        chunk_size: int,
        chunk_overlap: int,
        embedding_model: str,
        ollama_host: str,
    ) -> None:
        self._db_path = str(db_path)
        self._table_name = table_name
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._embedding_model = embedding_model
        self._ollama_host = ollama_host
        self._pipeline: Any = None
        self._init_lock = threading.Lock()

    # --- public API -------------------------------------------------------

    def index_file(self, staged_path: Path) -> dict[str, Any]:
        """Convert → chunk → embed → index one staged file. Returns stats."""
        pipeline = self._pipeline_or_init()
        started = time.perf_counter()
        # IndexingPipeline.run accepts a list of paths and derives document_id
        # from the basename — the stager guarantees that basename is our UUID.
        pipeline.run([str(staged_path)])
        elapsed = time.perf_counter() - started
        return {
            "staged_path": str(staged_path),
            "document_id": staged_path.stem,
            "elapsed_seconds": round(elapsed, 2),
        }

    def delete_document(self, document_id: str) -> int:
        """Remove all chunk rows for a document from the LanceDB table."""
        import lancedb

        from backend.storage.lancedb import has_table

        db = lancedb.connect(self._db_path)
        if not has_table(db, self._table_name):
            return 0
        if "'" in document_id:
            raise ValueError("document_id must not contain single quotes")
        table = db.open_table(self._table_name)
        result = table.delete(f"document_id = '{document_id}'")
        deleted = getattr(result, "num_deleted_rows", 0) or 0
        return int(deleted)

    def chunk_count(self, document_id: str | None = None) -> int:
        """Rows in the index table, optionally filtered to one document."""
        import lancedb

        from backend.storage.lancedb import has_table

        db = lancedb.connect(self._db_path)
        if not has_table(db, self._table_name):
            return 0
        table = db.open_table(self._table_name)
        if document_id is None:
            return table.count_rows()
        if "'" in document_id:
            raise ValueError("document_id must not contain single quotes")
        return int(table.count_rows(filter=f"document_id = '{document_id}'"))

    @property
    def embedding_model(self) -> str:
        return self._embedding_model

    @property
    def table_name(self) -> str:
        return self._table_name

    # --- internals ---------------------------------------------------------

    def _pipeline_or_init(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        with self._init_lock:
            if self._pipeline is None:
                self._pipeline = self._build_pipeline()
            return self._pipeline

    def _build_pipeline(self) -> Any:
        if not _VENDOR_ROOT.is_dir():
            raise VendorNotAvailableError(f"vendored localGPT tree not found at {_VENDOR_ROOT}")
        try:
            import docling  # noqa: F401
            import lancedb  # noqa: F401
        except ImportError as exc:
            raise VendorNotAvailableError(
                f"ingestion dependencies missing ({exc}); run `uv sync` in backend/"
            ) from exc

        _ensure_vendor_on_path()
        started = time.perf_counter()
        from rag_system.pipelines.indexing_pipeline import IndexingPipeline
        from rag_system.utils.ollama_client import OllamaClient

        logger.info(
            "initializing localGPT IndexingPipeline (docling=%s, embedder=%s, table=%s)",
            _vendor_version() or "?",
            self._embedding_model,
            self._table_name,
        )
        # MappingProxyType: upstream only reads these dicts, but immutable
        # inputs make that assumption structural rather than conventional.
        # (cast: upstream annotates Dict, we pass read-only mappings.)
        pipeline = IndexingPipeline(
            config=cast(
                "dict[str, Any]",
                MappingProxyType(
                    {
                    "chunker_mode": "docling",
                    "embedding_model_name": self._embedding_model,
                    "chunking": {"chunk_size": self._chunk_size},
                    "overlap_sentences": self._chunk_overlap,
                    "storage": {"db_path": self._db_path, "text_table_name": self._table_name},
                    "retrievers": {"dense": {"enabled": True, "lancedb_table_name": self._table_name}},
                    "contextual_enricher": {"enabled": False},
                    "overview": {"enabled": False},
                    "indexing": {"embedding_batch_size": 32},
                }
                ),
            ),
            ollama_client=OllamaClient(host=self._ollama_host),
            ollama_config=cast(
                "dict[str, str]",
                MappingProxyType(
                    {
                        "host": self._ollama_host,
                        "generation_model": "",
                        "enrichment_model": "",
                    }
                ),
            ),
        )
        logger.info("localGPT IndexingPipeline ready in %.1fs", time.perf_counter() - started)
        return pipeline
