"""Knowledge endpoints (``/api/v1/knowledge/sop``).

There is no separate SOP table in this backend. There *is* a real, indexed SOP
in the document corpus (``data/corpus/refinery/SOP_Pump_Startup_Shutdown.docx``)
and an ingestion pipeline that can return its parsed text, so the SOP surface is
backed by that rather than by invented records: the list is exactly the stored
documents whose filename identifies them as an SOP, and each entry's content is
the real parsed text.

Fields the source document genuinely carries (document number, revision,
effective date) are parsed from its text. Fields it does not carry
(``equipment_types``, ``tags``) are returned as ``null`` instead of guessed. If
no SOP document has been uploaded, the list is honestly empty and a by-id
lookup is a 404 — not a fabricated procedure.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends

from backend.api.src.deps import get_documents, get_ingestion
from backend.api.src.errors import NotFound
from backend.api.src.routes.mobile._common import get_mobile_principal, require_mobile_permission
from backend.ingestion.service import IngestionService
from backend.security.mobile_roles import SOP_VIEW
from backend.security.rbac import Principal
from backend.storage.documents import DocumentStorage

logger = logging.getLogger(__name__)

router = APIRouter()

#: The document number is the SOP's real identifier ("SOP-CDU-PUMP-01"); the
#: stored document UUID is the fallback when a file carries none.
_DOC_NUMBER = re.compile(r"Document\s*No\.?\s*:\s*([A-Za-z0-9._/-]+)", re.IGNORECASE)
_REVISION = re.compile(r"Revision\s*:\s*([^\s|]+)", re.IGNORECASE)
_EFFECTIVE = re.compile(r"Effective\s+Date\s*:\s*([0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4})", re.IGNORECASE)

#: Bounds so one enormous upload cannot make a list response unbounded.
MAX_CONTENT_CHARS = 200_000
MAX_SUMMARY_CHARS = 400
MAX_TITLE_CHARS = 200


def _is_sop_document(filename: str) -> bool:
    """A stored document is an SOP when its filename says so.

    Matching on the name rather than the content keeps the classification
    auditable: an operator can see exactly which files the SOP library will
    serve. It is deliberately the *only* filter — a document whose name does
    not identify it as a procedure is not silently presented as one.
    """
    return "SOP" in str(filename or "").upper()


def _document_text(ingestion: IngestionService, document_id: str) -> str:
    """The real parsed text of a document, in reading order.

    An index that cannot be read yields empty text rather than an error: the
    document is real and its metadata is still worth serving, and an unreadable
    index must not take down the whole SOP library.
    """
    try:
        chunks = ingestion.chunks(document_id, limit=1000)
    except Exception as exc:  # noqa: BLE001 - any index fault degrades to metadata
        logger.warning("SOP chunks unavailable for %s: %s", document_id, exc)
        return ""
    ordered = sorted(
        (chunk for chunk in chunks if isinstance(chunk, dict)),
        key=lambda chunk: int(chunk.get("chunk_index") or 0),
    )
    return "\n\n".join(str(chunk.get("text") or "") for chunk in ordered).strip()


def _first_group(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _effective_date(text: str) -> str | None:
    raw = _first_group(_EFFECTIVE, text)
    if not raw:
        return None
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _sop_payload(document: Any, ingestion: IngestionService) -> dict[str, Any]:
    """Build the frozen ``SopDto`` from one real document."""
    text = _document_text(ingestion, document.id)
    document_number = _first_group(_DOC_NUMBER, text)
    revision = _first_group(_REVISION, text)
    # The title line sits between the document heading and the "Document No"
    # field; everything before that marker is the real heading.
    title = text.split("Document No")[0].strip() if text else ""
    if not title:
        title = str(document.filename).rsplit(".", 1)[0].replace("_", " ")
    effective = _effective_date(text)
    return {
        "id": document_number or document.id,
        "title": title[:MAX_TITLE_CHARS],
        "category": (
            "Standard Operating Procedure"
            if text.lower().startswith("standard operating procedure")
            else "SOP"
        ),
        "version": revision or "",
        "summary": text[:MAX_SUMMARY_CHARS],
        "content": text[:MAX_CONTENT_CHARS],
        # Not present in the source: reported as null rather than guessed.
        "equipment_types": None,
        "tags": None,
        "last_updated": effective
        or (document.updated_at.date().isoformat() if document.updated_at else ""),
    }


def _sop_documents(documents: DocumentStorage) -> list[Any]:
    return [document for document in documents.list(limit=500) if _is_sop_document(document.filename)]


@router.get("/knowledge/sop")
def list_sops(
    principal: Principal = Depends(get_mobile_principal),
    documents: DocumentStorage = Depends(get_documents),
    ingestion: IngestionService = Depends(get_ingestion),
) -> dict:
    require_mobile_permission(principal, SOP_VIEW)
    return {"items": [_sop_payload(document, ingestion) for document in _sop_documents(documents)]}


@router.get("/knowledge/sop/{sop_id}")
def get_sop(
    sop_id: str,
    principal: Principal = Depends(get_mobile_principal),
    documents: DocumentStorage = Depends(get_documents),
    ingestion: IngestionService = Depends(get_ingestion),
) -> dict:
    require_mobile_permission(principal, SOP_VIEW)
    for document in _sop_documents(documents):
        payload = _sop_payload(document, ingestion)
        if str(payload["id"]).lower() == sop_id.lower() or document.id.lower() == sop_id.lower():
            return payload
    raise NotFound(f"SOP {sop_id} not found")


__all__ = ["router"]
