"""Equipment endpoints (operations surface).

Serves equipment records, telemetry trends and operational history. Equipment
comes from the project's real plant dataset in the simulation SQLite store —
``refinery`` (58 assets) by default, or ``?plant=steel`` (55) — mapped onto the
existing response fields by ``backend.storage.operations``. Two rules hold:

* every payload carries ``source: "plant-dataset"`` so a caller knows where the
  record came from, and
* a missing dataset is reported as ``503`` rather than answered with invented
  rows. Telemetry and per-asset history have no real backing store yet and are
  reported absent (``404`` / empty) rather than synthesized.

Reads require ``connectors:read`` — an unauthenticated viewer on a shared
deployment does not get plant data by default.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from backend.api.src.deps import get_operations, get_principal
from backend.api.src.qr_codes import equipment_tag, qr_payload, qr_svg
from backend.security.rbac import AuthorizationError, Principal, require
from backend.storage.operations import (
    EQUIPMENT_SOURCE,
    OperationsDataUnavailable,
    OperationsStore,
)
from backend.tools.base import Permission

router = APIRouter(prefix="/api/equipment", tags=["equipment"])


def authorize(principal: Principal, permission: Permission) -> None:
    """Enforce the permission at the handler, not in the UI."""
    try:
        require(permission, roles=principal.roles)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def unavailable(exc: OperationsDataUnavailable) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.reason, "message": exc.message},
    )


@router.get("")
def list_equipment(
    plant: str | None = Query(default=None, description="refinery|steel (default refinery)"),
    status: str | None = Query(default=None, description="healthy|warning|critical|maintenance"),
    criticality: str | None = Query(default=None, description="low|medium|high"),
    q: str | None = Query(default=None, max_length=120, description="id, name or unit substring"),
    principal: Principal = Depends(get_principal),
    operations: OperationsStore = Depends(get_operations),
) -> dict:
    authorize(principal, Permission.CONNECTORS_READ)
    try:
        rows = operations.equipment(plant=plant, status=status, criticality=criticality, query=q)
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown plant {plant}") from exc
    return {
        "items": rows,
        "count": len(rows),
        "filters": {"plant": plant, "status": status, "criticality": criticality, "q": q},
        "source": EQUIPMENT_SOURCE,
    }


@router.get("/{equipment_id}")
def get_equipment(
    equipment_id: str,
    principal: Principal = Depends(get_principal),
    operations: OperationsStore = Depends(get_operations),
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
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"equipment {equipment_id} not found") from exc
    return {
        "equipment": item,
        "openWorkOrders": [
            wo
            for wo in work_orders
            if wo.get("status") in {"draft", "open", "in_progress", "on_hold"}
        ],
        "workOrders": work_orders,
        "documents": documents,
        "history": history,
        "source": EQUIPMENT_SOURCE,
    }


@router.get("/{equipment_id}/qr.svg")
def get_equipment_qr(
    equipment_id: str,
    principal: Principal = Depends(get_principal),
    operations: OperationsStore = Depends(get_operations),
) -> Response:
    """The printable QR label for one asset, as an SVG document.

    The payload is the namespaced ``P117:EQUIP:<tag>`` string (see
    ``api.qr_codes``): the Project 117 Android client strips the prefix and
    resolves the tag, while a generic camera app sees opaque text. Rendering is
    local — ``segno`` is pure-Python, so no image library, no QR web service and
    no egress. The document is returned rather than an image because vector
    prints crisply at label size, and it is cacheable because a tag's symbol
    never changes.
    """
    authorize(principal, Permission.CONNECTORS_READ)
    try:
        row = operations.equipment_item(equipment_id)
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"equipment {equipment_id} not found") from exc
    tag = equipment_tag(row)
    if not tag:
        # A tagless asset cannot have a resolvable label; say so rather than
        # printing a symbol that decodes to nothing the store can find.
        raise HTTPException(
            status_code=404, detail=f"equipment {equipment_id} has no tag to encode"
        )
    return Response(
        content=qr_svg(qr_payload(tag)),
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Content-Disposition": f'inline; filename="{tag}-qr.svg"',
        },
    )


@router.get("/{equipment_id}/telemetry")
def get_telemetry(
    equipment_id: str,
    signal: str | None = Query(default=None, description="restrict to a single signal"),
    principal: Principal = Depends(get_principal),
    operations: OperationsStore = Depends(get_operations),
) -> dict:
    authorize(principal, Permission.CONNECTORS_READ)
    try:
        return operations.telemetry(equipment_id, signal=signal)
    except OperationsDataUnavailable as exc:
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
    operations: OperationsStore = Depends(get_operations),
) -> dict:
    authorize(principal, Permission.CONNECTORS_READ)
    try:
        rows = operations.history(equipment_id)
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    return {
        "equipmentId": equipment_id,
        "items": rows,
        "count": len(rows),
        "source": EQUIPMENT_SOURCE,
    }
