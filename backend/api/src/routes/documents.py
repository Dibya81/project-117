"""Document endpoints.

Phase 1: upload / list / get / delete (file storage + metadata + audit).
Phase 3: ``POST /{id}/reindex`` runs the localGPT ingestion pipeline
(parse → OCR → chunk → embed → LanceDB) and purge-on-delete removes vectors.

Response shape (``_out``) includes the ``ingestion`` metadata block from
Phase 3 on; ``status`` is ``stored → indexing → indexed | failed``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback

from fastapi import APIRouter, File, Request, UploadFile

from backend.api.src.deps import get_documents, get_ingestion
from backend.api.src.errors import BadRequest, NotFound
from backend.api.src.schemas.document import DocumentOut
from backend.database.models import Document
from backend.ingestion.service import IngestionError
from backend.storage.documents import DocumentNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload", status_code=201)
async def upload_documents(request: Request, files: list[UploadFile] = File(...)) -> dict:
    documents = get_documents(request)
    saved: list[Document] = []
    for file in files:
        document = documents.save_upload(
            filename=file.filename or "unnamed",
            content_type=file.content_type,
            file_obj=file.file,
        )
        saved.append(document)
    return {"uploaded": len(saved), "documents": [_out(d) for d in saved]}


@router.get("")
def list_documents(request: Request) -> dict:
    documents = get_documents(request)
    rows = documents.list()
    return {"total": len(rows), "documents": [_out(d) for d in rows]}


@router.get("/{document_id}")
def get_document(document_id: str, request: Request) -> dict:
    try:
        document = get_documents(request).get(document_id)
    except DocumentNotFoundError:
        raise NotFound(f"document '{document_id}' does not exist") from None
    return _out(document)


@router.delete("/{document_id}")
def delete_document(document_id: str, request: Request) -> dict:
    documents = get_documents(request)
    try:
        document = documents.get(document_id)
    except DocumentNotFoundError:
        raise NotFound(f"document '{document_id}' does not exist") from None
    # Purge vectors first (best-effort: the row must be deletable even if the
    # index is gone or the document was never indexed).
    try:
        get_ingestion(request).purge(document_id)
    except Exception:  # noqa: BLE001 - purge must never block deletion
        logger.warning(
            "vector purge failed for %s; deleting row anyway", document_id, exc_info=True
        )
    documents.delete(document_id)
    return {"deleted": True, "id": document.id, "filename": document.filename}


@router.get("/{document_id}/chunks")
def document_chunks(document_id: str, request: Request, limit: int = 200) -> dict:
    """The parsed text of a document, in reading order.

    After parsing, the vector table is the only place this text exists — the
    upload is staged and the source is not re-parsed on read. Any surface that
    shows what a document says must read it from here; the alternative is a
    hand-written copy that drifts from the corpus.
    """
    documents = get_documents(request)
    try:
        document = documents.get(document_id)
    except DocumentNotFoundError:
        raise NotFound(f"document '{document_id}' does not exist") from None

    ingestion = get_ingestion(request)
    chunks = ingestion.chunks(document_id, limit=max(1, min(limit, 1000)))
    return {
        "documentId": document.id,
        "filename": document.filename,
        "chunkCount": len(chunks),
        "chunks": chunks,
    }


@router.post("/{document_id}/reindex")
async def reindex_document(document_id: str, request: Request) -> dict:
    """Index or re-index a stored document through the localGPT pipeline.

    Runs in a worker thread (docling OCR on a large PDF can take minutes);
    the document row moves to ``indexing`` immediately, then ``indexed`` or
    ``failed`` when the pipeline completes.
    """
    documents = get_documents(request)
    try:
        documents.get(document_id)
    except DocumentNotFoundError:
        raise NotFound(f"document '{document_id}' does not exist") from None

    ingestion = get_ingestion(request)
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, ingestion.reindex, document_id)
    except IngestionError:
        # Typed failures (unsupported type, pipeline error) are mapped to
        # structured 415/422 responses by the app-level handler.
        raise
    except LookupError:
        raise NotFound(f"document '{document_id}' does not exist") from None
    except Exception as exc:  # noqa: BLE001 - converted to structured 4xx
        logger.error("reindex failed for %s: %s", document_id, traceback.format_exc())
        raise BadRequest(f"indexing failed: {exc}") from exc
    return result


def _out(document: Document) -> dict:
    """Serialise through the declared contract so the wire shape cannot drift
    from ``schemas/document.py`` (and so from the generated frontend types)."""
    metadata: dict = {}
    try:
        metadata = json.loads(document.metadata_json or "{}")
    except ValueError:
        pass
    return DocumentOut(
        id=document.id,
        filename=document.filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes or 0,
        status=document.status,
        metadata=metadata,
        created_at=document.created_at.isoformat(),
        updated_at=document.updated_at.isoformat(),
    ).model_dump()
