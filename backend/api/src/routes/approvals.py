"""Approval endpoints (human decision surface).

Two kinds of approval exist in this system and they are deliberately kept
separate:

* **job approvals** — the orchestrator parking a risky plan step until a human
  signs off. Those live in ``/api/jobs/{id}/approve`` and are backed by the
  job state machine.
* **operational approvals** — outage windows, priority escalations, artifact
  releases. Those are served here from the local operations SQLite store
  (``P117_OPERATIONS_DB``); there is no committed seed yet, so the list starts
  empty.

Deciding an approval requires ``jobs:approve`` — checked in the handler, not
in the UI — and every decision is written to the audit log with the acting
principal. Deciding an already-decided approval answers ``409``: a decision
is not something that can be silently overwritten.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from backend.api.src.deps import get_audit, get_operations, get_principal
from backend.api.src.routes.equipment import authorize, unavailable
from backend.security.audit import AuditService
from backend.security.rbac import Principal
from backend.storage.operations import (
    APPROVAL_TRANSITIONS,
    OPERATIONS_SOURCE,
    OperationsDataUnavailable,
    OperationsStateError,
    OperationsStore,
)
from backend.tools.base import Permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


class ApprovalRequest(BaseModel):
    """Raise something for human decision.

    Deliberately narrow: a title, a type, what it relates to, and the evidence a
    reviewer needs. A caller cannot set ``status`` — everything this creates is
    ``pending``, and the only way it becomes anything else is a decision.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    type: str = Field(min_length=1, max_length=60)
    summary: str = Field(default="", max_length=4000)
    related_id: str | None = Field(default=None, max_length=120)
    risk: str = Field(default="medium", max_length=20)
    required_role: str | None = Field(default=None, max_length=40)
    evidence: list[dict] = Field(default_factory=list, max_length=50)


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(description="approved | rejected")
    note: str = Field(default="", max_length=1000)


@router.get("")
def list_approvals(
    status: str | None = Query(default=None, description="pending|approved|rejected"),
    principal: Principal = Depends(get_principal),
    operations: OperationsStore = Depends(get_operations),
) -> dict:
    authorize(principal, Permission.CONNECTORS_READ)
    if status and status not in APPROVAL_TRANSITIONS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown status {status!r}; expected one of {sorted(APPROVAL_TRANSITIONS)}",
        )
    try:
        rows = operations.approvals(status=status)
        pending = operations.approvals(status="pending")
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    # Whether *this* caller may act on them, so the UI can show a decision
    # affordance only when the click would actually succeed.
    can_decide = principal.has(Permission.JOBS_APPROVE)
    return {
        "items": rows,
        "count": len(rows),
        "pendingCount": len(pending),
        "canDecide": can_decide,
        "source": OPERATIONS_SOURCE,
    }


@router.post("")
def raise_approval(
    payload: ApprovalRequest,
    principal: Principal = Depends(get_principal),
    operations: OperationsStore = Depends(get_operations),
    audit: AuditService = Depends(get_audit),
) -> dict:
    """Create a PENDING approval.

    This is the only entry point that mints an approval, and it grants nothing:
    the record is parked for a human, and deciding it is
    ``POST /api/approvals/{id}/decision``, which requires ``jobs:approve`` and is
    audited with the acting principal. Idempotent per (type, related_id) so
    re-raising the same request returns the open one instead of duplicating it.
    """
    try:
        approval = operations.request_approval(
            title=payload.title,
            approval_type=payload.type,
            actor=principal.user,
            summary=payload.summary,
            related_id=payload.related_id,
            risk=payload.risk,
            required_role=payload.required_role,
            evidence=payload.evidence,
        )
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    # Audited with the acting principal: who asked, for what, and whether the
    # request was deduplicated onto an already-open approval.
    audit.record(
        action="approval.requested",
        resource_type=payload.type,
        resource_id=payload.related_id or approval["id"],
        user=principal.user,
        approval="pending",
        detail={
            "approval_id": approval["id"],
            "deduplicated": approval.get("deduplicated", False),
        },
    )
    return {"approval": approval, "source": OPERATIONS_SOURCE}


@router.get("/{approval_id}")
def get_approval(
    approval_id: str,
    principal: Principal = Depends(get_principal),
    operations: OperationsStore = Depends(get_operations),
) -> dict:
    authorize(principal, Permission.CONNECTORS_READ)
    try:
        row = operations.approval(approval_id)
        evidence_ids = set(row.get("evidence") or [])
        documents = [doc for doc in operations.documents() if doc.get("id") in evidence_ids]
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"approval {approval_id} not found") from exc
    return {
        "approval": row,
        "evidenceDocuments": documents,
        "allowedDecisions": sorted(APPROVAL_TRANSITIONS.get(str(row.get("status")), frozenset())),
        "canDecide": principal.has(Permission.JOBS_APPROVE),
        "source": OPERATIONS_SOURCE,
    }


@router.post("/{approval_id}/decision")
def decide_approval(
    approval_id: str,
    payload: ApprovalDecision,
    principal: Principal = Depends(get_principal),
    operations: OperationsStore = Depends(get_operations),
    audit: AuditService = Depends(get_audit),
) -> dict:
    # An approval gate is only meaningful if the approver is authorized to
    # approve, not merely authenticated (same rule as /api/jobs).
    authorize(principal, Permission.JOBS_APPROVE)
    try:
        row = operations.decide_approval(
            approval_id,
            decision=payload.decision,
            actor=principal.user,
            note=payload.note,
        )
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"approval {approval_id} not found") from exc
    except OperationsStateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    try:
        audit.record(
            action=f"approval.{payload.decision}",
            resource_type="approval",
            resource_id=str(row["id"]),
            user=principal.user,
            approval="granted" if payload.decision == "approved" else "denied",
            detail={
                "relatedId": row.get("relatedId"),
                "type": row.get("type"),
                "risk": row.get("risk"),
                "note": payload.note,
            },
        )
    except Exception:  # pragma: no cover - defensive
        logger.warning("audit write failed for approval decision", exc_info=True)
    return {"approval": row, "persistence": "local_sqlite"}
