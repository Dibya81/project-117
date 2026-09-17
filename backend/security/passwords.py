"""Password hashing for the mobile field API (stdlib only).

The rest of the backend authenticates machines with a shared API key
(``security/auth.py``); the mobile client authenticates *people*, so it needs a
real credential store. That store must never hold a plaintext password and must
not depend on a package the deployment cannot guarantee — ``passlib`` and
``bcrypt`` are deliberately absent from the base venv, so the hash is built from
``hashlib.scrypt`` with a per-user random salt.

Format on the wire between this module and the identity store is three columns
rather than one packed string: the algorithm/parameters, the salt, and the
digest. Keeping them separate means a future cost bump is a new row value, not
a string-format migration, and no column is ever ambiguous about what it holds.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

#: Chosen parameters. ``n=2**14`` costs ~40 ms on the target hardware — slow
#: enough to matter to an offline attacker, fast enough that a field login over
#: a slow link does not feel broken. The values are stored with the hash so an
#: old row keeps verifying after a parameter change.
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SALT_BYTES = 16

ALGO = f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}"


def hash_password(password: str) -> tuple[str, str, str]:
    """Return ``(algo, salt_hex, digest_hex)`` for a new credential.

    The salt comes from :mod:`secrets`, not :mod:`random`: it is a security
    value, and a predictable salt would let one rainbow table span every demo
    account on the box.
    """
    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return ALGO, salt.hex(), digest.hex()


def verify_password(
    password: str,
    *,
    algo: str,
    salt_hex: str,
    digest_hex: str,
) -> bool:
    """Constant-time verification against a stored credential.

    Returns ``False`` for a malformed stored row instead of raising: a corrupt
    row must fail closed (deny the login), and the caller cannot do anything
    useful with an exception here. ``hmac.compare_digest`` is used so a timing
    side channel cannot narrow the digest down byte by byte.
    """
    try:
        n, r, p = (int(part) for part in algo.split("$")[1:4])
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, IndexError, TypeError):
        return False
    try:
        candidate = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=len(expected)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, expected)


#: A digest that never matches, used to spend the same scrypt time when the
#: username does not exist. Without it, "no such user" answers measurably faster
#: than "wrong password" and a caller can enumerate accounts.
_DUMMY_ALGO, _DUMMY_SALT, _DUMMY_DIGEST = hash_password(secrets.token_hex(16))


def waste_time_like_a_verification() -> None:
    """Burn one scrypt round for a nonexistent account (see ``_DUMMY_*``)."""
    verify_password(
        "not-the-password",
        algo=_DUMMY_ALGO,
        salt_hex=_DUMMY_SALT,
        digest_hex=_DUMMY_DIGEST,
    )


__all__ = [
    "ALGO",
    "hash_password",
    "verify_password",
    "waste_time_like_a_verification",
]
