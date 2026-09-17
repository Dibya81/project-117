"""The mobile client's role vocabulary and permission grants.

The Android app has its own frozen role and permission enums
(``domain/model/Models.kt``: ``UserRole`` and ``Permissions``). Those names are
part of the wire contract — the client stores them in ``UserSession`` and gates
UI with ``hasPermission("approvals:decide")`` — so they cannot be replaced by
the backend's RBAC names.

This module is the single translation point between the two:

* ``MOBILE_ROLE_PERMISSIONS`` is what ``POST /auth/login`` returns and what the
  field handlers check before doing work. It mirrors the roles the demo backend
  has always modelled, so LIVE and DEMO modes grant the same capabilities.
* ``BACKEND_ROLE_FOR_MOBILE_ROLE`` maps a mobile role onto a real RBAC role so
  the existing permission middleware and ``require()`` calls keep working. Both
  technician and supervisor act as ``field`` (operator plus connector write),
  which is the RBAC role the ``/api/v1`` write gate needs; ``admin`` stays
  ``admin``. The mobile role itself is preserved on the token and reported by
  ``/auth/me``.
"""

from __future__ import annotations

#: Permission strings, copied verbatim from the frozen client contract
#: (``domain/model/Models.kt::Permissions``). A typo here is invisible on the
#: wire and silently hides a control in the app, so they are named constants.
EQUIPMENT_VIEW = "equipment:view"
WORK_ORDERS_VIEW = "work_orders:view"
WORK_ORDERS_UPDATE = "work_orders:update"
SOP_VIEW = "sop:view"
ISSUES_CREATE = "issues:create"
EVIDENCE_CAPTURE = "evidence:capture"
ASSISTANT_USE = "assistant:use"
APPROVALS_VIEW = "approvals:view"
APPROVALS_DECIDE = "approvals:decide"
AGENT_TASKS_VIEW = "agent_tasks:view"
AGENT_TASKS_COMPLETE = "agent_tasks:complete"

#: Mobile role -> mobile permission strings. Matches ``DemoBackend.login``
#: exactly so a user sees identical affordances in DEMO and LIVE.
MOBILE_ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "TECHNICIAN": (
        EQUIPMENT_VIEW,
        WORK_ORDERS_VIEW,
        WORK_ORDERS_UPDATE,
        SOP_VIEW,
        ISSUES_CREATE,
        EVIDENCE_CAPTURE,
        ASSISTANT_USE,
        AGENT_TASKS_VIEW,
        AGENT_TASKS_COMPLETE,
    ),
    "OPERATOR": (
        EQUIPMENT_VIEW,
        WORK_ORDERS_VIEW,
        SOP_VIEW,
        ISSUES_CREATE,
        EVIDENCE_CAPTURE,
        ASSISTANT_USE,
    ),
    "SUPERVISOR": (
        EQUIPMENT_VIEW,
        WORK_ORDERS_VIEW,
        WORK_ORDERS_UPDATE,
        SOP_VIEW,
        ISSUES_CREATE,
        EVIDENCE_CAPTURE,
        ASSISTANT_USE,
        APPROVALS_VIEW,
        APPROVALS_DECIDE,
        AGENT_TASKS_VIEW,
        AGENT_TASKS_COMPLETE,
    ),
    "ADMIN": (
        EQUIPMENT_VIEW,
        WORK_ORDERS_VIEW,
        WORK_ORDERS_UPDATE,
        SOP_VIEW,
        ISSUES_CREATE,
        EVIDENCE_CAPTURE,
        ASSISTANT_USE,
        APPROVALS_VIEW,
        APPROVALS_DECIDE,
        AGENT_TASKS_VIEW,
        AGENT_TASKS_COMPLETE,
    ),
}

#: Mobile role -> backend RBAC role used by the permission middleware.
BACKEND_ROLE_FOR_MOBILE_ROLE: dict[str, str] = {
    "TECHNICIAN": "field",
    "OPERATOR": "field",
    "SUPERVISOR": "field",
    "ADMIN": "admin",
}

MOBILE_ROLES: tuple[str, ...] = tuple(MOBILE_ROLE_PERMISSIONS)


def normalize_mobile_role(role: str | None) -> str:
    """Uppercase a role name, falling back to the least-privileged role."""
    candidate = str(role or "").strip().upper()
    return candidate if candidate in MOBILE_ROLE_PERMISSIONS else "TECHNICIAN"


def permissions_for_mobile_role(role: str | None) -> list[str]:
    return list(MOBILE_ROLE_PERMISSIONS[normalize_mobile_role(role)])


def backend_roles_for_mobile_role(role: str | None) -> list[str]:
    return [BACKEND_ROLE_FOR_MOBILE_ROLE[normalize_mobile_role(role)]]


__all__ = [
    "AGENT_TASKS_COMPLETE",
    "AGENT_TASKS_VIEW",
    "APPROVALS_DECIDE",
    "APPROVALS_VIEW",
    "ASSISTANT_USE",
    "BACKEND_ROLE_FOR_MOBILE_ROLE",
    "EQUIPMENT_VIEW",
    "EVIDENCE_CAPTURE",
    "ISSUES_CREATE",
    "MOBILE_ROLES",
    "MOBILE_ROLE_PERMISSIONS",
    "SOP_VIEW",
    "WORK_ORDERS_UPDATE",
    "WORK_ORDERS_VIEW",
    "backend_roles_for_mobile_role",
    "normalize_mobile_role",
    "permissions_for_mobile_role",
]
