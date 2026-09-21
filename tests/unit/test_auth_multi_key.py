"""Unit tests for multi-key RBAC authentication."""

from __future__ import annotations

import pytest
from backend.config import Settings
from backend.security.auth import AuthenticationError, principal_from_request
from starlette.datastructures import Headers
from starlette.requests import Request


def _mock_request(headers: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/documents",
        "headers": Headers(headers or {}).raw,
    }
    return Request(scope)


def test_multi_key_matching() -> None:
    settings = Settings(
        auth_required=True,
        auth_keys={
            "key-op-123": ("operator",),
            "key-admin-456": ("admin", "operator"),
            "key-audit-789": ("auditor",),
        },
    )

    # Operator key
    req_op = _mock_request({"X-P117-Api-Key": "key-op-123", "X-P117-User": "op1"})
    p_op = principal_from_request(req_op, settings=settings)
    assert p_op.authenticated is True
    assert p_op.user == "op1"
    assert p_op.roles == ("operator",)

    # Admin key
    req_admin = _mock_request({"X-P117-Api-Key": "key-admin-456", "X-P117-User": "root"})
    p_admin = principal_from_request(req_admin, settings=settings)
    assert p_admin.authenticated is True
    assert p_admin.user == "root"
    assert p_admin.roles == ("admin", "operator")

    # Invalid key
    req_bad = _mock_request({"X-P117-Api-Key": "bad-key"})
    with pytest.raises(AuthenticationError, match="the supplied API key is not valid"):
        principal_from_request(req_bad, settings=settings)


def test_multi_key_fallback_to_single_key() -> None:
    settings = Settings(
        auth_required=True,
        auth_api_key="legacy-single-key",
        auth_roles=("operator",),
        auth_keys={"new-admin-key": ("admin",)},
    )

    # Legacy key still works
    req_legacy = _mock_request({"X-P117-Api-Key": "legacy-single-key"})
    p_legacy = principal_from_request(req_legacy, settings=settings)
    assert p_legacy.authenticated is True
    assert p_legacy.roles == ("operator",)

    # Multi key works
    req_new = _mock_request({"X-P117-Api-Key": "new-admin-key"})
    p_new = principal_from_request(req_new, settings=settings)
    assert p_new.authenticated is True
    assert p_new.roles == ("admin",)
