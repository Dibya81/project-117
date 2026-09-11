"""Sandbox security surface.

The sandbox itself -- client, policy and service -- lives in
:mod:`backend.sandbox`, next to the code that runs executions. This package
exists because sandboxing is a security control, and a reviewer auditing
``backend/security`` should find it addressed here rather than have to know
it lives elsewhere.

What is re-exported is the *policy* half: the rules about what may run, which
images are permitted, and where inputs and artifacts are allowed to live. The
execution half (:class:`~backend.sandbox.service.SandboxService`) is
deliberately not re-exported, because reaching for an executor through the
security package is the wrong direction -- security constrains execution, it
does not provide it.
"""

from __future__ import annotations

from typing import Any

from backend.sandbox.policy import (
    ALLOWED_IMAGES,
    ARTIFACTS_DIR,
    INPUTS_DIR,
    WORKSPACE_DIR,
    SandboxPolicy,
    SandboxPolicyError,
    policy_from_settings,
)


def describe(policy: SandboxPolicy) -> dict[str, Any]:
    """Non-sensitive summary of the sandbox constraints in force.

    Base URLs and API keys are deliberately absent: this is rendered in the
    Admin security view, and a sandbox endpoint is a credentialed internal
    address.
    """
    return {
        "workspace_dir": WORKSPACE_DIR,
        "inputs_dir": INPUTS_DIR,
        "artifacts_dir": ARTIFACTS_DIR,
        "allowed_images": sorted(ALLOWED_IMAGES),
        "network": "disabled inside the sandbox",
        "operations": ["run_python", "render_artifact"],
        "binary_inputs": False,
    }


__all__ = [
    "ALLOWED_IMAGES",
    "ARTIFACTS_DIR",
    "INPUTS_DIR",
    "WORKSPACE_DIR",
    "SandboxPolicy",
    "SandboxPolicyError",
    "describe",
    "policy_from_settings",
]
