#!/usr/bin/env python
"""``verify_artifact <file>`` — standalone artifact signature/integrity check.

Prints exactly one of:

    SIGNATURE VALID      the file matches a signature over it (authentic)
    INTEGRITY VALID      the file matches its recorded digest, but no signature
                         was checked, so substitution is not ruled out
    SIGNATURE INVALID    a signature exists and does not match this file
    UNSIGNED             there is no signature to check

Exit codes: 0 for SIGNATURE VALID / INTEGRITY VALID, 1 for SIGNATURE INVALID,
2 for UNSIGNED or an unusable invocation. The distinction matters to a script:
"this file was tampered with" and "this file was never signed" are different
findings and must not share an exit code.

Usage::

    python -m backend.security.verify_artifact path/to/report.pdf
    python -m backend.security.verify_artifact report.pdf --signature custom.sig.json
    python -m backend.security.verify_artifact report.pdf --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.security.signing import verify_file

EXIT_VALID = 0
EXIT_INVALID = 1
EXIT_UNSIGNED = 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify_artifact",
        description=(
            "Verify the Ed25519 signature of a generated artifact. Reports a "
            "missing signature as UNSIGNED rather than as valid."
        ),
    )
    parser.add_argument("file", help="the artifact to verify")
    parser.add_argument(
        "--signature",
        default=None,
        help="path to the detached signature (default: <file>.sig.json)",
    )
    parser.add_argument("--json", action="store_true", help="emit the full result as JSON")
    args = parser.parse_args(argv)

    target = Path(args.file)
    outcome = verify_file(target, signature=args.signature)

    if args.json:
        print(json.dumps(outcome.as_dict(), indent=2, sort_keys=True))
    else:
        print(outcome.status)
        print(f"  file:   {target}")
        print(f"  sha256: {outcome.digest}")
        if outcome.expected_digest and outcome.expected_digest != outcome.digest:
            print(f"  signed: {outcome.expected_digest}   (recorded when it was signed)")
        if outcome.key_id:
            print(f"  key:    {outcome.key_id} ({outcome.algorithm})")
        if outcome.signed_at:
            print(f"  at:     {outcome.signed_at}")
        print(f"  detail: {outcome.detail}")

    if outcome.status == "SIGNATURE INVALID":
        return EXIT_INVALID
    if outcome.status == "UNSIGNED":
        return EXIT_UNSIGNED
    return EXIT_VALID


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
