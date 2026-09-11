"""Document contracts.

``routes/documents.py`` builds its responses through :class:`DocumentOut`, so
the wire shape is declared once here instead of being re-typed as a bare dict
in each handler. The frontend's document types are generated from this.

Status lifecycle: ``stored -> indexing -> indexed | failed``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DocumentStatus = Literal["stored", "indexing", "indexed", "failed"]


class DocumentOut(BaseModel):
    """A stored document as returned by the API."""

    model_config = ConfigDict(extra="forbid")

    id: str
    filename: str
    content_type: str | None = None
    size_bytes: int = 0
    status: DocumentStatus | str = "stored"
    metadata: dict = Field(default_factory=dict)
    created_at: str
    updated_at: str


class DocumentListResponse(BaseModel):
    total: int
    documents: list[DocumentOut] = Field(default_factory=list)


class UploadResponse(BaseModel):
    """Result of a multi-file upload. ``rejected`` is explicit: a file that
    could not be accepted is reported, never silently dropped."""

    uploaded: list[DocumentOut] = Field(default_factory=list)
    rejected: list[dict] = Field(default_factory=list)


class ReindexResponse(BaseModel):
    """Outcome of re-running the ingestion pipeline for one document."""

    document_id: str
    status: DocumentStatus | str
    chunks: int | None = None
    pages: int | None = None
    ocr_used: bool | None = None
    duration_ms: float | None = None
    error: str | None = None


__all__ = [
    "DocumentListResponse",
    "DocumentOut",
    "DocumentStatus",
    "ReindexResponse",
    "UploadResponse",
]
