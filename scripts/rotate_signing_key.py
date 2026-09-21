#!/usr/bin/env python3
"""Ed25519 signing key rotation script.

Generates a new Ed25519 signing key, backs up the old one with a timestamp suffix,
and updates the active key file in the configured key directory.

Usage:
    python scripts/rotate_signing_key.py [--key-dir PATH]

All operations are logged. The old key is preserved; it is NOT deleted.
"""

import argparse
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("rotate_signing_key")


def rotate(key_dir: Path) -> None:
    key_dir.mkdir(parents=True, exist_ok=True)

    try:
        from backend.security.signing import (
            DEFAULT_KEY_FILE,
            SigningKey,
            load_or_create_key,
        )
    except ImportError as exc:
        logger.error("Cannot import backend.security.signing: %s", exc)
        sys.exit(1)

    active_key_path = key_dir / DEFAULT_KEY_FILE

    # Backup existing key if present
    if active_key_path.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = key_dir / f"artifact_signing_ed25519.{ts}.pem.bak"
        shutil.copy2(active_key_path, backup_path)
        logger.info("Backed up existing key to %s", backup_path)
        active_key_path.unlink()

    # Generate new key
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            NoEncryption,
            PrivateFormat,
        )

        private_key = Ed25519PrivateKey.generate()
        pem_bytes = private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        )
        active_key_path.write_bytes(pem_bytes)
        active_key_path.chmod(0o600)
        logger.info("New Ed25519 signing key written to %s (mode 0600)", active_key_path)
    except ImportError as exc:
        logger.error("cryptography package not installed: %s", exc)
        sys.exit(1)

    # Load and log the new key_id
    new_key = load_or_create_key(key_dir=key_dir)
    logger.info("New key_id: %s", new_key.key_id)
    logger.info(
        "Rotation complete. Verify new signatures with: "
        "python scripts/verify_artifact_standalone.py --key-id %s <artifact>",
        new_key.key_id,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Rotate Project 117 Ed25519 signing key")
    parser.add_argument("--key-dir", default="./data/keys", help="Key directory path")
    args = parser.parse_args()
    rotate(Path(args.key_dir))


if __name__ == "__main__":
    main()
