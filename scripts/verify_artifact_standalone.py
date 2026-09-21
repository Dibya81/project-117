#!/usr/bin/env python3
"""Standalone Ed25519 artifact signature verifier (zero Project 117 dependencies)."""
import base64, hashlib, json, sys
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

def verify(artifact_path: Path) -> bool:
    sig_path = artifact_path.with_name(artifact_path.name + ".sig.json")
    if not sig_path.exists():
        print(f"FAIL: Signature file '{sig_path.name}' not found.", file=sys.stderr)
        return False
    data = json.loads(sig_path.read_text(encoding="utf-8"))
    content = artifact_path.read_bytes()
    sha256_calc = hashlib.sha256(content).hexdigest()
    if sha256_calc != data.get("sha256"):
        print("FAIL: SHA-256 digest mismatch.", file=sys.stderr)
        return False
    payload = json.dumps(
        {"filename": artifact_path.name, "sha256": sha256_calc, "size": len(content)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    msg = b"project117-artifact-v1\x00" + payload
    pub_bytes = base64.b64decode(data["public_key"])
    sig_bytes = base64.b64decode(data["signature"])
    try:
        Ed25519PublicKey.from_public_bytes(pub_bytes).verify(sig_bytes, msg)
        print(f"OK: Verified {artifact_path.name} (Ed25519 signature valid, digest matched)")
        return True
    except Exception as exc:
        print(f"FAIL: Signature verification failed: {exc}", file=sys.stderr)
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <path-to-artifact>", file=sys.stderr)
        sys.exit(2)
    sys.exit(0 if verify(Path(sys.argv[1])) else 1)
