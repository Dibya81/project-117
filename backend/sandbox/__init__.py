"""Sandboxed execution (Phase 9).

The rule this package exists to enforce: **model-authored code never runs on
the host.** Everything else here - image whitelisting, digest pinning,
default-deny egress, output caps, workspace isolation - exists to make that
rule hold even when a caller is careless.

Entry points:

* :class:`SandboxPolicy` - the limits, loaded from settings once at startup.
* :class:`OpenSandboxClient` - creates and destroys sandboxes under the policy.
* :class:`SandboxService` - the two operations tools are allowed to ask for.

Importing this package does not import the OpenSandbox SDK; see
``client._load_sdk``.
"""

from backend.sandbox.client import (
    OpenSandboxClient,
    SandboxExecution,
    SandboxSession,
    SandboxUnavailable,
)
from backend.sandbox.policy import (
    ALLOWED_IMAGES,
    ARTIFACTS_DIR,
    INPUTS_DIR,
    WORKSPACE_DIR,
    SandboxPolicy,
    SandboxPolicyError,
    policy_from_settings,
)
from backend.sandbox.service import SandboxService

__all__ = [
    "ALLOWED_IMAGES",
    "ARTIFACTS_DIR",
    "INPUTS_DIR",
    "WORKSPACE_DIR",
    "OpenSandboxClient",
    "SandboxExecution",
    "SandboxPolicy",
    "SandboxPolicyError",
    "SandboxService",
    "SandboxSession",
    "SandboxUnavailable",
    "policy_from_settings",
]
