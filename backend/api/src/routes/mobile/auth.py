"""Mobile authentication endpoints (``/api/v1/auth/*``).

A real login, not a placeholder: the credential is verified against the salted
scrypt digest in the identity store, a device token is checked when one is
presented, and a session row is created so ``logout`` and ``refresh`` have
something real to act on. Tokens are minted by ``security/mobile_auth.py`` and
verified on every protected request; nothing here trusts an unsigned claim.

These five routes are the only place a token is created, and the first three
(enrol, login, refresh) are reachable without one — a client cannot present a
token before it has logged in. They are listed as public paths in
``middleware/auth.py`` explicitly rather than being carved out of the gate.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from backend.api.src.deps import get_audit, get_identity, get_settings
from backend.api.src.errors import BadRequest, ServiceUnavailable
from backend.api.src.routes.mobile._common import get_mobile_principal, user_payload
from backend.config import Settings
from backend.security.audit import AuditService
from backend.security.auth import AuthenticationError
from backend.security.mobile_auth import MobileAuthConfigError, codec_for_settings
from backend.security.mobile_roles import backend_roles_for_mobile_role
from backend.security.rbac import Principal
from backend.storage.identity import (
    IdentityError,
    IdentityStore,
    InactiveSession,
    UnknownEnrollmentCode,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class EnrollRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1, max_length=128)
    enrollment_code: str = Field(min_length=1, max_length=128)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=512)
    #: The client always sends the field, possibly blank when the operator has
    #: not enrolled the handset yet. A blank value means "unbound device", a
    #: present one is validated.
    device_token: str = Field(default="", max_length=256)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=1)


def _codec(settings: Settings):
    """The token codec, or a 503 when the service is misconfigured.

    A misconfiguration must never fall through to an anonymous or unsigned
    token: refusing the request is the only safe failure mode.
    """
    try:
        return codec_for_settings(settings)
    except MobileAuthConfigError as exc:
        logger.error("mobile auth is misconfigured: %s", exc)
        raise ServiceUnavailable(str(exc), code="mobile_auth_misconfigured") from exc


def _audit(audit: AuditService, **kwargs) -> None:
    try:
        audit.record(**kwargs)
    except Exception:  # pragma: no cover - auditing must not break a login
        logger.warning("audit write failed for %s", kwargs.get("action"), exc_info=True)


@router.post("/auth/enroll")
def enroll(
    payload: EnrollRequest,
    identity: IdentityStore = Depends(get_identity),
    audit: AuditService = Depends(get_audit),
) -> dict:
    """Bind a handset to the cluster and return its device token.

    The token is returned exactly once, in this response; only its SHA-256
    digest is stored. A wrong code answers 401, never an enrolled device.
    """
    try:
        result = identity.enroll_device(
            device_id=payload.device_id, enrollment_code=payload.enrollment_code
        )
    except UnknownEnrollmentCode as exc:
        _audit(
            audit,
            action="mobile.enroll_rejected",
            resource_type="device",
            resource_id=payload.device_id,
            user="unknown",
            outcome="refused",
            error=str(exc),
        )
        raise AuthenticationError(str(exc)) from exc
    except IdentityError as exc:
        raise BadRequest(str(exc)) from exc
    _audit(
        audit,
        action="mobile.enrolled",
        resource_type="device",
        resource_id=result["device_id"],
        user="unknown",
        detail={"enrolledAt": result["enrolled_at"]},
    )
    return {"enrolled": True, "device_token": result["device_token"]}


@router.post("/auth/login")
def login(
    payload: LoginRequest,
    settings: Settings = Depends(get_settings),
    identity: IdentityStore = Depends(get_identity),
    audit: AuditService = Depends(get_audit),
) -> dict:
    """Verify a real credential and issue an access + refresh token pair."""
    user = identity.authenticate(payload.username, payload.password)
    if user is None:
        _audit(
            audit,
            action="mobile.login_rejected",
            resource_type="user",
            resource_id=payload.username,
            user=payload.username,
            outcome="refused",
            error="invalid credentials",
        )
        # One message for unknown user and wrong password alike: the endpoint
        # must not be usable to discover which usernames exist.
        raise AuthenticationError("invalid username or password")

    device_id = None
    device_token = payload.device_token.strip()
    if device_token:
        device = identity.device_for_token(device_token)
        if device is None:
            _audit(
                audit,
                action="mobile.login_rejected",
                resource_type="user",
                resource_id=user["id"],
                user=user["username"],
                outcome="refused",
                error="unknown device token",
            )
            raise AuthenticationError("the device token is not recognised; enrol the device first")
        device_id = str(device["device_id"])

    codec = _codec(settings)
    session = identity.create_session(
        user_id=user["id"],
        device_id=device_id,
        ttl_seconds=getattr(settings, "mobile_refresh_ttl_seconds", 0) or 60 * 60,
    )
    roles = backend_roles_for_mobile_role(user["role"])
    access_token = codec.issue_access(
        user_id=user["id"],
        username=user["username"],
        mobile_role=user["role"],
        rbac_roles=roles,
        permissions=user["permissions"],
        session_id=session["id"],
    )
    refresh_token = codec.issue_refresh(
        user_id=user["id"],
        session_id=session["id"],
        refresh_jti=session["refresh_jti"],
        device_id=device_id,
    )
    _audit(
        audit,
        action="mobile.login",
        resource_type="user",
        resource_id=user["id"],
        user=user["username"],
        detail={"role": user["role"], "deviceBound": device_id is not None},
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        **user_payload(user),
    }


@router.post("/auth/refresh")
def refresh_token(
    payload: RefreshRequest,
    settings: Settings = Depends(get_settings),
    identity: IdentityStore = Depends(get_identity),
    audit: AuditService = Depends(get_audit),
) -> dict:
    """Exchange a live refresh token for a new access token.

    The refresh token must be signed, unexpired, and backed by a session row
    that has not been revoked. Rotating it is deliberately *not* done here: the
    client's contract (``RefreshResponse``) carries only ``access_token``, so a
    rotated refresh token would have nowhere to go.
    """
    codec = _codec(settings)
    claims = codec.verify(payload.refresh_token, expected_type="refresh")
    try:
        identity.assert_session_active(
            session_id=str(claims.get("sid") or ""),
            refresh_jti=str(claims.get("jti") or ""),
            user_id=str(claims.get("sub") or ""),
        )
    except InactiveSession as exc:
        raise AuthenticationError(str(exc)) from exc
    user = identity.get_user(str(claims.get("sub") or ""))
    if user is None or user.get("disabled"):
        raise AuthenticationError("the account for this token no longer exists")
    access_token = codec.issue_access(
        user_id=user["id"],
        username=user["username"],
        mobile_role=user["role"],
        rbac_roles=backend_roles_for_mobile_role(user["role"]),
        permissions=user["permissions"],
        session_id=str(claims.get("sid") or ""),
    )
    _audit(
        audit,
        action="mobile.token_refreshed",
        resource_type="user",
        resource_id=user["id"],
        user=user["username"],
    )
    return {"access_token": access_token}


@router.post("/auth/logout")
def logout(
    principal: Principal = Depends(get_mobile_principal),
    identity: IdentityStore = Depends(get_identity),
    audit: AuditService = Depends(get_audit),
) -> dict:
    """Revoke this session so its refresh token can no longer be exchanged."""
    session_id = str(principal.extra.get("session_id") or "")
    revoked = identity.revoke_session(session_id, reason="logout") if session_id else False
    _audit(
        audit,
        action="mobile.logout",
        resource_type="session",
        resource_id=session_id or principal.user,
        user=principal.user,
        detail={"revoked": revoked},
    )
    return {"revoked": revoked}


@router.get("/auth/me")
def me(
    principal: Principal = Depends(get_mobile_principal),
    identity: IdentityStore = Depends(get_identity),
) -> dict:
    """The identity the access token was issued for, read live from the store.

    Reading the store (rather than echoing token claims) means a role or
    display-name change takes effect on the next call, without forcing a
    re-login or waiting for the token to expire.
    """
    user_id = str(principal.extra.get("user_id") or "")
    user = identity.get_user(user_id) if user_id else None
    if user is None:
        raise AuthenticationError("the account for this token no longer exists")
    return user_payload(user)


__all__ = ["router"]
