"""Document staging for the localGPT ingestion adapter.

localGPT's ``IndexingPipeline`` derives ``document_id`` from
``os.path.basename(file_path)``. Project 117 identifies documents by UUID, so
the adapter stages a *symlink* named ``<uuid><ext>`` pointing at the real
uploaded file. The symlink is what gets converted/chunked, so every chunk
inherits ``document_id == documents.id`` and citation metadata (page,
heading_path, chunk_index) resolves back to a database row.

Symlinks (not copies) avoid duplicating potentially hundreds of megabytes of
industrial PDFs on every reindex.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class StagingError(RuntimeError):
    """Staging a document into the ingestion workspace failed."""


class DocumentStager:
    """Maintains ``staging_dir / <document_id><ext>`` symlinks for ingestion."""

    def __init__(self, staging_dir: Path) -> None:
        self._staging_dir = staging_dir

    def stage(self, document_id: str, uploads_dir: Path, stored_name: str) -> Path:
        """Create (or refresh) the symlink for a document; returns its path."""
        source = uploads_dir / stored_name
        if not source.exists():
            raise StagingError(f"uploaded file '{stored_name}' is missing from {uploads_dir}")

        self._staging_dir.mkdir(parents=True, exist_ok=True)
        # Original extension is preserved: localGPT's DocumentConverter
        # dispatches on it (PDF/DOCX/HTML/MD/TXT paths).
        link = self._staging_dir / f"{document_id}{source.suffix.lower()}"
        if link.exists() or link.is_symlink():
            link.unlink()
        try:
            link.symlink_to(source.resolve())
        except OSError as exc:
            raise StagingError(f"could not stage document {document_id}: {exc}") from exc
        return link

    def staged_context(self, document_id: str, uploads_dir: Path, stored_name: str):
        """Context manager guaranteeing unstage / tempfile cleanup on normal exit or exception."""
        from contextlib import contextmanager

        @contextmanager
        def _ctx():
            staged = self.stage(document_id, uploads_dir, stored_name)
            try:
                yield staged
            finally:
                self.unstage(document_id, staged.suffix)

        return _ctx()

    def unstage(self, document_id: str, extension: str | None = None) -> None:
        """Remove the staging link(s) for a document (best-effort)."""
        if extension:
            candidates = [self._staging_dir / f"{document_id}{extension.lower()}"]
        else:
            candidates = (
                sorted(self._staging_dir.glob(f"{document_id}.*"))
                if self._staging_dir.exists()
                else []
            )
        for link in candidates:
            try:
                link.unlink(missing_ok=True)
            except OSError as exc:  # pragma: no cover - best effort
                logger.warning("staging cleanup failed for %s: %s", link, exc)

    @staticmethod
    def basename(document_id: str, extension: str) -> str:
        """The basename localGPT will derive as the LanceDB ``document_id``."""
        return f"{document_id}{extension.lower()}"
