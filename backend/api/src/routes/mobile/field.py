"""Field-operations endpoints (``/api/v1``): equipment, work orders, chat,
evidence, issues.

Every handler calls the *same* store or service the existing console route
calls (``OperationsStore``, ``ChatService``, ``DocumentStorage``) and then maps
the result onto the frozen Android DTO. Nothing re-implements plant logic, and
nothing proxies an HTTP request back into this process.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from backend.api.src.deps import (
    get_audit,
    get_documents,
    get_mobile,
    get_operations,
)
from backend.api.src.errors import BadRequest, NotFound, ServiceUnavailable
from backend.api.src.qr_codes import MalformedQRCode, resolve_scanned_code
from backend.api.src.routes.equipment import unavailable
from backend.api.src.routes.mobile._common import (
    ISSUE_SEVERITIES,
    NOTIFICATION_TYPES,
    WORK_ORDER_STATUS_FROM_MOBILE,
    equipment_dto,
    equipment_name_for,
    get_mobile_principal,
    require_mobile_permission,
    work_order_dto,
)
from backend.models.providers.base import ProviderUnreachable
from backend.models.router import ModelUnavailableError
from backend.security.audit import AuditService
from backend.security.mobile_roles import (
    ASSISTANT_USE,
    EQUIPMENT_VIEW,
    EVIDENCE_CAPTURE,
    ISSUES_CREATE,
    WORK_ORDERS_UPDATE,
    WORK_ORDERS_VIEW,
)
from backend.security.rbac import Principal
from backend.storage.documents import DocumentStorage
from backend.storage.mobile import MobileStore
from backend.storage.operations import (
    OperationsDataUnavailable,
    OperationsStateError,
    OperationsStore,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _not_found(what: str, identifier: str) -> NotFound:
    return NotFound(f"{what} {identifier} not found")


# ─── Equipment ────────────────────────────────────────────────────────────────
@router.get("/equipment")
def list_equipment(
    principal: Principal = Depends(get_mobile_principal),
    operations: OperationsStore = Depends(get_operations),
) -> dict:
    require_mobile_permission(principal, EQUIPMENT_VIEW)
    try:
        rows = operations.equipment()
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    return {"items": [equipment_dto(row) for row in rows]}


@router.get("/equipment/{equipment_id}")
def get_equipment(
    equipment_id: str,
    principal: Principal = Depends(get_mobile_principal),
    operations: OperationsStore = Depends(get_operations),
) -> dict:
    require_mobile_permission(principal, EQUIPMENT_VIEW)
    try:
        return equipment_dto(operations.equipment_item(equipment_id))
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    except KeyError as exc:
        raise _not_found("equipment", equipment_id) from exc


class IdentifyEquipmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    qr_code: str = Field(min_length=1, max_length=160)


@router.post("/equipment/identify")
def identify_equipment(
    payload: IdentifyEquipmentRequest,
    principal: Principal = Depends(get_mobile_principal),
    operations: OperationsStore = Depends(get_operations),
) -> dict:
    """Resolve a scanned QR label to an asset.

    Three payload forms are accepted, and all three resolve to the same asset:

    * ``P117:EQUIP:<tag>`` — the namespaced label the console prints
      (``api.qr_codes.QR_PREFIX``); the prefix is stripped and ``<tag>`` looked
      up.
    * ``<tag>`` (e.g. ``P-1001``) — labels printed before the namespace and the
      mobile DTO's own ``qr_code`` value.
    * ``<id>`` (e.g. ``e-P-1001``) — the asset id.

    The store's index already keys every asset by id *and* tag
    (``OperationsStore._equipment_index``), so the stripped value resolves
    directly. Strictness is preserved: a payload that carries the prefix but no
    tag is a 422 (malformed, never a lookup of the empty string), and an unknown
    code is a 404 — never a "closest match".
    """
    require_mobile_permission(principal, EQUIPMENT_VIEW)
    try:
        code = resolve_scanned_code(payload.qr_code)
    except MalformedQRCode as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.reason, "message": str(exc)},
        ) from exc
    try:
        return equipment_dto(operations.equipment_item(code))
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    except KeyError as exc:
        raise NotFound(f"no equipment matches code '{payload.qr_code}'") from exc


# ─── Work orders ──────────────────────────────────────────────────────────────
@router.get("/work-orders")
def list_work_orders(
    principal: Principal = Depends(get_mobile_principal),
    operations: OperationsStore = Depends(get_operations),
) -> dict:
    require_mobile_permission(principal, WORK_ORDERS_VIEW)
    try:
        rows = operations.work_orders()
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    return {
        "items": [
            work_order_dto(row, equipment_name=equipment_name_for(operations, row.get("equipmentId")))
            for row in rows
        ]
    }


@router.get("/work-orders/{work_order_id}")
def get_work_order(
    work_order_id: str,
    principal: Principal = Depends(get_mobile_principal),
    operations: OperationsStore = Depends(get_operations),
) -> dict:
    require_mobile_permission(principal, WORK_ORDERS_VIEW)
    try:
        row = operations.work_order(work_order_id)
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    except KeyError as exc:
        raise _not_found("work order", work_order_id) from exc
    return work_order_dto(row, equipment_name=equipment_name_for(operations, row.get("equipmentId")))


class UpdateWorkOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(min_length=1, max_length=40)
    notes: str | None = Field(default=None, max_length=1000)


@router.post("/work-orders/{work_order_id}/update")
def update_work_order(
    work_order_id: str,
    payload: UpdateWorkOrderRequest,
    principal: Principal = Depends(get_mobile_principal),
    operations: OperationsStore = Depends(get_operations),
    audit: AuditService = Depends(get_audit),
) -> dict:
    """Advance a real work order's status and record a closing note.

    The store's lifecycle rules still apply: an illegal transition is a 409,
    not a silent overwrite. The client's status vocabulary is mapped onto the
    store's before the call (see ``WORK_ORDER_STATUS_FROM_MOBILE``), so the
    client keeps using its own frozen enum names.
    """
    require_mobile_permission(principal, WORK_ORDERS_UPDATE)
    requested = payload.status.strip().upper()
    store_status = WORK_ORDER_STATUS_FROM_MOBILE.get(requested)
    if store_status is None:
        raise BadRequest(
            f"unknown status '{payload.status}'; expected one of "
            f"{sorted(WORK_ORDER_STATUS_FROM_MOBILE)}"
        )
    try:
        row = operations.update_work_order(
            work_order_id,
            status=store_status,
            note=payload.notes,
            actor=principal.user,
        )
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    except KeyError as exc:
        raise _not_found("work order", work_order_id) from exc
    except OperationsStateError as exc:
        raise _conflict(exc) from exc
    try:
        audit.record(
            action="mobile.work_order_updated",
            resource_type="work_order",
            resource_id=str(row.get("id")),
            user=principal.user,
            detail={"requestedStatus": requested, "storedStatus": row.get("status")},
        )
    except Exception:  # pragma: no cover - auditing must not break the write
        logger.warning("audit write failed for work order update", exc_info=True)
    return work_order_dto(row, equipment_name=equipment_name_for(operations, row.get("equipmentId")))


def _conflict(exc: OperationsStateError) -> HTTPException:
    """An illegal lifecycle move is a 409, matching the console route."""
    return HTTPException(
        status_code=getattr(exc, "status_code", 409),
        detail={"code": getattr(exc, "reason", "invalid_transition"), "message": str(exc)},
    )


# ─── Chat / assistant ─────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    equipment_id: str | None = Field(default=None, max_length=80)
    work_order_id: str | None = Field(default=None, max_length=80)


def _chat_context(
    operations: OperationsStore, equipment_id: str | None, work_order_id: str | None
) -> str | None:
    """Ground the turn in the real records the client referenced.

    The chat service has a system-prompt channel but no structured context
    argument, so the resolved records are stated in the prompt. Only real store
    values are used; an unknown reference is stated as unknown rather than
    left out silently.
    """
    lines: list[str] = []
    if equipment_id:
        try:
            equipment = operations.equipment_item(str(equipment_id))
            lines.append(
                f"Equipment {equipment.get('id')} is {equipment.get('name')} "
                f"({equipment.get('type')}) at {equipment.get('area') or equipment.get('unit')}, "
                f"status {equipment.get('status')}."
            )
        except (KeyError, OperationsDataUnavailable):
            lines.append(f"Equipment {equipment_id} is not present in the plant dataset.")
    if work_order_id:
        try:
            work_order = operations.work_order(str(work_order_id))
            lines.append(
                f"Work order {work_order.get('id')} is '{work_order.get('title')}' "
                f"with status {work_order.get('status')} and priority {work_order.get('priority')}."
            )
        except (KeyError, OperationsDataUnavailable):
            lines.append(f"Work order {work_order_id} is not present in the operations store.")
    if not lines:
        return None
    return "Project 117 field assistant. Known plant context: " + " ".join(lines)


@router.post("/chat")
async def chat(
    payload: ChatRequest,
    request: Request,
    principal: Principal = Depends(get_mobile_principal),
    operations: OperationsStore = Depends(get_operations),
) -> dict:
    require_mobile_permission(principal, ASSISTANT_USE)
    service = request.app.state.chat
    system_prompt = _chat_context(operations, payload.equipment_id, payload.work_order_id)
    try:
        result = await service.run_turn(
            message=payload.message,
            role="reasoning",
            system_prompt=system_prompt,
            user=principal.user,
        )
    except ModelUnavailableError as exc:
        # Honest 503: no local model is configured/serving, so no answer exists.
        raise ServiceUnavailable(
            exc.message, code="model_unavailable", detail={"available_models": exc.available_models}
        ) from exc
    except ProviderUnreachable as exc:
        raise ServiceUnavailable(
            f"local model backend unreachable: {exc.message}", code="provider_unreachable"
        ) from exc
    return {"response": result.response}


# ─── Evidence upload ──────────────────────────────────────────────────────────
@router.post("/documents/upload", status_code=201)
async def upload_evidence(
    file: UploadFile = File(...),
    equipment_id: str | None = Form(default=None),
    work_order_id: str | None = Form(default=None),
    caption: str | None = Form(default=None),
    principal: Principal = Depends(get_mobile_principal),
    documents: DocumentStorage = Depends(get_documents),
    mobile: MobileStore = Depends(get_mobile),
) -> dict:
    """Store a field photo/recording and return its document id.

    Delegates the bytes and the row to ``DocumentStorage`` (the same service the
    console uses). The equipment/work-order/caption parts of the multipart body
    are persisted by ``MobileStore`` so the field context is not discarded.
    """
    require_mobile_permission(principal, EVIDENCE_CAPTURE)
    document = documents.save_upload(
        filename=file.filename or "field-evidence",
        content_type=file.content_type,
        file_obj=file.file,
        user=principal.user,
    )
    mobile.record_evidence_upload(
        document_id=document.id,
        equipment_id=equipment_id,
        work_order_id=work_order_id,
        caption=caption,
        uploaded_by=principal.user,
    )
    return {"document_id": document.id}


# ─── Issues ───────────────────────────────────────────────────────────────────
class ReportIssueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    equipment_id: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=4000)
    severity: str = Field(min_length=1, max_length=20)
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)


@router.post("/issues", status_code=201)
def report_issue(
    payload: ReportIssueRequest,
    principal: Principal = Depends(get_mobile_principal),
    operations: OperationsStore = Depends(get_operations),
    mobile: MobileStore = Depends(get_mobile),
    audit: AuditService = Depends(get_audit),
) -> dict:
    """Record a field issue against a real asset.

    The equipment must resolve in the plant dataset: a report against an
    unknown tag is a data-entry error the operator should see immediately, not
    a record nobody can act on. The report also emits a notification — the feed
    is written by the event, not synthesised when it is read.
    """
    require_mobile_permission(principal, ISSUES_CREATE)
    severity = payload.severity.strip().upper()
    if severity not in ISSUE_SEVERITIES:
        raise BadRequest(f"severity must be one of {sorted(ISSUE_SEVERITIES)}")
    try:
        equipment = operations.equipment_item(payload.equipment_id)
    except OperationsDataUnavailable as exc:
        raise unavailable(exc) from exc
    except KeyError as exc:
        raise _not_found("equipment", payload.equipment_id) from exc

    equipment_name = str(equipment.get("name") or "") or None
    issue = mobile.create_issue(
        equipment_id=str(equipment.get("id") or payload.equipment_id),
        equipment_name=equipment_name,
        description=payload.description,
        severity=severity,
        reported_by=principal.user,
        evidence_ids=payload.evidence_ids,
    )
    notification_type = "ALERT" if severity in {"CRITICAL", "HIGH"} else "SYSTEM"
    if notification_type not in NOTIFICATION_TYPES:  # pragma: no cover - defensive
        notification_type = "SYSTEM"
    mobile.add_notification(
        user=principal.user,
        notification_type=notification_type,
        title=f"{severity.title()} issue reported on {equipment_name or payload.equipment_id}",
        body=payload.description[:280],
        reference_id=issue["id"],
        reference_type="issue",
    )
    try:
        audit.record(
            action="mobile.issue_reported",
            resource_type="issue",
            resource_id=issue["id"],
            user=principal.user,
            detail={"equipmentId": issue["equipment_id"], "severity": severity},
        )
    except Exception:  # pragma: no cover - auditing must not break the report
        logger.warning("audit write failed for issue report", exc_info=True)
    return {
        "id": issue["id"],
        "equipment_id": issue["equipment_id"],
        "equipment_name": issue["equipment_name"],
        "description": issue["description"],
        "severity": issue["severity"],
        "reported_by": issue["reported_by"],
        "reported_at": issue["reported_at"],
        "work_order_id": issue["work_order_id"],
    }


__all__ = ["router"]
