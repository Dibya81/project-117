"""Tests for backend.security.auth — CRIT-1 regression + edge cases.

Key assertions:
- An authenticated caller (valid API key) with X-P117-Roles: admin does NOT
  receive admin permissions; it receives exactly what P117_AUTH_ROLES says.
- The anonymous path is still capped correctly by ANONYMOUS_MAX_ROLES.
- Garbage/unknown role strings are silently ignored (they grant nothing).
- Missing X-P117-Roles falls back to DEFAULT_ROLE on both paths.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.security.auth import (
    API_KEY_HEADER,
    ROLES_HEADER,
    USER_HEADER,
    AuthenticationError,
    describe,
    principal_from_request,
    split_roles,
)
from backend.security.rbac import ANONYMOUS_MAX_ROLES, DEFAULT_ROLE
from backend.tools.base import Permission

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings(
    *,
    auth_required: bool = False,
    api_key: str = "",
    auth_roles: tuple[str, ...] = ("operator",),
):
    s = MagicMock()
    s.auth_required = auth_required
    s.auth_api_key = api_key
    s.auth_roles = auth_roles
    return s


def _request(
    *,
    api_key: str | None = None,
    roles_header: str | None = None,
    user_header: str | None = None,
    settings=None,
    authorization: str | None = None,
):
    """Build a minimal mock Request that satisfies principal_from_request."""
    req = MagicMock()
    headers: dict[str, str] = {}
    if api_key is not None:
        headers[API_KEY_HEADER] = api_key
    if authorization is not None:
        headers["Authorization"] = authorization
    if roles_header is not None:
        headers[ROLES_HEADER] = roles_header
    if user_header is not None:
        headers[USER_HEADER] = user_header
    req.headers.get = lambda k, default=None: headers.get(k, default)
    req.app.state.settings = settings or _settings()
    return req


VALID_KEY = "secret-key-123"


# ---------------------------------------------------------------------------
# CRIT-1 regression: authenticated caller cannot self-escalate via header
# ---------------------------------------------------------------------------


class TestCrit1RoleEscalation:
    """The core regression. An authenticated caller with a valid API key MUST
    NOT be able to obtain admin permissions by setting X-P117-Roles: admin."""

    def test_header_admin_claim_ignored_for_authenticated_caller(self):
        """CRIT-1: the roles header is silently ignored for authenticated callers."""
        settings = _settings(api_key=VALID_KEY, auth_roles=("operator",))
        req = _request(api_key=VALID_KEY, roles_header="admin", settings=settings)
        principal = principal_from_request(req, settings=settings)

        assert principal.authenticated is True
        assert "admin" not in principal.roles, (
            "Authenticated caller self-escalated to admin via X-P117-Roles header -- CRIT-1 not fixed"
        )
        assert "operator" in principal.roles

    def test_authenticated_caller_receives_configured_roles_not_header_roles(self):
        """Roles come from settings.auth_roles, not from the request header."""
        settings = _settings(api_key=VALID_KEY, auth_roles=("analyst",))
        req = _request(api_key=VALID_KEY, roles_header="admin,operator", settings=settings)
        principal = principal_from_request(req, settings=settings)

        assert principal.roles == ("analyst",)
        assert "admin" not in principal.roles
        assert "operator" not in principal.roles

    def test_authenticated_admin_only_when_configured(self):
        """Admin IS reachable when the server explicitly grants it."""
        settings = _settings(api_key=VALID_KEY, auth_roles=("admin",))
        req = _request(api_key=VALID_KEY, settings=settings)
        principal = principal_from_request(req, settings=settings)

        assert "admin" in principal.roles
        assert principal.has(Permission.DOCUMENTS_WRITE)

    def test_authenticated_multiple_roles_from_config(self):
        """Multiple roles can be granted via P117_AUTH_ROLES."""
        settings = _settings(api_key=VALID_KEY, auth_roles=("viewer", "analyst"))
        req = _request(api_key=VALID_KEY, roles_header="admin", settings=settings)
        principal = principal_from_request(req, settings=settings)

        assert set(principal.roles) == {"viewer", "analyst"}
        assert "admin" not in principal.roles

    def test_authenticated_default_role_when_auth_roles_empty(self):
        """If auth_roles is empty/falsy, falls back to DEFAULT_ROLE."""
        settings = _settings(api_key=VALID_KEY, auth_roles=())
        req = _request(api_key=VALID_KEY, roles_header="admin", settings=settings)
        principal = principal_from_request(req, settings=settings)

        assert "admin" not in principal.roles
        assert DEFAULT_ROLE in principal.roles

    def test_authenticated_header_matching_config_not_an_error(self):
        """No problem if the header happens to match the configured roles."""
        settings = _settings(api_key=VALID_KEY, auth_roles=("operator",))
        req = _request(api_key=VALID_KEY, roles_header="operator", settings=settings)
        principal = principal_from_request(req, settings=settings)

        assert principal.roles == ("operator",)
        assert principal.authenticated is True


# ---------------------------------------------------------------------------
# Anonymous path: ANONYMOUS_MAX_ROLES ceiling still intact
# ---------------------------------------------------------------------------


class TestAnonymousRoleCeiling:
    """The anonymous path must still cap at ANONYMOUS_MAX_ROLES."""

    def test_anonymous_admin_claim_stripped(self):
        settings = _settings()
        req = _request(roles_header="admin", settings=settings)
        principal = principal_from_request(req, settings=settings)

        assert principal.authenticated is False
        assert "admin" not in principal.roles

    def test_anonymous_allowed_roles_pass_through(self):
        for role in ANONYMOUS_MAX_ROLES:
            settings = _settings()
            req = _request(roles_header=role, settings=settings)
            principal = principal_from_request(req, settings=settings)
            assert role in principal.roles, f"Expected anonymous role {role!r} to be allowed"

    def test_anonymous_mixed_good_and_bad_roles(self):
        settings = _settings()
        req = _request(roles_header="viewer,admin", settings=settings)
        principal = principal_from_request(req, settings=settings)

        assert "viewer" in principal.roles
        assert "admin" not in principal.roles

    def test_anonymous_no_roles_header_defaults(self):
        settings = _settings()
        req = _request(settings=settings)
        principal = principal_from_request(req, settings=settings)

        assert DEFAULT_ROLE in principal.roles


# ---------------------------------------------------------------------------
# Garbage / unknown role strings
# ---------------------------------------------------------------------------


class TestGarbageRoleStrings:
    def test_unknown_role_ignored_anonymous(self):
        settings = _settings()
        req = _request(roles_header="superadmin,rootlevel,viewer", settings=settings)
        principal = principal_from_request(req, settings=settings)

        assert "superadmin" not in principal.roles
        assert "rootlevel" not in principal.roles
        assert "viewer" in principal.roles

    def test_garbage_only_roles_fall_back_to_default_anonymous(self):
        settings = _settings()
        req = _request(roles_header="notarole,fakepermission", settings=settings)
        principal = principal_from_request(req, settings=settings)

        assert DEFAULT_ROLE in principal.roles

    def test_unknown_role_in_auth_roles_config_grants_nothing(self):
        """An unknown role in auth_roles config does not crash; it just grants no permissions."""
        settings = _settings(api_key=VALID_KEY, auth_roles=("unknownrole",))
        req = _request(api_key=VALID_KEY, settings=settings)
        principal = principal_from_request(req, settings=settings)

        assert "unknownrole" in principal.roles
        # unknown role string -> no permissions in the permission map
        assert not principal.permissions


# ---------------------------------------------------------------------------
# Wrong / missing API key
# ---------------------------------------------------------------------------


class TestApiKeyChecks:
    def test_wrong_key_refused(self):
        settings = _settings(api_key=VALID_KEY)
        req = _request(api_key="wrong-key", settings=settings)
        with pytest.raises(AuthenticationError):
            principal_from_request(req, settings=settings)

    def test_no_key_auth_required_refused(self):
        settings = _settings(auth_required=True, api_key=VALID_KEY)
        req = _request(settings=settings)
        with pytest.raises(AuthenticationError):
            principal_from_request(req, settings=settings)

    def test_misconfiguration_auth_required_no_key(self):
        """auth_required=True with no configured key refuses every request."""
        settings = _settings(auth_required=True, api_key="")
        req = _request(settings=settings)
        with pytest.raises(AuthenticationError, match="P117_AUTH_REQUIRED"):
            principal_from_request(req, settings=settings)

    def test_wrong_key_refused_even_when_auth_not_required(self):
        """A supplied-but-wrong key is always refused, even in optional-auth mode."""
        settings = _settings(auth_required=False, api_key=VALID_KEY)
        req = _request(api_key="bad-key", settings=settings)
        with pytest.raises(AuthenticationError):
            principal_from_request(req, settings=settings)


# ---------------------------------------------------------------------------
# Case/whitespace handling in split_roles
# ---------------------------------------------------------------------------


class TestSplitRoles:
    def test_normalises_case(self):
        assert split_roles("ADMIN,Operator") == ("admin", "operator")

    def test_strips_whitespace(self):
        assert split_roles("  viewer ,  analyst  ") == ("viewer", "analyst")

    def test_empty_string_returns_empty(self):
        assert split_roles("") == ()

    def test_none_returns_empty(self):
        assert split_roles(None) == ()

    def test_single_role(self):
        assert split_roles("admin") == ("admin",)

    def test_extra_commas_ignored(self):
        assert split_roles(",,,viewer,,,") == ("viewer",)


# ---------------------------------------------------------------------------
# describe() surfaces auth_roles
# ---------------------------------------------------------------------------


class TestDescribe:
    def test_describe_includes_authenticated_roles(self):
        settings = _settings(api_key=VALID_KEY, auth_roles=("admin",))
        result = describe(settings)
        assert result["authenticated_roles"] == ["admin"]

    def test_describe_does_not_include_key_value(self):
        settings = _settings(api_key=VALID_KEY, auth_roles=("operator",))
        result = describe(settings)
        assert VALID_KEY not in str(result)

    def test_describe_default_roles(self):
        settings = _settings()
        result = describe(settings)
        assert "operator" in result["authenticated_roles"]
