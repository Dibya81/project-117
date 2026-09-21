#!/usr/bin/env python3
"""Tamper Signature Demo.

Demonstrates:
1. Generating/loading an Ed25519 signing keypair.
2. Digitally signing an industrial artifact and creating a detached `.sig.json` sidecar.
3. Verifying the clean artifact (passes with SIGNATURE VALID).
4. Maliciously tampering with 1 byte of the artifact data.
5. Re-verifying the tampered artifact (fails with SIGNATURE INVALID).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.security.signing import (  # noqa: E402
    load_or_create_key,
    sign_file,
    verify_file,
)


def main() -> int:
    print("=" * 70)
    print("Project 117 — Ed25519 Artifact Tamper & Signature Demo")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        key_dir = tmp_path / "keys"
        key_dir.mkdir(parents=True, exist_ok=True)
        key_path = key_dir / "artifact_signing_ed25519.pem"

        print("\n[Step 1] Initializing Ed25519 Keypair...")
        key = load_or_create_key(key_path)
        print(f"  ✓ Key initialized at: {key_path}")
        print(f"  ✓ Key ID: {key.key_id}")
        print(f"  ✓ Public Key (Base64): {key.public_b64[:32]}...")

        print("\n[Step 2] Creating industrial report artifact...")
        report_file = tmp_path / "INC-00142_RootCause_Report.pdf"
        report_content = b"%PDF-1.4\n1 0 obj\n<< /Title (Refinery Incident Report INC-00142) >>\nendobj\n"
        report_file.write_bytes(report_content)
        print(f"  ✓ Created: {report_file.name} ({len(report_content)} bytes)")

        print("\n[Step 3] Digitally signing artifact...")
        signed = sign_file(report_file, key=key)
        print(f"  ✓ Detached signature created: {signed.signature_path.name}")
        print(f"  ✓ SHA-256 Digest: {signed.digest}")
        print(f"  ✓ Sidecar JSON:\n{signed.signature_path.read_text().strip()}")

        print("\n[Step 4] Verifying original untampered artifact...")
        outcome = verify_file(report_file)
        print(f"  ✓ Verification status: {outcome.status}")
        print(f"  ✓ Detail: {outcome.detail}")
        assert outcome.status == "SIGNATURE VALID", f"Expected valid signature, got {outcome.status}"
        print("  ✓ SUCCESS: Cryptographic signature verified against Ed25519 public key.")

        print("\n[Step 5] Simulating unauthorized byte modification in storage...")
        tampered_content = bytearray(report_content)
        tampered_content[10] = (tampered_content[10] + 1) % 256  # Modify single byte
        report_file.write_bytes(bytes(tampered_content))
        print("  ⚡ Tampered 1 byte in artifact payload.")

        print("\n[Step 6] Re-verifying tampered artifact...")
        tampered_outcome = verify_file(report_file)
        print(f"  ✗ Verification status: {tampered_outcome.status}")
        print(f"  ✗ Detail: {tampered_outcome.detail}")
        assert tampered_outcome.status == "SIGNATURE INVALID", "Tampered file must be detected!"
        print("  ✓ SUCCESS: Tampering was caught. Signature rejected by verifier.")

    print("\n" + "=" * 70)
    print("Demo complete: Ed25519 signing and tamper detection verified successfully.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
