from pathlib import Path
from backend.security.signing import generate_key, sign_file
from scripts.verify_artifact_standalone import verify


def test_standalone_verifier_validates_signed_file(tmp_path: Path):
    key_path = tmp_path / "key.pem"
    key = generate_key(key_path)

    artifact_file = tmp_path / "report.pdf"
    artifact_file.write_bytes(b"%PDF-1.4 Mock PDF Content For Project 117")

    # Sign using backend signer
    sign_file(artifact_file, key=key)

    # Verify using standalone verifier
    assert verify(artifact_file) is True


def test_standalone_verifier_detects_tampering(tmp_path: Path):
    key_path = tmp_path / "key.pem"
    key = generate_key(key_path)

    artifact_file = tmp_path / "tampered_report.pdf"
    artifact_file.write_bytes(b"Original Content")
    sign_file(artifact_file, key=key)

    # Tamper with file
    artifact_file.write_bytes(b"Modified Attacker Content")

    # Standalone verifier must fail
    assert verify(artifact_file) is False

