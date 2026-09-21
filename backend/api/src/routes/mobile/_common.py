"""Shared helpers for the ``/api/v1`` mobile surface.

Two jobs live here, both contract-shaped:

* **Mappers** from the backend's real records onto the frozen Android DTOs. The
  client's field names and enum spellings are fixed
  (``apps/mobile/.../dto/Dtos.kt``, ``domain/model/Models.kt``); an extra or
  renamed key is a runtime failure on the phone, so every payload is built here
  and nothing else builds one.
* **The mobile authorisation helpers** — the bearer-token requirement and the
  per-endpoint mobile permission check. They are separate from backend RBAC
  because the phone's vocabulary (``approvals:decide``) is not the backend's
  (``jobs:approve``); see ``security/mobile_roles.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from starlette.requests import Request

from backend.api.src.qr_codes import equipment_tag as _equipment_tag
from backend.security.auth import AuthenticationError
from backend.security.rbac import AuthorizationError, Principal

# ─── Status vocabularies ──────────────────────────────────────────────────────
#
# The operations store and the Android enums do not share spellings. These
# tables are the translation, and every lossy edge is called out.

#: operations work-order status -> the client's WorkOrderStatus constant.
WORK_ORDER_STATUS_TO_MOBILE: dict[str, str] = {
    "draft": "OPEN",
    "open": "OPEN",
    "in_progress": "IN_PROGRESS",
    # The store has no "waiting on approval" state; on_hold is the closest real
    # state (work is paused awaiting a decision).
    "on_hold": "PENDING_APPROVAL",
    "completed": "COMPLETED",
    "cancelled": "CANCELLED",
}

#: WorkOrderStatus -> operations status. ASSIGNED/FAILED/PENDING_APPROVAL have
#: no distinct store state and collapse onto the nearest real one.
WORK_ORDER_STATUS_FROM_MOBILE: dict[str, str] = {
    "OPEN": "open",
    "ASSIGNED": "open",
    "IN_PROGRESS": "in_progress",
    "PENDING_APPROVAL": "on_hold",
    "COMPLETED": "completed",
    "CANCELLED": "cancelled",
    "FAILED": "cancelled",
}

EQUIPMENT_STATUS_TO_MOBILE: dict[str, str] = {
    "healthy": "OPERATIONAL",
    "warning": "DEGRADED",
    "critical": "DEGRADED",
    "maintenance": "UNDER_MAINTENANCE",
}

#: Incident severity -> AgentTaskPriority. The task itself records no priority;
#: the incident it belongs to records a real severity, which is what an
#: operator would triage on.
INCIDENT_SEVERITY_TO_PRIORITY: dict[str, str] = {
    "critical": "URGENT",
    "warning": "HIGH",
    "info": "MEDIUM",
}

#: NotificationType constants, to avoid emitting a spelling the phone drops.
NOTIFICATION_TYPES = frozenset(
    {"ASSIGNMENT", "WORK_ORDER_UPDATE", "APPROVAL_REQUIRED", "AGENT_TASK", "ALERT", "SYSTEM"}
)

ISSUE_SEVERITIES = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})


# ─── Authorisation ────────────────────────────────────────────────────────────
def get_mobile_principal(request: Request) -> Principal:
    """A principal backed by a verified mobile bearer token and a live session.

    ``get_principal`` alone is not enough: the console runs with
    ``P117_AUTH_REQUIRED=false``, where an unauthenticated caller is a valid
    ``operator``. The mobile surface is a person-authenticated surface, so it
    refuses an anonymous caller with 401 even in that mode. The middleware
    enforces this first; the dependency is the second, independent check.

    It also re-checks the session row, so an access token presented after
    ``POST /auth/logout`` is refused instead of staying valid until it expires.
    """
    from backend.api.src.deps import get_identity, get_principal
    from backend.storage.identity import InactiveSession

    principal = get_principal(request)
    if not principal.authenticated:
        raise AuthenticationError("a valid mobile bearer token is required")
    session_id = str(principal.extra.get("session_id") or "")
    user_id = str(principal.extra.get("user_id") or "")
    if session_id and user_id:
        try:
            get_identity(request).assert_access_session_active(
                session_id=session_id, user_id=user_id
            )
        except InactiveSession as exc:
            raise AuthenticationError(str(exc)) from exc
    return principal


def require_mobile_permission(principal: Principal, permission: str) -> None:
    """Refuse the call unless the token's role carries ``permission``.

    Checked against the grants baked into the token (from the identity store),
    not against backend RBAC: the phone's roles and the backend's roles answer
    different questions, and this is the one the app renders.
    """
    granted = principal.extra.get("permissions") or ()
    if permission in granted:
        return
    role = principal.extra.get("mobile_role") or "unknown"
    raise AuthorizationError(f"mobile role '{role}' lacks permission '{permission}'")


# ─── Auth payloads ────────────────────────────────────────────────────────────
def user_payload(user: dict[str, Any]) -> dict[str, Any]:
    """The shared subset of ``LoginResponse`` / ``MeResponse`` the client reads."""
    return {
        "user_id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "role": user["role"],
        "permissions": list(user["permissions"]),
    }


# ─── Equipment ────────────────────────────────────────────────────────────────
def _asset_tag(row: dict[str, Any]) -> str | None:
    """The real plant tag.

    ``OperationsStore._map_equipment`` packs ``[kind, area_id, tag]`` into
    ``tags``; the tag is the identifier a physical QR label encodes, so it is
    what the client should receive as ``qr_code`` (and what
    ``POST /equipment/identify`` resolves). The extraction itself lives in
    ``api.qr_codes`` because the label renderer needs the identical value — one
    implementation, so the DTO and the printed symbol cannot disagree.
    """
    return _equipment_tag(row)


def _equipment_metadata(row: dict[str, Any]) -> dict[str, str]:
    """Real dataset fields the DTO has no column for, as string key/values."""
    metadata: dict[str, str] = {}

    def put(key: str, value: Any) -> None:
        if value is None or value == "":
            return
        metadata[key] = value if isinstance(value, str) else str(value)

    put("asset_tag", _asset_tag(row))
    put("criticality", row.get("criticality"))
    put("unit", row.get("unit"))
    put("area_id", row.get("area"))
    put("installed_year", row.get("installedYear"))
    put("last_inspection", row.get("lastInspection"))
    put("next_inspection", row.get("nextInspection"))
    put("summary", row.get("summary"))
    signals = row.get("keySignals") or []
    if signals:
        metadata["key_signals"] = "; ".join(
            f"{signal.get('signal')}={signal.get('value')}{signal.get('unit') or ''}"
            for signal in signals
        )
    metadata["source"] = "plant-dataset"
    return metadata


def equipment_dto(row: dict[str, Any]) -> dict[str, Any]:
    """Map a real plant asset onto the frozen ``EquipmentDto``.

    ``readings`` is ``null`` on purpose. The dataset carries *configured*
    instrument baselines, not a live telemetry feed and not a timestamped
    sample — presenting a baseline as a reading would look like a measurement
    the backend cannot actually make. The baselines are preserved verbatim in
    ``metadata.key_signals`` instead. ``last_maintenance_date`` /
    ``next_maintenance_date`` carry the dataset's real inspection dates, which
    are the only maintenance-cadence dates the store has.
    """
    return {
        "id": row.get("id") or "",
        "name": row.get("name") or "",
        "type": row.get("type") or "",
        "location": row.get("area") or row.get("unit") or "",
        "status": EQUIPMENT_STATUS_TO_MOBILE.get(str(row.get("status") or ""), "UNKNOWN"),
        "qr_code": _asset_tag(row),
        "barcode": None,
        "manufacturer": row.get("manufacturer"),
        "model": row.get("model"),
        "serial_number": None,
        "last_maintenance_date": row.get("lastInspection"),
        "next_maintenance_date": row.get("nextInspection"),
        "metadata": _equipment_metadata(row),
        "readings": None,
    }


# ─── Work orders ──────────────────────────────────────────────────────────────
def equipment_name_for(operations: Any, equipment_id: str | None) -> str | None:
    """The real asset name for a reference, or ``None`` when it does not resolve.

    Used to enrich work-order and approval payloads. A dangling reference is
    reported as ``null`` rather than substituted with the id, so a caller can
    tell "no such asset" from "asset with an odd name".
    """
    if not equipment_id:
        return None
    try:
        name = operations.equipment_item(str(equipment_id)).get("name")
    except Exception:
        # KeyError (unknown asset) and OperationsDataUnavailable (dataset
        # missing) both mean "this enrichment is not available"; neither is
        # worth failing the primary record over.
        return None
    return str(name) if name else None


def work_order_dto(row: dict[str, Any], *, equipment_name: str | None = None) -> dict[str, Any]:
    """Map an operations work order onto the frozen ``WorkOrderDto``.

    ``steps`` and ``issue_id`` are ``null``: the store keeps no checklist and no
    issue link, and inventing an empty checklist would read as "this job has no
    steps" rather than "no step store exists".
    """
    created = row.get("createdAt") or ""
    return {
        "id": row.get("id") or "",
        "title": row.get("title") or "",
        "description": row.get("description") or "",
        "status": WORK_ORDER_STATUS_TO_MOBILE.get(str(row.get("status") or ""), "OPEN"),
        "priority": str(row.get("priority") or "medium").upper(),
        "assigned_to": row.get("assignee"),
        "equipment_id": row.get("equipmentId"),
        "equipment_name": equipment_name,
        "due_date": row.get("dueDate"),
        "created_at": created,
        "updated_at": row.get("updatedAt") or created,
        "steps": None,
        "issue_id": None,
        "notes": row.get("lastNote"),
    }


# ─── Approvals ────────────────────────────────────────────────────────────────
def approval_dto(
    row: dict[str, Any],
    *,
    work_order: dict[str, Any] | None = None,
    equipment_name: str | None = None,
) -> dict[str, Any]:
    """Map an operations approval onto the frozen ``ApprovalDto``.

    The store has no ``consequence`` column, so that field carries the real
    ``summary`` when one was recorded and otherwise names the approval type and
    its stored risk level — both real values, composed rather than invented.
    ``deadline`` is ``null`` because nothing stores one.
    """
    summary = str(row.get("summary") or "")
    approval_type = str(row.get("type") or "approval")
    risk = str(row.get("risk") or "medium")
    consequence = summary or f"{approval_type} approval (risk: {risk})"
    work_order = work_order or {}
    return {
        "id": row.get("id") or "",
        "title": row.get("title") or "",
        "description": summary,
        "work_order_id": row.get("relatedId"),
        "work_order_title": work_order.get("title"),
        "equipment_id": work_order.get("equipmentId"),
        "equipment_name": equipment_name,
        "consequence": consequence,
        "requested_by": row.get("requestedBy") or "",
        "requested_at": row.get("requestedAt") or "",
        "deadline": None,
        "status": str(row.get("status") or "pending").upper(),
    }


# ─── Agent tasks ──────────────────────────────────────────────────────────────
def _iso_from_epoch(value: Any) -> str:
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError, OSError):
        return ""


def agent_task_dto(row: dict[str, Any], *, equipment_name: str | None = None) -> dict[str, Any]:
    """Map an engine agent task + its field-handling overlay.

    ``status`` is the *field* lifecycle (PENDING until a technician acts on it),
    not the agent's own run state; the task's real title is reused as the
    instruction because the engine writes titles as imperatives. ``description``
    carries the agent's recorded result. ``priority`` is derived from the
    incident's real severity; ``work_order_id``/``due_by`` are ``null`` because
    nothing links a task to either.
    """
    severity = str(row.get("severity") or "").lower()
    return {
        "id": row.get("id") or "",
        "title": row.get("title") or "",
        "description": row.get("result") or "",
        "source": row.get("agent") or "agent",
        "priority": INCIDENT_SEVERITY_TO_PRIORITY.get(severity, "MEDIUM"),
        "status": row.get("field_status") or "PENDING",
        "equipment_id": row.get("origin_equipment"),
        "equipment_name": equipment_name,
        "work_order_id": None,
        "instructions": row.get("title") or "",
        "evidence_required": bool(row.get("evidence_count")),
        "due_by": None,
        "created_at": _iso_from_epoch(row.get("wall_ts")),
    }


# ─── Notifications ────────────────────────────────────────────────────────────
def notification_dto(row: dict[str, Any]) -> dict[str, Any]:
    notification_type = str(row.get("type") or "SYSTEM").upper()
    return {
        "id": row.get("id") or "",
        "type": notification_type if notification_type in NOTIFICATION_TYPES else "SYSTEM",
        "title": row.get("title") or "",
        "body": row.get("body") or "",
        "timestamp": row.get("timestamp") or "",
        "is_read": bool(row.get("is_read", 0)),
        "reference_id": row.get("reference_id"),
        "reference_type": row.get("reference_type"),
    }


__all__ = [
    "EQUIPMENT_STATUS_TO_MOBILE",
    "INCIDENT_SEVERITY_TO_PRIORITY",
    "ISSUE_SEVERITIES",
    "NOTIFICATION_TYPES",
    "WORK_ORDER_STATUS_FROM_MOBILE",
    "WORK_ORDER_STATUS_TO_MOBILE",
    "agent_task_dto",
    "approval_dto",
    "equipment_dto",
    "equipment_name_for",
    "get_mobile_principal",
    "notification_dto",
    "require_mobile_permission",
    "user_payload",
    "work_order_dto",
]
