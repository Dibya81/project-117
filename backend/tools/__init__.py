"""Tool registry (Phase 8).

Every tool declares its name, description, input/output schemas, permission,
risk level, timeout and resource limits in one :class:`ToolSpec`. Nothing
executes without passing, in order: existence, schema validation,
authorisation, approval, and resource limits. Those five gates live in
:class:`ToolRegistry`, not in the tools, so a tool cannot forget to check
something - it never gets the chance.

What is registered by default is in :mod:`backend.tools.builtin`:
search_documents, read_document, extract_table, analyze_csv, run_python and
the four create_* artifact tools. ``run_shell`` and ``convert_document`` from
the original list are deliberately absent - a shell tool adds no capability
that ``run_python`` lacks while widening the blast radius considerably, and
nothing is wired behind document conversion yet.
"""

# Import layout note: backend.tools.base is a leaf (stdlib + pydantic only).
# backend.security.rbac imports Permission from it, while
# backend.tools.registry imports AuthorizationError/require back from rbac.
# Re-exporting the registry eagerly closed that loop, so importing
# backend.security.rbac before backend.tools raised ImportError at startup.
# The registry is therefore resolved lazily through PEP 562, matching the
# pattern already documented in backend.security.network.
from typing import Any as _Any

from backend.tools.base import (
    Permission,
    ResourceLimits,
    RiskLevel,
    Tool,
    ToolApprovalRequired,
    ToolArgumentError,
    ToolContext,
    ToolError,
    ToolNotFound,
    ToolPermissionDenied,
    ToolResult,
    ToolSpec,
    ToolTimeout,
    ToolUnavailable,
    risk_rank,
)

_LAZY = {"ToolRegistry", "redact_arguments"}


def __getattr__(name: str) -> _Any:
    if name in _LAZY:
        from backend.tools import registry

        return getattr(registry, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | _LAZY)

# pyright: reportUnsupportedDunderAll=false
# ToolRegistry and redact_arguments are resolved through the PEP 562
# __getattr__ below, which keeps backend.tools.base a leaf module. pyright
# cannot follow __getattr__, so it flags them as absent from the module.

__all__ = [
    "Permission",
    "ResourceLimits",
    "RiskLevel",
    "Tool",
    "ToolApprovalRequired",
    "ToolArgumentError",
    "ToolContext",
    "ToolError",
    "ToolNotFound",
    "ToolPermissionDenied",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "ToolTimeout",
    "ToolUnavailable",
    "redact_arguments",
    "risk_rank",
]
