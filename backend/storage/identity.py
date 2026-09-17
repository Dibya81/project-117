"""Persistent identity for the mobile field API.

The rest of the backend has no per-person identity store: it authenticates a
shared API key and accepts a caller-supplied user name for the audit trail
(``backend/security/auth.py``). A phone cannot work that way — it must prove
*which technician* is holding it, survive a restart, and bind to an enrolled
device. This module is that store.

One SQLite file (``P117_IDENTITY_DB``, default ``data/identity.db``) holds:

* **users** — username, display name, mobile role, and a salted scrypt digest.
  A plaintext password is never written (see ``security/passwords.py``).
* **devices** — enrolment records. The device token is stored as a SHA-256
  digest, so a stolen database does not hand out working devices.
* **sessions** — one row per login, carrying the refresh-token id. Revoking a
  session on logout is what makes ``POST /auth/logout`` mean something.
* **enrollment_codes** — the shared codes a device presents to enrol.
* **secrets** — the generated token-signing secret, so tokens survive a restart
  on a deployment that never configured ``P117_MOBILE_TOKEN_SECRET``.

Demo accounts are seeded only into an empty users table, are flagged
``is_demo``, and are logged loudly as SYNTHETIC DEMO credentials. Leaving them
in place on a shared deployment is an operator decision, stated in the log
rather than hidden in code.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from backend.security.mobile_roles import normalize_mobile_role, permissions_for_mobile_role
from backend.security.passwords import (
    hash_password,
    verify_password,
    waste_time_like_a_verification,
)

logger = logging.getLogger(__name__)

#: One account per mobile role. Passwords are deliberately obvious and every
#: row is flagged ``is_demo``: these exist to make a fresh checkout usable, not
#: to be a credential anyone should keep.
SYNTHETIC_DEMO_ACCOUNTS: tuple[tuple[str, str, str, str], ...] = (
    ("technician", "Demo-Technician-117!", "TECHNICIAN", "Field Technician"),
    ("operator", "Demo-Operator-117!", "OPERATOR", "Plant Operator"),
    ("supervisor", "Demo-Supervisor-117!", "SUPERVISOR", "Shift Supervisor"),
    ("admin", "Demo-Admin-117!", "ADMIN", "System Administrator"),
)

#: Shared enrolment codes used when ``P117_ENROLLMENT_CODES`` is not set.
DEFAULT_ENROLLMENT_CODES: tuple[str, ...] = (
    "ENROLL-2026-X9",
    "ENROLL-2026-DEMO",
    "ENROLL-2026-FIELD",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    role          TEXT NOT NULL,
    password_algo TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    is_demo       INTEGER NOT NULL DEFAULT 0,
    disabled      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
    device_id       TEXT PRIMARY KEY,
    token_hash      TEXT NOT NULL,
    enrollment_code TEXT,
    enrolled_at     TEXT NOT NULL,
    last_seen_at    TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    refresh_jti   TEXT NOT NULL,
    device_id     TEXT,
    created_at    TEXT NOT NULL,
    expires_at    TEXT NOT NULL,
    revoked_at    TEXT,
    revoked_reason TEXT
);

CREATE TABLE IF NOT EXISTS enrollment_codes (
    code          TEXT PRIMARY KEY,
    note          TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    last_used_at  TEXT,
    use_count     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS secrets (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class IdentityError(RuntimeError):
    """Base class for identity-store refusals."""

    reason = "identity_error"
    status_code = 400


class UnknownUser(IdentityError):
    reason = "unknown_user"
    status_code = 401


class InactiveSession(IdentityError):
    reason = "invalid_session"
    status_code = 401


class UnknownEnrollmentCode(IdentityError):
    reason = "invalid_enrollment_code"
    status_code = 401


def default_identity_db() -> Path:
    """``P117_IDENTITY_DB`` if set, else ``<repo>/data/identity.db``."""
    override = os.getenv("P117_IDENTITY_DB", "").strip()
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[2] / "data" / "identity.db"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


def _device_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class IdentityStore:
    """SQLite-backed users, devices, sessions and enrolment codes."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else default_identity_db()
        if str(self._db_path) != ":memory:":
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript(_SCHEMA)
            self._db.commit()

    @property
    def path(self) -> Path:
        return self._db_path

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # ------------------------------------------------------------- seeding
    def seed_demo_accounts(self) -> int:
        """Insert the synthetic demo accounts if the users table is empty.

        Returns the number of accounts created (0 when users already exist), so
        the caller can log the once-only event rather than firing every start.
        """
        with self._lock:
            existing = self._db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
            if existing:
                return 0
            for username, password, role, display_name in SYNTHETIC_DEMO_ACCOUNTS:
                self._insert_user(
                    username=username,
                    password=password,
                    role=role,
                    display_name=display_name,
                    is_demo=True,
                )
            return len(SYNTHETIC_DEMO_ACCOUNTS)

    def seed_enrollment_codes(self, codes: Iterable[str]) -> int:
        """Add any missing enrolment codes; never removes an existing one.

        Additive on purpose: rotating ``P117_ENROLLMENT_CODES`` should open the
        new codes without invalidating a device that is mid-enrolment, and a
        code that has been used stays visible for the audit trail.
        """
        added = 0
        with self._lock:
            for code in codes:
                normalized = str(code or "").strip()
                if not normalized:
                    continue
                cursor = self._db.execute(
                    "INSERT OR IGNORE INTO enrollment_codes (code, note, created_at)"
                    " VALUES (?,?,?)",
                    (normalized, "SYNTHETIC DEMO enrollment code", _iso(_now())),
                )
                added += cursor.rowcount
            self._db.commit()
        return added

    def _insert_user(
        self,
        *,
        username: str,
        password: str,
        role: str,
        display_name: str,
        is_demo: bool,
    ) -> str:
        user_id = f"USR-{username.lower()}"
        algo, salt, digest = hash_password(password)
        with self._lock:
            self._db.execute(
                "INSERT INTO users (id,username,display_name,role,password_algo,password_salt,"
                "password_hash,is_demo,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    user_id,
                    username.lower(),
                    display_name,
                    normalize_mobile_role(role),
                    algo,
                    salt,
                    digest,
                    1 if is_demo else 0,
                    _iso(_now()),
                ),
            )
            self._db.commit()
        return user_id

    # --------------------------------------------------------------- users
    @staticmethod
    def _public_user(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        """A user record safe to serialise (never the salt or digest)."""
        data = dict(row)
        return {
            "id": data["id"],
            "username": data["username"],
            "display_name": data["display_name"],
            "role": normalize_mobile_role(data["role"]),
            "permissions": permissions_for_mobile_role(data["role"]),
            "is_demo": bool(data.get("is_demo", 0)),
            "disabled": bool(data.get("disabled", 0)),
        }

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM users WHERE lower(id)=lower(?)", (str(user_id),)
            ).fetchone()
        return self._public_user(row) if row is not None else None

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM users WHERE lower(username)=lower(?)", (str(username).strip(),)
            ).fetchone()
        return self._public_user(row) if row is not None else None

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        """Return the user when the credential is valid, else ``None``.

        Unknown user and wrong password are deliberately indistinguishable —
        both spend one scrypt round and both answer ``None`` — so the endpoint
        cannot be used to enumerate accounts.
        """
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM users WHERE lower(username)=lower(?)", (str(username).strip(),)
            ).fetchone()
        if row is None:
            waste_time_like_a_verification()
            return None
        if row["disabled"]:
            waste_time_like_a_verification()
            return None
        valid = verify_password(
            password or "",
            algo=row["password_algo"],
            salt_hex=row["password_salt"],
            digest_hex=row["password_hash"],
        )
        return self._public_user(row) if valid else None

    # ------------------------------------------------------------- devices
    def enroll_device(self, *, device_id: str, enrollment_code: str) -> dict[str, Any]:
        """Validate the enrolment code and return ``{device_token, device_id}``.

        A re-enrolment of the same ``device_id`` rotates the token rather than
        failing: a phone that was factory-reset presents the same hardware id
        and must be able to come back. The old token stops working, which is
        the point of the rotation.
        """
        device_id = str(device_id or "").strip()
        code = str(enrollment_code or "").strip()
        if not device_id:
            raise IdentityError("device_id is required")
        with self._lock:
            known = self._db.execute(
                "SELECT code FROM enrollment_codes WHERE code=?", (code,)
            ).fetchone()
            if known is None:
                raise UnknownEnrollmentCode("the enrollment code is not recognised")
            token = f"dtok_{secrets.token_urlsafe(24)}"
            now = _iso(_now())
            self._db.execute(
                "INSERT INTO devices (device_id,token_hash,enrollment_code,enrolled_at)"
                " VALUES (?,?,?,?)"
                " ON CONFLICT(device_id) DO UPDATE SET token_hash=excluded.token_hash,"
                " enrollment_code=excluded.enrollment_code, enrolled_at=excluded.enrolled_at",
                (device_id, _device_token_hash(token), code, now),
            )
            self._db.execute(
                "UPDATE enrollment_codes SET last_used_at=?, use_count=use_count+1 WHERE code=?",
                (now, code),
            )
            self._db.commit()
        return {"device_id": device_id, "device_token": token, "enrolled_at": now}

    def device_for_token(self, token: str) -> dict[str, Any] | None:
        if not token:
            return None
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM devices WHERE token_hash=?", (_device_token_hash(str(token)),)
            ).fetchone()
            if row is not None:
                self._db.execute(
                    "UPDATE devices SET last_seen_at=? WHERE device_id=?",
                    (_iso(_now()), row["device_id"]),
                )
                self._db.commit()
        return dict(row) if row is not None else None

    # ------------------------------------------------------------ sessions
    def create_session(
        self, *, user_id: str, device_id: str | None, ttl_seconds: int
    ) -> dict[str, Any]:
        session_id = f"sess_{secrets.token_hex(12)}"
        refresh_jti = secrets.token_hex(16)
        created = _now()
        expires = created + timedelta(seconds=max(60, int(ttl_seconds)))
        with self._lock:
            self._db.execute(
                "INSERT INTO sessions (id,user_id,refresh_jti,device_id,created_at,expires_at)"
                " VALUES (?,?,?,?,?,?)",
                (
                    session_id,
                    user_id,
                    refresh_jti,
                    device_id,
                    _iso(created),
                    _iso(expires),
                ),
            )
            self._db.commit()
        return {
            "id": session_id,
            "refresh_jti": refresh_jti,
            "device_id": device_id,
            "expires_at": _iso(expires),
        }

    def _active_session_row(self, session_id: str, user_id: str) -> sqlite3.Row:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM sessions WHERE id=?", (str(session_id),)
            ).fetchone()
        if row is None:
            raise InactiveSession("the session no longer exists")
        if row["revoked_at"] is not None:
            raise InactiveSession("the session has been revoked")
        if row["user_id"] != user_id:
            raise InactiveSession("the session does not belong to this user")
        try:
            expires = datetime.fromisoformat(row["expires_at"])
        except ValueError:
            raise InactiveSession("the session has no valid expiry") from None
        if expires <= _now():
            raise InactiveSession("the session has expired")
        return row

    def assert_session_active(self, *, session_id: str, refresh_jti: str, user_id: str) -> dict:
        row = self._active_session_row(session_id, user_id)
        if not secrets.compare_digest(str(row["refresh_jti"]), str(refresh_jti)):
            raise InactiveSession("the refresh token is not valid for this session")
        return dict(row)

    def assert_access_session_active(self, *, session_id: str, user_id: str) -> None:
        """Reject an access token whose session has been logged out.

        Without this, ``logout`` would only kill the refresh token and the
        access token would keep working until it expired. Checking the session
        row makes "log out" mean "this credential stops working now", which is
        what an operator expects when they hand the handset back.
        """
        self._active_session_row(session_id, user_id)

    def revoke_session(self, session_id: str, *, reason: str = "logout") -> bool:
        if not session_id:
            return False
        with self._lock:
            cursor = self._db.execute(
                "UPDATE sessions SET revoked_at=?, revoked_reason=?"
                " WHERE id=? AND revoked_at IS NULL",
                (_iso(_now()), reason, str(session_id)),
            )
            self._db.commit()
        return bool(cursor.rowcount)

    def revoke_user_sessions(self, user_id: str, *, reason: str = "logout") -> int:
        with self._lock:
            cursor = self._db.execute(
                "UPDATE sessions SET revoked_at=?, revoked_reason=?"
                " WHERE user_id=? AND revoked_at IS NULL",
                (_iso(_now()), reason, str(user_id)),
            )
            self._db.commit()
        return int(cursor.rowcount)


#: Guards first-time secret creation against two threads racing to insert.
_secret_lock = threading.Lock()


def load_or_create_token_secret(db_path: str | Path | None) -> str:
    """Return the deployment's signing secret, creating it once if absent.

    Persisting a random secret means a restart does not invalidate every issued
    token, without requiring the operator to configure anything. An explicitly
    configured ``P117_MOBILE_TOKEN_SECRET`` never reaches this function.
    """
    path = Path(db_path) if db_path else default_identity_db()
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    with _secret_lock:
        connection = sqlite3.connect(str(path), check_same_thread=False)
        try:
            connection.row_factory = sqlite3.Row
            connection.executescript(_SCHEMA)
            row = connection.execute(
                "SELECT value FROM secrets WHERE key='mobile_token_secret'"
            ).fetchone()
            if row is not None and str(row["value"]).strip():
                return str(row["value"])
            value = secrets.token_hex(32)
            connection.execute(
                "INSERT OR REPLACE INTO secrets (key,value,created_at) VALUES ('mobile_token_secret',?,?)",
                (value, _iso(_now())),
            )
            connection.commit()
            logger.info(
                "mobile token secret generated and stored in %s (set "
                "P117_MOBILE_TOKEN_SECRET to manage it explicitly)",
                path,
            )
            return value
        finally:
            connection.close()


__all__ = [
    "DEFAULT_ENROLLMENT_CODES",
    "SYNTHETIC_DEMO_ACCOUNTS",
    "IdentityError",
    "IdentityStore",
    "InactiveSession",
    "UnknownEnrollmentCode",
    "UnknownUser",
    "default_identity_db",
    "load_or_create_token_secret",
]
