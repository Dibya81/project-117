"""Execution tools (Phase 8 + Phase 9).

Two tools that both end up inside a container, for opposite reasons.

``run_python`` executes **model-authored code**. It is the highest-risk tool in
the system and is priced accordingly: ``execute`` risk, which the approval
policy gates above, and ``sandboxed=True``, which the sandbox service enforces
rather than merely documents. Note what the argument model does *not* accept -
no ``image``, no ``network``, no ``env``, no working directory. A planner
cannot ask for a different container or for outbound access, because there is
nowhere to put the request. The image is chosen by purpose in
:mod:`backend.sandbox.policy` and pinned by digest.

``analyze_csv`` also runs in a container, but executes a **constant, reviewed
script** over caller-supplied data. No model output is executed, so it is
``compute`` risk and needs no approval. That distinction is the whole point of
having a risk axis: "runs in a sandbox" and "runs untrusted code" are
different properties, and conflating them would either gate profiling behind a
human or let arbitrary code through ungated.

One deliberate behaviour in ``run_python``: **a non-zero exit code is returned,
not raised.** The agent is supposed to read the traceback and fix its own
code - that is the test-before-returning loop the brief asks for. Raising
would collapse "your code has a bug" into the same channel as "the sandbox is
down", and the correct response to those two is not the same. Only
infrastructure failures raise.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.tools.base import (
    Permission,
    ResourceLimits,
    RiskLevel,
    ToolArgumentError,
    ToolContext,
    ToolError,
    ToolResult,
    ToolSpec,
    ToolUnavailable,
)

MAX_CODE_CHARS = 100_000
MAX_INPUT_FILES = 10
MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_CSV_CHARS = 2_000_000
MAX_TEXT_RETURNED = 40_000

_INPUT_NAME = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

_NO_SANDBOX = (
    "code execution is unavailable: no sandbox is configured. Set "
    "P117_OPEN_SANDBOX_BASE_URL and P117_SANDBOX_API_KEY. Code is never run in "
    "the API process as a fallback."
)


def _sandbox_errors() -> tuple[type[Exception], type[Exception]]:
    from backend.sandbox import SandboxPolicyError, SandboxUnavailable

    return SandboxPolicyError, SandboxUnavailable


class RunPythonArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=MAX_CODE_CHARS)
    #: filename -> text content, written under /workspace/inputs. Data arrives
    #: as files so a value containing quotes cannot alter the program.
    inputs: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float | None = Field(default=None, gt=0, le=300)
    #: Collect files the script wrote to the artifacts directory.
    collect_artifacts: bool = False
    #: Free text recorded in the audit trail, e.g. "recompute MTBF".
    purpose: str = Field(default="", max_length=200)

    @field_validator("inputs")
    @classmethod
    def _check_inputs(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > MAX_INPUT_FILES:
            raise ValueError(f"at most {MAX_INPUT_FILES} input files may be supplied")
        total = 0
        for name, content in value.items():
            if not _INPUT_NAME.match(name):
                raise ValueError(
                    f"input filename '{name}' must be a plain name of letters, digits, "
                    "dot, dash or underscore"
                )
            total += len(content.encode("utf-8"))
        if total > MAX_INPUT_BYTES:
            raise ValueError(
                f"input files total {total} bytes, above the {MAX_INPUT_BYTES} byte limit"
            )
        return value


class RunPythonTool:
    def __init__(self) -> None:
        self._spec = ToolSpec(
            name="run_python",
            description=(
                "Run Python in an isolated OpenSandbox container with no network access. "
                "Use for calculations, data processing and checking generated code. "
                "Pass data via 'inputs' (filename -> text), read it from ./inputs/. "
                "The container image, CPU, memory, timeout and network policy are set by "
                "server policy and cannot be requested. Requires human approval by default; "
                "a non-zero exit code is returned with stderr so the code can be corrected."
            ),
            permission=Permission.CODE_EXECUTE,
            risk=RiskLevel.EXECUTE,
            limits=ResourceLimits(timeout_seconds=300.0, max_output_bytes=256_000),
            sandboxed=True,
            capabilities=["python", "calculation", "data-processing"],
            latency_class=4,
            cost_class=3,
            input_schema=RunPythonArguments.model_json_schema(),
            output_schema={
                "type": "object",
                "properties": {
                    "exit_code": {"type": "integer"},
                    "stdout": {"type": "string"},
                    "stderr": {"type": "string"},
                    "truncated": {"type": "boolean"},
                    "files": {"type": "array", "items": {"type": "string"}},
                },
            },
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    @property
    def arguments_model(self) -> type[BaseModel]:
        return RunPythonArguments

    async def run(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, RunPythonArguments)
        if context.sandbox is None:
            raise ToolUnavailable(_NO_SANDBOX)

        policy_error, unavailable = _sandbox_errors()
        try:
            execution = await context.sandbox.run_python(
                arguments.code,
                job_id=context.job_id,
                timeout_seconds=arguments.timeout_seconds,
                inputs=dict(arguments.inputs),
                collect_artifacts=arguments.collect_artifacts,
            )
        except policy_error as exc:
            raise ToolArgumentError(str(exc)) from exc
        except unavailable as exc:
            raise ToolUnavailable(str(exc)) from exc

        stdout = (execution.get("stdout") or "")[-MAX_TEXT_RETURNED:]
        stderr = (execution.get("stderr") or "")[-MAX_TEXT_RETURNED:]
        ok = bool(execution.get("ok"))
        error: str | None = None
        if not ok:
            if execution.get("error"):
                error = str(execution.get("error"))
            else:
                lines = stderr.strip().splitlines()
                tail = lines[-1] if lines else "no stderr output"
                error = f"the code exited with status {execution.get('exit_code')}: {tail}"

        return ToolResult(
            tool=self._spec.name,
            status="ok" if ok else "error",
            output={
                "exit_code": execution.get("exit_code"),
                "stdout": stdout,
                "stderr": stderr,
                "truncated": bool(execution.get("truncated")),
                "files": list(execution.get("files") or []),
                "image": execution.get("image", ""),
                "duration_ms": execution.get("duration_ms"),
            },
            error=error,
            sandbox_execution_id=execution.get("execution_id"),
        )


# --- analyze_csv -----------------------------------------------------------

#: Constant, reviewed. Never assembled from model output - which is why this
#: tool is compute risk rather than execute risk.
_PROFILE_SCRIPT = '''
import json

import pandas as pd

with open("inputs/options.json", "r", encoding="utf-8") as handle:
    options = json.load(handle)

frame = pd.read_csv(
    "inputs/data.csv",
    sep=options.get("delimiter", ","),
    header=0 if options.get("has_header", True) else None,
)
if options.get("columns"):
    keep = [column for column in options["columns"] if column in frame.columns]
    if keep:
        frame = frame[keep]

report = {
    "rows": int(frame.shape[0]),
    "column_count": int(frame.shape[1]),
    "columns": [str(column) for column in frame.columns],
    "dtypes": {str(column): str(dtype) for column, dtype in frame.dtypes.items()},
    "null_counts": {str(column): int(value) for column, value in frame.isna().sum().items()},
    "numeric": {},
    "categorical": {},
}

for column in frame.select_dtypes("number").columns:
    series = frame[column].dropna()
    if series.empty:
        continue
    report["numeric"][str(column)] = {
        "count": int(series.count()),
        "mean": round(float(series.mean()), 6),
        "min": round(float(series.min()), 6),
        "max": round(float(series.max()), 6),
        "std": round(float(series.std(ddof=0)), 6),
        "sum": round(float(series.sum()), 6),
    }

for column in frame.select_dtypes(exclude="number").columns:
    counts = frame[column].astype(str).value_counts().head(5)
    report["categorical"][str(column)] = [
        {"value": str(index)[:120], "count": int(value)} for index, value in counts.items()
    ]

preview_rows = int(options.get("max_preview_rows", 5))
if preview_rows > 0:
    report["preview"] = frame.head(preview_rows).astype(str).to_dict(orient="records")

print(json.dumps(report))
'''


class AnalyzeCsvArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    csv_text: str = Field(min_length=1, max_length=MAX_CSV_CHARS)
    delimiter: str = Field(default=",", min_length=1, max_length=4)
    has_header: bool = True
    max_preview_rows: int = Field(default=5, ge=0, le=20)
    columns: list[str] | None = Field(default=None, max_length=64)


class AnalyzeCsvTool:
    def __init__(self) -> None:
        self._spec = ToolSpec(
            name="analyze_csv",
            description=(
                "Profile tabular data: row and column counts, dtypes, null counts, "
                "numeric summaries (count, mean, min, max, std, sum), top categorical "
                "values and an optional preview. Runs a fixed reviewed script in the "
                "sandbox, so it executes no generated code and needs no approval. Use "
                "this before quoting any figure derived from a table."
            ),
            permission=Permission.DOCUMENTS_READ,
            risk=RiskLevel.COMPUTE,
            limits=ResourceLimits(timeout_seconds=120.0),
            sandboxed=True,
            capabilities=["tabular", "statistics"],
            latency_class=3,
            cost_class=2,
            input_schema=AnalyzeCsvArguments.model_json_schema(),
            output_schema={"type": "object", "properties": {"profile": {"type": "object"}}},
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    @property
    def arguments_model(self) -> type[BaseModel]:
        return AnalyzeCsvArguments

    async def run(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, AnalyzeCsvArguments)
        if context.sandbox is None:
            raise ToolUnavailable(_NO_SANDBOX)

        options: dict[str, Any] = {
            "delimiter": arguments.delimiter,
            "has_header": arguments.has_header,
            "max_preview_rows": arguments.max_preview_rows,
            "columns": list(arguments.columns) if arguments.columns else None,
        }
        policy_error, unavailable = _sandbox_errors()
        try:
            execution = await context.sandbox.run_python(
                _PROFILE_SCRIPT,
                job_id=context.job_id,
                inputs={"data.csv": arguments.csv_text, "options.json": json.dumps(options)},
            )
        except policy_error as exc:
            raise ToolArgumentError(str(exc)) from exc
        except unavailable as exc:
            raise ToolUnavailable(str(exc)) from exc

        if not execution.get("ok"):
            tail = (execution.get("stderr") or "").strip().splitlines()
            raise ToolError(
                "the data could not be profiled: "
                + (tail[-1] if tail else str(execution.get("error") or "no output"))
            )

        try:
            profile = json.loads((execution.get("stdout") or "").strip().splitlines()[-1])
        except (ValueError, IndexError) as exc:
            raise ToolError("the profiling script produced no parseable report") from exc

        return ToolResult(
            tool=self._spec.name,
            output={"profile": profile},
            sandbox_execution_id=execution.get("execution_id"),
        )
