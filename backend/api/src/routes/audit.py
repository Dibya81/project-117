"""Audit endpoints.

Fully functional in Phase 1: every sensitive operation (uploads, deletions)
already writes audit events, and these endpoints read them back.

Phase 0.5 added the provenance fields (agent, tool, model, approval) and the
filters an auditor actually asks for — in particular "what is waiting on a
human right now?" (``?approval=pending``).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request

from backend.api.src.deps import get_audit
from backend.api.src.errors import NotFound
from backend.database.models import AuditEvent

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
def list_audit(
    request: Request,
    resource_type: str | None = None,
    resource_id: str | None = None,
    action: str | None = None,
    agent: str | None = None,
    tool: str | None = None,
    approval: str | None = None,
    limit: int = 100,
) -> dict:
    events = get_audit(request).list(
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        agent=agent,
        tool=tool,
        approval=approval,
        limit=min(limit, 500),
    )
    return {"total": len(events), "events": [_out(e) for e in events]}


@router.get("/{event_id}")
def get_audit_event(event_id: str, request: Request) -> dict:
    event = get_audit(request).get(event_id)
    if event is None:
        raise NotFound(f"audit event '{event_id}' does not exist")
    return _out(event)


def _out(event: AuditEvent) -> dict:
    try:
        detail = json.loads(event.detail_json or "{}")
    except ValueError:
        detail = {}
    return {
        "id": event.id,
        "timestamp": event.timestamp.isoformat(),
        "user": event.user,
        "action": event.action,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "outcome": event.outcome,
        "agent": event.agent,
        "tool": event.tool,
        "model": event.model,
        "approval": event.approval,
        "detail": detail,
        "error": event.error,
    }
