"""Sandbox operations used by tools (Phase 9 + Phase 10).

Two operations, because they are the only two the product needs:

``run_python``
    Execute model-authored Python and return its output. Used for analysis and
    for testing generated code before its result is trusted.

``render_artifact``
    Upload a validated :class:`~backend.deliverables.spec.ArtifactSpec` as
    JSON plus one of the reviewed generator scripts, run it, and read the
    produced file back out.

The second one is where the artifact-integrity requirement is met. The model
never writes file-generation code; it writes a spec. The generator that renders
it is a static file in this repository that was reviewed once. The bytes are
hashed as they leave the sandbox, so the sha256 recorded against the artifact
belongs to exactly the bytes that were produced - not to a file that was
re-read from disk later and might have changed.

The code is written to a file inside the sandbox and executed as a script,
rather than passed through ``python -c``. A heredoc or ``-c`` string requires
escaping model output into a shell command line, and getting that wrong is a
command injection in the one place where the input is explicitly untrusted.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from backend.sandbox.client import OpenSandboxClient, SandboxExecution, SandboxUnavailable
from backend.sandbox.policy import ARTIFACTS_DIR, INPUTS_DIR, SandboxPolicy, SandboxPolicyError

logger = logging.getLogger(__name__)

#: Local directory holding the reviewed generator scripts.
_GENERATORS_DIR = Path(__file__).resolve().parent.parent / "deliverables" / "generators"

#: Artifact type -> generator script filename.
_GENERATORS = {
    "pptx": "pptx_generator.py",
    "docx": "docx_generator.py",
    "xlsx": "xlsx_generator.py",
    "pdf": "pdf_generator.py",
}

#: Extension used for the produced file.
_EXTENSIONS = {"pptx": ".pptx", "docx": ".docx", "xlsx": ".xlsx", "pdf": ".pdf"}


class SandboxService:
    def __init__(
        self,
        policy: SandboxPolicy,
        *,
        client: OpenSandboxClient | None = None,
    ) -> None:
        self._policy = policy
        self._client = client or OpenSandboxClient(policy)

    @property
    def policy(self) -> SandboxPolicy:
        return self._policy

    def summary(self) -> dict[str, Any]:
        return self._policy.summary()

    # --- code execution ---------------------------------------------------

    async def run_python(
        self,
        code: str,
        *,
        job_id: str | None = None,
        timeout_seconds: float | None = None,
        inputs: dict[str, str] | None = None,
        collect_artifacts: bool = False,
    ) -> dict[str, Any]:
        """Run Python in a fresh sandbox.

        ``inputs`` maps filename -> text content, written under
        ``/workspace/inputs``. Data goes in as files, never interpolated into
        the source, so a CSV extract containing quotes cannot break the script
        that reads it.
        """
        if not code or not code.strip():
            raise SandboxPolicyError("no code was supplied to run")

        async with self._client.session(purpose="python", job_id=job_id) as session:
            for name, content in (inputs or {}).items():
                safe_name = Path(name).name  # no traversal out of inputs/
                await session.write_text(f"{INPUTS_DIR}/{safe_name}", content)

            script_path = f"{self._policy.workspace_dir}/main.py"
            await session.write_text(script_path, code)
            execution = await session.run(
                f"python3 {script_path}", timeout_seconds=timeout_seconds
            )

            files: list[str] = []
            if collect_artifacts:
                files = await session.list_artifacts()
            execution.files = files
            return execution.to_dict()

    # --- artifact rendering ----------------------------------------------

    async def render_artifact(
        self,
        *,
        artifact_type: str,
        spec: dict[str, Any],
        filename: str,
        job_id: str | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        """Render a spec into a file and return the bytes plus their sha256.

        Returns ``{"bytes", "sha256", "size_bytes", "filename", "execution"}``.
        The caller (``ArtifactService``) is responsible for storing it; this
        method deliberately has no access to the host filesystem.
        """
        kind = (artifact_type or "").strip().lower()
        script_name = _GENERATORS.get(kind)
        if script_name is None:
            raise SandboxPolicyError(
                f"'{artifact_type}' is not a supported artifact type; "
                f"supported: {', '.join(sorted(_GENERATORS))}"
            )

        script_source = _GENERATORS_DIR / script_name
        try:
            generator_code = script_source.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - packaging problem
            raise SandboxUnavailable(
                f"generator script {script_name} is missing from the installation"
            ) from exc

        safe_name = Path(filename).name or f"artifact{_EXTENSIONS[kind]}"
        if not safe_name.lower().endswith(_EXTENSIONS[kind]):
            safe_name += _EXTENSIONS[kind]
        output_path = f"{ARTIFACTS_DIR}/{safe_name}"

        # 'documents' is a distinct approved purpose: that image has
        # python-pptx, python-docx, openpyxl and reportlab baked in, because
        # the sandbox has no network and cannot pip install them.
        async with self._client.session(purpose="documents", job_id=job_id) as session:
            spec_path = f"{INPUTS_DIR}/spec.json"
            await session.write_text(
                spec_path, json.dumps(spec, ensure_ascii=False, default=str)
            )
            script_path = f"{self._policy.workspace_dir}/generate.py"
            await session.write_text(script_path, generator_code)

            execution: SandboxExecution = await session.run(
                f"python3 {script_path} --spec {spec_path} --out {output_path}",
                timeout_seconds=timeout_seconds,
            )
            if not execution.ok:
                detail = execution.stderr.strip() or execution.error or "no error output"
                return {
                    "ok": False,
                    "filename": safe_name,
                    "execution": execution.to_dict(),
                    "error": f"the {kind} generator failed: {detail}",
                }

            data = await session.read_bytes(output_path)
            digest = hashlib.sha256(data).hexdigest()
            execution.files = [safe_name]
            return {
                "ok": True,
                "bytes": data,
                "sha256": digest,
                "size_bytes": len(data),
                "filename": safe_name,
                "execution": execution.to_dict(),
            }
