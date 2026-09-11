"""Hashing, fingerprinting and constant-time comparison.

**Scope, stated plainly.** This module does not encrypt anything. Project 117
deliberately does not implement its own payload encryption: an in-process
cipher written here would be weaker than what the deployment already provides,
and it would move the key into the same address space as the data it protects.
Encryption at rest is delegated to the platform -- LUKS / dm-crypt on the data
volume, or the database's own transparent encryption -- and that requirement is
recorded in ``docs/security/``.

What *is* implemented here is the small set of primitives the application
genuinely needs and can get right with the standard library:

* API-key verification that does not leak timing information.
* Stable, non-reversible fingerprints so an audit row can say *which* key or
  document it saw without storing the thing itself.

Everything uses :mod:`hashlib` and :mod:`hmac` from the standard library. No
third-party cryptography is imported, so nothing here can silently stop
working when an optional dependency is missing.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

#: Length of a truncated fingerprint. 16 hex chars = 64 bits, which is far
#: more than enough to distinguish the handful of keys and documents one
#: deployment sees, and short enough to read in a log line.
FINGERPRINT_CHARS = 16

#: PBKDF2 iteration count for stored key hashes. Deliberately a named constant
#: so it can be raised without hunting through call sites.
PBKDF2_ITERATIONS = 200_000

_SALT_BYTES = 16


def sha256_hex(data: bytes | str) -> str:
    """Full SHA-256 hex digest."""
    payload = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(payload).hexdigest()


def fingerprint(data: bytes | str, *, chars: int = FINGERPRINT_CHARS) -> str:
    """Short, stable, non-reversible identifier for a value.

    Used to record *which* secret or artifact was involved in an operation
    without recording the value. Truncation is safe here because the purpose
    is identification within one deployment, not collision resistance against
    an adversary who can choose both inputs.
    """
    if chars < 8 or chars > 64:
        raise ValueError("fingerprint length must be between 8 and 64 hex characters")
    return sha256_hex(data)[:chars]


def constant_time_equals(left: str | bytes | None, right: str | bytes | None) -> bool:
    """Compare two secrets without leaking their common prefix length.

    ``None`` never matches, including ``None`` against ``None``: an unset
    credential must not authenticate an unset credential.
    """
    if left is None or right is None:
        return False
    a = left.encode("utf-8") if isinstance(left, str) else left
    b = right.encode("utf-8") if isinstance(right, str) else right
    return hmac.compare_digest(a, b)


def hash_api_key(key: str, *, salt: bytes | None = None) -> str:
    """Derive a storable representation of an API key.

    Returns ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>``, which carries
    its own parameters so a stored hash stays verifiable after the iteration
    count is raised.
    """
    if not key:
        raise ValueError("refusing to hash an empty API key")
    resolved_salt = salt if salt is not None else os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", key.encode("utf-8"), resolved_salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${resolved_salt.hex()}${digest.hex()}"


def verify_api_key(key: str | None, stored: str | None) -> bool:
    """Check a presented key against a value produced by :func:`hash_api_key`.

    Returns ``False`` for anything malformed rather than raising, because this
    sits on the authentication path and an exception there is an availability
    problem. A malformed stored hash is a configuration error that fails
    closed.
    """
    if not key or not stored:
        return False
    parts = stored.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return False
    try:
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected = bytes.fromhex(parts[3])
    except ValueError:
        return False
    if iterations < 1000:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", key.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)


def describe() -> dict[str, Any]:
    """What this module does and does not provide, for the Admin security view."""
    return {
        "key_hashing": f"pbkdf2_sha256 x{PBKDF2_ITERATIONS}",
        "comparison": "constant-time (hmac.compare_digest)",
        "fingerprint": f"sha256 truncated to {FINGERPRINT_CHARS} hex chars",
        "payload_encryption": "delegated to the platform (disk/volume or database TDE)",
        "implements_own_cipher": False,
    }


__all__ = [
    "FINGERPRINT_CHARS",
    "PBKDF2_ITERATIONS",
    "constant_time_equals",
    "describe",
    "fingerprint",
    "hash_api_key",
    "sha256_hex",
    "verify_api_key",
]
