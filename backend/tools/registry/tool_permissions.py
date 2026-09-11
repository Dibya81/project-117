"""Which roles may invoke which tools.

The registry knows what a tool *is*; this module answers whether a given
principal may run it. Keeping that decision out of the tool bodies means a
new tool cannot forget to check - the executor consults this before dispatch.

Default is deny. A tool whose declared permission is unknown to the RBAC
matrix is refused rather than allowed, because the failure mode of the
opposite default is silent privilege escalation.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from backend.security.rbac import Permission, permissions_for
from backend.tools.base import RiskLevel, ToolPermissionDenied, ToolSpec, risk_rank

#: Risk levels that always require an approved job, whatever the role.
APPROVAL_RISKS: frozenset[RiskLevel] = frozenset({RiskLevel.EXECUTE, RiskLevel.EXTERNAL})


def required_permission(spec: ToolSpec) -> Permission | None:
    """The permission a tool declares, or None if it is unrestricted."""
    return getattr(spec, "permission", None)


def permitted(spec: ToolSpec, roles: Sequence[str]) -> bool:
    """True when the roles carry the tool's declared permission."""
    needed = required_permission(spec)
    if needed is None:
        return True
    try:
        granted = permissions_for(roles)
    except Exception:
        # An unreadable role set is not a grant.
        return False
    return needed in granted


def check(spec: ToolSpec, roles: Sequence[str]) -> None:
    """Raise :class:`ToolPermissionDenied` unless the roles allow the tool."""
    if permitted(spec, roles):
        return
    needed = required_permission(spec)
    raise ToolPermissionDenied(
        f"tool '{spec.name}' requires permission "
        f"'{getattr(needed, 'value', needed)}', which roles {sorted(roles)} do not carry"
    )


def requires_approval(spec: ToolSpec) -> bool:
    """Whether this tool is gated behind human approval by risk alone."""
    return risk_rank(spec.risk) >= risk_rank(RiskLevel.EXECUTE)


def allowed_specs(specs: Iterable[ToolSpec], roles: Sequence[str]) -> list[ToolSpec]:
    """Subset of tools these roles may call - used to build agent toolsets."""
    return [spec for spec in specs if permitted(spec, roles)]


def matrix(specs: Iterable[ToolSpec]) -> list[dict[str, Any]]:
    """Human-readable tool/permission/risk table for the admin screen."""
    rows: list[dict[str, Any]] = []
    for spec in specs:
        needed = required_permission(spec)
        rows.append(
            {
                "tool": spec.name,
                "permission": getattr(needed, "value", None),
                "risk": getattr(spec.risk, "value", str(spec.risk)),
                "sandboxed": bool(getattr(spec, "sandboxed", False)),
                "requiresApproval": requires_approval(spec),
            }
        )
    rows.sort(key=lambda row: row["tool"])
    return rows


__all__ = [
    "APPROVAL_RISKS",
    "allowed_specs",
    "check",
    "matrix",
    "permitted",
    "required_permission",
    "requires_approval",
]
