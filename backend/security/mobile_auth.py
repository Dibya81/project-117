"""Mobile bearer-token identity (Phase 12 extension).

The console authenticates with a shared API key (``security/auth.py``). The
Android field client cannot: it authenticates a *person*, carries the resulting
credential in ``Authorization: Bearer <access_token>`` and renews it with a
refresh token. This module is the small, self-contained token service that
makes that possible without introducing a JWT dependency.

Token format (a compact, HMAC-signed envelope, not a JWT):

    p117a.<base64url(payload json)>.<base64url(hmac-sha256)>
    p117r.<base64url(payload json)>.<base64url(hmac-sha256)>

``p117a`` is an access token, ``p117r`` a refresh token. The type is signed
*and* repeated inside the payload, so a refresh token cannot be replayed as an
access token (or the reverse). Signing and expiry are enforced on every
protected request by ``principal_from_request``; nothing trusts a claim that
was not verified in this module.

The signing secret resolves in this order:

1. ``P117_MOBILE_TOKEN_SECRET`` if set — the deployment's explicit choice.
2. A random secret generated once and persisted in the identity SQLite store,
   so tokens survive a restart on a machine that never configured one.

A secret that is set but too short is treated as a misconfiguration and the
service refuses to issue or accept a token rather than silently weakening the
signature.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any

from backend.security.auth import AuthenticationError
from backend.security.rbac import Principal

logger = logging.getLogger(__name__)

MOBILE_ACCESS_PREFIX = "p117a"
MOBILE_REFRESH_PREFIX = "p117r"
_MOBILE_PREFIXES = (MOBILE_ACCESS_PREFIX + ".", MOBILE_REFRESH_PREFIX + ".")

#: Below this, the configured secret is a guess away from being brute-forced.
MIN_SECRET_CHARS = 16

#: Default lifetimes. Access is short because it is the credential on every
#: field request; refresh is long because a technician on a plant network
#: should not have to retype a password mid-shift.
DEFAULT_ACCESS_TTL_SECONDS = 30 * 60
DEFAULT_REFRESH_TTL_SECONDS = 30 * 24 * 60 * 60


class MobileAuthConfigError(RuntimeError):
    """The token service cannot operate with the current configuration."""

    reason = "mobile_auth_misconfigured"


def is_mobile_token(value: str | None) -> bool:
    """True when ``value`` claims to be one of our tokens (cheap pre-check)."""
    return bool(value) and str(value).startswith(_MOBILE_PREFIXES)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(secret: str, prefix: str, body: str) -> str:
    return _b64url_encode(
        hmac.new(secret.encode("utf-8"), f"{prefix}.{body}".encode("utf-8"), hashlib.sha256).digest()
    )


@dataclass(frozen=True)
class TokenCodec:
    """Issues and verifies the two token kinds with one signing secret."""

    secret: str
    access_ttl_seconds: int = DEFAULT_ACCESS_TTL_SECONDS
    refresh_ttl_seconds: int = DEFAULT_REFRESH_TTL_SECONDS

    def __post_init__(self) -> None:
        if len(self.secret) < MIN_SECRET_CHARS:
            raise MobileAuthConfigError(
                f"mobile token secret must be at least {MIN_SECRET_CHARS} characters; "
                "set P117_MOBILE_TOKEN_SECRET to a long random value"
            )

    # ------------------------------------------------------------- issuing
    def _encode(self, prefix: str, payload: dict[str, Any]) -> str:
        body = _b64url_encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        return f"{prefix}.{body}.{_sign(self.secret, prefix, body)}"

    def issue_access(
        self,
        *,
        user_id: str,
        username: str,
        mobile_role: str,
        rbac_roles: list[str],
        permissions: list[str],
        session_id: str,
        now: float | None = None,
    ) -> str:
        issued = time.time() if now is None else now
        return self._encode(
            MOBILE_ACCESS_PREFIX,
            {
                "typ": "access",
                "sub": user_id,
                "usr": username,
                "mrole": mobile_role,
                "roles": list(rbac_roles),
                "perms": list(permissions),
                "sid": session_id,
                "jti": secrets.token_hex(8),
                "iat": int(issued),
                "exp": int(issued) + self.access_ttl_seconds,
            },
        )

    def issue_refresh(
        self,
        *,
        user_id: str,
        session_id: str,
        refresh_jti: str,
        device_id: str | None = None,
        now: float | None = None,
    ) -> str:
        issued = time.time() if now is None else now
        return self._encode(
            MOBILE_REFRESH_PREFIX,
            {
                "typ": "refresh",
                "sub": user_id,
                "sid": session_id,
                "jti": refresh_jti,
                "dev": device_id,
                "iat": int(issued),
                "exp": int(issued) + self.refresh_ttl_seconds,
            },
        )

    # ---------------------------------------------------------- verifying
    def verify(self, token: str, *, expected_type: str) -> dict[str, Any]:
        """Return the verified claims or raise :class:`AuthenticationError`.

        Every failure mode answers the same generic message: telling a caller
        *why* a token failed (bad signature vs expired vs wrong kind) is free
        reconnaissance.
        """
        if not is_mobile_token(token):
            raise AuthenticationError("not a mobile token")
        try:
            prefix, body, signature = token.split(".", 2)
        except ValueError:
            raise AuthenticationError("malformed token") from None
        if prefix != (MOBILE_ACCESS_PREFIX if expected_type == "access" else MOBILE_REFRESH_PREFIX):
            # A refresh token is not an access token, even though both are ours.
            raise AuthenticationError("wrong token kind for this operation")
        if not hmac.compare_digest(signature, _sign(self.secret, prefix, body)):
            raise AuthenticationError("token signature is not valid")
        try:
            claims = json.loads(_b64url_decode(body))
        except (ValueError, TypeError):
            raise AuthenticationError("malformed token payload") from None
        if str(claims.get("typ")) != expected_type:
            raise AuthenticationError("wrong token kind for this operation")
        try:
            expires = int(claims["exp"])
        except (KeyError, TypeError, ValueError):
            raise AuthenticationError("token has no valid expiry") from None
        if expires <= int(time.time()):
            raise AuthenticationError("token has expired")
        return claims


#: Process-local cache, keyed by the primitive inputs. ``Settings`` is a mutable
#: pydantic model and cannot be a cache key, and the secret should not be
#: re-derived from SQLite on every request.
_codec_cache: dict[tuple[str, str, int, int], TokenCodec] = {}


def codec_for_settings(settings: Any) -> TokenCodec:
    """Build (or reuse) the codec for this deployment's settings."""
    configured = str(getattr(settings, "mobile_token_secret", "") or "").strip()
    access_ttl = int(
        getattr(settings, "mobile_access_ttl_seconds", DEFAULT_ACCESS_TTL_SECONDS)
        or DEFAULT_ACCESS_TTL_SECONDS
    )
    refresh_ttl = int(
        getattr(settings, "mobile_refresh_ttl_seconds", DEFAULT_REFRESH_TTL_SECONDS)
        or DEFAULT_REFRESH_TTL_SECONDS
    )
    if configured:
        secret = configured
        if len(secret) < MIN_SECRET_CHARS:
            raise MobileAuthConfigError(
                "P117_MOBILE_TOKEN_SECRET is set but shorter than "
                f"{MIN_SECRET_CHARS} characters; refusing to sign tokens with a weak secret"
            )
    else:
        # Imported lazily: the identity store imports this module's password
        # helpers, so a module-level import here would be a cycle.
        from backend.storage.identity import load_or_create_token_secret

        secret = load_or_create_token_secret(getattr(settings, "identity_db", None))
    key = (secret, str(getattr(settings, "identity_db", "")), access_ttl, refresh_ttl)
    codec = _codec_cache.get(key)
    if codec is None:
        codec = TokenCodec(secret=secret, access_ttl_seconds=access_ttl, refresh_ttl_seconds=refresh_ttl)
        _codec_cache[key] = codec
    return codec


def resolve_mobile_principal(token: str, *, settings: Any) -> Principal:
    """Turn a verified access token into the request's :class:`Principal`.

    A misconfigured token service refuses the request instead of letting it
    through: the failure mode of a missing or weak secret must be "denied",
    never "anonymous with whatever roles the caller asked for".
    """
    try:
        codec = codec_for_settings(settings)
    except MobileAuthConfigError as exc:
        logger.error("mobile auth refused: %s", exc)
        raise AuthenticationError("the mobile token service is misconfigured") from exc
    claims = codec.verify(token, expected_type="access")
    roles = tuple(str(role) for role in (claims.get("roles") or []) if str(role).strip())
    return Principal(
        user=str(claims.get("usr") or claims.get("sub") or "mobile"),
        roles=roles or ("field",),
        authenticated=True,
        extra={
            "user_id": str(claims.get("sub") or ""),
            "mobile_role": str(claims.get("mrole") or ""),
            "permissions": tuple(str(p) for p in (claims.get("perms") or [])),
            "session_id": str(claims.get("sid") or ""),
        },
    )


__all__ = [
    "DEFAULT_ACCESS_TTL_SECONDS",
    "DEFAULT_REFRESH_TTL_SECONDS",
    "MIN_SECRET_CHARS",
    "MOBILE_ACCESS_PREFIX",
    "MOBILE_REFRESH_PREFIX",
    "MobileAuthConfigError",
    "TokenCodec",
    "codec_for_settings",
    "is_mobile_token",
    "resolve_mobile_principal",
]
