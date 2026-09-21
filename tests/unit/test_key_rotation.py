"""Unit tests for Ed25519 key rotation."""

import json
from pathlib import Path

from backend.security.signing import (
    DEFAULT_KEY_FILE,
    load_or_create_key,
    sign_file,
    verify_file,
)


def _key_path(d: Path) -> Path:
    return d / DEFAULT_KEY_FILE


def test_key_has_key_id(tmp_path):
    key = load_or_create_key(path=_key_path(tmp_path))
    assert key.key_id
    assert len(key.key_id) >= 8
    assert _key_path(tmp_path).exists()


def test_key_id_stable_across_reloads(tmp_path):
    key1 = load_or_create_key(path=_key_path(tmp_path))
    key2 = load_or_create_key(path=_key_path(tmp_path))
    assert key1.key_id == key2.key_id


def test_sign_file_writes_key_id(tmp_path):
    artifact = tmp_path / "report.pdf"
    artifact.write_bytes(b"Industrial report data v1")
    key = load_or_create_key(path=_key_path(tmp_path))
    signed = sign_file(artifact, key=key)
    sidecar = json.loads(signed.signature_path.read_text())
    assert "key_id" in sidecar
    assert sidecar["key_id"] == key.key_id


def test_verify_after_sign_succeeds(tmp_path):
    artifact = tmp_path / "pump_report.pdf"
    artifact.write_bytes(b"Pump P-1042 operational report")
    key = load_or_create_key(path=_key_path(tmp_path))
    sign_file(artifact, key=key)
    result = verify_file(artifact)
    assert result.valid is True
    assert result.status == "SIGNATURE VALID"
    assert result.key_id == key.key_id


def test_tampered_artifact_fails_verification(tmp_path):
    artifact = tmp_path / "report.pdf"
    artifact.write_bytes(b"Legitimate content")
    key = load_or_create_key(path=_key_path(tmp_path))
    sign_file(artifact, key=key)
    # Tamper with content
    artifact.write_bytes(b"Tampered content")
    result = verify_file(artifact)
    assert result.valid is False


def test_key_rotation_generates_different_key_ids(tmp_path):
    """Generating two separate keys in different dirs gives different IDs."""
    dir1 = tmp_path / "key1"
    dir2 = tmp_path / "key2"
    dir1.mkdir()
    dir2.mkdir()

    key1 = load_or_create_key(path=_key_path(dir1))
    key2 = load_or_create_key(path=_key_path(dir2))
    assert key1.key_id != key2.key_id
