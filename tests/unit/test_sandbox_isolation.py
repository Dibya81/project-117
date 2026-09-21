"""Unit tests for OpenSandbox policy enforcement, default-deny egress, and isolation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.sandbox.policy import SandboxPolicy, SandboxPolicyError, policy_from_settings
from backend.sandbox.client import OpenSandboxClient, SandboxUnavailable
from backend.sandbox.service import SandboxService


def test_sandbox_policy_default_deny_network():
    policy = SandboxPolicy(base_url="http://127.0.0.1:8080", api_key="secret-key")
    net_policy = policy.network_policy()
    assert net_policy["defaultAction"] == "deny"
    assert net_policy["rules"] == []


def test_sandbox_policy_environment_isolation():
    policy = SandboxPolicy()
    env = policy.environment()
    assert "DATABASE_URL" not in env
    assert "P117_API_KEY" not in env
    assert env["HOME"] == "/workspace"
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert env["PYTHONNOUSERSITE"] == "1"


def test_sandbox_policy_image_whitelist():
    policy = SandboxPolicy()
    # Approved purposes succeed
    assert "python" in policy.resolve_image("python")
    assert "sandbox-documents" in policy.resolve_image("documents")

    # Arbitrary images or unauthorized purposes fail
    with pytest.raises(SandboxPolicyError, match="not an approved sandbox purpose"):
        policy.resolve_image("ubuntu:latest")

    with pytest.raises(SandboxPolicyError, match="not an approved sandbox purpose"):
        policy.resolve_image("alpine")


def test_sandbox_policy_validation_requires_key():
    policy = SandboxPolicy(base_url="http://127.0.0.1:8080", api_key="", require_api_key=True)
    with pytest.raises(SandboxPolicyError, match="sandbox API key is not configured"):
        policy.validate_ready()


def test_sandbox_policy_validation_missing_url():
    policy = SandboxPolicy(base_url="", api_key="test", require_api_key=True)
    with pytest.raises(SandboxPolicyError, match="sandbox base URL is not configured"):
        policy.validate_ready()


@pytest.mark.asyncio
async def test_sandbox_run_python_rejects_empty_code():
    policy = SandboxPolicy(base_url="http://127.0.0.1:8080", api_key="test", require_api_key=False)
    service = SandboxService(policy)
    with pytest.raises(SandboxPolicyError, match="no code was supplied"):
        await service.run_python("")


@pytest.mark.asyncio
async def test_sandbox_render_artifact_rejects_unsupported_type():
    policy = SandboxPolicy(base_url="http://127.0.0.1:8080", api_key="test", require_api_key=False)
    service = SandboxService(policy)
    with pytest.raises(SandboxPolicyError, match="not a supported artifact type"):
        await service.render_artifact(artifact_type="exe", spec={}, filename="bad.exe")
