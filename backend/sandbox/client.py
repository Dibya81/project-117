"""Thin, policy-enforcing wrapper around the vendored OpenSandbox SDK (Phase 9).

Why a wrapper and not a second sandbox: OpenSandbox already does the hard part
- container lifecycle, an in-container exec daemon, a filesystem API, egress
policy. Reimplementing that would mean maintaining our own container escape
surface. What it does *not* do is refuse to run whatever it is told, so this
module is the choke point where :class:`~backend.sandbox.policy.SandboxPolicy`
becomes non-optional.

Every execution therefore looks like this and cannot look like anything else::

    run_python -> SandboxService -> OpenSandboxClient -> policy
               -> approved image -> OpenSandbox -> Docker

Specifics that matter:

* The image comes from ``policy.resolve_image(purpose)``. This module has no
  parameter for an image reference, so no caller - and no model - can pick one.
* ``env`` is ``policy.environment()``, which is built from an empty dict. The
  host's environment is never inherited, so the model endpoint, the database
  URL and any API key stay on the host side.
* ``network_policy`` is always sent explicitly, default-deny. An omitted policy
  would mean "whatever the daemon defaults to", which is exactly the ambiguity
  the sovereignty requirement exists to remove.
* The sandbox is destroyed in a ``finally``. A leaked container is a leaked
  copy of confidential data, so cleanup is not conditional on success.
* stdout/stderr are truncated to the policy limit. Unbounded output from
  model-authored code is a memory exhaustion vector on the *host*, not in the
  container.

The SDK is imported lazily. The backend must start, serve ``/health`` and
answer document questions on a machine where the sandbox has never been
installed; only code execution should fail there, and it fails with
:class:`SandboxUnavailable` rather than an ``ImportError`` at startup.
"""

from __future__ import annotations

import contextlib
import logging
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, AsyncIterator
from urllib.parse import urlsplit

from backend.sandbox.policy import (
    ARTIFACTS_DIR,
    INPUTS_DIR,
    SandboxPolicy,
    SandboxPolicyError,
)

logger = logging.getLogger(__name__)


class SandboxUnavailable(RuntimeError):
    """The sandbox cannot be used: not installed, not configured, unreachable.

    Deliberately distinct from a failed execution. This one is an operator
    problem and is never retried by the recovery manager.
    """

    reason = "sandbox_unavailable"


@dataclass
class SandboxExecution:
    """The result of one command. Note what is absent: no host paths."""

    execution_id: str | None
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    truncated: bool = False
    duration_ms: float = 0.0
    error: str | None = None
    image: str = ""
    files: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None and (self.exit_code == 0 or self.exit_code is None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "truncated": self.truncated,
            "duration_ms": round(self.duration_ms, 1),
            "error": self.error,
            "image": self.image,
            "files": list(self.files),
            "ok": self.ok,
        }


def _load_sdk() -> dict[str, Any]:
    """Import the vendored SDK, or explain why code execution is unavailable."""
    try:
        from opensandbox import Sandbox
        from opensandbox.config import ConnectionConfig
        from opensandbox.models.execd import RunCommandOpts
        from opensandbox.models.sandboxes import NetworkPolicy, NetworkRule
    except ImportError as exc:  # pragma: no cover - depends on the install
        raise SandboxUnavailable(
            "the OpenSandbox SDK is not installed, so code execution and artifact "
            "generation are unavailable. Install it from the vendored copy: "
            "`uv sync` picks up OpenSandbox-main/sdks/sandbox/python via "
            "[tool.uv.sources]. Document questions and retrieval are unaffected."
        ) from exc
    return {
        "Sandbox": Sandbox,
        "ConnectionConfig": ConnectionConfig,
        "RunCommandOpts": RunCommandOpts,
        "NetworkPolicy": NetworkPolicy,
        "NetworkRule": NetworkRule,
    }


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text.encode("utf-8", errors="ignore")) <= limit:
        return text, False
    clipped = text.encode("utf-8", errors="ignore")[:limit].decode("utf-8", errors="ignore")
    return clipped + f"\n...[output truncated at {limit} bytes]", True


def _messages_to_text(messages: Any) -> str:
    parts = []
    for message in messages or []:
        text = getattr(message, "text", None)
        if text:
            parts.append(str(text))
    return "".join(parts)


class SandboxSession:
    """A live sandbox. Obtained from :meth:`OpenSandboxClient.session`.

    Not constructed directly, because a session that was not created through
    the client would not have had the policy applied to it.
    """

    def __init__(self, sandbox: Any, policy: SandboxPolicy, sdk: dict[str, Any], image: str):
        self._sandbox = sandbox
        self._policy = policy
        self._sdk = sdk
        self._image = image

    @property
    def image(self) -> str:
        return self._image

    async def prepare(self) -> None:
        """Create the workspace directories the generators expect."""
        await self.run(f"mkdir -p {ARTIFACTS_DIR} {INPUTS_DIR} {self._policy.workspace_dir}/tmp")

    async def run(self, command: str, *, timeout_seconds: float | None = None) -> SandboxExecution:
        """Run one shell command under the policy's limits."""
        run_opts = self._sdk["RunCommandOpts"]
        limit = float(timeout_seconds or self._policy.execution_timeout_seconds)
        limit = min(limit, float(self._policy.execution_timeout_seconds))
        started = time.perf_counter()
        try:
            execution = await self._sandbox.commands.run(
                self._policy.guard_command(command),
                opts=run_opts(
                    working_directory=self._policy.workspace_dir,
                    timeout=timedelta(seconds=limit),
                ),
            )
        except Exception as exc:
            raise SandboxUnavailable(f"the sandbox refused the command: {exc}") from exc

        duration = (time.perf_counter() - started) * 1000
        logs = getattr(execution, "logs", None)
        stdout, out_clipped = _truncate(
            _messages_to_text(getattr(logs, "stdout", None)), self._policy.max_output_bytes
        )
        stderr, err_clipped = _truncate(
            _messages_to_text(getattr(logs, "stderr", None)), self._policy.max_output_bytes
        )
        failure = getattr(execution, "error", None)
        error = None
        if failure is not None:
            error = f"{getattr(failure, 'name', 'error')}: {getattr(failure, 'value', '')}"

        return SandboxExecution(
            execution_id=getattr(execution, "id", None),
            exit_code=getattr(execution, "exit_code", None),
            stdout=stdout,
            stderr=stderr,
            truncated=out_clipped or err_clipped,
            duration_ms=duration,
            error=error,
            image=self._image,
        )

    async def write_text(self, path: str, content: str) -> None:
        """Upload a text file (a script, or a JSON spec) into the sandbox."""
        payload = content.encode("utf-8")
        if len(payload) > self._policy.max_input_bytes:
            raise SandboxPolicyError(
                f"input for {path} is {len(payload)} bytes, over the "
                f"{self._policy.max_input_bytes} byte limit"
            )
        try:
            await self._sandbox.files.write_file(path, content, mode=644)
        except Exception as exc:
            raise SandboxUnavailable(f"could not write {path} into the sandbox: {exc}") from exc

    async def read_bytes(self, path: str) -> bytes:
        """Read a generated file out of the sandbox, enforcing the size cap."""
        try:
            data = await self._sandbox.files.read_bytes(
                path, limit=self._policy.max_artifact_bytes + 1
            )
        except Exception as exc:
            raise SandboxUnavailable(f"could not read {path} from the sandbox: {exc}") from exc
        if len(data) > self._policy.max_artifact_bytes:
            raise SandboxPolicyError(
                f"{path} is larger than the {self._policy.max_artifact_bytes} byte "
                "artifact limit and was discarded"
            )
        return data

    async def list_artifacts(self) -> list[str]:
        """Filenames present in the artifacts directory.

        Uses ``ls`` rather than the filesystem API so the result is a plain
        list of names regardless of SDK entry shapes.
        """
        listing = await self.run(f"ls -1 {ARTIFACTS_DIR} 2>/dev/null || true")
        return [line.strip() for line in listing.stdout.splitlines() if line.strip()]


class OpenSandboxClient:
    def __init__(self, policy: SandboxPolicy) -> None:
        self._policy = policy

    @property
    def policy(self) -> SandboxPolicy:
        return self._policy

    @contextlib.asynccontextmanager
    async def session(
        self,
        *,
        purpose: str = "python",
        job_id: str | None = None,
    ) -> AsyncIterator[SandboxSession]:
        """Create a sandbox, yield it, and always destroy it.

        One sandbox per execution. Reuse would be faster and would also mean
        one job's model-authored code could read the previous job's documents
        out of ``/workspace``.
        """
        self._policy.validate_ready()
        sdk = _load_sdk()
        image = self._policy.resolve_image(purpose)

        split = urlsplit(self._policy.base_url)
        if not split.netloc:
            raise SandboxPolicyError(
                f"sandbox base URL '{self._policy.base_url}' is not a valid URL"
            )
        config = sdk["ConnectionConfig"](
            api_key=self._policy.api_key or None,
            domain=split.netloc,
            protocol=split.scheme or "http",
            request_timeout=timedelta(seconds=30),
        )

        policy_dict = self._policy.network_policy()
        network_policy = sdk["NetworkPolicy"](
            default_action=policy_dict["defaultAction"],
            egress=[
                sdk["NetworkRule"](action=rule["action"], target=rule["target"])
                for rule in policy_dict.get("rules", [])
            ]
            or None,
        )

        sandbox = None
        try:
            try:
                sandbox = await sdk["Sandbox"].create(
                    image,
                    timeout=timedelta(seconds=self._policy.sandbox_timeout_seconds),
                    env=self._policy.environment(),
                    metadata=self._policy.metadata(job_id=job_id, purpose=purpose),
                    resource=self._policy.resource_limits(),
                    network_policy=network_policy,
                    connection_config=config,
                )
            except Exception as exc:
                raise SandboxUnavailable(
                    f"could not start a sandbox from '{image}': {exc}. Check that the "
                    "OpenSandbox server is running and that the image exists locally."
                ) from exc

            session = SandboxSession(sandbox, self._policy, sdk, image)
            await session.prepare()
            yield session
        finally:
            if sandbox is not None:
                # Never conditional: a surviving container holds a copy of
                # whatever was uploaded into it.
                try:
                    await sandbox.destroy()
                except Exception:
                    logger.warning(
                        "failed to destroy sandbox for job %s; it will expire after %ss",
                        job_id,
                        self._policy.sandbox_timeout_seconds,
                        exc_info=True,
                    )
