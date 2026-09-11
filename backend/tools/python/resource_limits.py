"""Resource limits for sandboxed execution.

Limits arrive from two places - the tool's declared
:class:`~backend.tools.base.ResourceLimits` and the deployment's sandbox
policy. They are combined by taking the **stricter** of the two on every
axis. A tool may lower its own ceiling; it can never raise the one the
deployment set, which is what stops a permissive tool declaration from
quietly widening the blast radius.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.tools.base import ResourceLimits

#: Absolute ceilings, applied even if both sources ask for more.
HARD_TIMEOUT_SECONDS = 600
HARD_MEMORY_MIB = 4096
HARD_OUTPUT_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class EffectiveLimits:
    """The limits actually applied to one execution."""

    timeout_seconds: int
    max_output_bytes: int
    cpu_millicores: int
    memory_mib: int
    max_artifact_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeoutSeconds": self.timeout_seconds,
            "maxOutputBytes": self.max_output_bytes,
            "cpuMillicores": self.cpu_millicores,
            "memoryMib": self.memory_mib,
            "maxArtifactBytes": self.max_artifact_bytes,
        }

    def describe(self) -> str:
        return (
            f"{self.timeout_seconds}s, {self.memory_mib} MiB, "
            f"{self.cpu_millicores}m CPU, {self.max_output_bytes} B output"
        )


def _stricter(left: int, right: int | None) -> int:
    if right is None:
        return left
    return min(int(left), int(right))


def resolve(
    declared: ResourceLimits | None = None, *, policy_limits: dict[str, Any] | None = None
) -> EffectiveLimits:
    """Combine tool-declared limits with the deployment policy.

    ``policy_limits`` accepts the mapping produced by
    :meth:`backend.sandbox.policy.SandboxPolicy.resource_limits`, whose values
    may be strings; non-numeric entries are ignored rather than crashing an
    execution over a formatting difference.
    """
    base = declared or ResourceLimits()
    policy = policy_limits or {}

    def from_policy(*names: str) -> int | None:
        for name in names:
            raw = policy.get(name)
            if raw is None:
                continue
            try:
                return int(float(str(raw).rstrip("m").rstrip("MiB").strip()))
            except (TypeError, ValueError):
                continue
        return None

    return EffectiveLimits(
        timeout_seconds=min(
            _stricter(getattr(base, "timeout_seconds", 60), from_policy("timeout_seconds", "timeout")),
            HARD_TIMEOUT_SECONDS,
        ),
        max_output_bytes=min(
            _stricter(getattr(base, "max_output_bytes", 256_000), from_policy("max_output_bytes")),
            HARD_OUTPUT_BYTES,
        ),
        cpu_millicores=_stricter(
            getattr(base, "cpu_millicores", 500), from_policy("cpu_millicores", "cpu")
        ),
        memory_mib=min(
            _stricter(getattr(base, "memory_mib", 512), from_policy("memory_mib", "memory")),
            HARD_MEMORY_MIB,
        ),
        max_artifact_bytes=_stricter(
            getattr(base, "max_artifact_bytes", 25 * 1024 * 1024), from_policy("max_artifact_bytes")
        ),
    )


__all__ = [
    "EffectiveLimits",
    "HARD_MEMORY_MIB",
    "HARD_OUTPUT_BYTES",
    "HARD_TIMEOUT_SECONDS",
    "resolve",
]
