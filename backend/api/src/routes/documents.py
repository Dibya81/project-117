"""Document endpoints.

Phase 1: upload / list / get / delete (file storage + metadata + audit).
Phase 3: ``POST /{id}/reindex`` runs the localGPT ingestion pipeline
(parse → OCR → chunk → embed → LanceDB) and purge-on-delete removes vectors.
Phase KW: workspace_id support on upload/list; SSE progress stream on
``GET /{id}/progress``; graph extraction triggered after reindex.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import traceback
from typing import AsyncIterator

from fastapi import APIRouter, File, Query, Request, UploadFile
from fastapi.responses import StreamingResponse

from backend.api.src.deps import get_documents, get_graph_extractor, get_ingestion, get_workspaces
from backend.api.src.errors import BadRequest, NotFound
from backend.api.src.schemas.document import DocumentOut
from backend.database.models import Document
from backend.ingestion.service import IngestionError
from backend.storage.documents import DocumentNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload", status_code=201)
def upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),
    workspace_id: str | None = Query(default=None),
) -> dict:
    """Accept one or more uploaded files and store them.

    Declared as plain ``def`` (not ``async def``) so FastAPI offloads it to a
    worker thread automatically, matching the other handlers in this file.
    The body calls ``documents.save_upload`` which does synchronous disk I/O and
    a SQLAlchemy commit — those must NOT run on the async event loop.

    Phase KW: stores ``workspace_id`` and ``checksum`` in metadata_json so
    the knowledge workspace can filter its own documents.
    """
    documents = get_documents(request)
    ws_svc = get_workspaces(request)
    # Resolve workspace: use provided id, or default.
    if not workspace_id:
        workspace_id = ws_svc.get_or_create_default()["id"]

    saved: list[Document] = []
    for file in files:
        # Read bytes to compute checksum before handing to save_upload.
        raw = file.file.read()
        checksum = hashlib.sha256(raw).hexdigest()
        # Reset the stream so the storage layer reads from the beginning.
        import io
        file.file = io.BytesIO(raw)

        document = documents.save_upload(
            filename=file.filename or "unnamed",
            content_type=file.content_type,
            file_obj=file.file,
        )
        # Write workspace_id + checksum into metadata_json
        _set_doc_metadata(request, document.id, {"workspace_id": workspace_id, "checksum": checksum})
        saved.append(document)
    return {"uploaded": len(saved), "documents": [_out(d) for d in saved]}


@router.get("")
def list_documents(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    workspace_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict:
    """List documents, optionally filtered by workspace and/or status."""
    clamped_limit = max(1, min(limit, 500))
    clamped_offset = max(0, offset)
    documents = get_documents(request)
    total = documents.count()
    rows = documents.list(limit=clamped_limit, offset=clamped_offset)

    # Phase KW: filter by workspace_id stored in metadata
    if workspace_id or status:
        all_rows = documents.list(limit=10000, offset=0)
        if workspace_id:
            all_rows = [
                r for r in all_rows
                if json.loads(r.metadata_json or "{}").get("workspace_id") == workspace_id
            ]
        if status:
            all_rows = [r for r in all_rows if r.status == status]
        total = len(all_rows)
        rows = all_rows[clamped_offset : clamped_offset + clamped_limit]

    return {
        "total": total,
        "limit": clamped_limit,
        "offset": clamped_offset,
        "documents": [_out(d) for d in rows],
    }


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
def document_chunks(
    document_id: str,
    request: Request,
    limit: int = 200,
    offset: int = 0,
) -> dict:
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

    clamped_limit = max(1, min(limit, 1000))
    clamped_offset = max(0, offset)
    ingestion = get_ingestion(request)
    chunks = ingestion.chunks(document_id, limit=clamped_limit, offset=clamped_offset)
    return {
        "documentId": document.id,
        "filename": document.filename,
        "chunkCount": len(chunks),
        "limit": clamped_limit,
        "offset": clamped_offset,
        "chunks": chunks,
    }


@router.post("/{document_id}/reindex")
async def reindex_document(document_id: str, request: Request) -> dict:
    """Index or re-index a stored document through the localGPT pipeline.

    Runs in a worker thread (docling OCR on a large PDF can take minutes);
    the document row moves to ``indexing`` immediately, then ``indexed`` or
    ``failed`` when the pipeline completes.

    Phase KW: after successful indexing, triggers graph entity extraction
    in a background asyncio task so the endpoint returns quickly.
    """
    documents = get_documents(request)
    try:
        doc = documents.get(document_id)
    except DocumentNotFoundError:
        raise NotFound(f"document '{document_id}' does not exist") from None

    ingestion = get_ingestion(request)
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, ingestion.reindex, document_id)
    except IngestionError:
        raise
    except LookupError:
        raise NotFound(f"document '{document_id}' does not exist") from None
    except Exception as exc:  # noqa: BLE001 - converted to structured 4xx
        logger.error("reindex failed for %s: %s", document_id, traceback.format_exc())
        raise BadRequest(f"indexing failed: {exc}") from exc

    # Phase KW: fire-and-forget graph extraction after successful indexing.
    async def _extract() -> None:
        try:
            meta = json.loads(doc.metadata_json or "{}")
            ws_id = meta.get("workspace_id")
            if not ws_id:
                ws_id = get_workspaces(request).get_or_create_default()["id"]
            chunks = await loop.run_in_executor(
                None, lambda: ingestion.chunks(document_id, limit=200)
            )
            extractor = get_graph_extractor(request)
            await loop.run_in_executor(
                None,
                lambda: extractor.extract_and_store(
                    document_id=document_id,
                    workspace_id=ws_id,
                    filename=doc.filename,
                    chunks=chunks,
                ),
            )
            # Bump workspace version after extraction
            get_workspaces(request).bump_version(ws_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("graph extraction failed for %s: %s", document_id, exc)

    asyncio.create_task(_extract())
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


@router.get("/{document_id}/progress")
async def document_progress(document_id: str, request: Request) -> StreamingResponse:
    """Server-Sent Events stream of ingestion progress for one document.

    Polls ``metadata_json["ingestion"]["stage"]`` every 800 ms and emits a
    ``data:`` event on each change.  The stream closes when the document
    reaches ``indexed``, ``failed``, or after 15 minutes.
    """
    documents = get_documents(request)
    try:
        documents.get(document_id)
    except DocumentNotFoundError:
        raise NotFound(f"document '{document_id}' does not exist") from None

    async def _stream() -> AsyncIterator[str]:
        last_stage: str | None = None
        deadline = asyncio.get_event_loop().time() + 900  # 15 minutes
        while asyncio.get_event_loop().time() < deadline:
            try:
                doc = documents.get(document_id)
            except DocumentNotFoundError:
                break
            try:
                meta = json.loads(doc.metadata_json or "{}")
            except ValueError:
                meta = {}

            ingestion_meta = meta.get("ingestion") or {}
            stage = ingestion_meta.get("stage") or doc.status
            pct = ingestion_meta.get("stage_pct", _STATUS_PCT.get(doc.status, 0))
            message = ingestion_meta.get("stage_message") or _STATUS_LABEL.get(doc.status, "")

            if stage != last_stage:
                payload = json.dumps({
                    "stage": stage.upper(),
                    "pct": pct,
                    "message": message,
                    "status": doc.status,
                    "document_id": document_id,
                })
                yield f"data: {payload}\n\n"
                last_stage = stage

            if doc.status in ("indexed", "failed"):
                # Emit a final completion event
                final = json.dumps({"stage": doc.status.upper(), "pct": 100, "done": True})
                yield f"data: {final}\n\n"
                break

            await asyncio.sleep(0.8)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STATUS_PCT: dict[str, int] = {
    "stored": 5,
    "indexing": 40,
    "indexed": 100,
    "failed": 0,
}

_STATUS_LABEL: dict[str, str] = {
    "stored": "Queued for processing…",
    "indexing": "Running ingestion pipeline…",
    "indexed": "Ready",
    "failed": "Failed",
}


def _set_doc_metadata(request: Request, document_id: str, extra: dict) -> None:
    """Merge *extra* into the document's metadata_json without losing existing keys."""
    from backend.api.src.deps import get_session_factory
    from backend.database.models import Document as DocModel
    sf = get_session_factory(request)
    with sf() as session:
        row = session.get(DocModel, document_id)
        if row is None:
            return
        try:
            meta = json.loads(row.metadata_json or "{}")
        except ValueError:
            meta = {}
        meta.update(extra)
        row.metadata_json = json.dumps(meta)
        session.commit()
