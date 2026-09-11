"""Access to the execution sandbox, and the rules for reaching it.

There is exactly one way for model-authored code to run: through the sandbox
service. This module is the gate. It never falls back to running code in the
API process - if no sandbox is configured the operation fails with an
actionable message naming the environment variables to set.

That refusal is the security property. A "convenient" local fallback would
mean the difference between a configured deployment and a misconfigured one
is silent, and arbitrary generated code would execute against the host that
holds the plant's documents.
"""

from __future__ import annotations

import posixpath
import re
from typing import Any

from backend.sandbox.policy import ARTIFACTS_DIR, INPUTS_DIR, WORKSPACE_DIR
from backend.tools.base import ToolArgumentError, ToolContext, ToolUnavailable

NO_SANDBOX_MESSAGE = (
    "code execution is unavailable: no sandbox is configured. Set "
    "P117_OPEN_SANDBOX_BASE_URL and P117_SANDBOX_API_KEY. Code is never run in "
    "the API process as a fallback."
)

_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def require(context: ToolContext) -> Any:
    """Return the sandbox service, or refuse with an actionable message."""
    sandbox = getattr(context, "sandbox", None)
    if sandbox is None:
        raise ToolUnavailable(NO_SANDBOX_MESSAGE)
    return sandbox


def available(context: ToolContext) -> bool:
    return getattr(context, "sandbox", None) is not None


def safe_name(name: str) -> str:
    """Validate a caller-supplied file name.

    Rejects separators and traversal outright instead of sanitising them: a
    name that needed rewriting was not the name the caller meant, and quietly
    changing it makes later path reasoning unreliable.
    """
    candidate = str(name or "").strip()
    if not _SAFE_NAME.match(candidate):
        raise ToolArgumentError(
            f"invalid file name '{name}': use 1-64 characters from A-Z a-z 0-9 . _ - "
            "with no path separators"
        )
    if candidate in {".", ".."}:
        raise ToolArgumentError("invalid file name")
    return candidate


def input_path(name: str) -> str:
    """Absolute in-container path for a supplied input file."""
    return posixpath.join(INPUTS_DIR, safe_name(name))


def artifact_path(name: str) -> str:
    """Absolute in-container path for a produced artifact."""
    return posixpath.join(ARTIFACTS_DIR, safe_name(name))


def workspace_path(name: str) -> str:
    return posixpath.join(WORKSPACE_DIR, safe_name(name))


def summary(context: ToolContext) -> dict[str, Any]:
    """Sandbox posture for the admin screen; safe when unconfigured."""
    sandbox = getattr(context, "sandbox", None)
    if sandbox is None:
        return {"configured": False, "reason": NO_SANDBOX_MESSAGE}
    try:
        detail = sandbox.summary()
    except Exception as exc:  # pragma: no cover - defensive
        return {"configured": True, "healthy": False, "error": str(exc)}
    return {"configured": True, "healthy": True, **(detail or {})}


__all__ = [
    "NO_SANDBOX_MESSAGE",
    "artifact_path",
    "available",
    "input_path",
    "require",
    "safe_name",
    "summary",
    "workspace_path",
]
