"""Knowledge Hub endpoints — /api/knowledge-hub.

Entity and graph data derived from ingested workspace documents.

GET  /api/knowledge-hub/entities          paginated entity list (filter by workspace)
GET  /api/knowledge-hub/entities/{id}     entity detail + relationships + source docs
GET  /api/knowledge-hub/graph             graph nodes/edges for canvas rendering
POST /api/knowledge-hub/rebuild           trigger full graph rebuild for workspace
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from backend.api.src.deps import get_graph_extractor, get_ingestion, get_workspaces
from backend.knowledge.workspace_service import WorkspaceNotFound

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge-hub", tags=["knowledge-hub"])


@router.get("/entities")
def list_entities(
    request: Request,
    workspace_id: str | None = None,
    entity_type: str | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Paginated, filterable list of extracted entities.

    ``workspace_id`` defaults to the ``default`` workspace when omitted so
    a fresh UI load shows something useful without extra query params.
    """
    from sqlalchemy import select
    from backend.api.src.deps import get_session_factory
    from backend.database.models import KnowledgeEntity

    sf = get_session_factory(request)
    # Resolve default workspace
    if not workspace_id:
        ws = get_workspaces(request).get_or_create_default()
        workspace_id = ws["id"]

    with sf() as session:
        q = select(KnowledgeEntity).where(KnowledgeEntity.workspace_id == workspace_id)
        if entity_type:
            q = q.where(KnowledgeEntity.entity_type == entity_type)
        if search:
            q = q.where(KnowledgeEntity.name.ilike(f"%{search}%"))
        total_q = q
        rows = session.execute(q.offset(offset).limit(limit)).scalars().all()
        # Deduplicate by name for listing purposes
        seen: dict[str, dict] = {}
        for r in rows:
            if r.name not in seen:
                seen[r.name] = _entity_out(r)
        entities = list(seen.values())

    return {
        "workspace_id": workspace_id,
        "total": len(entities),
        "limit": limit,
        "offset": offset,
        "entities": entities,
    }


@router.get("/entities/{entity_id}")
def get_entity(entity_id: str, request: Request) -> dict:
    from sqlalchemy import select
    from backend.api.src.deps import get_session_factory
    from backend.database.models import KnowledgeEntity

    sf = get_session_factory(request)
    with sf() as session:
        row = session.get(KnowledgeEntity, entity_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"entity '{entity_id}' not found")
        # All rows for this entity name (get all relationships)
        all_rows = session.execute(
            select(KnowledgeEntity).where(
                KnowledgeEntity.workspace_id == row.workspace_id,
                KnowledgeEntity.name == row.name,
            )
        ).scalars().all()
        relationships = [
            {
                "rel": r.rel_type,
                "target": r.target_name,
                "source_chunk": r.source_chunk,
                "confidence": r.confidence,
                "document_id": r.document_id,
            }
            for r in all_rows
            if r.rel_type
        ]
        source_docs = list({r.document_id for r in all_rows})

    return {
        **_entity_out(row),
        "relationships": relationships,
        "source_document_ids": source_docs,
    }


@router.get("/graph")
def get_graph(
    request: Request,
    workspace_id: str | None = None,
    max_nodes: int = Query(default=300, ge=10, le=2000),
) -> dict:
    """Return a graph structure (nodes + edges) for the knowledge canvas.

    Nodes are deduplicated entities; edges are entity→relationship→entity.
    ``max_nodes`` caps the response so the browser canvas stays responsive.
    """
    from sqlalchemy import select
    from backend.api.src.deps import get_session_factory
    from backend.database.models import KnowledgeEntity, Document

    sf = get_session_factory(request)
    if not workspace_id:
        ws = get_workspaces(request).get_or_create_default()
        workspace_id = ws["id"]

    with sf() as session:
        entity_rows = session.execute(
            select(KnowledgeEntity).where(KnowledgeEntity.workspace_id == workspace_id)
        ).scalars().all()

        # Build document name map
        doc_ids = {r.document_id for r in entity_rows}
        docs = {}
        for doc_id in doc_ids:
            d = session.get(Document, doc_id)
            if d:
                docs[doc_id] = d.filename

    # Build nodes (deduplicated by name)
    node_map: dict[str, dict] = {}
    for r in entity_rows:
        if r.name not in node_map:
            node_map[r.name] = {
                "id": f"entity:{r.name}",
                "label": r.name,
                "type": r.entity_type.lower(),
                "document_ids": [],
                "confidence": r.confidence or 0.0,
            }
        if r.document_id not in node_map[r.name]["document_ids"]:
            node_map[r.name]["document_ids"].append(r.document_id)

    # Cap nodes
    nodes = list(node_map.values())[:max_nodes]
    node_names = {n["label"] for n in nodes}

    # Build edges
    edges: list[dict] = []
    seen_edges: set[tuple] = set()
    for r in entity_rows:
        if r.rel_type and r.target_name and r.name in node_names:
            # Ensure target node exists (add if not capped)
            if r.target_name not in node_names and len(nodes) < max_nodes:
                node_map[r.target_name] = {
                    "id": f"entity:{r.target_name}",
                    "label": r.target_name,
                    "type": "unknown",
                    "document_ids": [r.document_id],
                    "confidence": r.confidence or 0.0,
                }
                nodes.append(node_map[r.target_name])
                node_names.add(r.target_name)
            if r.target_name in node_names:
                key = (r.name, r.rel_type, r.target_name)
                if key not in seen_edges:
                    seen_edges.add(key)
                    edges.append({
                        "id": f"edge:{r.name}:{r.rel_type}:{r.target_name}",
                        "from": f"entity:{r.name}",
                        "to": f"entity:{r.target_name}",
                        "label": r.rel_type,
                    })

    # Add document nodes
    for doc_id, filename in docs.items():
        nodes.append({
            "id": f"document:{doc_id}",
            "label": filename,
            "type": "document",
            "document_ids": [doc_id],
            "confidence": 1.0,
        })
        # mentioned_in edges
        for entity_name, node in node_map.items():
            if doc_id in node.get("document_ids", []):
                key = (entity_name, "mentioned_in", doc_id)
                if key not in seen_edges:
                    seen_edges.add(key)
                    edges.append({
                        "id": f"edge:{entity_name}:mentioned_in:{doc_id}",
                        "from": f"entity:{entity_name}",
                        "to": f"document:{doc_id}",
                        "label": "mentioned_in",
                    })

    return {
        "workspace_id": workspace_id,
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "entities": len(node_map),
            "documents": len(docs),
        },
        "nodes": nodes,
        "edges": edges,
    }


class RebuildRequest(BaseModel):
    workspace_id: str | None = None


@router.post("/rebuild")
async def rebuild_graph(payload: RebuildRequest, request: Request) -> dict:
    """Trigger a full graph rebuild for a workspace.

    Re-runs entity extraction for every indexed document.  This is an
    async background task — the endpoint returns immediately and the client
    polls /api/workspaces/{id}/health for the updated entity counts.
    """
    svc = get_workspaces(request)
    if payload.workspace_id:
        try:
            ws = svc.get(payload.workspace_id)
        except WorkspaceNotFound:
            raise HTTPException(status_code=404, detail="workspace not found")
        workspace_id = ws["id"]
    else:
        ws = svc.get_or_create_default()
        workspace_id = ws["id"]

    extractor = get_graph_extractor(request)
    ingestion = get_ingestion(request)

    async def _rebuild() -> None:
        from sqlalchemy import select
        from backend.api.src.deps import get_session_factory
        from backend.database.models import Document
        import json as _json

        sf = get_session_factory(request)
        # Purge existing entities first
        extractor.purge_workspace(workspace_id)

        with sf() as session:
            docs = session.execute(
                select(Document).where(Document.status == "indexed")
            ).scalars().all()
            # Filter by workspace
            ws_docs = [
                d for d in docs
                if _json.loads(d.metadata_json or "{}").get("workspace_id") == workspace_id
            ]

        for doc in ws_docs:
            try:
                chunks = ingestion.chunks(doc.id, limit=200)
                extractor.extract_and_store(
                    document_id=doc.id,
                    workspace_id=workspace_id,
                    filename=doc.filename,
                    chunks=chunks,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("rebuild: extraction failed for %s: %s", doc.id, exc)

        svc.bump_version(workspace_id)
        logger.info("graph rebuild complete for workspace %s", workspace_id)

    asyncio.create_task(_rebuild())
    return {"status": "rebuilding", "workspace_id": workspace_id}


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _entity_out(row: Any) -> dict:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "document_id": row.document_id,
        "entity_type": row.entity_type,
        "name": row.name,
        "confidence": row.confidence,
        "created_at": row.created_at.isoformat(),
    }
