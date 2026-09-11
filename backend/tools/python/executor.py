"""Run Python in the sandbox and normalise the outcome.

One behaviour is deliberate and worth stating plainly: **a non-zero exit code
is returned, not raised.** An agent is expected to read its own traceback and
fix its code. Raising would collapse "your code has a bug" into the same
channel as "the sandbox is down", and those two require different responses -
the first is the agent's problem, the second is an operator's.

Infrastructure failures do raise.
"""

from __future__ import annotations

from typing import Any, Mapping

from backend.tools.base import ToolArgumentError, ToolContext, ToolError
from backend.tools.python import sandbox as sandbox_gate
from backend.tools.python.resource_limits import EffectiveLimits, resolve

MAX_CODE_CHARS = 100_000
MAX_INPUT_FILES = 10


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit], True


async def execute(
    context: ToolContext,
    *,
    code: str,
    inputs: Mapping[str, str] | None = None,
    limits: EffectiveLimits | None = None,
    collect_artifacts: bool = False,
) -> dict[str, Any]:
    """Execute model-authored Python inside the sandbox.

    Returns a normalised result: ``exitCode``, ``stdout``, ``stderr``,
    ``timedOut``, ``truncated`` and the limits that were applied - so a caller
    can tell a timeout from a crash from a clean run without parsing text.
    """
    source = str(code or "")
    if not source.strip():
        raise ToolArgumentError("no code was supplied")
    if len(source) > MAX_CODE_CHARS:
        raise ToolArgumentError(
            f"code is {len(source)} characters; the limit is {MAX_CODE_CHARS}"
        )
    files = dict(inputs or {})
    if len(files) > MAX_INPUT_FILES:
        raise ToolArgumentError(
            f"{len(files)} input files supplied; the limit is {MAX_INPUT_FILES}"
        )
    for name in files:
        sandbox_gate.safe_name(name)

    service = sandbox_gate.require(context)
    applied = limits or resolve()

    # Signature verified against backend.sandbox.service.SandboxService.run_python:
    #   run_python(code, *, job_id, timeout_seconds, inputs, collect_artifacts)
    try:
        raw = await service.run_python(
            source,
            job_id=getattr(context, "job_id", None),
            timeout_seconds=applied.timeout_seconds,
            inputs=files,
            collect_artifacts=collect_artifacts,
        )
    except ToolError:
        raise
    except Exception as exc:  # infrastructure failure - not the agent's bug
        raise ToolError(f"sandbox execution failed: {exc}") from exc

    result = raw if isinstance(raw, dict) else getattr(raw, "__dict__", {}) or {}
    stdout, out_truncated = _truncate(str(result.get("stdout", "")), applied.max_output_bytes)
    stderr, err_truncated = _truncate(str(result.get("stderr", "")), applied.max_output_bytes)
    raw_exit = result.get("exit_code")
    exit_code = int(raw_exit) if raw_exit is not None else 0
    error = result.get("error")
    timed_out = bool(error) and "timeout" in str(error).lower()

    return {
        "exitCode": exit_code,
        # A non-zero exit is the *agent's* result, not an infrastructure fault,
        # so it is returned rather than raised. ``error`` is the transport-level
        # failure the sandbox itself reported.
        "ok": bool(result.get("ok", error is None and exit_code == 0)),
        "stdout": stdout,
        "stderr": stderr,
        "error": error,
        "timedOut": timed_out,
        "truncated": bool(result.get("truncated")) or out_truncated or err_truncated,
        "executionId": result.get("execution_id"),
        "durationMs": result.get("duration_ms"),
        # SandboxExecution reports produced files under ``files``.
        "artifacts": list(result.get("files", []) or []),
        "limits": applied.to_dict(),
    }


def summarise(result: Mapping[str, Any], *, limit: int = 400) -> str:
    """One-line outcome for a trace or an agent's next prompt."""
    if result.get("timedOut"):
        return f"execution timed out after {result.get('limits', {}).get('timeoutSeconds')}s"
    if result.get("ok"):
        head = str(result.get("stdout", "")).strip().splitlines()
        return head[-1][:limit] if head else "execution completed with no output"
    tail = str(result.get("stderr", "")).strip().splitlines()
    return f"exit {result.get('exitCode')}: {tail[-1][:limit] if tail else 'no stderr'}"


__all__ = ["MAX_CODE_CHARS", "MAX_INPUT_FILES", "execute", "summarise"]
