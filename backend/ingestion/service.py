"""Ingestion service.

Orchestrates one document's journey from ``stored`` to ``indexed``:

    validate → stage (symlink) → localGPT pipeline (parse → OCR → chunk →
    embed → LanceDB) → update document status/metadata → audit

Design rules:
- One implementation per responsibility: this service owns *orchestration and
  state*, the adapter owns *vendor plumbing*, localGPT owns *the pipeline*.
- Failures are loud and typed; a failed index never leaves silent partial
  state — the document row flips to ``failed`` with the reason in metadata.
- Audit events carry ids/durations/counts, never raw document content.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from sqlalchemy.orm import sessionmaker

from backend.database.models import Document
from backend.ingestion.adapter import LocalGPTIndexer
from backend.ingestion.staging import DocumentStager
from backend.security.audit import AuditService

logger = logging.getLogger(__name__)


class IngestionError(RuntimeError):
    """A document could not be indexed; message is safe to expose via API."""

    def __init__(self, message: str, *, reason: str = "ingestion_failed") -> None:
        super().__init__(message)
        self.reason = reason


class UnsupportedForIngestion(IngestionError):
    def __init__(self, extension: str) -> None:
        super().__init__(
            f"'{extension or '<none>'}' files are stored but not ingestible",
            reason="unsupported_for_ingestion",
        )


class IngestionService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker,
        stager: DocumentStager,
        indexer: LocalGPTIndexer,
        audit: AuditService,
        ingestible_extensions: set[str],
        uploads_dir: Any,
    ) -> None:
        self._session_factory = session_factory
        self._stager = stager
        self._indexer = indexer
        self._audit = audit
        self._ingestible_extensions = {e.lower() for e in ingestible_extensions}
        self._uploads_dir = uploads_dir

    # --- public API -------------------------------------------------------

    def reindex(self, document_id: str, *, user: str | None = None) -> dict[str, Any]:
        """Index (or re-index) one stored document. Synchronous and blocking.

        The API layer runs this behind a worker thread so the event loop is
        never blocked by a 10-minute OCR run.
        """
        started = time.perf_counter()
        document = self._get(document_id)
        extension = _extension_of(document.filename)

        if extension not in self._ingestible_extensions:
            self._fail(document, UnsupportedForIngestion(extension), elapsed=0.0, user=user)
            raise UnsupportedForIngestion(extension)

        self._set_status(document, "indexing")
        try:
            staged = self._stager.stage(document.id, self._uploads_dir, document.stored_name)
            self._indexer.index_file(staged)
            # localGPT derives the LanceDB document_id from the *basename*
            # (extension included), so counting/purging must use the staged
            # name, not the bare UUID.
            index_document_id = staged.name
            chunk_count = self._indexer.chunk_count(index_document_id)
        except Exception as exc:  # noqa: BLE001
            # localGPT raises bare RuntimeError/KeyError for conversion
            # failures; everything becomes a typed IngestionError here.
            error = exc if isinstance(exc, IngestionError) else IngestionError(str(exc))
            self._fail(document, error, elapsed=time.perf_counter() - started, user=user)
            raise error from exc

        elapsed = time.perf_counter() - started
        metadata = _document_metadata(
            document,
            indexed=True,
            extra={
                "embedding_model": self._indexer.embedding_model,
                "chunk_count": chunk_count,
                "index_table": self._indexer.table_name,
                "index_document_id": index_document_id,
                "last_index_seconds": round(elapsed, 2),
                "last_index_error": None,
            },
        )
        self._update(document, status="indexed", metadata=metadata)
        self._audit.record(
            action="document.indexed",
            resource_type="document",
            resource_id=document.id,
            user=user,
            detail={
                "chunk_count": chunk_count,
                "elapsed_seconds": round(elapsed, 2),
                "embedding_model": self._indexer.embedding_model,
            },
        )
        return {
            "document_id": document.id,
            "status": "indexed",
            "chunk_count": chunk_count,
            "elapsed_seconds": round(elapsed, 2),
        }

    def purge(self, document_id: str, *, user: str | None = None) -> int:
        """Remove a document's vectors (used by DELETE /api/documents/{id})."""
        # Rows are keyed by the staged basename (<uuid><ext>); resolve the
        # extension from the document row, falling back to the bare id for
        # robustness against documents indexed before this convention.
        document = self._find(document_id)
        targets = [f"{document_id}{_extension_of(document.filename)}"] if document else []
        targets.append(document_id)
        deleted = 0
        for target in dict.fromkeys(targets):
            deleted += self._indexer.delete_document(target)
        if deleted:
            self._audit.record(
                action="document.index_purged",
                resource_type="document",
                resource_id=document_id,
                user=user,
                detail={"vectors_removed": deleted},
            )
        self._stager.unstage(document_id)
        return deleted

    # --- internals ---------------------------------------------------------

    def _get(self, document_id: str) -> Document:
        with self._session_factory() as session:
            document = session.get(Document, document_id)
            if document is None:
                raise LookupError(document_id)
            session.expunge(document)
            return document

    def _find(self, document_id: str) -> Document | None:
        try:
            return self._get(document_id)
        except LookupError:
            return None

    def _set_status(self, document: Document, status: str) -> None:
        self._update(document, status=status)

    def _update(self, document: Document, *, status: str, metadata: dict | None = None) -> None:
        with self._session_factory() as session:
            row = session.get(Document, document.id)
            if row is None:  # deleted mid-flight
                return
            row.status = status
            if metadata is not None:
                row.metadata_json = json.dumps(metadata)
            session.commit()

    def _fail(self, document: Document, error: Exception, *, elapsed: float, user: str | None) -> None:
        metadata = _document_metadata(
            document,
            indexed=False,
            extra={"last_index_error": str(error)[:500], "last_index_seconds": round(elapsed, 2)},
        )
        self._update(document, status="failed", metadata=metadata)
        self._audit.record(
            action="document.index_failed",
            resource_type="document",
            resource_id=document.id,
            user=user,
            outcome="failure",
            error=str(error)[:500],
            detail={"elapsed_seconds": round(elapsed, 2)},
        )


def _extension_of(filename: str) -> str:
    from pathlib import Path

    return Path(filename or "").suffix.lower()


def _document_metadata(document: Document, *, indexed: bool, extra: dict[str, Any]) -> dict[str, Any]:
    try:
        metadata: dict[str, Any] = json.loads(document.metadata_json or "{}")
    except ValueError:
        metadata = {}
    metadata["ingestion"] = {"indexed": indexed, **extra}
    return metadata
