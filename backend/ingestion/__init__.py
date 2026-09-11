"""Document ingestion (Phase 3).

Components:
- ``staging.DocumentStager`` — UUID-named symlinks bridging our document ids
  to localGPT's basename-derived ``document_id``.
- ``adapter.LocalGPTIndexer`` — embedder over the vendored localGPT
  ``IndexingPipeline`` (docling parse → OCR → chunk → embed → LanceDB+FTS).
- ``service.IngestionService`` — orchestration and document state.

localGPT owns the pipeline; nothing here re-implements parsing, chunking or
vector storage.
"""

from backend.ingestion.adapter import LocalGPTIndexer, VendorNotAvailableError
from backend.ingestion.service import (
    IngestionError,
    IngestionService,
    UnsupportedForIngestion,
)
from backend.ingestion.staging import DocumentStager, StagingError

__all__ = [
    "DocumentStager",
    "IngestionError",
    "IngestionService",
    "LocalGPTIndexer",
    "StagingError",
    "UnsupportedForIngestion",
    "VendorNotAvailableError",
]
