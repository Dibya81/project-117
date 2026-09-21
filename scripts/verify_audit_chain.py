#!/usr/bin/env python3
"""CLI tool to verify the cryptographic SHA-256 hash chain of the audit database."""
import sys
from pathlib import Path
from backend.security.audit.audit_chain import verify_chain

def main():
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/project117.db")
    if not db_path.exists():
        print(f"Audit database '{db_path}' does not exist.", file=sys.stderr)
        sys.exit(1)
    
    result = verify_chain(db_path)
    if result.valid:
        print(f"SUCCESS: Audit chain verified ({result.rows_checked} rows checked). Head hash: {result.head_hash}")
        sys.exit(0)
    else:
        print(f"FAILURE: Audit chain broken! Broken at sequence {result.broken_at}: {result.reason}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
