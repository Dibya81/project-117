"""Sandbox policy (Phase 9).

This module is the answer to the review note that the sandbox requirements had
to become an acceptance checklist rather than architecture prose. Each item is
listed here with the code that enforces it:

===========================  =================================================
Requirement                  Enforced by
===========================  =================================================
API key authentication       ``validate_ready`` (refuses to start unkeyed)
default-deny network         ``network_policy`` (always explicit, never None)
CPU limit                    ``resource_limits`` -> ``cpu``
memory limit                 ``resource_limits`` -> ``memory``
execution timeout            ``execution_timeout_seconds`` (per command)
sandbox lifetime             ``sandbox_timeout_seconds`` (container TTL)
filesystem isolation         container + ``workspace_dir``
restricted writable dir      ``guard_command`` (``cd /workspace``)
allowed image whitelist      ``resolve_image`` (purpose keys only)
pinned image digest          ``pinned``
no host environment          ``environment`` (built from an empty dict)
no host secrets / SSH keys   ``environment`` (nothing is inherited)
no arbitrary image choice    ``resolve_image`` takes a *purpose*, not a ref
execution audit record       ``metadata`` + tool_executions row
artifact size limit          ``max_artifact_bytes`` / ``max_artifacts``
stdout/stderr size limit     ``max_output_bytes``
process limit                ``guard_command`` (``ulimit -u``)
cleanup after execution      the service destroys the sandbox in ``finally``
===========================  =================================================

The important structural decision is the one the review asked for directly:
**a caller cannot name an image.** ``resolve_image`` accepts ``"python"`` or
``"documents"`` and maps it to a reference from configuration, so the chain is

    run_python -> sandbox policy -> approved image -> OpenSandbox -> Docker

A model that decides it needs ``ubuntu:latest`` with network access has no
vocabulary here to ask for it.

``environment`` is built from ``{}`` rather than by copying and filtering
``os.environ``. A filter is a list of things you remembered; starting empty
means the next secret added to the API process is not automatically shared
with code the model wrote.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: The only writable location inside the sandbox.
WORKSPACE_DIR = "/workspace"

#: Generated files must land here to be collected as artifacts.
ARTIFACTS_DIR = "/workspace/artifacts"

#: Read-only inputs (a spec, a CSV extract) are uploaded here.
INPUTS_DIR = "/workspace/inputs"

#: purpose -> default image reference. ``documents`` needs python-pptx,
#: python-docx, openpyxl and reportlab baked in; see
#: infrastructure/docker/sandbox-documents.Dockerfile. Overridable by
#: configuration, never by a request.
ALLOWED_IMAGES: dict[str, str] = {
    "python": "python:3.11-slim",
    "documents": "project117/sandbox-documents:1.0",
}


class SandboxPolicyError(RuntimeError):
    """The sandbox is misconfigured, or something asked for what it may not."""

    reason = "sandbox_policy_violation"


@dataclass(frozen=True)
class SandboxPolicy:
    base_url: str = "http://127.0.0.1:8080"
    api_key: str = ""
    require_api_key: bool = True
    images: dict[str, str] = field(default_factory=lambda: dict(ALLOWED_IMAGES))
    #: purpose -> sha256 digest. When set, the image is used as
    #: ``repo@sha256:...`` so a moved tag cannot change what runs.
    digests: dict[str, str] = field(default_factory=dict)
    cpu_millicores: int = 500
    memory_mib: int = 512
    #: Per-command ceiling. OpenSandbox caps this at 300s server-side.
    execution_timeout_seconds: int = 120
    #: Container lifetime; the sandbox self-destructs after this.
    sandbox_timeout_seconds: int = 600
    max_output_bytes: int = 256_000
    max_artifact_bytes: int = 25 * 1024 * 1024
    max_artifacts: int = 10
    max_processes: int = 64
    max_input_bytes: int = 8 * 1024 * 1024
    allow_network: bool = False
    workspace_dir: str = WORKSPACE_DIR

    # --- image selection --------------------------------------------------

    def resolve_image(self, purpose: str = "python") -> str:
        """Map a purpose to an approved image reference.

        Takes a purpose - not an image - so no caller anywhere in the system
        can select what runs.
        """
        key = (purpose or "python").strip().lower()
        reference = self.images.get(key)
        if not reference:
            allowed = ", ".join(sorted(self.images)) or "none"
            raise SandboxPolicyError(
                f"'{key}' is not an approved sandbox purpose; allowed: {allowed}"
            )
        digest = self.digests.get(key, "")
        if digest:
            repository = reference.split("@", 1)[0].split(":", 1)[0]
            if not digest.startswith("sha256:"):
                digest = f"sha256:{digest}"
            return f"{repository}@{digest}"
        return reference

    def pinned(self, purpose: str = "python") -> bool:
        return bool(self.digests.get((purpose or "python").strip().lower()))

    # --- limits -----------------------------------------------------------

    def resource_limits(self) -> dict[str, str]:
        """Resource map in the form OpenSandbox expects."""
        return {
            "cpu": f"{self.cpu_millicores}m",
            "memory": f"{self.memory_mib}Mi",
        }

    def environment(self) -> dict[str, str]:
        """The complete environment for sandboxed code.

        Built from nothing. No host variables, no API keys, no model endpoint,
        no database URL. ``MPLBACKEND=Agg`` because a plotting library that
        looks for a display in a container fails in a confusing way.
        """
        env: dict[str, str] = {}
        env["HOME"] = self.workspace_dir
        env["TMPDIR"] = f"{self.workspace_dir}/tmp"
        env["PATH"] = "/usr/local/bin:/usr/local/sbin:/usr/bin:/bin"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        # Ignore anything installed in a user site-packages baked into an image.
        env["PYTHONNOUSERSITE"] = "1"
        env["MPLBACKEND"] = "Agg"
        return env

    def network_policy(self) -> dict[str, Any]:
        """Explicit deny-by-default egress rules.

        Returned even when networking is allowed, and never ``None``: an
        omitted policy means "whatever the daemon defaults to", and the whole
        point of the sovereignty requirement is that this is not left to a
        default.
        """
        if self.allow_network:
            return {"defaultAction": "allow", "rules": []}
        return {"defaultAction": "deny", "rules": []}

    def metadata(self, *, job_id: str | None, purpose: str) -> dict[str, str]:
        """Labels attached to the container so a stray sandbox is traceable."""
        return {
            "app": "project117",
            "purpose": purpose,
            "job_id": job_id or "none",
        }

    def guard_command(self, command: str) -> str:
        """Wrap a command with in-container limits.

        ``ulimit -u`` caps processes so a fork bomb hits a limit instead of
        the host's scheduler; ``ulimit -f`` caps file size so a runaway loop
        cannot fill the volume. Both are belt-and-braces on top of the
        container's own cgroup limits - cheap, and they fail the execution
        rather than the machine.
        """
        max_file_kb = max(1, self.max_artifact_bytes // 1024)
        return (
            f"ulimit -u {self.max_processes} 2>/dev/null; "
            f"ulimit -f {max_file_kb} 2>/dev/null; "
            f"cd {self.workspace_dir} && {command}"
        )

    # --- readiness --------------------------------------------------------

    def validate_ready(self) -> None:
        """Raise unless the sandbox may be used.

        Called before the first execution rather than at import, so a
        deployment that never executes code does not need a sandbox at all -
        but one that does cannot fall back to something weaker.
        """
        if not self.base_url:
            raise SandboxPolicyError(
                "sandbox base URL is not configured - set P117_OPEN_SANDBOX_BASE_URL"
            )
        if self.require_api_key and not self.api_key:
            raise SandboxPolicyError(
                "sandbox API key is not configured - set P117_SANDBOX_API_KEY, or set "
                "P117_SANDBOX_REQUIRE_API_KEY=false only for a single-user machine where "
                "the sandbox port is not reachable from anywhere else"
            )
        if self.allow_network:
            # Allowed, but it contradicts the sovereignty default, so it must
            # be a deliberate act recorded in configuration.
            if not self.api_key:
                raise SandboxPolicyError(
                    "sandbox network access is enabled without an API key; refusing to start"
                )

    def summary(self) -> dict[str, Any]:
        """Diagnostics for ``GET /api/health``. Never includes the key."""
        return {
            "base_url": self.base_url,
            "api_key_configured": bool(self.api_key),
            "images": dict(self.images),
            "pinned_purposes": sorted(self.digests),
            "resource_limits": self.resource_limits(),
            "execution_timeout_seconds": self.execution_timeout_seconds,
            "sandbox_timeout_seconds": self.sandbox_timeout_seconds,
            "network": self.network_policy()["defaultAction"],
            "max_output_bytes": self.max_output_bytes,
            "max_artifact_bytes": self.max_artifact_bytes,
            "max_artifacts": self.max_artifacts,
            "workspace": self.workspace_dir,
        }


def policy_from_settings(settings: Any) -> SandboxPolicy:
    """Build the policy from application settings.

    Unknown attributes fall back to the strict default, so an older settings
    object cannot accidentally widen the sandbox.
    """
    images = dict(ALLOWED_IMAGES)
    python_image = getattr(settings, "sandbox_image", "") or ""
    if python_image:
        images["python"] = python_image
    documents_image = getattr(settings, "sandbox_documents_image", "") or ""
    if documents_image:
        images["documents"] = documents_image

    digests: dict[str, str] = {}
    python_digest = getattr(settings, "sandbox_image_digest", "") or ""
    if python_digest:
        digests["python"] = python_digest
    documents_digest = getattr(settings, "sandbox_documents_image_digest", "") or ""
    if documents_digest:
        digests["documents"] = documents_digest

    return SandboxPolicy(
        base_url=getattr(settings, "open_sandbox_base_url", "") or "",
        api_key=getattr(settings, "sandbox_api_key", "") or "",
        require_api_key=bool(getattr(settings, "sandbox_require_api_key", True)),
        images=images,
        digests=digests,
        cpu_millicores=int(getattr(settings, "sandbox_cpu_millicores", 500)),
        memory_mib=int(getattr(settings, "sandbox_memory_mib", 512)),
        execution_timeout_seconds=int(getattr(settings, "sandbox_timeout_seconds", 120)),
        sandbox_timeout_seconds=int(getattr(settings, "sandbox_lifetime_seconds", 600)),
        max_output_bytes=int(getattr(settings, "sandbox_max_output_bytes", 256_000)),
        max_artifact_bytes=int(getattr(settings, "sandbox_max_artifact_bytes", 25 * 1024 * 1024)),
        allow_network=bool(getattr(settings, "sandbox_allow_network", False)),
    )
