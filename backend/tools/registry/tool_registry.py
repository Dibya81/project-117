"""The tool registry (Phase 8).

Every tool call in this backend goes through :meth:`ToolRegistry.execute`,
and it passes five gates in this order:

1. **Existence** - unknown name, no call.
2. **Schema** - raw arguments are validated against the tool's pydantic
   model. A handler never sees unvalidated input.
3. **Authorisation** - the caller's roles must carry the tool's declared
   permission (``backend.security.rbac``).
4. **Approval** - risk at or above ``execute`` parks the job
   (``backend.security.approvals``). Raised *before* the handler, so a parked
   job has done nothing.
5. **Limits** - the call runs under ``asyncio.wait_for`` with the tool's
   timeout.

The order matters. Authorisation before approval means an unauthorised caller
is refused outright instead of being offered an approval prompt they could
never legitimately satisfy, and validation before both means a malformed call
never creates an approval request that a reviewer has to interpret.

Every outcome - including refusals - writes a ``tool_executions`` row and an
audit event. Arguments are redacted first: a tool call can contain a document
quote, generated code, or a credential, and none of those belong in a table
that exists to be read by operators. Bookkeeping never raises; failing to
record a successful call is logged, not turned into a failed call.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from pydantic import BaseModel, ValidationError

from backend.security.approvals import ApprovalDecision, ApprovalPolicy
from backend.security.rbac import AuthorizationError, require
from backend.tools.base import (
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
)

logger = logging.getLogger(__name__)

#: Argument keys whose values are replaced with a length marker before being
#: recorded. Document text, generated code and anything credential-shaped.
_REDACT_KEYS = frozenset(
    {
        "answer",
        "code",
        "content",
        "context",
        "evidence",
        "password",
        "script",
        "secret",
        "text",
        "token",
    }
)

#: Everything else is truncated: an argument is an identifier or a short
#: parameter, and anything longer is content by another name.
_MAX_RECORDED_VALUE_CHARS = 200


def redact_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Make arguments safe to persist. Shape is kept; content is not."""
    safe: dict[str, Any] = {}
    for key, value in (arguments or {}).items():
        lowered = str(key).lower()
        if lowered in _REDACT_KEYS:
            length = len(value) if isinstance(value, (str, bytes, list, dict)) else 0
            safe[key] = f"<redacted:{length}>"
        elif isinstance(value, str) and len(value) > _MAX_RECORDED_VALUE_CHARS:
            safe[key] = value[:_MAX_RECORDED_VALUE_CHARS] + f"...<+{len(value)}>"
        elif isinstance(value, dict):
            safe[key] = redact_arguments(value)
        elif isinstance(value, list):
            safe[key] = f"<list:{len(value)}>"
        else:
            safe[key] = value
    return safe


def _format_validation_error(name: str, error: ValidationError) -> str:
    problems = []
    for item in error.errors()[:5]:
        location = ".".join(str(part) for part in item.get("loc", ())) or "(root)"
        problems.append(f"{location}: {item.get('msg', 'invalid')}")
    return f"invalid arguments for '{name}' - " + "; ".join(problems)


def _as_result(name: str, value: Any) -> ToolResult:
    if isinstance(value, ToolResult):
        return value
    if isinstance(value, dict):
        return ToolResult(tool=name, output=value)
    return ToolResult(tool=name, output={"value": value})


class ToolRegistry:
    def __init__(
        self,
        *,
        session_factory: Any = None,
        audit: Any = None,
        approval_policy: ApprovalPolicy | None = None,
        metrics: Any = None,
    ) -> None:
        self._tools: dict[str, Tool] = {}
        self._sessions = session_factory
        self._audit = audit
        self._policy = approval_policy or ApprovalPolicy()
        self._metrics = metrics

    # --- catalogue --------------------------------------------------------

    def register(self, tool: Tool) -> Tool:
        name = tool.spec.name
        if name in self._tools:
            raise ValueError(f"tool '{name}' is already registered")
        self._tools[name] = tool
        return tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            known = ", ".join(sorted(self._tools)) or "none"
            raise ToolNotFound(f"unknown tool '{name}'; registered: {known}") from exc

    def names(self) -> list[str]:
        return sorted(self._tools)

    def specs(self) -> list[ToolSpec]:
        return [self._tools[name].spec for name in sorted(self._tools)]

    def list(self) -> list[dict[str, Any]]:
        """Catalogue for ``GET /api/tools`` and for planner prompts."""
        return [spec.public() for spec in self.specs()]

    # --- execution --------------------------------------------------------

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any] | None,
        context: ToolContext,
        *,
        step_id: str | None = None,
        approved: bool = False,
        agent: str | None = None,
    ) -> ToolResult:
        raw = dict(arguments or {})
        safe_arguments = redact_arguments(raw)

        # Gate 1: existence.
        try:
            tool = self.get(name)
        except ToolNotFound as exc:
            self._record(
                name=name,
                spec=None,
                context=context,
                step_id=step_id,
                agent=agent,
                status="unknown_tool",
                arguments=safe_arguments,
                duration_ms=0.0,
                error=str(exc),
                approval="not_required",
            )
            raise
        spec = tool.spec

        # Gate 2: schema.
        try:
            parsed: BaseModel = tool.arguments_model.model_validate(raw)
        except ValidationError as exc:
            message = _format_validation_error(name, exc)
            self._record(
                name=name,
                spec=spec,
                context=context,
                step_id=step_id,
                agent=agent,
                status="invalid_arguments",
                arguments=safe_arguments,
                duration_ms=0.0,
                error=message,
                approval="not_required",
            )
            raise ToolArgumentError(message) from exc

        # Gate 3: authorisation.
        try:
            require(spec.permission, roles=context.roles)
        except AuthorizationError as exc:
            self._record(
                name=name,
                spec=spec,
                context=context,
                step_id=step_id,
                agent=agent,
                status="denied",
                arguments=safe_arguments,
                duration_ms=0.0,
                error=str(exc),
                approval="not_required",
                outcome="refused",
            )
            raise ToolPermissionDenied(str(exc)) from exc

        # Gate 4: approval. Nothing has happened yet at this point.
        decision: ApprovalDecision = self._policy.evaluate(spec, already_approved=approved)
        if decision.required:
            self._record(
                name=name,
                spec=spec,
                context=context,
                step_id=step_id,
                agent=agent,
                status="awaiting_approval",
                arguments=safe_arguments,
                duration_ms=0.0,
                error=None,
                approval="pending",
                approval_basis=decision.basis,
                # Nothing has executed yet. Stated explicitly because the
                # absence of an outcome must never read as a completed call.
                outcome="pending",
            )
            raise ToolApprovalRequired(decision.reason, tool=name, risk=spec.risk)

        # Gate 5: limits.
        started = time.perf_counter()
        try:
            outcome = await asyncio.wait_for(
                tool.run(parsed, context), timeout=spec.limits.timeout_seconds
            )
        except asyncio.TimeoutError as exc:
            duration = (time.perf_counter() - started) * 1000
            message = (
                f"'{name}' exceeded its {spec.limits.timeout_seconds:g}s limit and was stopped"
            )
            self._record(
                name=name,
                spec=spec,
                context=context,
                step_id=step_id,
                agent=agent,
                status="timeout",
                arguments=safe_arguments,
                duration_ms=duration,
                error=message,
                approval=decision.as_state(),
                approval_basis=decision.basis,
                outcome="failure",
            )
            raise ToolTimeout(message) from exc
        except ToolError as exc:
            duration = (time.perf_counter() - started) * 1000
            self._record(
                name=name,
                spec=spec,
                context=context,
                step_id=step_id,
                agent=agent,
                status=getattr(exc, "reason", "error"),
                arguments=safe_arguments,
                duration_ms=duration,
                error=str(exc),
                approval=decision.as_state(),
                approval_basis=decision.basis,
                outcome="failure",
            )
            raise
        except Exception as exc:
            duration = (time.perf_counter() - started) * 1000
            self._record(
                name=name,
                spec=spec,
                context=context,
                step_id=step_id,
                agent=agent,
                status="error",
                arguments=safe_arguments,
                duration_ms=duration,
                error=f"{type(exc).__name__}: {exc}",
                approval=decision.as_state(),
                approval_basis=decision.basis,
                outcome="failure",
            )
            raise ToolError(f"'{name}' failed: {type(exc).__name__}: {exc}") from exc

        duration = (time.perf_counter() - started) * 1000
        result = _as_result(name, outcome)
        result = result.model_copy(update={"duration_ms": duration, "tool": name})
        self._record(
            name=name,
            spec=spec,
            context=context,
            step_id=step_id,
            agent=agent,
            status=result.status,
            arguments=safe_arguments,
            duration_ms=duration,
            error=result.error,
            approval=decision.as_state(),
            approval_basis=decision.basis,
            sandbox_execution_id=result.sandbox_execution_id,
            outcome="success" if result.status == "ok" else "failure",
        )
        return result

    # --- bookkeeping ------------------------------------------------------

    def _record(
        self,
        *,
        name: str,
        spec: ToolSpec | None,
        context: ToolContext,
        step_id: str | None,
        agent: str | None,
        status: str,
        arguments: dict[str, Any],
        duration_ms: float,
        error: str | None,
        approval: str,
        approval_basis: str = "risk",
        sandbox_execution_id: str | None = None,
        outcome: str | None = None,
    ) -> None:
        """Persist the attempt and audit it. Never raises."""
        risk = spec.risk.value if spec else "unknown"
        # An omitted outcome is derived, never defaulted to success: a call
        # parked at an approval gate has not run, and recording it as a
        # success would forge both consent and completion.
        if outcome is not None:
            resolved_outcome = outcome
        elif error:
            resolved_outcome = "failure"
        elif approval == "pending":
            resolved_outcome = "pending"
        elif status not in ("ok", "success"):
            resolved_outcome = "failure"
        else:
            resolved_outcome = "success"
        try:
            if self._metrics is not None:
                self._metrics.observe_tool(name=name, status=status, duration_ms=duration_ms)
        except Exception:  # pragma: no cover - metrics are advisory
            logger.debug("metrics rejected tool observation for %s", name, exc_info=True)

        if self._sessions is not None:
            try:
                from backend.database.execution import ToolExecution

                with self._sessions() as session:
                    session.add(
                        ToolExecution(
                            job_id=context.job_id,
                            step_id=step_id,
                            tool=name,
                            agent=agent,
                            user=context.user,
                            status=status,
                            risk=risk,
                            approval=approval,
                            arguments_json=json.dumps(arguments, default=str),
                            sandbox_execution_id=sandbox_execution_id,
                            duration_ms=duration_ms,
                            error=error,
                        )
                    )
                    session.commit()
            except Exception:
                logger.warning("failed to persist tool execution for %s", name, exc_info=True)

        if self._audit is not None:
            try:
                self._audit.record(
                    action=f"tool.{status}",
                    resource_type="tool",
                    resource_id=name,
                    user=context.user,
                    outcome=resolved_outcome,
                    tool=name,
                    agent=agent,
                    approval=approval,
                    error=error,
                    detail={
                        "job_id": context.job_id,
                        "step_id": step_id,
                        "risk": risk,
                        "approval_basis": approval_basis,
                        "arguments": arguments,
                        "duration_ms": round(duration_ms, 1),
                        "sandbox_execution_id": sandbox_execution_id,
                    },
                )
            except Exception:
                logger.warning("failed to audit tool call for %s", name, exc_info=True)
