"""Secret resolution and redaction.

Two jobs, both narrow:

* Resolve a named secret from the process environment, and say clearly when
  it is absent. Nothing here reads a file, calls a vault or caches a value
  beyond the process, because a sovereign deployment is expected to inject
  secrets through the environment (systemd, Docker, Kubernetes) rather than
  have the application go looking for them.
* Redact secrets out of anything on its way to a log, an audit row or an API
  response. This is the half that actually earns its place: the audit service
  serialises arbitrary ``detail`` mappings, and without a redactor a caller
  can trivially write an API key into a permanent audit record.

A secret is never returned in a ``describe``-style output, never logged, and
never compared with ``==`` -- use :func:`backend.security.encryption.constant_time_equals`.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from typing import Any

#: What a redacted value is replaced with. A fixed string, not a length-
#: preserving mask: leaking the length of a key is still leaking something.
REDACTED = "[redacted]"

#: Environment variables this application treats as secret. Anything listed
#: here is resolvable through :func:`resolve` and is redacted out of logs and
#: audit detail by name.
SECRET_ENV_VARS: tuple[str, ...] = (
    "P117_AUTH_API_KEY",
    "P117_SANDBOX_API_KEY",
    "P117_DATABASE_PASSWORD",
    "P117_MODEL_API_KEY",
    "P117_CONNECTOR_SAP_PASSWORD",
    "P117_CONNECTOR_CMMS_TOKEN",
    "P117_CONNECTOR_DMS_TOKEN",
    "P117_CONNECTOR_HISTORIAN_TOKEN",
)

#: Substrings that mark a mapping key as sensitive regardless of whether it
#: appears in SECRET_ENV_VARS. Deliberately broad: a false positive costs a
#: redacted debug field, a false negative costs a leaked credential.
SENSITIVE_KEY_PARTS: tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "auth_header",
    "credential",
    "private_key",
    "session_key",
    "cookie",
)

#: Values that look like credentials wherever they appear in free text.
_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{8,}", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}"),
    re.compile(r"\bhf_[A-Za-z0-9]{16,}"),
)

#: Redaction stops here. A cyclic or absurdly nested structure is a bug in the
#: caller, but it must not become an unbounded recursion inside the audit path.
MAX_REDACT_DEPTH = 12


class SecretMissing(RuntimeError):
    """A required secret is not configured.

    Raised rather than returning ``None`` so a caller cannot accidentally
    authenticate with an empty string.
    """

    reason = "secret_missing"

    def __init__(self, name: str) -> None:
        super().__init__(
            f"secret '{name}' is not set; export it in the environment "
            "(see .env.example) before starting the service"
        )
        self.name = name


def is_secret_name(name: str) -> bool:
    """Whether ``name`` identifies a secret, by declaration or by shape."""
    if name in SECRET_ENV_VARS:
        return True
    lowered = name.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def is_configured(name: str) -> bool:
    """Whether a secret has a non-empty value, without revealing it."""
    return bool((os.environ.get(name) or "").strip())


def resolve(name: str, *, required: bool = True, default: str | None = None) -> str | None:
    """Read a secret from the environment.

    Whitespace is stripped, because a trailing newline from ``echo`` into a
    Docker secret file is the single most common cause of a credential that
    looks correct and is not.
    """
    raw = os.environ.get(name)
    value = raw.strip() if isinstance(raw, str) else ""
    if value:
        return value
    if default is not None:
        return default
    if required:
        raise SecretMissing(name)
    return None


def redact_text(text: str) -> str:
    """Replace anything that looks like a credential in free text."""
    if not text:
        return text
    result = text
    for name in SECRET_ENV_VARS:
        actual = (os.environ.get(name) or "").strip()
        if len(actual) >= 6 and actual in result:
            result = result.replace(actual, REDACTED)
    for pattern in _VALUE_PATTERNS:
        result = pattern.sub(REDACTED, result)
    return result


def redact(value: Any, *, _depth: int = 0) -> Any:
    """Recursively redact secrets from a JSON-shaped value.

    Mapping keys are matched by name; strings are additionally scanned for
    values that look like credentials. Non-JSON values are returned unchanged
    -- redaction is not serialisation, and pretending otherwise would hide
    the fact that something unserialisable reached the audit path.
    """
    if _depth >= MAX_REDACT_DEPTH:
        return "[truncated: too deeply nested to redact safely]"
    if isinstance(value, Mapping):
        return {
            key: (REDACTED if is_secret_name(str(key)) else redact(item, _depth=_depth + 1))
            for key, item in value.items()
        }
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, (list, tuple, set)) or (
        isinstance(value, Sequence) and not isinstance(value, (str, bytes))
    ):
        return [redact(item, _depth=_depth + 1) for item in value]
    return value


def describe() -> dict[str, Any]:
    """Which secrets are configured. Names and booleans only, never values."""
    return {
        "known": list(SECRET_ENV_VARS),
        "configured": sorted(name for name in SECRET_ENV_VARS if is_configured(name)),
        "missing": sorted(name for name in SECRET_ENV_VARS if not is_configured(name)),
    }


__all__ = [
    "MAX_REDACT_DEPTH",
    "REDACTED",
    "SECRET_ENV_VARS",
    "SENSITIVE_KEY_PARTS",
    "SecretMissing",
    "describe",
    "is_configured",
    "is_secret_name",
    "redact",
    "redact_text",
    "resolve",
]
