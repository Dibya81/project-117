"""Equipment endpoints (operations surface).

Serves equipment records, telemetry trends and operational history. The
records come from the committed dataset in ``data/demo`` through
``backend.storage.demo`` until a real CMMS/SAP/historian connector is
configured (see ``backend/connectors/``). Two rules hold here:

* every payload carries ``source: "demo-dataset"`` so a caller can never
  mistake it for connector-backed truth, and
* a missing dataset is reported as ``503 demo_data_unavailable`` rather than
  answered with invented rows.

Reads require ``connectors:read`` — an unauthenticated viewer on a shared
deployment does not get plant data by default.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.src.deps import get_operations, get_principal
from backend.security.rbac import AuthorizationError, Principal, require
from backend.storage.demo import SOURCE, DemoDataUnavailable, DemoStore
from backend.tools.base import Permission

router = APIRouter(prefix="/api/equipment", tags=["equipment"])


def authorize(principal: Principal, permission: Permission) -> None:
    """Enforce the permission at the handler, not in the UI."""
    try:
        require(permission, roles=principal.roles)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def unavailable(exc: DemoDataUnavailable) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.reason, "message": exc.message},
    )


@router.get("")
def list_equipment(
    status: str | None = Query(default=None, description="healthy|warning|critical|maintenance"),
    criticality: str | None = Query(default=None, description="low|medium|high"),
    q: str | None = Query(default=None, max_length=120, description="id, name or unit substring"),
    principal: Principal = Depends(get_principal),
    operations: DemoStore = Depends(get_operations),
) -> dict:
    authorize(principal, Permission.CONNECTORS_READ)
    try:
        rows = operations.equipment(status=status, criticality=criticality, query=q)
    except DemoDataUnavailable as exc:
        raise unavailable(exc) from exc
    return {
        "items": rows,
        "count": len(rows),
        "filters": {"status": status, "criticality": criticality, "q": q},
        "source": SOURCE,
    }


@router.get("/{equipment_id}")
def get_equipment(
    equipment_id: str,
    principal: Principal = Depends(get_principal),
    operations: DemoStore = Depends(get_operations),
) -> dict:
    authorize(principal, Permission.CONNECTORS_READ)
    try:
        item = operations.equipment_item(equipment_id)
        history = operations.history(equipment_id)
        work_orders = operations.work_orders(equipment_id=equipment_id)
        documents = [
            doc
            for doc in operations.documents()
            if str(doc.get("equipmentId") or "").lower() == equipment_id.lower()
        ]
    except DemoDataUnavailable as exc:
        raise unavailable(exc) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"equipment {equipment_id} not found") from exc
    return {
        "equipment": item,
        "openWorkOrders": [
            wo for wo in work_orders if wo.get("status") in {"draft", "open", "in_progress", "on_hold"}
        ],
        "workOrders": work_orders,
        "documents": documents,
        "history": history,
        "source": SOURCE,
    }


@router.get("/{equipment_id}/telemetry")
def get_telemetry(
    equipment_id: str,
    signal: str | None = Query(default=None, description="restrict to a single signal"),
    principal: Principal = Depends(get_principal),
    operations: DemoStore = Depends(get_operations),
) -> dict:
    authorize(principal, Permission.CONNECTORS_READ)
    try:
        return operations.telemetry(equipment_id, signal=signal)
    except DemoDataUnavailable as exc:
        raise unavailable(exc) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"no telemetry for {equipment_id}" + (f" signal {signal}" if signal else ""),
        ) from exc


@router.get("/{equipment_id}/history")
def get_history(
    equipment_id: str,
    principal: Principal = Depends(get_principal),
    operations: DemoStore = Depends(get_operations),
) -> dict:
    authorize(principal, Permission.CONNECTORS_READ)
    try:
        rows = operations.history(equipment_id)
    except DemoDataUnavailable as exc:
        raise unavailable(exc) from exc
    return {"equipmentId": equipment_id, "items": rows, "count": len(rows), "source": SOURCE}
