"""Workspace service — CRUD + health statistics.

A workspace is the top-level container for a company's knowledge base.
All documents, vector-index chunks, and graph entities belong to exactly
one workspace (identified by ``workspace_id`` stored in document metadata).

This service owns workspace lifecycle and the ``/health`` computation.
It never touches the vector index or OCR pipeline directly — those are
``IngestionService``'s responsibility.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from backend.database.models import Document, KnowledgeEntity, Workspace

logger = logging.getLogger(__name__)

DEFAULT_WORKSPACE_NAME = "default"
DEFAULT_WORKSPACE_DESC = "Default knowledge workspace"


class WorkspaceNotFound(LookupError):
    pass


class WorkspaceService:
    def __init__(self, *, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def get_or_create_default(self) -> dict[str, Any]:
        """Return the default workspace, creating it if it does not exist."""
        with self._sf() as session:
            row = session.execute(
                select(Workspace).where(Workspace.name == DEFAULT_WORKSPACE_NAME)
            ).scalar_one_or_none()
            if row is None:
                row = Workspace(
                    name=DEFAULT_WORKSPACE_NAME,
                    description=DEFAULT_WORKSPACE_DESC,
                )
                session.add(row)
                session.commit()
                session.refresh(row)
            return _ws_out(row)

    def list(self) -> list[dict[str, Any]]:
        with self._sf() as session:
            rows = session.execute(
                select(Workspace).order_by(Workspace.created_at)
            ).scalars().all()
            return [_ws_out(r) for r in rows]

    def create(self, *, name: str, description: str | None = None) -> dict[str, Any]:
        with self._sf() as session:
            row = Workspace(name=name, description=description)
            session.add(row)
            session.commit()
            session.refresh(row)
            return _ws_out(row)

    def get(self, workspace_id: str) -> dict[str, Any]:
        with self._sf() as session:
            row = session.get(Workspace, workspace_id)
            if row is None:
                raise WorkspaceNotFound(workspace_id)
            return _ws_out(row)

    def delete(self, workspace_id: str) -> None:
        with self._sf() as session:
            row = session.get(Workspace, workspace_id)
            if row is None:
                raise WorkspaceNotFound(workspace_id)
            session.delete(row)
            session.commit()

    def bump_version(self, workspace_id: str) -> int:
        """Increment knowledge_version and return the new value."""
        with self._sf() as session:
            row = session.get(Workspace, workspace_id)
            if row is None:
                raise WorkspaceNotFound(workspace_id)
            row.knowledge_version += 1
            row.updated_at = datetime.now(timezone.utc)
            session.commit()
            return row.knowledge_version

    # ------------------------------------------------------------------
    # Health statistics
    # ------------------------------------------------------------------

    def health(self, workspace_id: str) -> dict[str, Any]:
        """Compute knowledge-base health statistics for one workspace.

        All counts come from the database in two queries.  Vector-index
        chunk counts are sourced from ``metadata_json["ingestion"]["chunk_count"]``
        so we never hit LanceDB at read time.
        """
        self.get(workspace_id)  # raises WorkspaceNotFound if missing

        with self._sf() as session:
            # ---- document counts ----------------------------------------
            docs = session.execute(
                select(Document)
            ).scalars().all()

            # Filter by workspace_id stored in metadata
            ws_docs = [d for d in docs if _doc_workspace(d) == workspace_id]

            total = len(ws_docs)
            indexed = sum(1 for d in ws_docs if d.status == "indexed")
            failed = sum(1 for d in ws_docs if d.status == "failed")
            processing = sum(
                1 for d in ws_docs if d.status in ("stored", "indexing")
            )
            # Sum chunk_count from each document's ingestion metadata
            chunks = sum(
                _doc_chunk_count(d) for d in ws_docs if d.status == "indexed"
            )
            last_updated = max(
                (d.updated_at for d in ws_docs), default=None
            )

            # ---- entity / relationship counts ---------------------------
            entity_rows = session.execute(
                select(KnowledgeEntity).where(
                    KnowledgeEntity.workspace_id == workspace_id
                )
            ).scalars().all()
            entities = len({r.name for r in entity_rows})
            relationships = sum(1 for r in entity_rows if r.rel_type is not None)

            # ---- workspace version --------------------------------------
            ws_row = session.get(Workspace, workspace_id)
            version = ws_row.knowledge_version if ws_row else 0

        # ---- overall status ----------------------------------------
        if processing > 0:
            status = "UPDATING"
        elif failed > 0 and indexed == 0:
            status = "FAILED"
        elif failed > 0:
            status = "DEGRADED"
        elif total == 0:
            status = "EMPTY"
        else:
            status = "READY"

        return {
            "workspace_id": workspace_id,
            "documents": total,
            "indexed": indexed,
            "processing": processing,
            "failed": failed,
            "chunks": chunks,
            "entities": entities,
            "relationships": relationships,
            "last_updated": last_updated.isoformat() if last_updated else None,
            "status": status,
            "knowledge_version": f"v{version}",
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ws_out(row: Workspace) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "knowledge_version": f"v{row.knowledge_version}",
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _doc_workspace(doc: Document) -> str | None:
    try:
        meta = json.loads(doc.metadata_json or "{}")
    except ValueError:
        return None
    return meta.get("workspace_id")


def _doc_chunk_count(doc: Document) -> int:
    try:
        meta = json.loads(doc.metadata_json or "{}")
    except ValueError:
        return 0
    ingestion = meta.get("ingestion", {})
    if isinstance(ingestion, dict):
        return ingestion.get("chunk_count", 0) or 0
    return 0


def compute_checksum(data: bytes) -> str:
    """SHA-256 hex digest of raw file bytes."""
    return hashlib.sha256(data).hexdigest()
