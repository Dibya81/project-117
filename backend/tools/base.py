"""Tool contracts (Phase 8).

Every tool declares, up front and in one place: what it is called, what it
accepts, what permission it needs, how dangerous it is, and what resources it
may consume. The registry enforces all five; a tool cannot opt out by
forgetting to check something, because it never gets the chance to check.

Risk is the axis the approval gate reads:

- ``read`` - retrieval and document reads. No side effects.
- ``compute`` - deterministic work on already-approved data.
- ``write`` - produces an artifact inside the workspace.
- ``execute`` - runs model-authored code in the sandbox. Gated.
- ``external`` - touches a system outside this machine. Gated.

``ToolSpec.sandboxed`` is documentation *and* a check: the sandbox service
refuses to run anything whose spec does not claim it, so "this runs in a
container" can never be an assumption made only in a docstring.

The ToolOrchestra idea we kept (ADR 0002) lives in ``capabilities``,
``latency_class`` and ``cost_class``: a router can pick between two tools that
can both do a job without hard-coding preferences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class RiskLevel(str, Enum):
    READ = "read"
    COMPUTE = "compute"
    WRITE = "write"
    EXECUTE = "execute"
    EXTERNAL = "external"


_RISK_ORDER: tuple[RiskLevel, ...] = (
    RiskLevel.READ,
    RiskLevel.COMPUTE,
    RiskLevel.WRITE,
    RiskLevel.EXECUTE,
    RiskLevel.EXTERNAL,
)


def risk_rank(risk: RiskLevel) -> int:
    """Ordinal rank, so policies can say "at or above execute"."""
    return _RISK_ORDER.index(risk)


class Permission(str, Enum):
    """Coarse permissions. Mapped to roles in ``backend.security.rbac``."""

    DOCUMENTS_READ = "documents:read"
    DOCUMENTS_WRITE = "documents:write"
    SEARCH_QUERY = "search:query"
    ARTIFACTS_WRITE = "artifacts:write"
    CODE_EXECUTE = "code:execute"
    CONNECTORS_READ = "connectors:read"
    CONNECTORS_WRITE = "connectors:write"
    # Creating/advancing a work order in *this* system. Deliberately separate
    # from CONNECTORS_WRITE, which is the right to push changes into an
    # external system of record (SAP, CMMS) — an operator may do the former
    # without being allowed the latter.
    WORK_ORDERS_WRITE = "work_orders:write"
    JOBS_APPROVE = "jobs:approve"


class ResourceLimits(BaseModel):
    """Per-call ceilings. Defaults are conservative on purpose."""

    model_config = ConfigDict(extra="forbid")

    timeout_seconds: float = Field(default=60.0, gt=0, le=900.0)
    max_output_bytes: int = Field(default=256_000, gt=0)
    cpu_millicores: int = Field(default=500, ge=100, le=4000)
    memory_mib: int = Field(default=512, ge=128, le=4096)
    max_artifact_bytes: int = Field(default=25 * 1024 * 1024, gt=0)


class ToolSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=1000)
    permission: Permission
    risk: RiskLevel
    limits: ResourceLimits = Field(default_factory=ResourceLimits)
    #: True when the implementation executes in OpenSandbox rather than in the
    #: API process. Checked by the sandbox service, not merely documented.
    sandboxed: bool = False
    capabilities: list[str] = Field(default_factory=list, max_length=16)
    latency_class: int = Field(default=2, ge=1, le=5)
    cost_class: int = Field(default=2, ge=1, le=5)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        """Catalogue entry for ``GET /api/tools`` and for planner prompts."""
        return {
            "name": self.name,
            "description": self.description,
            "permission": self.permission.value,
            "risk": self.risk.value,
            "sandboxed": self.sandboxed,
            "capabilities": list(self.capabilities),
            "latency_class": self.latency_class,
            "cost_class": self.cost_class,
            "limits": self.limits.model_dump(),
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "requires_approval_by_default": risk_rank(self.risk)
            >= risk_rank(RiskLevel.EXECUTE),
        }


@dataclass
class ToolContext:
    """Services a tool may use. A plain container, deliberately.

    Tools receive collaborators here instead of importing singletons, so a
    unit test can hand a tool a fake retriever and a fake sandbox without a
    running application. Nothing here is secret: no API keys, no raw settings
    object, no database engine - only the narrow services a tool needs.
    """

    job_id: str | None = None
    user: str | None = None
    roles: list[str] = field(default_factory=list)
    document_ids: list[str] | None = None
    retrieval: Any = None
    sandbox: Any = None
    artifacts: Any = None
    session_factory: Any = None
    audit: Any = None
    router: Any = None


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    status: str = "ok"
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0
    #: Set when the work happened in OpenSandbox, so an artifact can be traced
    #: back to the exact execution that produced it.
    sandbox_execution_id: str | None = None
    artifact_ids: list[str] = Field(default_factory=list)


# --- errors ---------------------------------------------------------------


class ToolError(RuntimeError):
    """Base class. Carries a stable ``reason`` for the API error envelope."""

    reason = "tool_failed"


class ToolNotFound(ToolError):
    reason = "tool_not_found"


class ToolArgumentError(ToolError):
    reason = "tool_invalid_arguments"


class ToolPermissionDenied(ToolError):
    """Not retryable and not approvable - the caller may not do this at all."""

    reason = "tool_forbidden"


class ToolApprovalRequired(ToolError):
    """Raised *before* the handler runs, so nothing has happened yet."""

    reason = "approval_required"

    def __init__(self, message: str, *, tool: str, risk: RiskLevel) -> None:
        super().__init__(message)
        self.tool = tool
        self.risk = risk.value if isinstance(risk, RiskLevel) else str(risk)


class ToolTimeout(ToolError):
    reason = "tool_timeout"


class ToolUnavailable(ToolError):
    """A dependency the tool needs is not configured or not reachable."""

    reason = "tool_unavailable"


@runtime_checkable
class Tool(Protocol):
    """What the registry requires of a tool.

    ``arguments_model`` is a pydantic model class; the registry validates raw
    arguments against it and hands ``run`` a typed instance.
    """

    @property
    def spec(self) -> ToolSpec: ...

    @property
    def arguments_model(self) -> type[BaseModel]: ...

    async def run(self, arguments: BaseModel, context: ToolContext) -> ToolResult | dict[str, Any]: ...
