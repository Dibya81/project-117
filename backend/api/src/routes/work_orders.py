"""Work-order endpoints (operations surface).

Records live in the local operations SQLite store
(``P117_OPERATIONS_DB``); there is no committed seed, so the list starts empty
and grows only from runtime writes. Two things are enforced here rather than in
the UI:

* **permissions** — reads need ``connectors:read``, writes need
  ``connectors:write``, checked in the handler;
* **the lifecycle** — status changes are validated against
  ``WORK_ORDER_TRANSITIONS``, so an illegal move answers ``409`` instead of
  quietly overwriting state.

Every write is recorded in the audit log with the acting principal.
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
    OPERATIONS_SOURCE,
    WORK_ORDER_TRANSITIONS,
    OperationsDataUnavailable,
    OperationsStateError,
    OperationsStore,
)
from backend.tools.base import Permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/work-orders", tags=["work-orders"])

PRIORITIES = ("low", "medium", "high", "critical")
TYPES = ("corrective", "preventive", "inspection", "modification")


class WorkOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=4, max_length=160)
    equipmentId: str | None = Field(default=None, max_length=40)
    priority: str = Field(default="medium")
    type: str = Field(default="corrective")
    status: str = Field(default="draft")
    assignee: str | None = Field(default=None, max_length=80)
    dueDate: str | None = Field(default=None, max_length=32)
    description: str = Field(default="", max_length=4000)
    evidence: list[str] = Field(default_factory=list)
    origin: str = Field(default="api", max_length=40)


class WorkOrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    assignee: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=1000)


def _record(audit: AuditService, **kwargs) -> None:
    """Audit is not allowed to break the request, but silence is not ok either."""
    try:
        audit.record(**kwargs)
    except Exception:  # pragma: no cover - defensive
        logger.warning("audit write failed for %s", kwargs.get("action"), exc_info=True)


@router.get("")
def list_work_orders(
    status: str | None = Query(
        default=None, description="draft|open|in_progress|on_hold|completed|cancelled"
    ),
    equipmentId: str | None = Query(default=None, max_length=40),
    principal: Principal = Depends(get_principal),
    operations: OperationsStore = Depends(get_operations),
) -> dict:
    authorize(principal, Permission.CONNECTORS_READ)
    if status and status not in WORK_ORDER_TRANSITIONS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown status {status!r}; expected one of {sorted(WORK_ORDER_TRANSITIONS)}",
        )
    try:
        rows = operations.work_orders(status=status, equipment_id=equipmentId)
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    return {
        "items": rows,
        "count": len(rows),
        "filters": {"status": status, "equipmentId": equipmentId},
        "source": OPERATIONS_SOURCE,
    }


@router.get("/meta/transitions")
def work_order_transitions(principal: Principal = Depends(get_principal)) -> dict:
    """The lifecycle the API enforces, so the UI can disable impossible moves."""
    authorize(principal, Permission.CONNECTORS_READ)
    return {
        "transitions": {state: sorted(nexts) for state, nexts in WORK_ORDER_TRANSITIONS.items()},
        "priorities": list(PRIORITIES),
        "types": list(TYPES),
    }


@router.get("/{work_order_id}")
def get_work_order(
    work_order_id: str,
    principal: Principal = Depends(get_principal),
    operations: OperationsStore = Depends(get_operations),
) -> dict:
    authorize(principal, Permission.CONNECTORS_READ)
    try:
        row = operations.work_order(work_order_id)
        equipment = None
        if row.get("equipmentId"):
            try:
                equipment = operations.equipment_item(str(row["equipmentId"]))
            except KeyError:
                equipment = None
        evidence_ids = set(row.get("evidence") or [])
        documents = [doc for doc in operations.documents() if doc.get("id") in evidence_ids]
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"work order {work_order_id} not found"
        ) from exc
    return {
        "workOrder": row,
        "equipment": equipment,
        "evidenceDocuments": documents,
        "allowedTransitions": sorted(
            WORK_ORDER_TRANSITIONS.get(str(row.get("status")), frozenset())
        ),
        "source": OPERATIONS_SOURCE,
    }


@router.post("", status_code=201)
def create_work_order(
    payload: WorkOrderCreate,
    principal: Principal = Depends(get_principal),
    operations: OperationsStore = Depends(get_operations),
    audit: AuditService = Depends(get_audit),
) -> dict:
    authorize(principal, Permission.WORK_ORDERS_WRITE)
    if payload.priority not in PRIORITIES:
        raise HTTPException(status_code=400, detail=f"priority must be one of {list(PRIORITIES)}")
    if payload.type not in TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of {list(TYPES)}")
    if payload.status not in {"draft", "open"}:
        raise HTTPException(status_code=400, detail="new work orders start as draft or open")
    try:
        if payload.equipmentId:
            operations.equipment_item(payload.equipmentId)  # 404 early on a bad tag
        row = operations.create_work_order(payload.model_dump(), actor=principal.user)
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"equipment {payload.equipmentId} not found"
        ) from exc
    except OperationsStateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    _record(
        audit,
        action="work_order.created",
        resource_type="work_order",
        resource_id=str(row["id"]),
        user=principal.user,
        detail={
            "equipmentId": row.get("equipmentId"),
            "priority": row.get("priority"),
            "origin": row.get("origin"),
            "evidence": row.get("evidence"),
        },
    )
    return {"workOrder": row, "persistence": "local_sqlite", "source": "runtime"}


@router.patch("/{work_order_id}")
def update_work_order(
    work_order_id: str,
    payload: WorkOrderUpdate,
    principal: Principal = Depends(get_principal),
    operations: OperationsStore = Depends(get_operations),
    audit: AuditService = Depends(get_audit),
) -> dict:
    authorize(principal, Permission.WORK_ORDERS_WRITE)
    if payload.status is not None and payload.status not in WORK_ORDER_TRANSITIONS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown status {payload.status!r}; expected one of {sorted(WORK_ORDER_TRANSITIONS)}",
        )
    if payload.status is None and payload.assignee is None and not payload.note:
        raise HTTPException(status_code=400, detail="nothing to update")
    try:
        row = operations.update_work_order(
            work_order_id,
            status=payload.status,
            assignee=payload.assignee,
            note=payload.note,
            actor=principal.user,
        )
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"work order {work_order_id} not found"
        ) from exc
    except OperationsStateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    _record(
        audit,
        action="work_order.updated",
        resource_type="work_order",
        resource_id=str(row["id"]),
        user=principal.user,
        detail={"status": row.get("status"), "assignee": row.get("assignee")},
    )
    return {
        "workOrder": row,
        "allowedTransitions": sorted(
            WORK_ORDER_TRANSITIONS.get(str(row.get("status")), frozenset())
        ),
        "persistence": "local_sqlite",
    }
