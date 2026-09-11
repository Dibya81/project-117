"""Document storage.

Phase 1 responsibility: validate an upload, persist the bytes to the uploads
directory, and register its metadata in the database. Indexing (parse → OCR →
chunk → embed → vector index) is Phase 3.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.database.models import Document
from backend.security.audit import AuditService


class DocumentValidationError(ValueError):
    """Raised for rejected uploads; carries an HTTP status code."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class DocumentNotFoundError(LookupError):
    pass


class DocumentStorage:
    def __init__(
        self,
        session_factory: sessionmaker,
        uploads_dir: Path,
        allowed_extensions: set[str],
        max_upload_bytes: int,
        audit: AuditService,
    ) -> None:
        self._session_factory = session_factory
        self._uploads_dir = uploads_dir
        self._allowed_extensions = allowed_extensions
        self._max_upload_bytes = max_upload_bytes
        self._audit = audit

    # --- public API ------------------------------------------------------

    def save_upload(
        self,
        *,
        filename: str,
        content_type: str | None,
        file_obj: BinaryIO,
        user: str | None = None,
    ) -> Document:
        extension = self._validate(filename)
        stored_name = f"{uuid.uuid4().hex}{extension}"
        size = self._stream_to_disk(file_obj, stored_name)
        document = Document(
            filename=filename,
            stored_name=stored_name,
            content_type=content_type,
            size_bytes=size,
            status="stored",
        )
        with self._session_factory() as session:
            session.add(document)
            session.commit()
            session.refresh(document)
        self._audit.record(
            action="document.uploaded",
            resource_type="document",
            resource_id=document.id,
            user=user,
            detail={"filename": filename, "size_bytes": size, "stored_name": stored_name},
        )
        return document

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Document]:
        with self._session_factory() as session:
            stmt = select(Document).order_by(Document.created_at.desc()).limit(limit).offset(offset)
            return list(session.scalars(stmt))

    def get(self, document_id: str) -> Document:
        with self._session_factory() as session:
            document = session.get(Document, document_id)
        if document is None:
            raise DocumentNotFoundError(document_id)
        return document

    def delete(self, document_id: str, *, user: str | None = None) -> Document:
        document = self.get(document_id)
        file_path = self._uploads_dir / document.stored_name
        if file_path.exists():
            file_path.unlink()
        with self._session_factory() as session:
            session.delete(session.get(Document, document_id))
            session.commit()
        self._audit.record(
            action="document.deleted",
            resource_type="document",
            resource_id=document_id,
            user=user,
            detail={"filename": document.filename},
        )
        return document

    # --- internals -------------------------------------------------------

    def _validate(self, filename: str) -> str:
        if not filename or Path(filename).suffix.lower() not in self._allowed_extensions:
            raise DocumentValidationError(
                f"Unsupported file type for '{filename or '<none>'}'. "
                f"Allowed: {', '.join(sorted(self._allowed_extensions))}",
                status_code=415,
            )
        return Path(filename).suffix.lower()

    def _stream_to_disk(self, file_obj: BinaryIO, stored_name: str) -> int:
        """Stream to disk in chunks, enforcing the size cap mid-stream."""
        self._uploads_dir.mkdir(parents=True, exist_ok=True)
        target = self._uploads_dir / stored_name
        size = 0
        with target.open("wb") as out:
            while True:
                chunk = file_obj.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > self._max_upload_bytes:
                    target.unlink(missing_ok=True)
                    raise DocumentValidationError(
                        f"Upload exceeds the {self._max_upload_bytes}-byte limit",
                        status_code=413,
                    )
                out.write(chunk)
        return size