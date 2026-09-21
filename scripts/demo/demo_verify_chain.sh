#!/usr/bin/env bash
# Demo script: Verify cryptographic audit trail and artifact signatures
set -euo pipefail

DB_PATH=${1:-"data/project117.db"}

echo "=== PROJECT 117 AUDIT CHAIN VERIFICATION DEMO ==="
echo "1. Checking SHA-256 Merkle link integrity across all recorded events in ${DB_PATH}..."

python3 scripts/verify_audit_chain.py "${DB_PATH}"

echo ""
echo "2. Checking Ed25519 signatures on generated post-incident deliverables..."
for sig in data/artifacts/*.sig.json; do
  if [ -f "$sig" ]; then
    art="${sig%.sig.json}"
    python3 scripts/verify_artifact_standalone.py "$art"
  fi
done

echo "=== AUDIT VERIFICATION COMPLETE ==="
