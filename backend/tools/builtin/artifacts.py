"""Artifact tools (Phase 8 + Phase 10).

Four tools, one implementation, distinguished only by output type. Each takes
a **content spec** - titles, bullets, sections, sheet rows, citations - and
never code. :class:`backend.deliverables.ArtifactService` renders it with a
reviewed generator inside the documents sandbox image.

Why these are ``write`` risk and not ``execute`` risk, even though a container
starts: the code that runs is a fixed generator script shipped with the
backend, not model output. The model's contribution is validated data. Gating
report generation behind a human would make the product useless for its main
use case; gating *arbitrary code* is the thing that actually matters, and
``run_python`` carries that gate. This mirrors the approval table from the
review - generate report auto, execute code approval.

One behaviour worth stating: if the artifact's own verification comes back
rejected, the tool returns ``status="error"`` while still reporting the
artifact id. The file exists and is traceable, but the agent is told plainly
that it did not pass, so it can fix the spec and re-render instead of
presenting a broken deck as finished work.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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

_SPEC_HELP = {
    "pptx": (
        "Provide 'spec' with title, optional subtitle, and 'slides': each slide has a "
        "title and up to 8 bullets, each bullet with text and citations "
        "(document_id, page, section, chunk_id)."
    ),
    "docx": (
        "Provide 'spec' with title and 'sections': each section has a heading, level, "
        "paragraphs and bullets, each bullet with citations "
        "(document_id, page, section, chunk_id)."
    ),
    "xlsx": (
        "Provide 'spec' with title and 'sheets': each sheet has a name, 'columns' and "
        "'rows' of plain values. Values only - the generator writes no formulas."
    ),
    "pdf": (
        "Provide 'spec' with title and 'sections' (heading, level, paragraphs, bullets "
        "with citations). Rendered as a paginated report."
    ),
}


class ArtifactArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: An ArtifactSpec payload. Validated by backend.deliverables.spec, which
    #: enforces the per-type limits, so an over-stuffed slide fails before a
    #: container is started.
    spec: dict[str, Any]
    #: Optional filename hint; slugified, and the extension always comes from
    #: the artifact type rather than from this value.
    filename: str | None = Field(default=None, max_length=120)


class _CreateArtifactTool:
    artifact_type = ""
    tool_name = ""

    def __init__(self) -> None:
        kind = self.artifact_type
        self._spec = ToolSpec(
            name=self.tool_name,
            description=(
                f"Create a {kind.upper()} file from a structured content specification. "
                f"{_SPEC_HELP[kind]} Cite evidence for every substantive claim: citations "
                "are rendered into the file and checked afterwards. The file is built by a "
                "reviewed generator in an isolated container, hashed, stored and verified."
            ),
            permission=Permission.ARTIFACTS_WRITE,
            risk=RiskLevel.WRITE,
            limits=ResourceLimits(timeout_seconds=300.0),
            sandboxed=True,
            capabilities=["artifact", kind],
            latency_class=4,
            cost_class=3,
            input_schema=ArtifactArguments.model_json_schema(),
            output_schema={
                "type": "object",
                "properties": {
                    "artifact_id": {"type": "string"},
                    "filename": {"type": "string"},
                    "size_bytes": {"type": "integer"},
                    "sha256": {"type": "string"},
                    "verification_status": {"type": "string"},
                },
            },
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    @property
    def arguments_model(self) -> type[BaseModel]:
        return ArtifactArguments

    async def run(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, ArtifactArguments)
        if context.artifacts is None:
            raise ToolUnavailable(
                "artifact generation is unavailable: no artifact service is configured "
                "(it requires the sandbox and the documents image)"
            )

        from backend.deliverables import ArtifactError, ArtifactSpecInvalid

        try:
            record = await context.artifacts.generate(
                spec=arguments.spec,
                artifact_type=self.artifact_type,
                job_id=context.job_id,
                user=context.user,
                filename=arguments.filename,
            )
        except ArtifactSpecInvalid as exc:
            # A spec problem is the planner's to fix, so it surfaces as an
            # argument error rather than a generic failure.
            raise ToolArgumentError(str(exc)) from exc
        except ArtifactError as exc:
            raise ToolError(str(exc)) from exc

        status = record.get("verification_status")
        verification = record.get("verification") or {}
        failed = status == "rejected"
        return ToolResult(
            tool=self._spec.name,
            status="error" if failed else "ok",
            output={
                "artifact_id": record["artifact_id"],
                "type": record["type"],
                "filename": record["filename"],
                "size_bytes": record["size_bytes"],
                "sha256": record["sha256"],
                "verification_status": status,
                "verification": {
                    "status": verification.get("status"),
                    "counts": verification.get("counts"),
                    "checks": [
                        {
                            "checker": check.get("checker"),
                            "status": check.get("status"),
                            "message": check.get("message"),
                        }
                        for check in (verification.get("checks") or [])
                    ],
                },
                "content_units": (record.get("spec") or {}).get("content_units"),
                "citations": (record.get("spec") or {}).get("citations"),
            },
            error=(
                f"the {self.artifact_type} was created but failed verification; "
                "fix the spec and render it again"
                if failed
                else None
            ),
            sandbox_execution_id=record.get("sandbox_execution_id"),
            artifact_ids=[record["artifact_id"]],
        )


class CreatePptxTool(_CreateArtifactTool):
    artifact_type = "pptx"
    tool_name = "create_pptx"


class CreateDocxTool(_CreateArtifactTool):
    artifact_type = "docx"
    tool_name = "create_docx"


class CreateXlsxTool(_CreateArtifactTool):
    artifact_type = "xlsx"
    tool_name = "create_xlsx"


class CreatePdfTool(_CreateArtifactTool):
    artifact_type = "pdf"
    tool_name = "create_pdf"
