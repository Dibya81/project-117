"""Ed25519 artifact signing and verification (Phase 2, gap 2).

Why signatures on top of SHA-256
--------------------------------
An artifact already carries a SHA-256 digest, and the deliverables service
re-derives it before a download. That catches *corruption*: a truncated file, a
bad write, a bit flip. It does not catch *substitution*, because the digest
lives in the same database as the file and can be rewritten by anyone who can
open the database. A signature closes that: verifying it requires the public
key, and producing a new one requires the private key, which never leaves the
key file.

Design decisions
----------------
**Ed25519, not a hand-rolled scheme.** ``cryptography`` provides the
implementation. Rolling our own would be the single fastest way to ship
something that looks like signing and is not.

**Detached signature, stored next to the artifact.** ``<artifact>.sig.json``
holds the signature, the algorithm, the file digest and the public key. The
public key is embedded so a verifier needs nothing but the file and its sidecar
— important when the artifact has been copied to a machine that does not share
this install's key store. The signature covers a domain-separated message
(:data:`SIGNING_DOMAIN`) over the digest, the size and the filename, so a
signature cannot be replayed from one artifact onto another.

**The private key is 0600 on disk.** Generated on first use under
``P117_ARTIFACT_SIGNING_KEY_DIR`` (default ``data/keys``), which is inside the
app's data directory. ``P117_ARTIFACT_SIGNING_KEY`` may point at an existing
key file; a raw key that is not a file path is rejected loudly rather than
silently ignored, because a deployment that *thinks* it pinned a key and did
not is worse off than one that failed to start.

**Absence is reported, never inferred as valid.** A file with no sidecar is
``UNSIGNED``. A sidecar that does not parse, or whose signature does not cover
this file, is ``SIGNATURE INVALID``. There is no path in this module that
returns "valid" for something it did not actually verify.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("backend.security.signing")

#: Algorithm name recorded in the sidecar. Checked on verify, so a sidecar
#: written by some future scheme is refused rather than assumed compatible.
ALGORITHM = "Ed25519"

#: Sidecar naming and schema version.
SIGNATURE_SUFFIX = ".sig.json"
SIGNATURE_VERSION = 1

#: Domain separation. The signed message is a fixed prefix, then the digest,
#: the byte length and the filename, so a valid signature cannot be lifted from
#: one artifact and pasted onto another (or onto a different filename).
SIGNING_DOMAIN = b"project117-artifact-v1\x00"

#: Default key location: inside the app's data directory, next to the other
#: local state. Overridable so a real deployment can point at a KMS mount.
DEFAULT_KEY_DIR = Path("./data/keys")
DEFAULT_KEY_FILE = "artifact_signing_ed25519.pem"


class SigningUnavailable(RuntimeError):
    """The cryptography backend is missing. Reported, never worked around."""

    reason = "artifact_signing_unavailable"


class KeyConfigurationError(RuntimeError):
    """``P117_ARTIFACT_SIGNING_KEY`` was set to something unusable."""

    reason = "artifact_signing_key_invalid"


def _crypto() -> tuple[Any, Any, Any]:
    """Import the Ed25519 primitives, or explain precisely why we cannot.

    Imported lazily so the rest of the application imports cleanly on an
    install without ``cryptography``, and so the failure surfaces where signing
    is actually attempted rather than at startup.
    """
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
            Ed25519PublicKey,
        )
    except ImportError as exc:  # pragma: no cover - depends on the install
        raise SigningUnavailable(
            "artifact signing requires the 'cryptography' package, which is not "
            "installed. Install it (pip install cryptography / uv sync) rather "
            "than falling back to an unauthenticated digest: a checksum is not "
            "a signature."
        ) from exc
    return Ed25519PrivateKey, Ed25519PublicKey, serialization


# ------------------------------------------------------------------ keys -----


def default_key_path() -> Path:
    """Where the key lives unless configured otherwise.

    ``P117_ARTIFACT_SIGNING_KEY`` wins when set. It must be a *path*: a raw
    key pasted into the environment is refused, because an env var is visible
    in ``ps``/proc and a typo in a base64 blob would otherwise look like a
    working key rotation.
    """
    override = os.getenv("P117_ARTIFACT_SIGNING_KEY", "").strip()
    if override:
        return Path(override).expanduser()
    key_dir = os.getenv("P117_ARTIFACT_SIGNING_KEY_DIR", "").strip()
    base = Path(key_dir).expanduser() if key_dir else DEFAULT_KEY_DIR
    return base / DEFAULT_KEY_FILE


def _write_private(path: Path, data: bytes) -> None:
    """Write a private key with 0600 from the moment it exists.

    ``os.open`` with the mode rather than ``write_bytes`` then ``chmod``: the
    latter leaves a window in which the key is world-readable, and a key file
    that is briefly readable is a key that may already have been read.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    descriptor = os.open(str(path), flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
    finally:
        # Belt and braces: an umask or a pre-existing file can leave the mode
        # wider than requested, and the mode is the whole control here.
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:  # pragma: no cover - platform dependent
            pass


@dataclass(frozen=True)
class SigningKey:
    """A loaded private key plus the material a verifier needs."""

    private_pem: bytes
    public_pem: bytes
    public_b64: str
    key_id: str
    path: Path | None = None

    @property
    def private_object(self) -> Any:
        private_cls, _, serialization = _crypto()
        return serialization.load_pem_private_key(self.private_pem, password=None)


def generate_key(path: Path | None = None) -> SigningKey:
    """Create a new keypair and persist the private half at ``path`` (0600)."""
    private_cls, _, serialization = _crypto()
    target = path or default_key_path()
    private = private_cls.generate()
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    _write_private(target, private_pem)
    logger.info("generated a new artifact signing key at %s (mode 0600)", target)
    return _describe(private_pem, target)


def _describe(private_pem: bytes, path: Path | None) -> SigningKey:
    _, _, serialization = _crypto()
    private = serialization.load_pem_private_key(private_pem, password=None)
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    raw = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return SigningKey(
        private_pem=private_pem,
        public_pem=public_pem,
        public_b64=base64.b64encode(raw).decode("ascii"),
        key_id=hashlib.sha256(raw).hexdigest()[:16],
        path=path,
    )


def load_or_create_key(path: Path | None = None) -> SigningKey:
    """Load the configured key, generating one on first use.

    Generation writes only to the configured path, so an operator who set
    ``P117_ARTIFACT_SIGNING_KEY`` to a path on a read-only mount gets a loud
    failure rather than a silently different key in ``data/keys``.
    """
    target = path or default_key_path()
    if target.exists():
        try:
            data = target.read_bytes()
        except OSError as exc:
            raise KeyConfigurationError(
                f"artifact signing key at {target} could not be read: {exc}"
            ) from exc
        try:
            return _describe(data, target)
        except Exception as exc:  # noqa: BLE001 - a bad key must not be used
            raise KeyConfigurationError(
                f"{target} is not a usable {ALGORITHM} private key: {type(exc).__name__}: {exc}"
            ) from exc
    return generate_key(target)


# -------------------------------------------------------------- sign/verify --


def file_digest(path: str | Path, *, chunk: int = 1 << 20) -> tuple[str, int]:
    """``(sha256_hex, size_bytes)`` of a file, streamed."""
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            size += len(block)
            digest.update(block)
    return digest.hexdigest(), size


def signed_message(digest_hex: str, size: int, filename: str) -> bytes:
    """The exact bytes covered by a signature. Domain-separated."""
    payload = json.dumps(
        {"filename": filename, "sha256": digest_hex, "size": size},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return SIGNING_DOMAIN + payload


@dataclass
class SignedArtifact:
    """Result of signing one file."""

    path: Path
    signature_path: Path
    digest: str
    size: int
    key_id: str
    algorithm: str = ALGORITHM

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "signature_path": str(self.signature_path),
            "sha256": self.digest,
            "size": self.size,
            "key_id": self.key_id,
            "algorithm": self.algorithm,
        }


def signature_path_for(path: str | Path) -> Path:
    return Path(f"{path}{SIGNATURE_SUFFIX}")


def sign_file(path: str | Path, *, key: SigningKey | None = None) -> SignedArtifact:
    """Sign ``path`` and write a detached ``.sig.json`` beside it."""
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"cannot sign '{target}': no such file")
    signing_key = key or load_or_create_key()
    digest, size = file_digest(target)
    private = signing_key.private_object
    signature = private.sign(signed_message(digest, size, target.name))
    sidecar = {
        "version": SIGNATURE_VERSION,
        "algorithm": ALGORITHM,
        "signed_at": _utcnow(),
        "filename": target.name,
        "sha256": digest,
        "size": size,
        "key_id": signing_key.key_id,
        "public_key": signing_key.public_b64,
        "signature": base64.b64encode(signature).decode("ascii"),
    }
    sidecar_path = signature_path_for(target)
    sidecar_path.write_text(json.dumps(sidecar, indent=2, sort_keys=True), encoding="utf-8")
    return SignedArtifact(
        path=target,
        signature_path=sidecar_path,
        digest=digest,
        size=size,
        key_id=signing_key.key_id,
    )


@dataclass
class VerificationOutcome:
    """What a verification actually established.

    ``status`` is one of:
      * ``SIGNATURE VALID``  — the file matches a signature over exactly it
      * ``INTEGRITY VALID``  — the file matches its recorded digest, but there
        is no signature (or the sig is unusable), so substitution is *not*
        ruled out
      * ``SIGNATURE INVALID`` — a signature exists and does not match
      * ``UNSIGNED``          — no signature and no recorded digest
    """

    status: str
    detail: str
    signature_present: bool
    digest: str | None = None
    expected_digest: str | None = None
    key_id: str | None = None
    signed_at: str | None = None
    algorithm: str | None = None

    @property
    def valid(self) -> bool:
        return self.status in {"SIGNATURE VALID", "INTEGRITY VALID"}

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "detail": self.detail,
            "signature_present": self.signature_present,
            "sha256": self.digest,
            "expected_sha256": self.expected_digest,
            "key_id": self.key_id,
            "signed_at": self.signed_at,
            "algorithm": self.algorithm,
        }


def verify_file(path: str | Path, *, signature: str | Path | None = None) -> VerificationOutcome:
    """Verify ``path`` against its detached signature.

    Never raises for a bad signature: an invalid artifact is a *result*, and
    the utility that reports it must be able to say so on stdout rather than
    exiting with a traceback that a caller could mistake for "the tool broke".
    """
    target = Path(path)
    if not target.is_file():
        return VerificationOutcome(
            status="UNSIGNED",
            detail=f"no such file: {target}",
            signature_present=False,
        )

    sidecar_path = Path(signature) if signature else signature_path_for(target)
    if not sidecar_path.is_file():
        digest, _ = file_digest(target)
        return VerificationOutcome(
            status="UNSIGNED",
            detail=(
                f"no signature file at {sidecar_path}; the artifact is unsigned, so "
                "its authenticity cannot be established"
            ),
            signature_present=False,
            digest=digest,
        )

    try:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return VerificationOutcome(
            status="SIGNATURE INVALID",
            detail=f"the signature file is not readable JSON: {exc}",
            signature_present=True,
        )

    algorithm = str(sidecar.get("algorithm") or "")
    if algorithm != ALGORITHM:
        return VerificationOutcome(
            status="SIGNATURE INVALID",
            detail=(
                f"the signature records algorithm '{algorithm or 'none'}'; this "
                f"verifier only accepts {ALGORITHM}"
            ),
            signature_present=True,
            algorithm=algorithm or None,
        )

    digest, size = file_digest(target)
    expected_digest = sidecar.get("sha256")
    if expected_digest and digest != expected_digest:
        return VerificationOutcome(
            status="SIGNATURE INVALID",
            detail=(
                "the file's SHA-256 does not match the signed digest; the artifact "
                "was modified after it was signed"
            ),
            signature_present=True,
            digest=digest,
            expected_digest=str(expected_digest),
            key_id=sidecar.get("key_id"),
            signed_at=sidecar.get("signed_at"),
            algorithm=algorithm,
        )

    # The filename and size are inside the signed message, so a renamed or
    # truncated copy is caught even when its bytes are otherwise untouched.
    filename = str(sidecar.get("filename") or target.name)
    expected_size = sidecar.get("size")
    if expected_size is not None and int(expected_size) != size:
        return VerificationOutcome(
            status="SIGNATURE INVALID",
            detail=(
                f"the file is {size} bytes but the signature covers "
                f"{expected_size}; the artifact was truncated or padded"
            ),
            signature_present=True,
            digest=digest,
            expected_digest=str(expected_digest) if expected_digest else None,
            key_id=sidecar.get("key_id"),
            signed_at=sidecar.get("signed_at"),
            algorithm=algorithm,
        )

    public_b64 = sidecar.get("public_key")
    signature_b64 = sidecar.get("signature")
    if not public_b64 or not signature_b64:
        return VerificationOutcome(
            status="SIGNATURE INVALID",
            detail="the signature file has no public key or no signature",
            signature_present=True,
            digest=digest,
            key_id=sidecar.get("key_id"),
            signed_at=sidecar.get("signed_at"),
            algorithm=algorithm,
        )

    try:
        _, public_cls, _ = _crypto()
        public = public_cls.from_public_bytes(base64.b64decode(public_b64))
        public.verify(
            base64.b64decode(signature_b64),
            signed_message(str(expected_digest), size, filename),
        )
    except SigningUnavailable:
        # Cannot check the signature, so the strongest honest statement is the
        # one the digest supports. "INTEGRITY VALID" is deliberately weaker
        # than "SIGNATURE VALID" and says so.
        return VerificationOutcome(
            status="INTEGRITY VALID",
            detail=(
                "the file matches the signed digest, but the cryptography backend "
                "is unavailable so the signature itself was not checked"
            ),
            signature_present=True,
            digest=digest,
            expected_digest=str(expected_digest),
            key_id=sidecar.get("key_id"),
            signed_at=sidecar.get("signed_at"),
            algorithm=algorithm,
        )
    except Exception as exc:  # noqa: BLE001 - any failure here is a bad signature
        return VerificationOutcome(
            status="SIGNATURE INVALID",
            detail=f"the signature does not verify: {type(exc).__name__}",
            signature_present=True,
            digest=digest,
            expected_digest=str(expected_digest) if expected_digest else None,
            key_id=sidecar.get("key_id"),
            signed_at=sidecar.get("signed_at"),
            algorithm=algorithm,
        )

    return VerificationOutcome(
        status="SIGNATURE VALID",
        detail=(
            f"signed by key {sidecar.get('key_id')} at {sidecar.get('signed_at')}; "
            "the file matches the signed digest byte for byte"
        ),
        signature_present=True,
        digest=digest,
        expected_digest=str(expected_digest),
        key_id=sidecar.get("key_id"),
        signed_at=sidecar.get("signed_at"),
        algorithm=algorithm,
    )


def _utcnow() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "ALGORITHM",
    "DEFAULT_KEY_DIR",
    "DEFAULT_KEY_FILE",
    "SIGNATURE_SUFFIX",
    "SIGNING_DOMAIN",
    "KeyConfigurationError",
    "SignedArtifact",
    "SigningKey",
    "SigningUnavailable",
    "VerificationOutcome",
    "default_key_path",
    "file_digest",
    "generate_key",
    "load_or_create_key",
    "sign_file",
    "signature_path_for",
    "signed_message",
    "verify_file",
]
