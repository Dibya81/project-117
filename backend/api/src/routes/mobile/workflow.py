"""Workflow endpoints (``/api/v1``): agent tasks, approvals, notifications.

Agent tasks come from the incident pipeline's real ``agent_tasks`` table; the
field-handling state (acknowledged/completed) is the mobile store's overlay, so
the list never diverges from what the engine actually produced. Approvals are
the operations store's real approval rows, decided through the same
``OperationsStore.decide_approval`` the console uses.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.api.src.deps import get_audit, get_mobile, get_operations
from backend.api.src.errors import BadRequest, NotFound
from backend.api.src.routes.equipment import unavailable
from backend.api.src.routes.mobile._common import (
    agent_task_dto,
    approval_dto,
    equipment_name_for,
    get_mobile_principal,
    notification_dto,
    require_mobile_permission,
)
from backend.security.audit import AuditService
from backend.security.mobile_roles import (
    AGENT_TASKS_COMPLETE,
    AGENT_TASKS_VIEW,
    APPROVALS_DECIDE,
    APPROVALS_VIEW,
)
from backend.security.rbac import Principal
from backend.storage.mobile import MobileStateError, MobileStore
from backend.storage.operations import (
    OperationsDataUnavailable,
    OperationsStateError,
    OperationsStore,
)

logger = logging.getLogger(__name__)

router = APIRouter()

#: The client's decision vocabulary (``ApprovalDecisionRequest``) -> the store's.
APPROVAL_DECISION_TO_STORE: dict[str, str] = {"approve": "approved", "reject": "rejected"}


def _not_found(what: str, identifier: str) -> NotFound:
    return NotFound(f"{what} {identifier} not found")


def _audit(audit: AuditService, **kwargs) -> None:
    try:
        audit.record(**kwargs)
    except Exception:  # pragma: no cover - auditing must not break the action
        logger.warning("audit write failed for %s", kwargs.get("action"), exc_info=True)


# ─── Agent tasks ──────────────────────────────────────────────────────────────
@router.get("/agents/tasks")
def list_agent_tasks(
    principal: Principal = Depends(get_mobile_principal),
    operations: OperationsStore = Depends(get_operations),
    mobile: MobileStore = Depends(get_mobile),
) -> dict:
    require_mobile_permission(principal, AGENT_TASKS_VIEW)
    rows = mobile.list_agent_tasks()
    return {
        "items": [
            agent_task_dto(
                row, equipment_name=equipment_name_for(operations, row.get("origin_equipment"))
            )
            for row in rows
        ]
    }


@router.post("/agents/tasks/{task_id}/acknowledge")
def acknowledge_agent_task(
    task_id: str,
    principal: Principal = Depends(get_mobile_principal),
    operations: OperationsStore = Depends(get_operations),
    mobile: MobileStore = Depends(get_mobile),
    audit: AuditService = Depends(get_audit),
) -> dict:
    """Record that a technician has seen and taken on a real agent task."""
    require_mobile_permission(principal, AGENT_TASKS_COMPLETE)
    try:
        row = mobile.acknowledge_agent_task(task_id, actor=principal.user)
    except KeyError as exc:
        raise _not_found("agent task", task_id) from exc
    except MobileStateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    _audit(
        audit,
        action="mobile.agent_task_acknowledged",
        resource_type="agent_task",
        resource_id=task_id,
        user=principal.user,
    )
    return agent_task_dto(
        row, equipment_name=equipment_name_for(operations, row.get("origin_equipment"))
    )


class CompleteAgentTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notes: str | None = Field(default=None, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)


@router.post("/agents/tasks/{task_id}/complete")
def complete_agent_task(
    task_id: str,
    payload: CompleteAgentTaskRequest,
    principal: Principal = Depends(get_mobile_principal),
    operations: OperationsStore = Depends(get_operations),
    mobile: MobileStore = Depends(get_mobile),
    audit: AuditService = Depends(get_audit),
) -> dict:
    """Close out a field task with the technician's notes and evidence ids."""
    require_mobile_permission(principal, AGENT_TASKS_COMPLETE)
    try:
        row = mobile.complete_agent_task(
            task_id,
            actor=principal.user,
            notes=payload.notes,
            evidence_ids=payload.evidence_ids,
        )
    except KeyError as exc:
        raise _not_found("agent task", task_id) from exc
    except MobileStateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    _audit(
        audit,
        action="mobile.agent_task_completed",
        resource_type="agent_task",
        resource_id=task_id,
        user=principal.user,
        detail={"evidenceCount": len(payload.evidence_ids)},
    )
    return agent_task_dto(
        row, equipment_name=equipment_name_for(operations, row.get("origin_equipment"))
    )


# ─── Approvals ────────────────────────────────────────────────────────────────
def _approval_context(
    operations: OperationsStore, row: dict
) -> tuple[dict | None, str | None]:
    related_id = row.get("relatedId")
    if not related_id:
        return None, None
    try:
        work_order = operations.work_order(str(related_id))
    except (KeyError, OperationsDataUnavailable):
        return None, None
    return work_order, equipment_name_for(operations, work_order.get("equipmentId"))


@router.get("/approvals")
def list_approvals(
    principal: Principal = Depends(get_mobile_principal),
    operations: OperationsStore = Depends(get_operations),
) -> dict:
    require_mobile_permission(principal, APPROVALS_VIEW)
    try:
        rows = operations.approvals()
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    items = []
    for row in rows:
        work_order, equipment_name = _approval_context(operations, row)
        items.append(approval_dto(row, work_order=work_order, equipment_name=equipment_name))
    return {"items": items}


class ApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(min_length=1, max_length=20)
    notes: str | None = Field(default=None, max_length=1000)


@router.post("/approvals/{approval_id}/decide")
def decide_approval(
    approval_id: str,
    payload: ApprovalDecisionRequest,
    principal: Principal = Depends(get_mobile_principal),
    operations: OperationsStore = Depends(get_operations),
    audit: AuditService = Depends(get_audit),
) -> dict:
    """Record a supervisor's real decision on a parked approval.

    The mobile permission ``approvals:decide`` (supervisor/admin only) is
    enforced here *in addition to* the backend ``jobs:approve`` right the store
    call carries, so a technician's token cannot approve an outage even though
    both share the RBAC ``field`` role.
    """
    require_mobile_permission(principal, APPROVALS_DECIDE)
    decision = payload.decision.strip().lower()
    store_decision = APPROVAL_DECISION_TO_STORE.get(decision)
    if store_decision is None:
        raise BadRequest(
            f"decision must be one of {sorted(APPROVAL_DECISION_TO_STORE)}, got '{payload.decision}'"
        )
    try:
        row = operations.decide_approval(
            approval_id,
            decision=store_decision,
            actor=principal.user,
            note=payload.notes,
        )
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    except KeyError as exc:
        raise _not_found("approval", approval_id) from exc
    except OperationsStateError as exc:
        raise HTTPException(
            status_code=getattr(exc, "status_code", 409),
            detail={"code": getattr(exc, "reason", "invalid_transition"), "message": str(exc)},
        ) from exc
    _audit(
        audit,
        action=f"mobile.approval_{decision}d",
        resource_type="approval",
        resource_id=str(row.get("id")),
        user=principal.user,
        detail={"note": payload.notes},
    )
    work_order, equipment_name = _approval_context(operations, row)
    return approval_dto(row, work_order=work_order, equipment_name=equipment_name)


# ─── Notifications ────────────────────────────────────────────────────────────
@router.get("/notifications")
def list_notifications(
    principal: Principal = Depends(get_mobile_principal),
    mobile: MobileStore = Depends(get_mobile),
) -> dict:
    """This user's in-app feed, newest first."""
    rows = mobile.notifications(user=principal.user)
    return {"items": [notification_dto(row) for row in rows]}


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    principal: Principal = Depends(get_mobile_principal),
    mobile: MobileStore = Depends(get_mobile),
) -> dict:
    """Mark a notification read; a foreign or unknown id is a 404."""
    if not mobile.mark_notification_read(notification_id, user=principal.user):
        raise _not_found("notification", notification_id)
    return {"id": notification_id, "read": True}


__all__ = ["router"]
