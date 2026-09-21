"""Auth-fuzzing and security edge-case test suite (Phase 7).

Tests adversarial inputs, role smuggling, fuzzing strings, malformed tokens,
oversized headers, and verifies that constant-time comparison (hmac.compare_digest)
is strictly on the credential verification path.
"""

from __future__ import annotations

import hmac
from unittest.mock import patch

import pytest
from backend.config import Settings
from backend.security.auth import (
    API_KEY_HEADER,
    ROLES_HEADER,
    USER_HEADER,
    AuthenticationError,
    principal_from_request,
)
from starlette.requests import Request


def _make_request(
    headers: dict[str, str] | None = None, settings: Settings | None = None
) -> Request:
    raw_headers = []
    if headers:
        for k, v in headers.items():
            raw_headers.append((k.lower().encode("utf-8"), v.encode("utf-8")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/test",
        "headers": raw_headers,
    }
    req = Request(scope)
    if settings is not None:
        req.state.settings = settings
    return req


FUZZ_ROLE_INPUTS = [
    "admin",
    "ADMIN",
    " Admin ",
    "aDmIn",
    "root",
    "superuser",
    "'; DROP TABLE users; --",
    "<script>alert(1)</script>",
    "../../../etc/passwd",
    "\x00admin",
    "admin\x00",
    "null",
    "undefined",
    "NaN",
    ",",
    ",,,",
    "   ,   ,   ",
    '"admin"',
    "'admin'",
    "аdmin",  # Cyrillic 'а' homoglyph
    "👨‍💻",
    "operator,admin",
    "operator, admin",
    "operator\nadmin",
    "operator\r\nadmin",
    " " * 500 + "admin",
    "a" * 10000,
]


@pytest.mark.parametrize("fuzz_role", FUZZ_ROLE_INPUTS)
def test_authenticated_caller_immune_to_role_fuzzing(fuzz_role):
    """Authenticated caller with valid API key MUST NEVER receive any role

    other than what server-side P117_AUTH_ROLES specifies, regardless of what
    garbage, injection, or escalation string is sent in X-P117-Roles.
    """
    settings = Settings(
        environment="test",
        auth_required=True,
        auth_api_key="secret-vault-key",
        auth_roles={"operator"},
    )
    req = _make_request(
        headers={
            API_KEY_HEADER: "secret-vault-key",
            ROLES_HEADER: fuzz_role,
            USER_HEADER: "adversary",
        },
        settings=settings,
    )
    principal = principal_from_request(req, settings=settings)
    assert principal.authenticated is True
    assert principal.roles == ("operator",), (
        f"Role escalation occurred with input {fuzz_role!r}: got {principal.roles}"
    )
    assert "admin" not in principal.roles


@pytest.mark.parametrize("fuzz_role", FUZZ_ROLE_INPUTS)
def test_unauthenticated_caller_immune_to_role_fuzzing(fuzz_role):
    """Unauthenticated caller on local trust boundary MUST NEVER receive admin

    or arbitrary escalated permissions from X-P117-Roles fuzzing.
    """
    settings = Settings(
        environment="test",
        auth_required=False,
        auth_api_key="",
    )
    req = _make_request(
        headers={
            ROLES_HEADER: fuzz_role,
            USER_HEADER: "guest",
        },
        settings=settings,
    )
    principal = principal_from_request(req, settings=settings)
    assert principal.authenticated is False
    assert "admin" not in principal.roles
    for role in principal.roles:
        assert role in {"operator", "viewer"}


MALFORMED_API_KEYS = [
    "",
    " ",
    "   ",
    "\t\n\r",
    "Bearer",
    "Bearer ",
    "Bearer \t",
    "Token secret-vault-key",
    "Basic dXNlcjpwYXNz",
    "secret-vault-key-wrong",
    "SECRET-VAULT-KEY",
    "secret-vault-key-extra",
    "wrong-key-entirely",
    "x" * 100_000,  # 100KB oversized key
]


@pytest.mark.parametrize("bad_key", MALFORMED_API_KEYS)
def test_malformed_and_oversized_api_keys_rejected(bad_key):
    """Malformed, oversized, or subtly wrong API keys must be rejected with AuthenticationError."""
    settings = Settings(
        environment="test",
        auth_required=True,
        auth_api_key="secret-vault-key",
    )
    req = _make_request(
        headers={API_KEY_HEADER: bad_key},
        settings=settings,
    )
    with pytest.raises(AuthenticationError):
        principal_from_request(req, settings=settings)


PSEUDO_MOBILE_TOKENS = [
    "p117a.",
    "p117a..",
    "p117a.fake",
    "p117a.malformed.token.format",
    "p117a." + "A" * 1000,
    "p117a.eyJhbGciOiJIUzI1NiJ9.e30.invalid_signature",
    "Bearer p117a.invalid",
]


@pytest.mark.parametrize("pseudo_token", PSEUDO_MOBILE_TOKENS)
def test_pseudo_mobile_tokens_rejected_without_fallback_escalation(pseudo_token):
    """Strings resembling mobile tokens (starting with p117a.) must be verified by the

    mobile token service and rejected on invalid format or signature, never accepted as valid keys.
    """
    settings = Settings(
        environment="test",
        auth_required=True,
        auth_api_key="secret-vault-key",
    )
    req = _make_request(
        headers={"Authorization": pseudo_token},
        settings=settings,
    )
    with pytest.raises(AuthenticationError):
        principal_from_request(req, settings=settings)


def test_hmac_compare_digest_is_strictly_on_comparison_path():
    """Verify that hmac.compare_digest is called to prevent timing side-channels."""
    settings = Settings(
        environment="test",
        auth_required=True,
        auth_api_key="correct-secure-key",
    )
    req = _make_request(
        headers={API_KEY_HEADER: "correct-secure-key"},
        settings=settings,
    )

    with patch(
        "backend.security.auth.hmac.compare_digest", wraps=hmac.compare_digest
    ) as mock_compare:
        principal = principal_from_request(req, settings=settings)
        assert principal.authenticated is True
        mock_compare.assert_called_once_with("correct-secure-key", "correct-secure-key")
